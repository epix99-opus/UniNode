from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


class Evidence(BaseModel):
    id: str
    type: str
    source_path: str
    summary: str
    validity: str
    blockers: list[str] = Field(default_factory=list)
    redaction_applied: bool = True


class EvidenceSummary(BaseModel):
    total: int
    blocked_count: int
    by_validity: dict[str, int]
    by_type: dict[str, int]


def _load_app_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}


def _audit_root(config_path: Path) -> Path | None:
    parsed = _load_app_config(config_path)
    raw_audit_root = parsed.get("audit_root")
    if not raw_audit_root:
        return None
    audit_root = Path(str(raw_audit_root)).expanduser()
    if audit_root.is_absolute():
        return audit_root
    return (config_path.parent.parent / audit_root).resolve()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _contains_na(value: Any) -> bool:
    if isinstance(value, str):
        return value.upper() == "NA"
    if isinstance(value, dict):
        return any(_contains_na(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_na(item) for item in value)
    return False


def _scan_bench_json(path: Path, root: Path) -> Evidence:
    source_path = _relative(path, root)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return Evidence(
            id=source_path,
            type="bench_json",
            source_path=source_path,
            summary="Bench JSON is not parseable.",
            validity="invalid_json",
            blockers=["invalid_json"],
        )

    if _contains_na(parsed):
        return Evidence(
            id=source_path,
            type="bench_json",
            source_path=source_path,
            summary="Bench JSON contains NA fields.",
            validity="invalid",
            blockers=["na_fields_present"],
        )

    return Evidence(
        id=source_path,
        type="bench_json",
        source_path=source_path,
        summary="Bench JSON parsed without NA fields.",
        validity="valid",
    )


def _scan_mobile_compare(path: Path, root: Path) -> Evidence:
    source_path = _relative(path, root)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return Evidence(
            id=source_path,
            type="mobile_compare_json",
            source_path=source_path,
            summary="Mobile compare JSON is not parseable.",
            validity="invalid_json",
            blockers=["invalid_json"],
        )

    bottleneck_hint = parsed.get("bottleneck_hint")
    hint_value = bottleneck_hint.get("value") if isinstance(bottleneck_hint, dict) else None
    if hint_value == "insufficient_data":
        return Evidence(
            id=source_path,
            type="mobile_compare_json",
            source_path=source_path,
            summary="Mobile compare has insufficient_data.",
            validity="blocked",
            blockers=["mobile_insufficient_data"],
        )

    return Evidence(
        id=source_path,
        type="mobile_compare_json",
        source_path=source_path,
        summary="Mobile compare parsed.",
        validity="valid",
    )


def _scan_subscription_hit(path: Path, root: Path) -> Evidence:
    source_path = _relative(path, root)
    if path.name.endswith(".template"):
        return Evidence(
            id=source_path,
            type="subscription_hit",
            source_path=source_path,
            summary="Subscription hit file is a template only.",
            validity="template_only",
            blockers=["template_only"],
        )

    return Evidence(
        id=source_path,
        type="subscription_hit",
        source_path=source_path,
        summary="Subscription hit file exists.",
        validity="valid",
    )


def _scan_fingerprint(path: Path, root: Path) -> Evidence:
    source_path = _relative(path, root)
    digest = path.read_text(encoding="utf-8").strip().split()[0] if path.exists() else ""
    if digest == EMPTY_SHA256 or digest == "":
        return Evidence(
            id=source_path,
            type="fingerprint",
            source_path=source_path,
            summary="Fingerprint is empty-content SHA-256 or blank.",
            validity="suspicious",
            blockers=["empty_fingerprint"],
        )

    return Evidence(
        id=source_path,
        type="fingerprint",
        source_path=source_path,
        summary="Fingerprint is non-empty.",
        validity="valid",
    )


def scan_evidence(config_path: Path) -> list[Evidence]:
    root = _audit_root(config_path)
    if root is None or not root.exists():
        return []

    evidence: list[Evidence] = []
    evidence.extend(_scan_bench_json(path, root) for path in sorted((root / "bench").glob("**/*.json")))
    evidence.extend(
        _scan_mobile_compare(path, root)
        for path in sorted((root / "mobile-compare").glob("**/*.json"))
    )
    evidence.extend(
        _scan_subscription_hit(path, root)
        for path in sorted((root / "subscription-hits").glob("**/*"))
        if path.is_file()
    )
    evidence.extend(
        _scan_fingerprint(path, root)
        for path in sorted((root / "fingerprints").glob("**/*.sha256"))
    )
    return evidence


def summarize_evidence(evidence: list[Evidence]) -> EvidenceSummary:
    by_validity = Counter(item.validity for item in evidence)
    by_type = Counter(item.type for item in evidence)
    blocked_count = sum(1 for item in evidence if item.validity != "valid")
    return EvidenceSummary(
        total=len(evidence),
        blocked_count=blocked_count,
        by_validity=dict(by_validity),
        by_type=dict(by_type),
    )


def create_evidence_router(config_path: Path) -> APIRouter:
    router = APIRouter(prefix="/api/evidence", tags=["evidence"])

    @router.get("", response_model=list[Evidence])
    def list_evidence() -> list[Evidence]:
        return scan_evidence(config_path)

    @router.get("/summary", response_model=EvidenceSummary)
    def evidence_summary() -> EvidenceSummary:
        return summarize_evidence(scan_evidence(config_path))

    return router
