"""Graph schemas."""

from pydantic import BaseModel
from typing import Any, List, Optional


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    label: str = ""
    properties: dict = {}


class GraphData(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class GraphStats(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    node_types: dict = {}  # {type: count}
    edge_types: dict = {}  # {type: count}


class GraphLoadStatus(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0
    total_nodes: int = 0
    total_relations: int = 0
    error_message: str = ""
