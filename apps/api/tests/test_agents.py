from pathlib import Path

from fastapi.testclient import TestClient

from uninode.agents import create_cursor_task
from uninode.main import create_app


def write_agent_fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "secrets.env").write_text("TOKEN=super-secret-token\n", encoding="utf-8")
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {source_root / "network-audit-2026Q2"}
security:
  secrets_policy_path: {tmp_path / "secrets.policy.yaml"}
  redact_secrets: true
agent_automation:
  cursor:
    enabled: true
    default_mode: readonly
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "secrets.policy.yaml").write_text(
        """
scan:
  include_extensions: [.env]
patterns:
  - id: token
    label: Token
    regex: '(?i)token\\s*=\\s*[^\\s]+'
""".strip(),
        encoding="utf-8",
    )
    devices_path = tmp_path / "devices.yaml"
    devices_path.write_text(
        """
devices:
  - id: minipc_gateway
    name: backup-gateway miniPC
    type: edge_node
    role: transparent_gateway
    expected_online: false
    human_action: power_on_if_check_required
    tags: [gateway]
""".strip(),
        encoding="utf-8",
    )
    automations_path = tmp_path / "automations.yaml"
    automations_path.write_text(
        """
jobs:
  - id: check_global_access
    title: Check global access
    category: readonly_check
    mode: dry_run
    target_devices: [minipc_gateway]
    precheck:
      - Confirm readonly mode.
    steps:
      - Inspect evidence paths and summarize findings.
    gates: [secret_scan_pass, device_offline_policy]
    evidence_required: [bench_json]
""".strip(),
        encoding="utf-8",
    )
    return config_path, devices_path, automations_path


def test_create_cursor_task_redacts_secrets_and_requires_readonly_output(tmp_path: Path) -> None:
    config_path, devices_path, automations_path = write_agent_fixtures(tmp_path)

    task = create_cursor_task(
        "check_global_access",
        config_path,
        devices_path,
        automations_path,
    )
    dumped = task.model_dump_json()

    assert task.provider == "cursor"
    assert task.mode == "readonly"
    assert "super-secret-token" not in dumped
    assert "TOKEN=" not in dumped
    assert "[REDACTED]" in dumped
    assert "data/evidence" in task.allowed_paths
    assert "network_write" in task.denied_actions
    assert {"findings", "evidence_paths", "recommended_actions", "needs_human_power_on"} <= set(
        task.expected_output_schema.keys()
    )
    assert "power_on_if_check_required" in task.human_actions
    assert "readonly or dry-run" in task.prompt


def test_cursor_agent_task_api_returns_redacted_package(tmp_path: Path) -> None:
    config_path, devices_path, automations_path = write_agent_fixtures(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
            devices_config_path=devices_path,
            automations_config_path=automations_path,
        )
    )

    response = client.post("/api/agents/cursor/tasks", json={"job_id": "check_global_access"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "cursor"
    assert payload["mode"] == "readonly"
    assert "super-secret-token" not in str(payload)
    assert payload["redaction"]["applied"] is True
