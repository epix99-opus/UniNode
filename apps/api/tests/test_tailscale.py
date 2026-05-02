import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.tailscale import load_tailscale_status


def write_tailscale_config(tmp_path: Path) -> Path:
    status_path = tmp_path / "tailscale-status.json"
    status_path.write_text(
        json.dumps(
            {
                "Self": {
                    "HostName": "mac-terminal",
                    "Online": True,
                    "TailscaleIPs": ["100.64.0.10"],
                    "KeyExpiry": "2099-01-01T00:00:00Z",
                },
                "Peer": {
                    "node-a": {
                        "HostName": "minipc-gateway",
                        "Online": False,
                        "TailscaleIPs": ["100.64.0.20"],
                        "ExitNodeOption": True,
                        "KeyExpiry": "2099-01-01T00:00:00Z",
                    },
                    "node-b": {
                        "HostName": "unexpected-router",
                        "Online": False,
                        "TailscaleIPs": ["100.64.0.30"],
                        "ExitNodeOption": False,
                        "KeyExpiry": "2020-01-01T00:00:00Z",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "tailscale.yaml"
    config_path.write_text(
        f"""
api_token_env: TAILSCALE_API_TOKEN
status_json_path: {status_path}
expected_offline_hosts:
  - minipc-gateway
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_tailscale_status_reports_missing_token_and_node_states(tmp_path: Path) -> None:
    config_path = write_tailscale_config(tmp_path)

    status = load_tailscale_status(config_path)
    nodes = {node.hostname: node for node in status.nodes}

    assert status.token_status == "missing"
    assert status.config_gap is True
    assert nodes["minipc-gateway"].state == "expected_offline"
    assert nodes["unexpected-router"].state == "unexpected_offline"
    assert nodes["minipc-gateway"].exit_node is True
    assert nodes["unexpected-router"].key_status == "expired"


def test_tailscale_api_returns_readonly_status(tmp_path: Path) -> None:
    config_path = write_tailscale_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            tailscale_config_path=config_path,
        )
    )

    response = client.get("/api/tailscale/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_status"] == "missing"
    assert payload["readonly"] is True
    assert any(node["exit_node"] for node in payload["nodes"])
