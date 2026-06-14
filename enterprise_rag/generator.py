from __future__ import annotations

from collections import defaultdict

from enterprise_rag.models import QueryTrace, RagAnswer, SearchHit


def generate_grounded_answer(query: str, hits: list[SearchHit], trace: QueryTrace) -> RagAnswer:
    if not hits:
        return RagAnswer(
            answer=(
                "I could not find accessible enterprise context for this question. "
                "The system will not guess or use restricted documents."
            ),
            citations=(),
            confidence=0.0,
            trace=trace,
            answer_strategy="no_evidence",
        )

    source_types = {hit.document.source_type for hit in hits}
    strategy = "multi_source" if len(source_types) > 1 else "single_source"

    if strategy == "multi_source":
        lines, citations = _build_multi_source_answer(hits)
    else:
        lines, citations = _build_single_source_answer(hits)

    confidence = _confidence(hits)
    if confidence < 0.45:
        lines.append(
            "⚠ Confidence is limited because the retrieved evidence is weak or sparse."
        )

    return RagAnswer(
        answer="\n".join(lines),
        citations=tuple(citations),
        confidence=confidence,
        trace=trace,
        answer_strategy=strategy,
    )


def _build_single_source_answer(hits: list[SearchHit]) -> tuple[list[str], list[str]]:
    lines = ["Based on the accessible enterprise sources:"]
    citations: list[str] = []
    for index, hit in enumerate(hits, start=1):
        citation = _citation(index, hit)
        citations.append(citation)
        lines.append(f"  • {hit.snippet} {citation}")
    return lines, citations


def _build_multi_source_answer(hits: list[SearchHit]) -> tuple[list[str], list[str]]:
    """Group hits by source type so the answer reads like a cross-source synthesis."""
    grouped: dict[str, list[tuple[int, SearchHit]]] = defaultdict(list)
    citations: list[str] = []
    for index, hit in enumerate(hits, start=1):
        grouped[hit.document.source_type.value].append((index, hit))

    source_labels = {
        "document": "📄 Internal Documents",
        "csv": "📊 Structured Records",
        "json_log": "📋 Log Events",
        "policy": "🔒 Policies",
    }

    lines = ["Based on multiple enterprise sources:\n"]
    for source_type, items in grouped.items():
        label = source_labels.get(source_type, source_type)
        lines.append(f"**{label}**")
        for index, hit in items:
            citation = _citation(index, hit)
            citations.append(citation)
            lines.append(f"  • {hit.snippet} {citation}")
        lines.append("")

    return lines, citations


def _citation(index: int, hit: SearchHit) -> str:
    return (
        f"[{index}] {hit.document.title} "
        f"doc_id={hit.document.doc_id} block={hit.block_id} ({hit.document.path})"
    )


def _confidence(hits: list[SearchHit]) -> float:
    """Calibrate confidence from score distribution and source diversity."""
    if not hits:
        return 0.0

    top_hits = hits[:4]
    score_sum = sum(hit.score for hit in top_hits)
    source_diversity = len({hit.document.source_type for hit in top_hits})
    hit_count_bonus = min(len(top_hits) * 0.05, 0.15)

    # Penalise if top score is very low
    top_score = top_hits[0].score
    weak_penalty = 0.10 if top_score < 0.3 else 0.0

    confidence = (
        0.15
        + (score_sum / 8.0)
        + (source_diversity * 0.08)
        + hit_count_bonus
        - weak_penalty
    )
    return round(min(0.95, max(0.0, confidence)), 2)
