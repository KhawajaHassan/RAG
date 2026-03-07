from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


EntityType = Literal["PERSON", "ORG", "LOCATION", "CONCEPT", "EVENT"]


class UploadResponse(BaseModel):
    job_id: str


class IndexStartResponse(BaseModel):
    job_id: str
    started: bool


class StatusResponse(BaseModel):
    job_id: str
    status: str
    current_step: str
    progress: float
    error: Optional[str] = None
    stats: Dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    question: str
    mode: Literal["vector_rag", "summary_rag", "graph_global", "graph_local", "all"]
    job_id: str


class QueryResult(BaseModel):
    mode: str
    answer: str
    latency_ms: int
    sources: List[Dict[str, Any]] = Field(default_factory=list)


class QueryResponse(BaseModel):
    job_id: str
    question: str
    results: List[QueryResult]


class GraphNode(BaseModel):
    id: str
    label: str
    type: EntityType
    description: str
    degree: float
    community_level: int
    community_id: Optional[str] = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    description: str
    weight: float


class GraphStats(BaseModel):
    entity_count: int
    edge_count: int
    community_count: int


class CommunityResponse(BaseModel):
    job_id: str
    level: int
    community_id: str
    title: str
    executive_summary: str
    impact_severity: float
    impact_explanation: str
    findings: List[str]
    members: List[str]


class EvaluationGenerateResponse(BaseModel):
    job_id: str
    question_count: int


class EvaluationEstimateRequest(BaseModel):
    question_count: int = 125
    systems: int = 5
    runs: int = 5
    price_per_unit_usd: float = 0.002


class EvaluationEstimateResponse(BaseModel):
    estimated_cost_usd: float


class EvaluationRunResponse(BaseModel):
    job_id: str
    started: bool


class EvaluationResultsResponse(BaseModel):
    job_id: str
    results: Dict[str, Any]

