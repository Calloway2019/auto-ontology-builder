"""Project model - represents a data project / ontology workspace."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "building", "ready", "error", name="project_status"),
        default="draft",
    )
    ontology_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    datasources = relationship("DataSource", back_populates="project", cascade="all, delete-orphan")
    ontology_versions = relationship("OntologyVersion", back_populates="project", cascade="all, delete-orphan")
    import_tasks = relationship("ImportTask", back_populates="project", cascade="all, delete-orphan")
    qa_history = relationship("QAHistory", back_populates="project", cascade="all, delete-orphan")
