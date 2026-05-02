from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from uninode.config_status import DEFAULT_CONFIG_PATH
from uninode.devices import DEFAULT_DEVICES_CONFIG_PATH
from uninode.jobs import DEFAULT_AUTOMATIONS_CONFIG_PATH, run_job_dry
from uninode.security import redact_text, scan_security_findings


class CursorTaskRequest(BaseModel):
    job_id: str


class RedactionStatus(BaseModel):
    applied: bool = True
    policy: str = "secret_values_allowed_in_reports=false"


class AgentTask(BaseModel):
    provider: Literal["cursor"] = "cursor"
    job_id: str
    title: str
    mode: Literal["readonly", "dry_run"] = "readonly"
    prompt: str
    allowed_paths: list[str] = Field(default_factory=list)
    denied_actions: list[str] = Field(default_factory=list)
    expected_output_schema: dict[str, str]
    evidence_required: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    human_actions: list[str] = Field(default_factory=list)
    redaction: RedactionStatus = Field(default_factory=RedactionStatus)


def _default_allowed_paths(config_path: Path) -> list[str]:
    return [
        str((config_path.parent.parent / "configs").resolve()),
        "data/evidence",
        "data/reports",
    ]


def _expected_output_schema() -> dict[str, str]:
    return {
        "findings": "List of observations with severity and rationale.",
        "evidence_paths": "Local evidence paths used or required.",
        "recommended_actions": "Readonly or dry-run next steps only.",
        "needs_human_power_on": "Boolean or list of devices requiring manual power-on.",
    }


def _prompt(job_id: str, steps: list[str], human_actions: list[str], findings: list[str]) -> str:
    raw_prompt = f"""
You are Cursor running a UniNode diagnostic task.

Task: {job_id}
Mode: readonly or dry-run only.

Constraints:
- Do not modify routers, VPS, firewall, DNS, subscriptions, NAS services, or production config.
- Do not output secrets, tokens, private keys, auth keys, UUIDs, or subscription URLs.
- Return findings, evidence_paths, recommended_actions, and needs_human_power_on.

Dry-run steps:
{chr(10).join(f"- {step}" for step in steps)}

Human actions:
{chr(10).join(f"- {action}" for action in human_actions) if human_actions else "- none"}

Redacted security context:
{chr(10).join(f"- {finding}" for finding in findings) if findings else "- no findings"}
""".strip()
    return redact_text(raw_prompt)


def create_cursor_task(
    job_id: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    automations_config_path: Path = DEFAULT_AUTOMATIONS_CONFIG_PATH,
) -> AgentTask:
    dry_run = run_job_dry(job_id, config_path, devices_config_path, automations_config_path)
    security_findings = scan_security_findings(config_path)
    finding_lines = [
        f"{finding.label} at {finding.source_path}:{finding.line}: [REDACTED]"
        for finding in security_findings[:10]
    ]
    steps = [step.description for step in dry_run.steps]
    return AgentTask(
        job_id=job_id,
        title=f"Cursor diagnostic package for {job_id}",
        prompt=_prompt(job_id, steps, dry_run.human_actions, finding_lines),
        allowed_paths=_default_allowed_paths(config_path),
        denied_actions=[
            "network_write",
            "router_config_change",
            "vps_config_change",
            "firewall_change",
            "dns_change",
            "credential_dump",
            "secret_print",
        ],
        expected_output_schema=_expected_output_schema(),
        evidence_required=dry_run.evidence_required,
        evidence_paths=["data/evidence"],
        human_actions=dry_run.human_actions,
    )


def create_agents_router(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    automations_config_path: Path = DEFAULT_AUTOMATIONS_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/agents", tags=["agents"])

    @router.post("/cursor/tasks", response_model=AgentTask)
    def cursor_task(request: CursorTaskRequest) -> AgentTask:
        return create_cursor_task(
            request.job_id,
            config_path,
            devices_config_path,
            automations_config_path,
        )

    return router
