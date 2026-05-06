"""QA routes - intelligent question answering."""

import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import get_db
from app.models.project import Project
from app.models.qa_history import QAHistory
from app.schemas.common import ApiResponse
from app.schemas.qa import QARequest, QAFeedback
from app.services.qa_engine import QAEngine

router = APIRouter(prefix="/api/v1/projects/{project_id}/qa", tags=["QA"])


@router.post("/ask")
async def ask_question(
    project_id: str,
    req: QARequest,
    db: AsyncSession = Depends(get_db),
):
    """Submit a question and get an answer based on knowledge graph."""
    # Get project ontology
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        return ApiResponse(code=404, message="Project not found")

    ontology = {}
    try:
        ontology = json.loads(project.ontology_json) if project.ontology_json else {}
    except (json.JSONDecodeError, TypeError):
        pass

    if not ontology.get("entities"):
        return ApiResponse(code=400, message="No ontology found. Build ontology first.")

    # Run QA pipeline
    qa_result = await QAEngine.answer(
        question=req.question,
        ontology=ontology,
        context=req.context,
        project_id=project_id,
    )

    # Save to history
    history = QAHistory(
        project_id=project_id,
        question=req.question,
        intent=qa_result.get("intent", ""),
        generated_cypher=qa_result.get("generated_cypher", ""),
        graph_result=json.dumps(qa_result.get("raw_result", []), ensure_ascii=False, default=str),
        answer=qa_result.get("answer", ""),
        latency_ms=qa_result.get("latency_ms", 0),
    )
    db.add(history)
    await db.commit()
    await db.refresh(history)

    qa_result["id"] = history.id
    return ApiResponse(data=qa_result)


@router.get("/history")
async def get_qa_history(
    project_id: str,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get question-answer history."""
    result = await db.execute(
        select(QAHistory)
        .where(QAHistory.project_id == project_id)
        .order_by(QAHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    data = [
        {
            "id": h.id,
            "question": h.question,
            "answer": h.answer,
            "intent": h.intent,
            "generated_cypher": h.generated_cypher,
            "graph_result": h.graph_result,
            "feedback": h.feedback,
            "latency_ms": h.latency_ms,
            "created_at": h.created_at.isoformat() if h.created_at else "",
        }
        for h in items
    ]
    return ApiResponse(data=data)


@router.post("/{qa_id}/feedback")
async def submit_feedback(
    project_id: str,
    qa_id: str,
    feedback: QAFeedback,
    db: AsyncSession = Depends(get_db),
):
    """Submit feedback for a QA result."""
    result = await db.execute(select(QAHistory).where(QAHistory.id == qa_id))
    qa = result.scalar_one_or_none()
    if not qa:
        return ApiResponse(code=404, message="QA record not found")

    qa.feedback = feedback.feedback
    await db.commit()
    return ApiResponse(message="Feedback submitted")
