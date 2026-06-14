import unittest
from pathlib import Path

from enterprise_rag.pipeline import EnterpriseRagPipeline


class EnterpriseRagPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = EnterpriseRagPipeline(Path("data"))

    def test_finance_user_gets_vendor_payment_context(self) -> None:
        answer = self.pipeline.ask("alice", "What changed in the vendor payment approval workflow?")

        self.assertIn("Vendor Payment", answer.answer)
        self.assertGreater(answer.confidence, 0.0)
        self.assertTrue(answer.citations)

    def test_security_user_blocked_from_payroll_document(self) -> None:
        """Bob can see audit log *mentions* of payroll, but the payroll document itself
        must be blocked.  Verify the payroll doc appears as a blocked document.
        """
        answer = self.pipeline.ask("bob", "What are the payroll audit findings?")

        blocked_titles = [bd.title for bd in answer.trace.blocked_documents]
        self.assertIn("Payroll Audit Findings", blocked_titles)

    def test_security_user_gets_security_log_context(self) -> None:
        answer = self.pipeline.ask("bob", "Show security alerts for impossible travel")

        self.assertIn("impossible_travel", answer.answer)
        self.assertTrue(any("security_events" in citation for citation in answer.citations))

    def test_executive_accesses_all_sources(self) -> None:
        answer = self.pipeline.ask("erin", "Show the GDPR compliance assessment status")

        self.assertGreater(answer.confidence, 0.0)
        self.assertEqual(len(answer.trace.blocked_documents), 0)

    def test_compliance_officer_gets_gdpr_context(self) -> None:
        answer = self.pipeline.ask("frank", "What is the GDPR compliance assessment status?")

        self.assertIn("GDPR", answer.answer)
        self.assertTrue(answer.citations)

    def test_legal_counsel_gets_contract_context(self) -> None:
        answer = self.pipeline.ask("grace", "Summarize active vendor contracts and SLAs")

        self.assertGreater(answer.confidence, 0.0)
        self.assertTrue(answer.citations)

    def test_hr_manager_gets_benefits_context(self) -> None:
        answer = self.pipeline.ask("carol", "What are the employee benefits for 2026?")

        self.assertIn("benefit", answer.answer.lower())
        self.assertTrue(answer.citations)

    def test_operations_manager_gets_infrastructure_context(self) -> None:
        answer = self.pipeline.ask("dave", "What is the cloud migration status?")

        self.assertGreater(answer.confidence, 0.0)
        self.assertTrue(answer.citations)

    def test_finance_user_blocked_from_restricted_pentest(self) -> None:
        """Finance analyst should not see the restricted penetration test report."""
        answer = self.pipeline.ask("alice", "What did the penetration test find?")

        blocked_titles = [bd.title for bd in answer.trace.blocked_documents]
        self.assertIn("Security Penetration Test Report", blocked_titles)
        self.assertTrue(answer.trace.sensitivity_filter_applied)

    def test_out_of_scope_query_short_circuits_before_retrieval(self) -> None:
        answer = self.pipeline.ask("alice", "What is the weather today?")

        self.assertEqual(answer.answer_strategy, "no_evidence")
        self.assertEqual(answer.trace.routed_sources, ())
        self.assertIn("short_circuit=out_of_scope", answer.trace.retrieval_notes)

    def test_trace_includes_latency_timings(self) -> None:
        answer = self.pipeline.ask("alice", "What changed in the vendor payment approval workflow?")

        self.assertIn("retrieval", answer.trace.timings_ms)
        self.assertIn("total", answer.trace.timings_ms)

    def test_runtime_audit_log_is_not_ingested_as_source_data(self) -> None:
        doc_paths = [document.path for document in self.pipeline.documents]

        self.assertFalse(any("query_audit.jsonl" in path for path in doc_paths))


if __name__ == "__main__":
    unittest.main()
