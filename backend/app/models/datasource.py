"""DataSource model - represents an uploaded file or database connection."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.database import Base


class DataSource(Base):
    __tablename__ = "datasources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(
        SAEnum("excel", "csv", "database", name="source_type"),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(String(500), default="")
    db_connection_string: Mapped[str] = mapped_column(Text, default="")
    db_table_name: Mapped[str] = mapped_column(String(200), default="")
    columns_meta: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        SAEnum("uploaded", "analyzed", "loaded", name="datasource_status"),
        default="uploaded",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="datasources")
