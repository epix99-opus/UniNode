from pathlib import Path

from fastapi.testclient import TestClient

from uninode.devices import load_devices
from uninode.main import create_app


def write_app_config(tmp_path: Path, source_root: Path) -> Path:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {source_root / "network-audit-2026Q2"}
storage:
  runtime_dir: {tmp_path / "data"}
execution:
  default_mode: dry_run
offline_policy:
  default_offline_state: needs_human_power_on
""".strip(),
        encoding="utf-8",
    )
    return config_path


def write_devices_config(tmp_path: Path) -> Path:
    devices_path = tmp_path / "devices.yaml"
    devices_path.write_text(
        """
devices:
  - id: minipc_gateway
    name: backup-gateway miniPC
    type: edge_node
    role: transparent_gateway_tailscale_exit_nas_candidate
    ip_lan_fact: MINIPC_LAN_IP
    ip_tailscale_fact: TAILSCALE_BACKUP_GW_IP
    expected_online: false
    human_action: power_on_if_check_required
  - id: contabo_vps
    name: Contabo VPS
    type: vps
    role: vpn_subscription_public_exit
    ip_public_fact: VPS_PUBLIC_IP
    expected_online: true
""".strip(),
        encoding="utf-8",
    )
    return devices_path


def write_network_facts(source_root: Path) -> None:
    audit_root = source_root / "network-audit-2026Q2"
    audit_root.mkdir(parents=True)
    (audit_root / "network_facts.env").write_text(
        """
MINIPC_LAN_IP=192.168.50.228
TAILSCALE_BACKUP_GW_IP="" # fill with tailscale ip of backup-gateway
VPS_PUBLIC_IP=203.0.113.8
""".strip(),
        encoding="utf-8",
    )


def test_load_devices_imports_network_facts_and_preserves_expected_offline(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    write_network_facts(source_root)
    app_config = write_app_config(tmp_path, source_root)
    devices_config = write_devices_config(tmp_path)

    devices = load_devices(app_config, devices_config)

    minipc = next(device for device in devices if device.id == "minipc_gateway")
    assert minipc.ip_lan == "192.168.50.228"
    assert minipc.ip_tailscale is None
    assert minipc.expected_online is False
    assert minipc.status == "needs_human_power_on"
    assert minipc.human_action == "power_on_if_check_required"
    assert "ip_tailscale" in minipc.missing_facts

    contabo = next(device for device in devices if device.id == "contabo_vps")
    assert contabo.ip_public == "203.0.113.8"
    assert contabo.status == "unknown"


def test_devices_api_lists_and_returns_individual_device(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    write_network_facts(source_root)
    app_config = write_app_config(tmp_path, source_root)
    devices_config = write_devices_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=app_config,
            devices_config_path=devices_config,
        )
    )

    list_response = client.get("/api/devices")
    assert list_response.status_code == 200
    assert [device["id"] for device in list_response.json()] == [
        "minipc_gateway",
        "contabo_vps",
    ]

    detail_response = client.get("/api/devices/minipc_gateway")
    assert detail_response.status_code == 200
    assert detail_response.json()["status"] == "needs_human_power_on"


def test_devices_api_404s_unknown_device(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    write_network_facts(source_root)
    app_config = write_app_config(tmp_path, source_root)
    devices_config = write_devices_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=app_config,
            devices_config_path=devices_config,
        )
    )

    response = client.get("/api/devices/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Device not found"
