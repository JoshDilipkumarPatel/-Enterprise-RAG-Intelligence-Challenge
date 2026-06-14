from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    DOCUMENT = "document"
    CSV = "csv"
    JSON_LOG = "json_log"
    POLICY = "policy"
    USER_MAPPING = "user_mapping"


class SensitivityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class QueryIntent(str, Enum):
    FACTUAL = "factual"
    COMPARISON = "comparison"
    AGGREGATION = "aggregation"
    TEMPORAL = "temporal"
    EXPLORATORY = "exploratory"


@dataclass(frozen=True)
class User:
    user_id: str
    display_name: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class Document:
    doc_id: str
    title: str
    source_type: SourceType
    text: str
    path: str
    allowed_roles: tuple[str, ...]
    sensitivity_level: SensitivityLevel = SensitivityLevel.INTERNAL
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    document: Document
    score: float
    reasons: tuple[str, ...]
    snippet: str
    block_id: str = "block-1"


@dataclass(frozen=True)
class BlockedDocument:
    doc_id: str
    title: str
    required_roles: tuple[str, ...]
    reason: str = "role_mismatch"


@dataclass(frozen=True)
class AuditEntry:
    timestamp: str
    user_id: str
    query: str
    routed_sources: tuple[str, ...]
    accessible_count: int
    blocked_count: int
    answer_confidence: float
    sensitivity_levels_accessed: tuple[str, ...]


@dataclass(frozen=True)
class QueryTrace:
    intent: QueryIntent | None
    routed_sources: tuple[SourceType, ...]
    route_reason: str
    accessible_documents: int
    blocked_documents: tuple[BlockedDocument, ...]
    retrieval_notes: tuple[str, ...]
    sensitivity_filter_applied: bool = False
    timings_ms: dict[str, float] = field(default_factory=dict)
    reranker_applied: bool = False


@dataclass
class PipelineState:
    user_id: str
    query: str
    intent: QueryIntent | None = None
    routed_sources: tuple[SourceType, ...] = field(default_factory=tuple)
    route_reason: str = ""
    accessible_documents: list[Document] = field(default_factory=list)
    blocked_documents: tuple[BlockedDocument, ...] = field(default_factory=tuple)
    sensitivity_filter_applied: bool = False
    search_hits: list[SearchHit] = field(default_factory=list)
    retrieval_notes: tuple[str, ...] = field(default_factory=tuple)
    reranker_applied: bool = False
    answer: RagAnswer | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    short_circuited: bool = False


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: tuple[str, ...]
    confidence: float
    trace: QueryTrace
    answer_strategy: str = "single_source"
