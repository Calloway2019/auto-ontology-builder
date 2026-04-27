"""QAHistory model - question-answer interaction records."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.database import Base


class QAHistory(Base):
    __tablename__ = "qa_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(100), default="")
    generated_cypher: Mapped[str] = mapped_column(Text, default="")
    graph_result: Mapped[str] = mapped_column(Text, default="")  # JSON
    answer: Mapped[str] = mapped_column(Text, default="")
    feedback: Mapped[int] = mapped_column(Integer, default=0)  # 1=useful, -1=not useful
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="qa_history")
