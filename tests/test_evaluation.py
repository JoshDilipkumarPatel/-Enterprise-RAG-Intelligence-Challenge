import unittest
from pathlib import Path

from enterprise_rag.evaluation import canonical_doc_id, evaluate_pipeline, load_eval_cases
from enterprise_rag.pipeline import EnterpriseRagPipeline


class EvaluationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        data_dir = Path("data")
        eval_file = data_dir / "evaluation" / "eval_cases.json"
        cls.pipeline = EnterpriseRagPipeline(data_dir)
        cls.cases = load_eval_cases(eval_file)
        cls.metrics = evaluate_pipeline(cls.pipeline, cls.cases)

    def test_mrr_meets_minimum_threshold(self) -> None:
        self.assertGreaterEqual(self.metrics.mrr, 0.85)

    def test_precision_meets_minimum_threshold(self) -> None:
        self.assertGreaterEqual(self.metrics.precision_at_3, 0.60)
        
    def test_ndcg_meets_minimum_threshold(self) -> None:
        self.assertGreaterEqual(self.metrics.ndcg, 0.80)

    def test_rbac_blocking_is_perfect(self) -> None:
        self.assertEqual(self.metrics.rbac_pass_rate, 1.0)

    def test_row_level_ids_canonicalize_to_source_ids(self) -> None:
        self.assertEqual(canonical_doc_id("security_events-1"), "security_events")
        self.assertEqual(canonical_doc_id("vendor_payment_workflow"), "vendor_payment_workflow")


if __name__ == "__main__":
    unittest.main()
