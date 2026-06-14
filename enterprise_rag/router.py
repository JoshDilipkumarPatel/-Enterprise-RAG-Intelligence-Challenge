from __future__ import annotations

from enterprise_rag.models import SourceType
from enterprise_rag.text_utils import tokenize


ROUTE_KEYWORDS = {
    SourceType.JSON_LOG: {
        "alert",
        "backup",
        "cpu",
        "error",
        "event",
        "failed",
        "health",
        "impossible",
        "incident",
        "login",
        "memory",
        "monitor",
        "security",
        "spike",
        "trail",
        "travel",
    },
    SourceType.CSV: {
        "amount",
        "asset",
        "compliance",
        "control",
        "customer",
        "dataset",
        "directory",
        "employee",
        "hardware",
        "inventory",
        "invoice",
        "metric",
        "payment",
        "row",
        "server",
        "software",
        "staff",
        "ticket",
        "vendor",
    },
    SourceType.DOCUMENT: {
        "assessment",
        "benefit",
        "cloud",
        "contract",
        "earning",
        "expense",
        "finding",
        "forecast",
        "gdpr",
        "infrastructure",
        "legal",
        "migration",
        "penetration",
        "pentest",
        "policy",
        "procedure",
        "quarterly",
        "renewal",
        "report",
        "revenue",
        "sla",
        "summary",
        "vulnerability",
        "workflow",
    },
    SourceType.POLICY: {
        "access",
        "allowed",
        "permission",
        "rbac",
        "role",
        "roles",
        "sensitivity",
    },
}

OUT_OF_SCOPE_KEYWORDS = {
    "cricket",
    "football",
    "joke",
    "movie",
    "music",
    "recipe",
    "song",
    "sports",
    "stock",
    "travel booking",
    "weather",
}


def is_out_of_scope_query(query: str) -> bool:
    normalized_query = " ".join(tokenize(query))
    tokens = set(normalized_query.split())
    if tokens & OUT_OF_SCOPE_KEYWORDS:
        return True
    return any(phrase in normalized_query for phrase in OUT_OF_SCOPE_KEYWORDS if " " in phrase)


def route_query(query: str) -> tuple[tuple[SourceType, ...], str]:
    tokens = set(tokenize(query))
    matches: list[SourceType] = []
    reasons: list[str] = []
    for source_type, keywords in ROUTE_KEYWORDS.items():
        overlap = tokens & keywords
        if overlap:
            matches.append(source_type)
            reasons.append(f"{source_type.value}: {', '.join(sorted(overlap))}")

    if not matches:
        return tuple(SourceType), "No strong route keyword found, searching all sources."
    return tuple(matches), "; ".join(reasons)
