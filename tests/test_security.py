import unittest
from pathlib import Path

from enterprise_rag.config import SecurityConfig
from enterprise_rag.loaders import load_documents, load_users
from enterprise_rag.models import SensitivityLevel
from enterprise_rag.security import filter_accessible_documents


class SecurityFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        data_dir = Path("data")
        self.config = SecurityConfig()
        self.users = load_users(data_dir)
        self.documents = load_documents(data_dir)

    def test_executive_sees_all_documents(self) -> None:
        user = self.users["erin"]
        accessible, blocked, _ = filter_accessible_documents(user, self.documents, self.config)
        self.assertEqual(len(blocked), 0)
        self.assertGreater(len(accessible), 0)

    def test_finance_analyst_blocked_from_restricted(self) -> None:
        user = self.users["alice"]
        restricted_docs = [
            doc for doc in self.documents
            if doc.sensitivity_level == SensitivityLevel.RESTRICTED
        ]
        _, blocked, sensitivity_applied = filter_accessible_documents(user, restricted_docs, self.config)
        self.assertTrue(sensitivity_applied)
        self.assertGreater(len(blocked), 0)

    def test_security_analyst_accesses_restricted_pentest(self) -> None:
        user = self.users["bob"]
        restricted_docs = [
            doc for doc in self.documents
            if doc.sensitivity_level == SensitivityLevel.RESTRICTED
        ]
        accessible, _, _ = filter_accessible_documents(user, restricted_docs, self.config)
        accessible_ids = [doc.doc_id for doc in accessible]
        self.assertIn("security_penetration_test_report", accessible_ids)

    def test_hr_manager_blocked_from_finance_docs(self) -> None:
        user = self.users["carol"]
        finance_docs = [
            doc for doc in self.documents
            if "Finance Analyst" in doc.allowed_roles and "HR Manager" not in doc.allowed_roles
        ]
        _, blocked, _ = filter_accessible_documents(user, finance_docs, self.config)
        self.assertEqual(len(blocked), len(finance_docs))

    def test_compliance_officer_accesses_gdpr_document(self) -> None:
        user = self.users["frank"]
        accessible, _, _ = filter_accessible_documents(user, self.documents, self.config)
        accessible_ids = [doc.doc_id for doc in accessible]
        self.assertIn("compliance_gdpr_assessment", accessible_ids)

    def test_legal_counsel_blocked_from_hr_documents(self) -> None:
        user = self.users["grace"]
        hr_docs = [
            doc for doc in self.documents
            if doc.doc_id == "payroll_audit_findings"
        ]
        _, blocked, _ = filter_accessible_documents(user, hr_docs, self.config)
        self.assertEqual(len(blocked), 1)

    def test_block_reason_is_role_mismatch_for_role_denied(self) -> None:
        user = self.users["carol"]  # HR Manager
        finance_docs = [
            doc for doc in self.documents
            if doc.doc_id == "vendor_payment_workflow"
        ]
        _, blocked, _ = filter_accessible_documents(user, finance_docs, self.config)
        self.assertEqual(blocked[0].reason, "role_mismatch")

    def test_block_reason_is_sensitivity_restricted(self) -> None:
        user = self.users["alice"]  # Finance Analyst
        restricted_docs = [
            doc for doc in self.documents
            if doc.sensitivity_level == SensitivityLevel.RESTRICTED
        ]
        _, blocked, _ = filter_accessible_documents(user, restricted_docs, self.config)
        sensitivity_blocked = [b for b in blocked if b.reason == "sensitivity_restricted"]
        self.assertGreater(len(sensitivity_blocked), 0)


if __name__ == "__main__":
    unittest.main()
