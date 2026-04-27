"""Project management routes."""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import get_db
from app.models.project import Project
from app.models.datasource import DataSource
from app.schemas.common import ApiResponse
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.post("")
async def create_project(data: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(name=data.name, description=data.description)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ApiResponse(data={"id": project.id, "name": project.name})


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()

    items = []
    for p in projects:
        # Count datasources
        ds_result = await db.execute(
            select(func.count()).where(DataSource.project_id == p.id)
        )
        ds_count = ds_result.scalar() or 0

        # Count entities/relations from ontology_json
        entity_count = 0
        relation_count = 0
        try:
            ontology = json.loads(p.ontology_json) if p.ontology_json else {}
            entity_count = len(ontology.get("entities", []))
            relation_count = len(ontology.get("relations", []))
        except (json.JSONDecodeError, TypeError):
            pass

        items.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else "",
            "updated_at": p.updated_at.isoformat() if p.updated_at else "",
            "datasource_count": ds_count,
            "entity_count": entity_count,
            "relation_count": relation_count,
        })

    return ApiResponse(data=items)


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    ontology = {}
    try:
        ontology = json.loads(project.ontology_json) if project.ontology_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    return ApiResponse(data={
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "ontology": ontology,
        "created_at": project.created_at.isoformat() if project.created_at else "",
        "updated_at": project.updated_at.isoformat() if project.updated_at else "",
    })


@router.put("/{project_id}")
async def update_project(
    project_id: str, data: ProjectUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description

    await db.commit()
    return ApiResponse(message="Updated")


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    await db.delete(project)
    await db.commit()
    return ApiResponse(message="Deleted")
