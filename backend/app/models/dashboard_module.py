"""DashboardModule model - configurable dashboard question modules."""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.database import Base


class DashboardModule(Base):
    __tablename__ = "dashboard_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    display_type: Mapped[str] = mapped_column(
        SAEnum("table", "bar", "line", "pie", "text", "list", name="display_type"),
        default="table",
    )
    chart_config: Mapped[str] = mapped_column(Text, default="{}")  # JSON
    refresh_interval: Mapped[int] = mapped_column(Integer, default=0)  # minutes, 0=manual
    order: Mapped[int] = mapped_column(Integer, default=0)
    size: Mapped[str] = mapped_column(
        SAEnum("small", "medium", "large", name="module_size"),
        default="medium",
    )
    last_result: Mapped[str] = mapped_column(Text, default="")  # JSON
    last_updated: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("idle", "loading", "success", "error", name="module_status"),
        default="idle",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
