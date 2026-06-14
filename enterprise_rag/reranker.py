from __future__ import annotations

from enterprise_rag.config import RerankerConfig
from enterprise_rag.models import SearchHit
from enterprise_rag.text_utils import tokenize


def rerank_hits(query: str, hits: list[SearchHit], config: RerankerConfig) -> list[SearchHit]:
    """Rescore and rerank initial retrieval hits using cross-document features."""
    if not config.enabled or not hits:
        return hits

    query_tokens = set(tokenize(query))
    if not query_tokens:
        return hits

    reranked_hits: list[SearchHit] = []
    
    for hit in hits:
        # Calculate coverage (what fraction of query terms appear in the snippet/document)
        hit_tokens = set(tokenize(hit.snippet))
        overlap = len(query_tokens & hit_tokens)
        coverage = overlap / len(query_tokens)
        
        # Calculate position weight (block-1 gets a higher weight than block-10)
        # Assuming block_id format: 'block-N'
        try:
            block_num = int(hit.block_id.split("-")[-1])
        except (ValueError, IndexError):
            block_num = 1
            
        position_penalty = max(0.0, min(1.0, (block_num - 1) * 0.05))
        position_score = 1.0 - position_penalty

        # Compute new score
        new_score = (
            hit.score 
            + (coverage * config.coverage_weight) 
            + (position_score * config.position_weight)
        )
        
        # We need to construct a new SearchHit since they are frozen
        new_hit = SearchHit(
            document=hit.document,
            score=round(new_score, 4),
            reasons=hit.reasons + ("reranked",),
            snippet=hit.snippet,
            block_id=hit.block_id,
        )
        reranked_hits.append(new_hit)

    # Sort by new score
    reranked_hits.sort(key=lambda h: h.score, reverse=True)

    # Diversity bonus: if the top 3 results are all from the same source, 
    # boost the best result from a different source.
    if len(reranked_hits) > 3:
        top_3_sources = {h.document.source_type for h in reranked_hits[:3]}
        if len(top_3_sources) == 1:
            dominant_source = list(top_3_sources)[0]
            for idx in range(3, len(reranked_hits)):
                candidate = reranked_hits[idx]
                if candidate.document.source_type != dominant_source:
                    # Apply diversity bonus
                    boosted_score = candidate.score + config.diversity_bonus
                    boosted_hit = SearchHit(
                        document=candidate.document,
                        score=round(boosted_score, 4),
                        reasons=candidate.reasons + ("diversity_boost",),
                        snippet=candidate.snippet,
                        block_id=candidate.block_id,
                    )
                    reranked_hits[idx] = boosted_hit
                    # Re-sort
                    reranked_hits.sort(key=lambda h: h.score, reverse=True)
                    break

    return reranked_hits
