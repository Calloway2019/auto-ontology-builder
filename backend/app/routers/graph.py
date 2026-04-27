"""Graph routes - Neo4j knowledge graph operations."""

import json
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.models.database import get_db
from app.models.project import Project
from app.models.datasource import DataSource
from app.models.import_task import ImportTask
from app.schemas.common import ApiResponse
from app.services.graph_manager import graph_manager
from app.services.import_pipeline import ImportPipeline

router = APIRouter(prefix="/api/v1/projects/{project_id}/graph", tags=["Graph"])


class CypherQuery(BaseModel):
    cypher: str
    params: dict = {}


async def _run_graph_load(project_id: str, ontology: dict, datasources_info: list):
    """Background task for loading data into Neo4j."""
    from app.models.database import async_session

    async with async_session() as db:
        # Create import task
        task = ImportTask(project_id=project_id, status="running", started_at=datetime.utcnow())
        db.add(task)
        await db.commit()
        await db.refresh(task)
        task_id = task.id

    try:
        # Clear existing graph data
        await graph_manager.clear_graph()

        result = await ImportPipeline.load_data_to_graph(ontology, datasources_info)

        async with async_session() as db:
            task_result = await db.execute(select(ImportTask).where(ImportTask.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "success"
                task.progress = 100.0
                task.total_nodes = result["total_nodes"]
                task.total_relations = result["total_relations"]
                task.finished_at = datetime.utcnow()
                await db.commit()

    except Exception as e:
        async with async_session() as db:
            task_result = await db.execute(select(ImportTask).where(ImportTask.id == task_id))
            task = task_result.scalar_one_or_none()
            if task:
                task.status = "failed"
                task.error_message = str(e)
                task.finished_at = datetime.utcnow()
                await db.commit()


@router.post("/load")
async def load_graph_data(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger data loading into Neo4j based on ontology."""
    # Get project and ontology
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    ontology = json.loads(project.ontology_json) if project.ontology_json else {}
    if not ontology.get("entities"):
        return ApiResponse(code=400, message="No ontology definition found. Build ontology first.")

    # Get datasources
    ds_result = await db.execute(
        select(DataSource).where(DataSource.project_id == project_id)
    )
    datasources = ds_result.scalars().all()
    datasources_info = [
        {"name": ds.name, "file_path": ds.file_path, "source_type": ds.source_type}
        for ds in datasources
    ]

    background_tasks.add_task(_run_graph_load, project_id, ontology, datasources_info)

    return ApiResponse(data={"message": "Graph loading started"})


@router.get("/load/status")
async def get_load_status(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get latest import task status."""
    result = await db.execute(
        select(ImportTask)
        .where(ImportTask.project_id == project_id)
        .order_by(ImportTask.created_at.desc())
    )
    task = result.scalars().first()
    if not task:
        return ApiResponse(data={"status": "no_task", "progress": 0})

    return ApiResponse(data={
        "task_id": task.id,
        "status": task.status,
        "progress": task.progress,
        "total_nodes": task.total_nodes,
        "total_relations": task.total_relations,
        "error_message": task.error_message,
    })


def _build_label_map(ontology: dict) -> dict:
    """Build a name->label mapping from ontology for Chinese display."""
    label_map = {}
    for entity in ontology.get("entities", []):
        if entity.get("label"):
            label_map[entity["name"]] = entity["label"]
    for relation in ontology.get("relations", []):
        if relation.get("label"):
            label_map[relation["name"]] = relation["label"]
    return label_map


@router.get("/stats")
async def get_graph_stats(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get graph statistics."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    ontology = json.loads(project.ontology_json) if project and project.ontology_json else {}
    label_map = _build_label_map(ontology)
    stats = await graph_manager.get_graph_stats(label_map=label_map)
    return ApiResponse(data=stats)


@router.get("/visualize")
async def get_graph_visualization(
    project_id: str,
    limit: int = 500,
    node_types: Optional[str] = None,
    rel_types: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get graph data for visualization."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    ontology = json.loads(project.ontology_json) if project and project.ontology_json else {}
    label_map = _build_label_map(ontology)

    nt = node_types.split(",") if node_types else None
    rt = rel_types.split(",") if rel_types else None
    data = await graph_manager.get_graph_visualization(limit=limit, node_types=nt, rel_types=rt, label_map=label_map)
    return ApiResponse(data=data)


@router.post("/query")
async def query_graph(project_id: str, query: CypherQuery):
    """Execute a custom Cypher query (read-only)."""
    try:
        results = await graph_manager.execute_cypher(query.cypher, query.params)
        # Serialize results
        clean = json.loads(json.dumps(results, default=str))
        return ApiResponse(data=clean)
    except ValueError as e:
        return ApiResponse(code=403, message=str(e))
    except Exception as e:
        return ApiResponse(code=500, message=str(e))


@router.delete("/clear")
async def clear_graph(project_id: str):
    """Clear all graph data."""
    await graph_manager.clear_graph()
    return ApiResponse(message="Graph cleared")
