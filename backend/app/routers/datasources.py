"""DataSource management routes - file upload and database connections."""

import os
import json
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.datasource import DataSource
from app.schemas.common import ApiResponse
from app.services.data_parser import DataParser
from app.config import settings

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
