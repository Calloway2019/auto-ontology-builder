"""Ontology management routes - build and manage ontologies."""

import json
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.project import Project
from app.models.datasource import DataSource
from app.models.ontology import OntologyVersion
from app.schemas.common import ApiResponse
from app.schemas.ontology import OntologyDefinition
from app.services.schema_analyzer import SchemaAnalyzer
from app.services.ontology_builder import OntologyBuilder

router = APIRouter(prefix="/api/v1/projects/{project_id}/ontology", tags=["Ontology"])

# In-memory build status tracking
_build_status = {}


async def _run_ontology_build(project_id: str, tables_meta: list, db_url: str):
    """Background task for ontology building."""
    from app.models.database import async_session

    _build_status[project_id] = {
        "status": "stage1",
        "progress": 0.0,
        "current_stage": "Schema Analysis",
        "message": "正在分析数据表结构...",
        "stage_summaries": {},
        "stage_details": {},
    }

    async def on_progress(stage: str, progress: float, message: str, stage_summary: str = "", stage_detail: dict = None):
        stage_map = {
            "stage1": ("模式分析", 0.0),
            "stage2": ("实体抽取", 0.25),
            "stage3": ("关系发现", 0.50),
            "stage4": ("本体优化", 0.75),
            "completed": ("已完成", 1.0),
        }
        stage_name, base_progress = stage_map.get(stage, (stage, 0.0))
        total = base_progress + progress * 0.25
        current_summaries = _build_status.get(project_id, {}).get("stage_summaries", {})
        current_details = _build_status.get(project_id, {}).get("stage_details", {})
        if stage_summary:
            current_summaries[stage] = stage_summary
        if stage_detail:
            current_details[stage] = stage_detail
        _build_status[project_id] = {
            "status": stage,
            "progress": min(total, 1.0),
            "current_stage": stage_name,
            "message": message,
            "stage_summaries": current_summaries,
            "stage_details": current_details,
        }

    try:
        result = await OntologyBuilder.build(
            tables_meta=tables_meta,
            on_progress=on_progress,
        )

        ontology = result["ontology"]
        reasoning = json.dumps(result["reasoning_log"], ensure_ascii=False, default=str)

        # Save to database
        async with async_session() as db:
            # Get current version count
            ver_result = await db.execute(
                select(OntologyVersion)
                .where(OntologyVersion.project_id == project_id)
                .order_by(OntologyVersion.version.desc())
            )
            latest = ver_result.scalars().first()
            new_version = (latest.version + 1) if latest else 1

            # Deactivate old versions
            if latest:
                old_versions = await db.execute(
                    select(OntologyVersion).where(
                        OntologyVersion.project_id == project_id
                    )
                )
                for ov in old_versions.scalars().all():
                    ov.is_active = False

            # Create new version
            ov = OntologyVersion(
                project_id=project_id,
                version=new_version,
                ontology_json=json.dumps(ontology, ensure_ascii=False),
                llm_reasoning=reasoning,
                is_active=True,
            )
            db.add(ov)

            # Update project
            proj_result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = proj_result.scalar_one_or_none()
            if project:
                project.ontology_json = json.dumps(ontology, ensure_ascii=False)
                project.status = "ready"
                project.updated_at = datetime.utcnow()

            await db.commit()

        _build_status[project_id] = {
            "status": "completed",
            "progress": 1.0,
            "current_stage": "已完成",
            "message": f"本体构建完成：{len(ontology.get('entities', []))} 个实体，"
                       f"{len(ontology.get('relations', []))} 个关系",
            "ontology": ontology,
            "stage_summaries": _build_status.get(project_id, {}).get("stage_summaries", {}),
            "stage_details": _build_status.get(project_id, {}).get("stage_details", {}),
        }

    except Exception as e:
        _build_status[project_id] = {
            "status": "failed",
            "progress": 0.0,
            "current_stage": "错误",
            "message": str(e),
            "stage_summaries": _build_status.get(project_id, {}).get("stage_summaries", {}),
            "stage_details": _build_status.get(project_id, {}).get("stage_details", {}),
        }

        # Update project status
        async with async_session() as db:
            proj_result = await db.execute(
                select(Project).where(Project.id == project_id)
            )
            project = proj_result.scalar_one_or_none()
            if project:
                project.status = "error"
            await db.commit()


@router.post("/build")
async def build_ontology(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger async ontology building from project datasources."""
    # Get all analyzed datasources
    result = await db.execute(
        select(DataSource).where(
            DataSource.project_id == project_id,
            DataSource.status.in_(["analyzed", "loaded"]),
        )
    )
    datasources = result.scalars().all()

    if not datasources:
        return ApiResponse(code=400, message="No analyzed datasources found")

    # Prepare table metadata
    tables_meta = []
    for ds in datasources:
        cols = json.loads(ds.columns_meta) if ds.columns_meta else []
        tables_meta.append({
            "table_name": ds.name,
            "columns": cols,
            "row_count": ds.row_count,
            "sample_rows": [],  # Will be enriched by SchemaAnalyzer
        })

    # Enrich with rule-based analysis
    tables_meta = SchemaAnalyzer.analyze(tables_meta)

    # Update project status
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one_or_none()
    if project:
        project.status = "building"
        await db.commit()

    # Start background build
    background_tasks.add_task(
        _run_ontology_build, project_id, tables_meta, str(db.bind.url) if db.bind else ""
    )

    return ApiResponse(data={"message": "Ontology build started", "project_id": project_id})


@router.get("/build/status")
async def get_build_status(project_id: str):
    """Get current ontology build progress."""
    status = _build_status.get(project_id, {
        "status": "idle",
        "progress": 0.0,
        "current_stage": "",
        "message": "No build in progress",
    })
    return ApiResponse(data=status)


@router.get("")
async def get_ontology(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get current active ontology definition."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    ontology = {}
    try:
        ontology = json.loads(project.ontology_json) if project.ontology_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return ApiResponse(data=ontology)


@router.put("")
async def update_ontology(
    project_id: str,
    ontology: OntologyDefinition,
    db: AsyncSession = Depends(get_db),
):
    """Manually update ontology definition."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    ontology_dict = ontology.model_dump()
    project.ontology_json = json.dumps(ontology_dict, ensure_ascii=False)
    project.updated_at = datetime.utcnow()
    await db.commit()

    return ApiResponse(message="Ontology updated")


@router.get("/versions")
async def list_ontology_versions(
    project_id: str, db: AsyncSession = Depends(get_db)
):
    """List all ontology versions."""
    result = await db.execute(
        select(OntologyVersion)
        .where(OntologyVersion.project_id == project_id)
        .order_by(OntologyVersion.version.desc())
    )
    versions = result.scalars().all()
    items = [
        {
            "id": v.id,
            "project_id": v.project_id,
            "version": v.version,
            "is_active": v.is_active,
            "created_at": v.created_at.isoformat() if v.created_at else "",
        }
        for v in versions
    ]
    return ApiResponse(data=items)


@router.get("/versions/{version_id}")
async def get_ontology_version_detail(
    project_id: str, version_id: str, db: AsyncSession = Depends(get_db)
):
    """Get a single ontology version with reasoning log for explainability."""
    result = await db.execute(
        select(OntologyVersion).where(OntologyVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        return ApiResponse(code=404, message="Version not found")

    ontology = {}
    reasoning_log = []
    try:
        ontology = json.loads(version.ontology_json) if version.ontology_json else {}
    except (json.JSONDecodeError, TypeError):
        pass
    try:
        reasoning_log = json.loads(version.llm_reasoning) if version.llm_reasoning else []
    except (json.JSONDecodeError, TypeError):
        pass

    return ApiResponse(data={
        "id": version.id,
        "version": version.version,
        "is_active": version.is_active,
        "created_at": version.created_at.isoformat() if version.created_at else "",
        "ontology": ontology,
        "reasoning_log": reasoning_log,
    })
