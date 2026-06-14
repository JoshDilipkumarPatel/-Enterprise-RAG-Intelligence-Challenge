import unittest

from enterprise_rag.intent import classify_intent
from enterprise_rag.models import QueryIntent


class IntentClassifierTest(unittest.TestCase):
    def test_factual_intent(self) -> None:
        self.assertEqual(classify_intent("What is the vendor payment workflow?"), QueryIntent.FACTUAL)
        self.assertEqual(classify_intent("Show me the GDPR assessment"), QueryIntent.FACTUAL)

    def test_comparison_intent(self) -> None:
        self.assertEqual(classify_intent("What is the difference between Q1 and Q2?"), QueryIntent.COMPARISON)
        self.assertEqual(classify_intent("Compare AWS and Azure migration status"), QueryIntent.COMPARISON)

    def test_aggregation_intent(self) -> None:
        self.assertEqual(classify_intent("How many vendors are pending?"), QueryIntent.AGGREGATION)
        self.assertEqual(classify_intent("Show the total revenue"), QueryIntent.AGGREGATION)

    def test_temporal_intent(self) -> None:
        self.assertEqual(classify_intent("When is the next audit?"), QueryIntent.TEMPORAL)
        self.assertEqual(classify_intent("What is the recent penetration test history?"), QueryIntent.TEMPORAL)

    def test_exploratory_intent(self) -> None:
        # Fallback case
        self.assertEqual(classify_intent("I need some help with my password"), QueryIntent.EXPLORATORY)
        self.assertEqual(classify_intent("Help me understand compliance"), QueryIntent.EXPLORATORY)


if __name__ == "__main__":
    unittest.main()
