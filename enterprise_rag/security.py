from __future__ import annotations

from enterprise_rag.config import SecurityConfig
from enterprise_rag.models import BlockedDocument, Document, SensitivityLevel, User


def filter_accessible_documents(
    user: User,
    documents: list[Document],
    config: SecurityConfig,
) -> tuple[list[Document], tuple[BlockedDocument, ...], bool]:
    """Filter documents by RBAC and sensitivity level.

    Returns (accessible, blocked, sensitivity_filter_applied).
    """
    accessible: list[Document] = []
    blocked: list[BlockedDocument] = []
    user_roles = set(user.roles)
    sensitivity_filter_applied = False

    for document in documents:
        # --- sensitivity gate ---
        if document.sensitivity_level == SensitivityLevel.RESTRICTED:
            if not user_roles.intersection(config.restricted_access_roles):
                sensitivity_filter_applied = True
                blocked.append(
                    BlockedDocument(
                        doc_id=document.doc_id,
                        title=document.title,
                        required_roles=document.allowed_roles,
                        reason="sensitivity_restricted",
                    )
                )
                continue

        # --- role-based gate ---
        if config.superuser_role in user_roles or user_roles.intersection(document.allowed_roles):
            accessible.append(document)
        else:
            blocked.append(
                BlockedDocument(
                    doc_id=document.doc_id,
                    title=document.title,
                    required_roles=document.allowed_roles,
                    reason="role_mismatch",
                )
            )

    return accessible, tuple(blocked), sensitivity_filter_applied
