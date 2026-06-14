from __future__ import annotations

import math
from collections import Counter

from enterprise_rag.config import RetrievalConfig
from enterprise_rag.models import Document, SearchHit, SourceType
from enterprise_rag.text_utils import (
    chunk_text,
    cosine_score,
    expand_query_terms,
    first_matching_sentence,
    term_counts,
    tokenize,
)


class HybridRetriever:
    def __init__(self, documents: list[Document], config: RetrievalConfig | None = None) -> None:
        self.documents = documents
        self.config = config or RetrievalConfig()
        self._chunks = self._build_chunks()
        self.doc_counts = {cid: term_counts(text) for cid, text, _doc in self._chunks}
        self.document_frequency = self._document_frequency()
        self.average_length = self._average_length()

    def search(
        self,
        query: str,
        routed_sources: tuple[SourceType, ...],
        allowed_doc_ids: set[str] | None = None,
        limit: int | None = None,
    ) -> tuple[list[SearchHit], tuple[str, ...]]:
        limit = limit or self.config.result_limit
        query_tokens = tokenize(query)
        query_token_set = set(query_tokens)
        expanded_terms = expand_query_terms(query_tokens)

        best_hit_by_doc: dict[str, SearchHit] = {}
        chunks_considered = 0

        for chunk_id, chunk_text_content, document in self._chunks:
            if document.source_type not in routed_sources:
                continue
            if allowed_doc_ids is not None and document.doc_id not in allowed_doc_ids:
                continue
            chunks_considered += 1
            counts = self.doc_counts[chunk_id]
            overlap_terms = set(counts) & expanded_terms
            original_overlap_terms = set(counts) & query_token_set
            
            min_overlap = self.config.min_overlap_terms if len(query_tokens) >= 3 else 1
            min_original_overlap = min_overlap
            
            if (
                len(overlap_terms) < min_overlap
                or len(original_overlap_terms) < min_original_overlap
            ):
                continue
                
            bm25 = self._bm25(query_tokens, counts)
            semantic = cosine_score(expanded_terms, counts)
            tfidf = self._tfidf_score(expanded_terms, counts)
            tag_boost = self.config.tag_boost_weight if set(document.tags) & expanded_terms else 0.0
            
            score = (
                (self.config.bm25_weight * bm25)
                + (self.config.semantic_weight * semantic)
                + (self.config.tfidf_weight * tfidf)
                + tag_boost
            )

            if score > 0:
                reasons = _score_reasons(bm25, semantic, tfidf, tag_boost)
                snippet = first_matching_sentence(chunk_text_content, expanded_terms)
                hit = SearchHit(
                    document=document,
                    score=round(score, 4),
                    reasons=tuple(reasons),
                    snippet=snippet,
                    block_id=_block_id(chunk_id),
                )
                existing = best_hit_by_doc.get(document.doc_id)
                if existing is None or hit.score > existing.score:
                    best_hit_by_doc[document.doc_id] = hit

        hits = list(best_hit_by_doc.values())
        hits.sort(key=lambda hit: hit.score, reverse=True)
        notes = (
            f"query_terms={', '.join(query_tokens) or 'none'}",
            f"expanded_terms={', '.join(sorted(expanded_terms)) or 'none'}",
            f"ranked_candidates={len(hits)}",
            f"chunks_indexed={len(self._chunks)}",
            f"chunks_considered={chunks_considered}",
            f"metadata_filter_allowed_docs={len(allowed_doc_ids) if allowed_doc_ids is not None else 'all'}",
            f"min_overlap_terms={min_overlap}",
            f"min_original_overlap_terms={min_original_overlap}",
        )
        return hits[:limit], notes

    # -- chunking -----------------------------------------------------------

    def _build_chunks(self) -> list[tuple[str, str, Document]]:
        """Break each document into chunks; short docs stay as-is."""
        chunks: list[tuple[str, str, Document]] = []
        for doc in self.documents:
            text_parts = chunk_text(
                _indexable_text(doc),
                chunk_size=self.config.chunk_size,
                overlap=self.config.chunk_overlap,
            )
            for idx, part in enumerate(text_parts):
                chunk_id = f"{doc.doc_id}__chunk{idx}"
                chunks.append((chunk_id, part, doc))
        return chunks

    # -- scoring ------------------------------------------------------------

    def _document_frequency(self) -> Counter[str]:
        frequency: Counter[str] = Counter()
        for counts in self.doc_counts.values():
            frequency.update(counts.keys())
        return frequency

    def _average_length(self) -> float:
        if not self.doc_counts:
            return 0.0
        return sum(sum(c.values()) for c in self.doc_counts.values()) / len(self.doc_counts)

    def _bm25(self, query_tokens: list[str], counts: Counter[str]) -> float:
        if not query_tokens or not counts:
            return 0.0
        k1 = 1.5
        b = 0.75
        total_docs = max(len(self._chunks), 1)
        doc_length = sum(counts.values())
        score = 0.0
        for token in query_tokens:
            term_frequency = counts.get(token, 0)
            if not term_frequency:
                continue
            df = self.document_frequency.get(token, 0)
            idf = math.log(1 + ((total_docs - df + 0.5) / (df + 0.5)))
            denominator = term_frequency + k1 * (1 - b + b * doc_length / max(self.average_length, 1))
            score += idf * ((term_frequency * (k1 + 1)) / denominator)
        return score

    def _tfidf_score(self, query_terms: set[str], counts: Counter[str]) -> float:
        """Simple TF-IDF scoring as a third retrieval signal."""
        if not query_terms or not counts:
            return 0.0
        total_docs = max(len(self._chunks), 1)
        doc_length = max(sum(counts.values()), 1)
        score = 0.0
        for term in query_terms:
            tf = counts.get(term, 0)
            if not tf:
                continue
            df = self.document_frequency.get(term, 0)
            idf = math.log(1 + total_docs / (df + 1))
            score += (tf / doc_length) * idf
        return score


def _indexable_text(document: Document) -> str:
    return " ".join([document.title, document.text, " ".join(document.tags)])


def _block_id(chunk_id: str) -> str:
    _, _, chunk_number = chunk_id.rpartition("__chunk")
    return f"block-{int(chunk_number) + 1}" if chunk_number.isdigit() else "block-1"


def _score_reasons(bm25: float, semantic: float, tfidf: float, tag_boost: float) -> list[str]:
    reasons: list[str] = []
    if bm25 > 0:
        reasons.append("keyword match")
    if semantic > 0:
        reasons.append("semantic expansion match")
    if tfidf > 0:
        reasons.append("tf-idf match")
    if tag_boost > 0:
        reasons.append("metadata tag match")
    return reasons
