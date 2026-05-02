from __future__ import annotations

from itertools import count

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


class IncidentCreateRequest(BaseModel):
    title: str
    signal: str
    affected_device: str | None = None
    evidence_statuses: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    id: str
    title: str
    signal: str
    status: str = "open"
    severity: str
    classification: str
    recommended_automations: list[str] = Field(default_factory=list)
    rollback_readiness: str = "not_applicable"
    human_actions: list[str] = Field(default_factory=list)
    blocked: bool = False


_incident_counter = count(1)
_incident_store: dict[str, Incident] = {}


def classify_incident(
    title: str,
    signal: str,
    affected_device: str | None = None,
    evidence_statuses: list[str] | None = None,
) -> Incident:
    statuses = set(evidence_statuses or [])
    incident_id = f"inc-{next(_incident_counter):06d}"

    if signal == "agent_privilege_escalation":
        return Incident(
            id=incident_id,
            title=title,
            signal=signal,
            severity="critical",
            classification="agent_policy_blocked",
            recommended_automations=[],
            rollback_readiness="not_applicable",
            blocked=True,
        )

    if signal == "device_offline":
        return Incident(
            id=incident_id,
            title=title,
            signal=signal,
            severity="low",
            classification="needs_human_power_on",
            recommended_automations=["check_nas", "check_tailscale"],
            human_actions=["power_on_if_check_required"],
        )

    if signal == "global_access_slow" and statuses & {
        "template_only",
        "blocked",
        "invalid",
        "invalid_json",
        "suspicious",
        "missing",
    }:
        return Incident(
            id=incident_id,
            title=title,
            signal=signal,
            severity="medium",
            classification="insufficient_evidence",
            recommended_automations=["check_global_access", "scan_security"],
        )

    if signal == "global_access_slow":
        return Incident(
            id=incident_id,
            title=title,
            signal=signal,
            severity="medium",
            classification="global_access_slow_untriaged",
            recommended_automations=["check_global_access", "check_tailscale"],
        )

    return Incident(
        id=incident_id,
        title=title,
        signal=signal,
        severity="low",
        classification="unclassified",
        recommended_automations=[],
    )


def create_incidents_router() -> APIRouter:
    router = APIRouter(prefix="/api/incidents", tags=["incidents"])

    @router.post("", response_model=Incident)
    def create_incident(request: IncidentCreateRequest) -> Incident:
        incident = classify_incident(
            title=request.title,
            signal=request.signal,
            affected_device=request.affected_device,
            evidence_statuses=request.evidence_statuses,
        )
        _incident_store[incident.id] = incident
        return incident

    @router.post("/{incident_id}/close", response_model=Incident)
    def close_incident(incident_id: str) -> Incident:
        incident = _incident_store.get(incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        closed = incident.model_copy(update={"status": "closed"})
        _incident_store[incident_id] = closed
        return closed

    return router
