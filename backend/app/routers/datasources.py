"""DataSource management routes - file upload and database connections."""

import os
import json
import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.datasource import DataSource
from app.schemas.common import ApiResponse
from app.services.data_parser import DataParser
from app.llm.client import llm_client
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/datasources", tags=["DataSources"])


@router.post("/upload")
async def upload_files(
    project_id: str,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload Excel/CSV files and parse metadata."""
    results = []
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    for file in files:
        # Determine file type
        filename = file.filename or "unknown"
        ext = os.path.splitext(filename)[1].lower()
        if ext in (".xlsx", ".xls"):
            source_type = "excel"
        elif ext == ".csv":
            source_type = "csv"
        else:
            results.append({"name": filename, "error": f"Unsupported file type: {ext}"})
            continue

        # Save file
        file_id = str(uuid.uuid4())[:8]
        safe_name = f"{file_id}_{filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Parse metadata
        try:
            if source_type == "excel":
                meta = await DataParser.parse_excel(file_path)
            else:
                meta = await DataParser.parse_csv(file_path)

            # Save datasource record
            ds = DataSource(
                project_id=project_id,
                name=meta.table_name,
                source_type=source_type,
                file_path=file_path,
                columns_meta=json.dumps(meta.columns, ensure_ascii=False),
                row_count=meta.row_count,
                status="analyzed",
            )
            db.add(ds)
            await db.commit()
            await db.refresh(ds)

            results.append({
                "id": ds.id,
                "name": meta.table_name,
                "source_type": source_type,
                "row_count": meta.row_count,
                "columns": meta.columns,
            })
        except Exception as e:
            results.append({"name": filename, "error": str(e)})

    return ApiResponse(data=results)


@router.post("/upload-with-desc")
async def upload_with_description(
    project_id: str,
    data_file: UploadFile = File(...),
    desc_text: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """Upload a data file together with a free-text field description.

    1. Parses the data file (Excel/CSV) to get columns metadata.
    2. Calls LLM to intelligently match each data column with the
       most relevant description from the user-provided text.
    3. Saves the datasource with descriptions already merged.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # --- Save & parse data file ---
    data_filename = data_file.filename or "unknown"
    ext = os.path.splitext(data_filename)[1].lower()
    if ext in (".xlsx", ".xls"):
        source_type = "excel"
    elif ext == ".csv":
        source_type = "csv"
    else:
        return ApiResponse(code=400, message=f"不支持的数据文件格式: {ext}")

    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{data_filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    content = await data_file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        if source_type == "excel":
            meta = await DataParser.parse_excel(file_path)
        else:
            meta = await DataParser.parse_csv(file_path)
    except Exception as e:
        return ApiResponse(code=500, message=f"数据文件解析失败: {e}")

    # --- LLM matching if description text provided ---
    matched = {}
    if desc_text and desc_text.strip():
        col_info = ""
        for c in meta.columns:
            sample = ", ".join(str(v) for v in c.get("sample_values", [])[:3])
            col_info += f"  - {c['name']} (类型: {c['dtype']}, 样例: [{sample}])\n"

        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是一个数据分析专家。用户上传了一张数据表，并提供了一段关于字段的描述信息。"
                        "请根据用户提供的描述信息，为数据表的每一列匹配最合适的业务含义描述。\n\n"
                        "匹配规则：\n"
                        "1. 仔细阅读用户提供的描述文本，从中提取每个字段的含义\n"
                        "2. 按字段名精确匹配或模糊匹配（如描述中提到相同或相似的列名/字段名）\n"
                        "3. 如果字段名不完全一致，根据字段类型、样例数据和描述的上下文语义推断匹配\n"
                        "4. 如果描述中没有对应信息，description 留空字符串\n"
                        "5. 描述要简洁明了，用中文\n\n"
                        "输出严格有效的 JSON，不要输出其他文字。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"数据表名：{meta.table_name}\n\n"
                        f"数据表的列：\n{col_info}\n"
                        f"用户提供的字段描述信息：\n{desc_text.strip()}\n\n"
                        "请为每一列输出匹配结果，JSON 格式如下：\n"
                        '{\n  "columns": [\n'
                        '    {"name": "列名", "description": "匹配到的业务含义描述"}\n'
                        "  ]\n}"
                    ),
                },
            ]
            llm_result = await llm_client.chat_completion_json(messages, temperature=0.1, max_tokens=4096)
            matched = {c["name"]: c.get("description", "") for c in llm_result.get("columns", []) if "name" in c}
        except Exception as e:
            logger.warning("LLM column description matching failed: %s", e)

    # Merge descriptions into column metadata
    for col in meta.columns:
        col["description"] = matched.get(col["name"], "")

    # Save datasource
    ds = DataSource(
        project_id=project_id,
        name=meta.table_name,
        source_type=source_type,
        file_path=file_path,
        columns_meta=json.dumps(meta.columns, ensure_ascii=False),
        row_count=meta.row_count,
        status="analyzed",
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)

    return ApiResponse(data={
        "id": ds.id,
        "name": meta.table_name,
        "source_type": source_type,
        "row_count": meta.row_count,
        "columns": meta.columns,
    })


@router.post("/database")
async def add_database_connection(
    project_id: str,
    db_type: str = Form(...),
    host: str = Form(...),
    port: int = Form(...),
    database: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    table_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Add a database table as datasource."""
    # Build connection string
    if db_type == "mysql":
        conn_str = f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}"
    elif db_type == "postgresql":
        conn_str = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    elif db_type == "sqlserver":
        conn_str = f"mssql+pymssql://{username}:{password}@{host}:{port}/{database}"
    else:
        return ApiResponse(code=400, message=f"Unsupported database type: {db_type}")

    try:
        meta = await DataParser.parse_database_table(conn_str, table_name)

        ds = DataSource(
            project_id=project_id,
            name=table_name,
            source_type="database",
            db_connection_string=conn_str,
            db_table_name=table_name,
            columns_meta=json.dumps(meta.columns, ensure_ascii=False),
            row_count=meta.row_count,
            status="analyzed",
        )
        db.add(ds)
        await db.commit()
        await db.refresh(ds)

        return ApiResponse(data={
            "id": ds.id,
            "name": table_name,
            "source_type": "database",
            "row_count": meta.row_count,
            "columns": meta.columns,
        })
    except Exception as e:
        return ApiResponse(code=500, message=str(e))


@router.get("")
async def list_datasources(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DataSource)
        .where(DataSource.project_id == project_id)
        .order_by(DataSource.created_at.desc())
    )
    datasources = result.scalars().all()
    items = []
    for ds in datasources:
        cols = []
        try:
            cols = json.loads(ds.columns_meta) if ds.columns_meta else []
        except (json.JSONDecodeError, TypeError):
            pass
        items.append({
            "id": ds.id,
            "project_id": ds.project_id,
            "name": ds.name,
            "source_type": ds.source_type,
            "row_count": ds.row_count,
            "status": ds.status,
            "columns_meta": cols,
            "created_at": ds.created_at.isoformat() if ds.created_at else "",
        })
    return ApiResponse(data=items)


@router.get("/{ds_id}/preview")
async def preview_datasource(
    project_id: str, ds_id: str, db: AsyncSession = Depends(get_db)
):
    """Preview first 20 rows of a datasource."""
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        return ApiResponse(code=404, message="DataSource not found")

    try:
        if ds.source_type in ("excel", "csv"):
            if ds.source_type == "excel":
                meta = await DataParser.parse_excel(ds.file_path)
            else:
                meta = await DataParser.parse_csv(ds.file_path)
            return ApiResponse(data={
                "columns": [c["name"] for c in meta.columns],
                "rows": meta.sample_rows,
                "total_rows": meta.row_count,
            })
        else:
            meta = await DataParser.parse_database_table(
                ds.db_connection_string, ds.db_table_name
            )
            return ApiResponse(data={
                "columns": [c["name"] for c in meta.columns],
                "rows": meta.sample_rows,
                "total_rows": meta.row_count,
            })
    except Exception as e:
        return ApiResponse(code=500, message=str(e))


@router.delete("/{ds_id}")
async def delete_datasource(
    project_id: str, ds_id: str, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        return ApiResponse(code=404, message="DataSource not found")

    # Delete file if exists
    if ds.file_path and os.path.exists(ds.file_path):
        try:
            os.remove(ds.file_path)
        except OSError:
            pass

    await db.delete(ds)
    await db.commit()
    return ApiResponse(message="Deleted")


@router.put("/{ds_id}/columns")
async def update_column_descriptions(
    project_id: str,
    ds_id: str,
    columns: list[dict],
    db: AsyncSession = Depends(get_db),
):
    """Update column descriptions/business meanings for a datasource."""
    result = await db.execute(select(DataSource).where(DataSource.id == ds_id))
    ds = result.scalar_one_or_none()
    if not ds:
        return ApiResponse(code=404, message="DataSource not found")

    try:
        existing = json.loads(ds.columns_meta) if ds.columns_meta else []
    except (json.JSONDecodeError, TypeError):
        existing = []

    # Merge descriptions into existing column metadata
    desc_map = {c["name"]: c.get("description", "") for c in columns if "name" in c}
    for col in existing:
        if col["name"] in desc_map:
            col["description"] = desc_map[col["name"]]

    ds.columns_meta = json.dumps(existing, ensure_ascii=False)
    await db.commit()
    return ApiResponse(message="Column descriptions updated")
