from __future__ import annotations

import re

from enterprise_rag.models import QueryIntent
from enterprise_rag.text_utils import tokenize


def classify_intent(query: str) -> QueryIntent:
    """Classify the user query into a QueryIntent for better routing and retrieval."""
    query_lower = query.lower()
    
    # Comparison
    comparison_patterns = [r"\bcompare\b", r"\bdifference\b", r"\bversus\b", r"\bvs\b"]
    if any(re.search(p, query_lower) for p in comparison_patterns):
        return QueryIntent.COMPARISON

    # Aggregation
    aggregation_patterns = [r"\bhow many\b", r"\btotal\b", r"\bcount\b", r"\ball\b", r"\bhow much\b"]
    if any(re.search(p, query_lower) for p in aggregation_patterns):
        return QueryIntent.AGGREGATION

    # Temporal
    temporal_patterns = [r"\bwhen\b", r"\btimeline\b", r"\bhistory\b", r"\brecent\b", r"\bpast\b", r"\byear\b", r"\bmonth\b"]
    if any(re.search(p, query_lower) for p in temporal_patterns):
        return QueryIntent.TEMPORAL

    # Factual (starts with what, who, where, show, find, etc.)
    factual_patterns = [r"^what\b", r"^who\b", r"^where\b", r"^show\b", r"^find\b", r"^list\b", r"^summarize\b", r"^tell\b"]
    if any(re.search(p, query_lower) for p in factual_patterns):
        return QueryIntent.FACTUAL

    return QueryIntent.EXPLORATORY
