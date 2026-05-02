from pathlib import Path

from fastapi.testclient import TestClient

from uninode.dashboard import build_dashboard_summary
from uninode.main import create_app


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def write_dashboard_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "source"
    audit_root = source_root / "network-audit-2026Q2"
    (audit_root / "subscription-hits").mkdir(parents=True)
    (audit_root / "fingerprints").mkdir(parents=True)
    (source_root / "secrets.env").write_text("PASSWORD=secret-value\n", encoding="utf-8")
    (audit_root / "subscription-hits" / "hits.csv.template").write_text("template\n", encoding="utf-8")
    (audit_root / "fingerprints" / "empty.sha256").write_text(EMPTY_SHA256, encoding="utf-8")

    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {audit_root}
security:
  secrets_policy_path: {tmp_path / "secrets.policy.yaml"}
  redact_secrets: true
  block_publish_on_secret_findings: true
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "secrets.policy.yaml").write_text(
        """
scan:
  include_extensions: [.env]
patterns:
  - id: password
    label: Password
    regex: '(?i)password\\s*=\\s*[^\\s]+'
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
    role: transparent_gateway_tailscale_exit
    expected_online: false
    human_action: power_on_if_check_required
    tags: [gateway, tailscale_exit_node]
  - id: contabo_vps
    name: Contabo VPS
    type: vps
    role: vpn_subscription_public_exit
    expected_online: true
    tags: [global_access]
""".strip(),
        encoding="utf-8",
    )

    services_path = tmp_path / "services.yaml"
    services_path.write_text(
        """
services:
  - id: minipc_tailscale_exit
    name: miniPC Tailscale Exit Node
    device_id: minipc_gateway
    type: tailscale
    endpoint: missing_tailscale_ip
    expected_status: missing_fact
    dependencies: []
    tags: [tailscale, exit_node, evidence_gap]
  - id: obsidian_sync_placeholder
    name: Obsidian sync service placeholder
    device_id: minipc_gateway
    type: obsidian_sync
    endpoint: sync_service_not_selected
    expected_status: missing_design_choice
    dependencies: []
    tags: [obsidian, evidence_gap]
  - id: openclaw_agent_placeholder
    name: OpenClaw Agent placeholder
    device_id: minipc_gateway
    type: agent_node
    endpoint: not_registered
    expected_status: placeholder
    dependencies: []
    tags: [agent, openclaw]
""".strip(),
        encoding="utf-8",
    )
    return config_path, devices_path, services_path


def test_dashboard_summary_preserves_human_action_and_blockers(tmp_path: Path) -> None:
    config_path, devices_path, services_path = write_dashboard_fixture(tmp_path)

    summary = build_dashboard_summary(config_path, devices_path, services_path)
    cards = {card.id: card for card in summary.cards}

    assert cards["devices"].status == "needs_human_power_on"
    assert "power_on_if_check_required" in summary.human_actions
    assert cards["evidence"].status == "evidence_gap"
    assert cards["security"].status == "security_blocked"
    assert cards["devices"].status != "architecture_failed"


def test_dashboard_api_returns_visual_home_summary(tmp_path: Path) -> None:
    config_path, devices_path, services_path = write_dashboard_fixture(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
            devices_config_path=devices_path,
            services_config_path=services_path,
        )
    )

    response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_status"] == "blocked"
    assert any(card["id"] == "tailscale" for card in payload["cards"])
    assert "power_on_if_check_required" in payload["human_actions"]
