from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

from uninode.config_status import DEFAULT_CONFIG_PATH
from uninode.dashboard import build_dashboard_summary
from uninode.devices import DEFAULT_DEVICES_CONFIG_PATH, load_devices
from uninode.evidence import scan_evidence
from uninode.security import redact_text, scan_security_findings
from uninode.services import DEFAULT_SERVICES_CONFIG_PATH


class ReportResponse(BaseModel):
    report_type: str
    path: str
    content: str
    redaction_applied: bool = True


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _reports_dir(config_path: Path) -> Path:
    parsed = _load_yaml(config_path)
    storage = parsed.get("storage") or {}
    raw_path = storage.get("reports_dir")
    if raw_path:
        path = Path(str(raw_path)).expanduser()
        if path.is_absolute():
            return path
        return (config_path.parent.parent / path).resolve()
    return config_path.parent.parent / "Docs"


def _render_report(
    report_type: str,
    config_path: Path,
    devices_config_path: Path,
    services_config_path: Path,
) -> str:
    dashboard = build_dashboard_summary(config_path, devices_config_path, services_config_path)
    evidence = scan_evidence(config_path)
    security_findings = scan_security_findings(config_path)
    devices = load_devices(config_path, devices_config_path)

    evidence_lines = "\n".join(
        f"- {item.source_path}: {item.validity} ({', '.join(item.blockers) or 'ok'})"
        for item in evidence
    ) or "- no evidence indexed"
    security_lines = "\n".join(
        f"- {finding.label} at {finding.source_path}:{finding.line}: [REDACTED]"
        for finding in security_findings
    ) or "- no security findings"
    offline_lines = "\n".join(
        f"- {device.id}: temporary_offline, action={device.human_action}"
        for device in devices
        if device.status == "needs_human_power_on"
    ) or "- none"
    content = f"""
# UniNode {report_type}

## Overall
- status: {dashboard.overall_status}
- redaction: applied

## Evidence Paths
{evidence_lines}

## Security
{security_lines}

## Classification
- temporary_offline: devices listed below require human power-on before live checks, not architecture failure.
- insufficient_evidence: evidence marked invalid_json, invalid, blocked, template_only, suspicious, or missing.
- real_failure: only assign after live evidence confirms a service/device failure.

## Temporary Offline Devices
{offline_lines}

## Human Actions
{chr(10).join(f"- {action}" for action in dashboard.human_actions) or "- none"}
""".strip()
    return redact_text(content)


def generate_report(
    report_type: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH,
) -> ReportResponse:
    content = _render_report(report_type, config_path, devices_config_path, services_config_path)
    reports_dir = _reports_dir(config_path)
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{report_type}.md"
    report_path.write_text(content, encoding="utf-8")
    return ReportResponse(
        report_type=report_type,
        path=str(report_path),
        content=content,
    )


def create_reports_router(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/reports", tags=["reports"])

    @router.post("/{report_type}", response_model=ReportResponse)
    def report(report_type: str) -> ReportResponse:
        return generate_report(report_type, config_path, devices_config_path, services_config_path)

    return router
