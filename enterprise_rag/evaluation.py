from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from enterprise_rag.pipeline import EnterpriseRagPipeline


@dataclass
class EvalCase:
    query: str
    user_id: str
    expected_doc_ids: set[str]
    expected_blocked_doc_ids: set[str]


@dataclass
class EvalMetrics:
    mrr: float
    precision_at_3: float
    recall_at_3: float
    ndcg: float
    rbac_pass_rate: float
    total_cases: int


def load_eval_cases(eval_file: Path) -> list[EvalCase]:
    with eval_file.open("r", encoding="utf-8") as f:
        cases = json.load(f)
        
    return [
        EvalCase(
            query=c["query"],
            user_id=c["user_id"],
            expected_doc_ids=set(c.get("expected_doc_ids", [])),
            expected_blocked_doc_ids=set(c.get("expected_blocked_doc_ids", [])),
        )
        for c in cases
    ]


def evaluate_pipeline(pipeline: EnterpriseRagPipeline, cases: list[EvalCase]) -> EvalMetrics:
    total_mrr = 0.0
    total_p3 = 0.0
    total_r3 = 0.0
    total_ndcg = 0.0
    rbac_passes = 0
    
    for case in cases:
        answer = pipeline.ask(case.user_id, case.query)
        
        # We need to extract the retrieved doc IDs from the hits or citations
        # But answer doesn't expose raw hits directly. The easiest way is to look at citations.
        # Citations format: [1] Title doc_id=XYZ block=... (path)
        retrieved_doc_ids = []
        for cit in answer.citations:
            parts = cit.split("doc_id=")
            if len(parts) > 1:
                doc_id = canonical_doc_id(parts[1].split()[0])
                if doc_id not in retrieved_doc_ids:
                    retrieved_doc_ids.append(doc_id)
                    
        blocked_doc_ids = {canonical_doc_id(bd.doc_id) for bd in answer.trace.blocked_documents}
        expected_doc_ids = {canonical_doc_id(doc_id) for doc_id in case.expected_doc_ids}
        expected_blocked_doc_ids = {
            canonical_doc_id(doc_id) for doc_id in case.expected_blocked_doc_ids
        }
        
        # RBAC Check
        rbac_passed = True
        for expected_blocked in expected_blocked_doc_ids:
            if expected_blocked not in blocked_doc_ids:
                rbac_passed = False
            if expected_blocked in retrieved_doc_ids:
                rbac_passed = False
        
        if rbac_passed:
            rbac_passes += 1
            
        # Retrieval Metrics
        if not expected_doc_ids:
            # If no docs expected and none retrieved, perfect score
            if not retrieved_doc_ids:
                total_mrr += 1.0
                total_p3 += 1.0
                total_r3 += 1.0
                total_ndcg += 1.0
            continue
            
        # MRR
        mrr = 0.0
        for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
            if doc_id in expected_doc_ids:
                mrr = 1.0 / rank
                break
        total_mrr += mrr
        
        # Precision@3 & Recall@3
        top_3 = retrieved_doc_ids[:3]
        hits_in_top_3 = len([d for d in top_3 if d in expected_doc_ids])
        total_p3 += hits_in_top_3 / min(3, len(top_3)) if top_3 else 0.0
        total_r3 += hits_in_top_3 / len(expected_doc_ids)
        
        # NDCG
        dcg = 0.0
        for rank, doc_id in enumerate(retrieved_doc_ids, start=1):
            if doc_id in expected_doc_ids:
                dcg += 1.0 / math.log2(rank + 1)
                
        idcg = 0.0
        for rank in range(1, min(len(expected_doc_ids), len(retrieved_doc_ids)) + 1):
            idcg += 1.0 / math.log2(rank + 1)
            
        ndcg = dcg / idcg if idcg > 0 else 0.0
        total_ndcg += ndcg

    n = len(cases)
    return EvalMetrics(
        mrr=total_mrr / n,
        precision_at_3=total_p3 / n,
        recall_at_3=total_r3 / n,
        ndcg=total_ndcg / n,
        rbac_pass_rate=rbac_passes / n,
        total_cases=n,
    )


def canonical_doc_id(doc_id: str) -> str:
    """Normalize row/event ids back to their source-level document id.

    CSV rows and JSONL events are represented internally as ``source-1``,
    ``source-2``, etc. Evaluation cases usually care about the source file,
    so ``security_events-1`` should count as ``security_events``.
    """
    prefix, separator, suffix = doc_id.rpartition("-")
    if separator and suffix.isdigit():
        return prefix
    return doc_id
