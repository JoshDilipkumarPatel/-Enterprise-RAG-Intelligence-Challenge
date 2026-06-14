from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from enterprise_rag.models import Document, SensitivityLevel, SourceType, User


def load_users(data_dir: Path) -> dict[str, User]:
    path = data_dir / "metadata" / "user_roles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["user_id"]: User(
            user_id=item["user_id"],
            display_name=item["display_name"],
            roles=tuple(item["roles"]),
        )
        for item in payload["users"]
    }


def load_documents(data_dir: Path) -> list[Document]:
    policies = _load_access_policies(data_dir)
    docs: list[Document] = []
    docs.extend(_load_internal_documents(data_dir, policies))
    docs.extend(_load_csv_records(data_dir, policies))
    docs.extend(_load_json_logs(data_dir, policies))
    docs.extend(_load_policy_documents(data_dir, policies))
    return docs


def _load_access_policies(data_dir: Path) -> dict[str, dict]:
    """Return a dict mapping resource path to its policy record.

    Each record contains ``allowed_roles`` and ``sensitivity_level``.
    """
    path = data_dir / "metadata" / "access_policies.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["resource"]: {
            "allowed_roles": tuple(item["allowed_roles"]),
            "sensitivity_level": _parse_sensitivity(item.get("sensitivity_level", "internal")),
        }
        for item in payload["resources"]
    }


def _parse_sensitivity(value: str) -> SensitivityLevel:
    try:
        return SensitivityLevel(value)
    except ValueError:
        return SensitivityLevel.INTERNAL


def _load_internal_documents(data_dir: Path, policies: dict[str, dict]) -> Iterable[Document]:
    for path in sorted((data_dir / "documents").glob("*.txt")):
        resource = f"documents/{path.name}"
        if resource not in policies:
            continue
        text = path.read_text(encoding="utf-8")
        policy = policies.get(resource, {})
        yield Document(
            doc_id=path.stem,
            title=_title_from_stem(path.stem),
            source_type=SourceType.DOCUMENT,
            text=text,
            path=resource,
            allowed_roles=policy.get("allowed_roles", ()),
            sensitivity_level=policy.get("sensitivity_level", SensitivityLevel.INTERNAL),
            tags=tuple(path.stem.split("_")),
        )


def _load_csv_records(data_dir: Path, policies: dict[str, dict]) -> Iterable[Document]:
    for path in sorted((data_dir / "structured").glob("*.csv")):
        resource = f"structured/{path.name}"
        if resource not in policies:
            continue
        policy = policies.get(resource, {})
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for index, row in enumerate(reader, start=1):
                title = f"{_title_from_stem(path.stem)} row {index}"
                text = "; ".join(f"{key}: {value}" for key, value in row.items())
                yield Document(
                    doc_id=f"{path.stem}-{index}",
                    title=title,
                    source_type=SourceType.CSV,
                    text=text,
                    path=f"{resource}#row={index}",
                    allowed_roles=policy.get("allowed_roles", ()),
                    sensitivity_level=policy.get("sensitivity_level", SensitivityLevel.INTERNAL),
                    tags=tuple(path.stem.split("_")),
                    metadata=row,
                )


def _load_json_logs(data_dir: Path, policies: dict[str, dict]) -> Iterable[Document]:
    for path in sorted((data_dir / "logs").glob("*.jsonl")):
        resource = f"logs/{path.name}"
        if resource not in policies:
            continue
        policy = policies.get(resource, {})
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                event = json.loads(line)
                text = "; ".join(f"{key}: {value}" for key, value in event.items())
                yield Document(
                    doc_id=f"{path.stem}-{index}",
                    title=f"{event.get('event_type', path.stem)} event {index}",
                    source_type=SourceType.JSON_LOG,
                    text=text,
                    path=f"{resource}#line={index}",
                    allowed_roles=policy.get("allowed_roles", ()),
                    sensitivity_level=policy.get("sensitivity_level", SensitivityLevel.INTERNAL),
                    tags=tuple(str(event.get("severity", "")).lower().split()),
                    metadata=event,
                )


def _load_policy_documents(data_dir: Path, policies: dict[str, dict]) -> Iterable[Document]:
    for path in sorted((data_dir / "metadata").glob("*policies.json")):
        resource = f"metadata/{path.name}"
        text = path.read_text(encoding="utf-8")
        policy = policies.get(resource, {})
        yield Document(
            doc_id=path.stem,
            title=_title_from_stem(path.stem),
            source_type=SourceType.POLICY,
            text=text,
            path=resource,
            allowed_roles=policy.get("allowed_roles", ("Executive", "Security Analyst")),
            sensitivity_level=policy.get("sensitivity_level", SensitivityLevel.RESTRICTED),
            tags=("policy", "metadata"),
        )


def _title_from_stem(stem: str) -> str:
    return stem.replace("_", " ").title()
