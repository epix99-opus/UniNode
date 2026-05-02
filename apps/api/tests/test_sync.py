import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.sync import load_sync_status


def write_sync_config(tmp_path: Path, selected: str | None = None) -> Path:
    marker_path = tmp_path / "backup-marker.json"
    marker_path.write_text(
        json.dumps({"last_sync_at": "2026-04-22T12:00:00Z", "backup_marker": "obsidian-ok"}),
        encoding="utf-8",
    )
    config_path = tmp_path / "sync.yaml"
    selected_line = f"selected: {selected}" if selected else "selected: null"
    config_path.write_text(
        f"""
{selected_line}
services:
  webdav:
    endpoint: http://nas.local/webdav
    health_snapshot_path: {marker_path}
  syncthing:
    endpoint: http://nas.local:8384
    health_snapshot_path: {tmp_path / "missing-syncthing.json"}
  livesync:
    endpoint: http://nas.local:5984
    health_snapshot_path: {tmp_path / "missing-couchdb.json"}
backup_marker_path: {marker_path}
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_sync_status_reports_not_selected_without_failure(tmp_path: Path) -> None:
    config_path = write_sync_config(tmp_path)

    status = load_sync_status(config_path)

    assert status.selected == "none"
    assert status.overall_status == "sync_service_not_selected"
    assert status.services[0].status == "not_selected"


def test_sync_status_checks_selected_service_and_backup_marker(tmp_path: Path) -> None:
    config_path = write_sync_config(tmp_path, selected="webdav")

    status = load_sync_status(config_path)

    assert status.selected == "webdav"
    assert status.overall_status == "healthy"
    assert status.services[0].reachable is True
    assert status.last_sync_at == "2026-04-22T12:00:00Z"
    assert status.backup_marker_status == "present"


def test_sync_api_returns_readonly_status(tmp_path: Path) -> None:
    config_path = write_sync_config(tmp_path, selected="webdav")
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            sync_config_path=config_path,
        )
    )

    response = client.get("/api/sync/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["readonly"] is True
    assert payload["overall_status"] == "healthy"
    assert payload["backup_marker_status"] == "present"
