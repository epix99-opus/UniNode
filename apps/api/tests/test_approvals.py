import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.approvals import create_approval_request, evaluate_permission, load_audit_log
from uninode.main import create_app


def write_policy_config(tmp_path: Path) -> Path:
    audit_path = tmp_path / "approval-audit.jsonl"
    config_path = tmp_path / "approvals.yaml"
    config_path.write_text(
        f"""
audit_log_path: {audit_path}
key_store:
  provider: local_file_reference
  secret_material_allowed_in_api: false
roles:
  readonly_operator:
    allowed_actions: [read_status, generate_report]
  operator:
    allowed_actions: [read_status, generate_report, request_config_change]
  agent:
    allowed_actions: [read_status, generate_report]
approval_required_actions: [request_config_change, execute_config_change]
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_readonly_user_cannot_execute_config(tmp_path: Path) -> None:
    config_path = write_policy_config(tmp_path)

    result = evaluate_permission("readonly_operator", "execute_config_change", config_path)

    assert result.allowed is False
    assert result.reason == "action_not_allowed_for_role"


def test_agent_cannot_bypass_approval(tmp_path: Path) -> None:
    config_path = write_policy_config(tmp_path)

    result = evaluate_permission("agent", "request_config_change", config_path)
    request = create_approval_request("agent", "request_config_change", "router_write", config_path)

    assert result.allowed is False
    assert request.status == "blocked"
    assert request.requires_approval is True


def test_operator_request_is_pending_and_audited(tmp_path: Path) -> None:
    config_path = write_policy_config(tmp_path)

    request = create_approval_request("operator", "request_config_change", "mihomo_update", config_path)
    audit_log = load_audit_log(config_path)

    assert request.status == "pending_approval"
    assert request.requires_approval is True
    assert audit_log[0]["target"] == "mihomo_update"


def test_approvals_api_exposes_policy_and_requests(tmp_path: Path) -> None:
    config_path = write_policy_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            approvals_config_path=config_path,
        )
    )

    policy = client.get("/api/approvals/policy")
    request = client.post(
        "/api/approvals/requests",
        json={"role": "operator", "action": "request_config_change", "target": "mihomo_update"},
    )
    audit = client.get("/api/approvals/audit-log")

    assert policy.status_code == 200
    assert policy.json()["key_store"]["secret_material_allowed_in_api"] is False
    assert request.status_code == 200
    assert request.json()["status"] == "pending_approval"
    assert len(audit.json()) == 1
