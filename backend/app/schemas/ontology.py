"""Ontology schemas."""

from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class OntologyProperty(BaseModel):
    name: str
    type: str  # string, integer, float, date, datetime, boolean
    source_table: str = ""
    source_column: str = ""
    is_key: bool = False
    description: str = ""


class OntologyEntity(BaseModel):
    name: str  # PascalCase
    label: str  # Chinese label
    description: str = ""
    source_tables: List[str] = []
    primary_key: str = ""
    properties: List[OntologyProperty] = []


class OntologyRelation(BaseModel):
    name: str  # UPPER_SNAKE_CASE
    label: str  # Chinese label
    source_entity: str
    target_entity: str
    source_key: str
    target_key: str
    cardinality: str = "1:N"
    description: str = ""


class QueryPattern(BaseModel):
    intent: str
    description: str = ""
    example_questions: List[str] = []
    entry_entity: str = ""
    entry_filter: str = ""


class OntologyDefinition(BaseModel):
    version: int = 1
    domain: str = ""
    description: str = ""
    entities: List[OntologyEntity] = []
    relations: List[OntologyRelation] = []
    query_patterns: List[QueryPattern] = []


class OntologyBuildStatus(BaseModel):
    status: str  # pending, stage1, stage2, stage3, stage4, completed, failed
    progress: float = 0.0
    current_stage: str = ""
    message: str = ""
    ontology: Optional[OntologyDefinition] = None


class OntologyVersionOut(BaseModel):
    id: str
    project_id: str
    version: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
