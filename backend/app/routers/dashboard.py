"""Dashboard module routes - configurable question modules."""

import json
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.models.database import get_db
from app.models.project import Project
from app.models.dashboard_module import DashboardModule
from app.schemas.common import ApiResponse
from app.services.qa_engine import QAEngine

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


class ModuleCreate(BaseModel):
    project_id: str
    title: str
    question: str
    display_type: str = "table"
    chart_config: dict = {}
    refresh_interval: int = 0
    size: str = "medium"


class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    question: Optional[str] = None
    display_type: Optional[str] = None
    chart_config: Optional[dict] = None
    refresh_interval: Optional[int] = None
    size: Optional[str] = None
    order: Optional[int] = None


@router.post("/modules")
async def create_module(data: ModuleCreate, db: AsyncSession = Depends(get_db)):
    """Create a new dashboard module."""
    # Get max order
    result = await db.execute(
        select(DashboardModule)
        .where(DashboardModule.project_id == data.project_id)
        .order_by(DashboardModule.order.desc())
    )
    last = result.scalars().first()
    next_order = (last.order + 1) if last else 0

    module = DashboardModule(
        project_id=data.project_id,
        title=data.title,
        question=data.question,
        display_type=data.display_type,
        chart_config=json.dumps(data.chart_config, ensure_ascii=False),
        refresh_interval=data.refresh_interval,
        size=data.size,
        order=next_order,
    )
    db.add(module)
    await db.commit()
    await db.refresh(module)

    return ApiResponse(data={"id": module.id, "title": module.title})


@router.get("/modules")
async def list_modules(project_id: str, db: AsyncSession = Depends(get_db)):
    """List all dashboard modules for a project."""
    result = await db.execute(
        select(DashboardModule)
        .where(DashboardModule.project_id == project_id)
        .order_by(DashboardModule.order)
    )
    modules = result.scalars().all()
    items = []
    for m in modules:
        last_result = {}
        try:
            last_result = json.loads(m.last_result) if m.last_result else {}
        except (json.JSONDecodeError, TypeError):
            pass
        chart_cfg = {}
        try:
            chart_cfg = json.loads(m.chart_config) if m.chart_config else {}
        except (json.JSONDecodeError, TypeError):
            pass

        items.append({
            "id": m.id,
            "project_id": m.project_id,
            "title": m.title,
            "question": m.question,
            "display_type": m.display_type,
            "chart_config": chart_cfg,
            "refresh_interval": m.refresh_interval,
            "order": m.order,
            "size": m.size,
            "last_result": last_result,
            "last_updated": m.last_updated.isoformat() if m.last_updated else None,
            "status": m.status,
        })
    return ApiResponse(data=items)


@router.put("/modules/{module_id}")
async def update_module(
    module_id: str, data: ModuleUpdate, db: AsyncSession = Depends(get_db)
):
    """Update a dashboard module."""
    result = await db.execute(select(DashboardModule).where(DashboardModule.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        return ApiResponse(code=404, message="Module not found")

    if data.title is not None:
        module.title = data.title
    if data.question is not None:
        module.question = data.question
    if data.display_type is not None:
        module.display_type = data.display_type
    if data.chart_config is not None:
        module.chart_config = json.dumps(data.chart_config, ensure_ascii=False)
    if data.refresh_interval is not None:
        module.refresh_interval = data.refresh_interval
    if data.size is not None:
        module.size = data.size
    if data.order is not None:
        module.order = data.order

    await db.commit()
    return ApiResponse(message="Updated")


@router.delete("/modules/{module_id}")
async def delete_module(module_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a dashboard module."""
    result = await db.execute(select(DashboardModule).where(DashboardModule.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        return ApiResponse(code=404, message="Module not found")

    await db.delete(module)
    await db.commit()
    return ApiResponse(message="Deleted")


@router.post("/modules/{module_id}/refresh")
async def refresh_module(
    module_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a module to re-run its question through the QA engine."""
    result = await db.execute(select(DashboardModule).where(DashboardModule.id == module_id))
    module = result.scalar_one_or_none()
    if not module:
        return ApiResponse(code=404, message="Module not found")

    # Get project ontology
    proj_result = await db.execute(
        select(Project).where(Project.id == module.project_id)
    )
    project = proj_result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    ontology = json.loads(project.ontology_json) if project.ontology_json else {}

    # Update status
    module.status = "loading"
    await db.commit()

    # Run in background
    background_tasks.add_task(
        _run_module_refresh, module_id, module.question, ontology
    )

    return ApiResponse(message="Refresh started")


async def _run_module_refresh(module_id: str, question: str, ontology: dict):
    """Background task for module refresh."""
    from app.models.database import async_session

    try:
        qa_result = await QAEngine.answer(question=question, ontology=ontology)

        module_result = {
            "type": "text",
            "text": qa_result.get("answer", ""),
            "raw_result": qa_result.get("raw_result"),
            "cypher": qa_result.get("generated_cypher", ""),
        }

        # Try to extract structured data
        raw = qa_result.get("raw_result", [])
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            columns = [{"key": k, "title": k} for k in raw[0].keys()]
            module_result["type"] = "structured"
            module_result["structured"] = {
                "columns": columns,
                "rows": raw[:100],
            }

        async with async_session() as db:
            result = await db.execute(
                select(DashboardModule).where(DashboardModule.id == module_id)
            )
            module = result.scalar_one_or_none()
            if module:
                module.last_result = json.dumps(module_result, ensure_ascii=False, default=str)
                module.last_updated = datetime.utcnow()
                module.status = "success"
                await db.commit()

    except Exception as e:
        async with async_session() as db:
            result = await db.execute(
                select(DashboardModule).where(DashboardModule.id == module_id)
            )
            module = result.scalar_one_or_none()
            if module:
                module.status = "error"
                module.last_result = json.dumps({"type": "text", "text": f"Error: {str(e)}"})
                module.last_updated = datetime.utcnow()
                await db.commit()
