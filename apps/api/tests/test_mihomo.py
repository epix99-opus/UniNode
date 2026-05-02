import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.mihomo import load_mihomo_status


def write_mihomo_config(tmp_path: Path, include_hits: bool = False) -> Path:
    snapshot_path = tmp_path / "controller.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "version": "mihomo 1.19.0",
                "proxy_groups": [
                    {"name": "GLOBAL", "now": "Contabo VLESS", "type": "Selector"},
                    {"name": "Auto", "now": "Contabo HY2", "type": "URLTest"},
                ],
                "subscription": {"name": "contabo", "updated_at": "2026-04-22T00:00:00Z"},
            }
        ),
        encoding="utf-8",
    )
    hits_path = tmp_path / "hits.csv"
    if include_hits:
        hits_path.write_text("rule,hit_count\nProxy,12\n", encoding="utf-8")
    config_path = tmp_path / "mihomo.yaml"
    config_path.write_text(
        f"""
controller_snapshot_path: {snapshot_path}
hits_csv_path: {hits_path}
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_mihomo_status_reads_proxy_groups_and_subscription_summary(tmp_path: Path) -> None:
    config_path = write_mihomo_config(tmp_path, include_hits=True)

    status = load_mihomo_status(config_path)

    assert status.controller_status == "snapshot_loaded"
    assert status.version == "mihomo 1.19.0"
    assert status.proxy_groups[0].name == "GLOBAL"
    assert status.subscription_summary["name"] == "contabo"
    assert status.rule_hits_status == "present"
    assert status.collection_task_required is False


def test_mihomo_status_reports_controller_gap_and_missing_hits(tmp_path: Path) -> None:
    config_path = tmp_path / "mihomo.yaml"
    config_path.write_text(
        f"""
controller_snapshot_path: {tmp_path / "missing-controller.json"}
hits_csv_path: {tmp_path / "missing-hits.csv"}
""".strip(),
        encoding="utf-8",
    )

    status = load_mihomo_status(config_path)

    assert status.controller_status == "unreachable_or_missing_snapshot"
    assert "device may be powered off" in status.next_action
    assert status.rule_hits_status == "missing"
    assert status.collection_task_required is True


def test_mihomo_api_returns_readonly_status(tmp_path: Path) -> None:
    config_path = write_mihomo_config(tmp_path, include_hits=False)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            mihomo_config_path=config_path,
        )
    )

    response = client.get("/api/mihomo/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["readonly"] is True
    assert payload["rule_hits_status"] == "missing"
    assert payload["collection_task_required"] is True
