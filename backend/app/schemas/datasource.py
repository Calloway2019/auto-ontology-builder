"""DataSource schemas."""

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class ColumnMeta(BaseModel):
    name: str
    dtype: str
    sample_values: List[str] = []
    null_rate: float = 0.0
    unique_count: int = 0


class FileUploadResponse(BaseModel):
    id: str
    name: str
    source_type: str
    row_count: int
    columns: List[ColumnMeta]


class DbConnectionCreate(BaseModel):
    db_type: str  # mysql, postgresql, oracle, sqlserver
    host: str
    port: int
    database: str
    username: str
    password: str
    table_name: str


class DataSourceOut(BaseModel):
    id: str
    project_id: str
    name: str
    source_type: str
    row_count: int
    status: str
    columns_meta: Any = []
    created_at: datetime

    model_config = {"from_attributes": True}


class DataPreview(BaseModel):
    columns: List[str]
    rows: List[dict]
    total_rows: int
