from pathlib import Path

from fastapi.testclient import TestClient

from uninode.config_status import load_config_status
from uninode.main import create_app


def write_config(tmp_path: Path, source_root: Path, audit_root: Path) -> Path:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {audit_root}
storage:
  runtime_dir: {tmp_path / "data"}
  evidence_dir: {tmp_path / "data" / "evidence"}
  runs_dir: {tmp_path / "data" / "runs"}
  reports_dir: {tmp_path / "data" / "reports"}
execution:
  default_mode: dry_run
  require_approval_for_network_changes: true
offline_policy:
  default_offline_state: needs_human_power_on
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_load_config_status_reports_existing_paths(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    audit_root = source_root / "network-audit-2026Q2"
    audit_root.mkdir(parents=True)
    (tmp_path / "data" / "evidence").mkdir(parents=True)
    (tmp_path / "data" / "runs").mkdir(parents=True)
    (tmp_path / "data" / "reports").mkdir(parents=True)
    config_path = write_config(tmp_path, source_root, audit_root)

    status = load_config_status(config_path)

    assert status.ok is True
    assert status.errors == []
    assert {path.id: path.status for path in status.paths} == {
        "workspace": "present",
        "source_root": "present",
        "audit_root": "present",
        "runtime_dir": "present",
        "evidence_dir": "present",
        "runs_dir": "present",
        "reports_dir": "present",
    }
    assert status.execution.default_mode == "dry_run"
    assert status.offline_policy.default_offline_state == "needs_human_power_on"


def test_load_config_status_reports_missing_source_without_device_failure(tmp_path: Path) -> None:
    source_root = tmp_path / "missing-source"
    audit_root = source_root / "network-audit-2026Q2"
    config_path = write_config(tmp_path, source_root, audit_root)

    status = load_config_status(config_path)

    assert status.ok is False
    assert "SOURCE_MISSING" in status.errors
    assert "DEVICE_OFFLINE_EXPECTED" in status.warnings
    path_status = {path.id: path.status for path in status.paths}
    assert path_status["source_root"] == "missing"
    assert path_status["audit_root"] == "missing"


def test_config_status_api_returns_model(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    audit_root = source_root / "network-audit-2026Q2"
    audit_root.mkdir(parents=True)
    config_path = write_config(tmp_path, source_root, audit_root)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
        )
    )

    response = client.get("/api/config/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_path"] == str(config_path)
    assert payload["ok"] is False
    assert payload["execution"]["default_mode"] == "dry_run"
