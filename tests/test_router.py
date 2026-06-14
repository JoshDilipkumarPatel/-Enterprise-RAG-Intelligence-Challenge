import unittest

from enterprise_rag.models import SourceType
from enterprise_rag.router import route_query


class RouteQueryTest(unittest.TestCase):
    def test_security_query_routes_to_logs(self) -> None:
        sources, reason = route_query("Show security alerts for impossible travel")
        self.assertIn(SourceType.JSON_LOG, sources)

    def test_payment_query_routes_to_csv(self) -> None:
        sources, reason = route_query("Which vendor invoices are pending?")
        self.assertIn(SourceType.CSV, sources)

    def test_policy_query_routes_to_document(self) -> None:
        sources, reason = route_query("What is the benefits policy?")
        self.assertIn(SourceType.DOCUMENT, sources)

    def test_gdpr_query_routes_to_document(self) -> None:
        sources, reason = route_query("Show the GDPR compliance assessment")
        self.assertIn(SourceType.DOCUMENT, sources)

    def test_rbac_query_routes_to_policy(self) -> None:
        sources, reason = route_query("Who has access and what roles are allowed?")
        self.assertIn(SourceType.POLICY, sources)

    def test_infrastructure_query_routes_to_document(self) -> None:
        sources, reason = route_query("What is the cloud migration status?")
        self.assertIn(SourceType.DOCUMENT, sources)

    def test_multi_source_routing(self) -> None:
        sources, reason = route_query("Show security audit trail events and compliance findings")
        self.assertGreater(len(sources), 1)

    def test_unknown_query_searches_all_sources(self) -> None:
        sources, reason = route_query("random unrelated nonsense")
        self.assertEqual(len(sources), len(SourceType))
        self.assertIn("all sources", reason.lower())

    def test_reason_contains_matched_keywords(self) -> None:
        _, reason = route_query("vendor payment invoice")
        self.assertIn("vendor", reason)


if __name__ == "__main__":
    unittest.main()
