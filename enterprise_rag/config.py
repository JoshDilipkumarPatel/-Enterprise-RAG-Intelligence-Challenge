from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RetrievalConfig:
    chunk_size: int = 200
    chunk_overlap: int = 40
    bm25_weight: float = 0.50
    semantic_weight: float = 0.25
    tfidf_weight: float = 0.15
    tag_boost_weight: float = 0.10
    min_overlap_terms: int = 2
    result_limit: int = 5


@dataclass(frozen=True)
class RerankerConfig:
    enabled: bool = True
    position_weight: float = 0.15
    coverage_weight: float = 0.20
    diversity_bonus: float = 0.10


@dataclass(frozen=True)
class CacheConfig:
    enabled: bool = True
    max_size: int = 64


@dataclass(frozen=True)
class SecurityConfig:
    superuser_role: str = "Executive"
    restricted_access_roles: tuple[str, ...] = ("Executive", "Security Analyst", "Compliance Officer")


@dataclass(frozen=True)
class PipelineConfig:
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    reranker: RerankerConfig = field(default_factory=RerankerConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)


def load_config(config_path: Path | None = None) -> PipelineConfig:
    """Load pipeline configuration from JSON file, falling back to defaults if not found."""
    if config_path is None:
        config_path = Path("config/pipeline.json")
        
    if not config_path.is_file():
        return PipelineConfig()
        
    with config_path.open("r", encoding="utf-8") as f:
        data = json.load(f) or {}

    ret_data = data.get("retrieval", {})
    weights = ret_data.get("scoring_weights", {})
    retrieval = RetrievalConfig(
        chunk_size=ret_data.get("chunk_size", 200),
        chunk_overlap=ret_data.get("chunk_overlap", 40),
        bm25_weight=weights.get("bm25", 0.50),
        semantic_weight=weights.get("semantic", 0.25),
        tfidf_weight=weights.get("tfidf", 0.15),
        tag_boost_weight=weights.get("tag_boost", 0.10),
        min_overlap_terms=ret_data.get("min_overlap_terms", 2),
        result_limit=ret_data.get("result_limit", 5),
    )

    rerank_data = data.get("reranker", {})
    reranker = RerankerConfig(
        enabled=rerank_data.get("enabled", True),
        position_weight=rerank_data.get("position_weight", 0.15),
        coverage_weight=rerank_data.get("coverage_weight", 0.20),
        diversity_bonus=rerank_data.get("diversity_bonus", 0.10),
    )

    cache_data = data.get("cache", {})
    cache = CacheConfig(
        enabled=cache_data.get("enabled", True),
        max_size=cache_data.get("max_size", 64),
    )

    sec_data = data.get("security", {})
    security = SecurityConfig(
        superuser_role=sec_data.get("superuser_role", "Executive"),
        restricted_access_roles=tuple(sec_data.get("restricted_access_roles", ["Executive", "Security Analyst", "Compliance Officer"])),
    )

    return PipelineConfig(
        retrieval=retrieval,
        reranker=reranker,
        cache=cache,
        security=security,
    )
