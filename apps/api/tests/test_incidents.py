from fastapi.testclient import TestClient

from uninode.incidents import classify_incident
from uninode.main import create_app


def test_classify_global_access_slow_by_evidence_gap() -> None:
    incident = classify_incident(
        title="Global access is slow",
        signal="global_access_slow",
        evidence_statuses=["template_only", "blocked"],
    )

    assert incident.classification == "insufficient_evidence"
    assert incident.severity == "medium"
    assert "check_global_access" in incident.recommended_automations
    assert incident.rollback_readiness == "not_applicable"


def test_classify_offline_device_as_human_power_on() -> None:
    incident = classify_incident(
        title="miniPC offline",
        signal="device_offline",
        affected_device="minipc_gateway",
    )

    assert incident.classification == "needs_human_power_on"
    assert incident.severity == "low"
    assert "power_on_if_check_required" in incident.human_actions


def test_classify_agent_privilege_escalation_as_blocked() -> None:
    incident = classify_incident(
        title="Agent requested router write",
        signal="agent_privilege_escalation",
    )

    assert incident.classification == "agent_policy_blocked"
    assert incident.severity == "critical"
    assert incident.blocked is True


def test_incident_api_creates_and_closes_incident() -> None:
    client = TestClient(create_app())

    create_response = client.post(
        "/api/incidents",
        json={"title": "miniPC offline", "signal": "device_offline", "affected_device": "minipc_gateway"},
    )
    close_response = client.post(f"/api/incidents/{create_response.json()['id']}/close")

    assert create_response.status_code == 200
    assert create_response.json()["classification"] == "needs_human_power_on"
    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"
