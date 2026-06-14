"""Append-only audit logger for enterprise RAG queries."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from enterprise_rag.models import AuditEntry

_lock = threading.Lock()


def log_query(data_dir: Path, entry: AuditEntry) -> None:
    """Append an audit entry to the query audit log."""
    path = data_dir / "logs" / "query_audit.jsonl"
    record = {
        "timestamp": entry.timestamp,
        "user_id": entry.user_id,
        "query": entry.query,
        "routed_sources": list(entry.routed_sources),
        "accessible_count": entry.accessible_count,
        "blocked_count": entry.blocked_count,
        "answer_confidence": entry.answer_confidence,
        "sensitivity_levels_accessed": list(entry.sensitivity_levels_accessed),
    }
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _lock:
        with path.open("a", encoding="utf-8") as file:
            file.write(line)


def create_audit_entry(
    user_id: str,
    query: str,
    routed_sources: tuple[str, ...],
    accessible_count: int,
    blocked_count: int,
    answer_confidence: float,
    sensitivity_levels_accessed: tuple[str, ...],
) -> AuditEntry:
    """Build an AuditEntry with the current UTC timestamp."""
    return AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id=user_id,
        query=query,
        routed_sources=routed_sources,
        accessible_count=accessible_count,
        blocked_count=blocked_count,
        answer_confidence=answer_confidence,
        sensitivity_levels_accessed=sensitivity_levels_accessed,
    )
