from __future__ import annotations

from pathlib import Path

from enterprise_rag.evaluation import evaluate_pipeline, load_eval_cases
from enterprise_rag.pipeline import EnterpriseRagPipeline


def main() -> None:
    data_dir = Path("data")
    eval_file = data_dir / "evaluation" / "eval_cases.json"
    
    print(f"Loading pipeline from {data_dir}...")
    pipeline = EnterpriseRagPipeline(data_dir)
    
    print(f"Loading eval cases from {eval_file}...")
    cases = load_eval_cases(eval_file)
    
    print(f"Running evaluation over {len(cases)} cases...")
    metrics = evaluate_pipeline(pipeline, cases)
    
    print("\n--- Evaluation Results ---")
    print(f"Total Cases:    {metrics.total_cases}")
    print(f"MRR:            {metrics.mrr:.3f}")
    print(f"Precision@3:    {metrics.precision_at_3:.3f}")
    print(f"Recall@3:       {metrics.recall_at_3:.3f}")
    print(f"NDCG:           {metrics.ndcg:.3f}")
    print(f"RBAC Pass Rate: {metrics.rbac_pass_rate * 100:.1f}%")
    print("--------------------------")


if __name__ == "__main__":
    main()
