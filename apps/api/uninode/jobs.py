from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from uninode.config_status import DEFAULT_CONFIG_PATH
from uninode.devices import DEFAULT_DEVICES_CONFIG_PATH, load_devices

DEFAULT_AUTOMATIONS_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "automations.yaml"


class AutomationJob(BaseModel):
    id: str
    title: str
    category: str
    mode: str = "dry_run"
    target_devices: list[str] = Field(default_factory=list)
    precheck: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    gates: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)


class DryRunStep(BaseModel):
    order: int
    description: str
    command: str = "DRY_RUN_ONLY"


class DryRunResult(BaseModel):
    job_id: str
    status: str
    executed: bool = False
    precheck: list[str]
    steps: list[DryRunStep]
    gates: list[str]
    evidence_required: list[str]
    human_actions: list[str] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_jobs(automations_config_path: Path = DEFAULT_AUTOMATIONS_CONFIG_PATH) -> list[AutomationJob]:
    parsed = _load_yaml(automations_config_path)
    return [AutomationJob(**item) for item in parsed.get("jobs", [])]


def _find_job(job_id: str, automations_config_path: Path) -> AutomationJob:
    for job in load_jobs(automations_config_path):
        if job.id == job_id:
            return job
    raise HTTPException(status_code=404, detail="Job not found")


def run_job_dry(
    job_id: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    automations_config_path: Path = DEFAULT_AUTOMATIONS_CONFIG_PATH,
) -> DryRunResult:
    job = _find_job(job_id, automations_config_path)
    devices_by_id = {device.id: device for device in load_devices(config_path, devices_config_path)}
    human_actions = sorted(
        {
            devices_by_id[device_id].human_action
            for device_id in job.target_devices
            if device_id in devices_by_id
            and devices_by_id[device_id].human_action
            and devices_by_id[device_id].status == "needs_human_power_on"
        }
    )
    return DryRunResult(
        job_id=job.id,
        status="dry_run_ready",
        executed=False,
        precheck=job.precheck,
        steps=[
            DryRunStep(order=index, description=step)
            for index, step in enumerate(job.steps, start=1)
        ],
        gates=job.gates,
        evidence_required=job.evidence_required,
        human_actions=human_actions,
    )


def create_jobs_router(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    automations_config_path: Path = DEFAULT_AUTOMATIONS_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/jobs", tags=["jobs"])

    @router.get("", response_model=list[AutomationJob])
    def jobs() -> list[AutomationJob]:
        return load_jobs(automations_config_path)

    @router.post("/{job_id}/run-dry", response_model=DryRunResult)
    def run_dry(job_id: str) -> DryRunResult:
        return run_job_dry(job_id, config_path, devices_config_path, automations_config_path)

    return router
