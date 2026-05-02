from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[3] / "configs" / "secrets.policy.yaml"


class SecretPattern(BaseModel):
    id: str
    label: str
    regex: str


class SecurityFinding(BaseModel):
    id: str
    type: str
    label: str
    severity: str = "blocker"
    source_path: str
    line: int
    redacted_excerpt: str
    redaction_applied: bool = True


class SecurityFindingsResponse(BaseModel):
    blocked: bool
    total: int
    findings: list[SecurityFinding] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_path(raw_path: str | None, config_path: Path) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def _source_root(config_path: Path) -> Path | None:
    parsed = _load_yaml(config_path)
    return _resolve_path(parsed.get("source_root"), config_path)


def _policy_path(config_path: Path) -> Path:
    parsed = _load_yaml(config_path)
    security = parsed.get("security") or {}
    return _resolve_path(security.get("secrets_policy_path"), config_path) or DEFAULT_POLICY_PATH


def _load_policy(config_path: Path) -> dict[str, Any]:
    return _load_yaml(_policy_path(config_path)) or _load_yaml(DEFAULT_POLICY_PATH)


def _compile_patterns(policy: dict[str, Any]) -> list[tuple[SecretPattern, re.Pattern[str]]]:
    patterns: list[tuple[SecretPattern, re.Pattern[str]]] = []
    for item in policy.get("patterns", []):
        pattern = SecretPattern(**item)
        patterns.append((pattern, re.compile(pattern.regex)))
    return patterns


def _scan_files(root: Path, policy: dict[str, Any]) -> list[Path]:
    scan = policy.get("scan") or {}
    include_extensions = set(scan.get("include_extensions") or [])
    ignore_dirs = set(scan.get("ignore_dirs") or [])
    files: list[Path] = []
    for path in root.rglob("*"):
        if any(part in ignore_dirs for part in path.parts):
            continue
        if not path.is_file():
            continue
        if include_extensions and path.suffix not in include_extensions:
            continue
        files.append(path)
    return files


def redact_text(text: str) -> str:
    redacted = re.sub(r"(?i)(password\s*[:=]\s*)[^\s'\",]+", r"\1[REDACTED]", text)
    redacted = re.sub(r"(?i)(token\s*[:=]\s*)[^\s'\",]+", r"\1[REDACTED]", redacted)
    redacted = re.sub(r"(?i)(auth[_-]?key\s*[:=]\s*)[^\s'\",]+", r"\1[REDACTED]", redacted)
    redacted = re.sub(
        r"https?://[^\s'\",]*(?:token|uuid|sub|subscribe)[^\s'\",]*",
        "[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        "[REDACTED]",
        redacted,
    )
    redacted = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "[REDACTED]", redacted)
    return redacted


def scan_security_findings(config_path: Path) -> list[SecurityFinding]:
    root = _source_root(config_path)
    if root is None or not root.exists():
        return []

    policy = _load_policy(config_path)
    patterns = _compile_patterns(policy)
    findings: list[SecurityFinding] = []
    for file_path in _scan_files(root, policy):
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        source_path = file_path.relative_to(root).as_posix()
        for line_number, line in enumerate(lines, start=1):
            for secret_pattern, compiled in patterns:
                if not compiled.search(line):
                    continue
                finding_id = f"{source_path}:{line_number}:{secret_pattern.id}"
                findings.append(
                    SecurityFinding(
                        id=finding_id,
                        type=secret_pattern.id,
                        label=secret_pattern.label,
                        source_path=source_path,
                        line=line_number,
                        redacted_excerpt=redact_text(line),
                    )
                )
    return findings


def create_security_router(config_path: Path) -> APIRouter:
    router = APIRouter(prefix="/api/security", tags=["security"])

    @router.get("/findings", response_model=SecurityFindingsResponse)
    def findings() -> SecurityFindingsResponse:
        items = scan_security_findings(config_path)
        return SecurityFindingsResponse(
            blocked=bool(items),
            total=len(items),
            findings=items,
        )

    return router
