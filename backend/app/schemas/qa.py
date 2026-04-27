"""QA schemas."""

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class QARequest(BaseModel):
    question: str
    context: str = ""


class QAResponse(BaseModel):
    question: str
    intent: str = ""
    generated_cypher: str = ""
    raw_result: Any = None
    answer: str = ""
    confidence: float = 0.0
    latency_ms: int = 0


class QAHistoryOut(BaseModel):
    id: str
    question: str
    answer: str
    intent: str
    feedback: int
    latency_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}


class QAFeedback(BaseModel):
    feedback: int  # 1=useful, -1=not useful
