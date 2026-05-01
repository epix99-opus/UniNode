from fastapi import APIRouter
from pydantic import BaseModel


class HealthSummary(BaseModel):
    status: str
    next_action: str


class CountSummary(BaseModel):
    devices: int
    services: int
    evidence: int
    automation_jobs: int


class SafetySummary(BaseModel):
    execution_mode: str
    network_changes_require_approval: bool
    offline_policy: str


class ConsoleSummary(BaseModel):
    health: HealthSummary
    counts: CountSummary
    safety: SafetySummary


router = APIRouter(prefix="/api/console", tags=["console"])


@router.get("/summary", response_model=ConsoleSummary)
def summary() -> ConsoleSummary:
    return ConsoleSummary(
        health=HealthSummary(
            status="evidence_gap",
            next_action="Import facts and scan evidence before claiming readiness.",
        ),
        counts=CountSummary(
            devices=0,
            services=0,
            evidence=0,
            automation_jobs=0,
        ),
        safety=SafetySummary(
            execution_mode="dry_run",
            network_changes_require_approval=True,
            offline_policy="needs_human_power_on",
        ),
    )
