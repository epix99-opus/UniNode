from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app


def test_console_summary_exposes_safe_empty_state(tmp_path: Path) -> None:
    client = TestClient(create_app(database_path=tmp_path / "uninode-test.db"))

    response = client.get("/api/console/summary")

    assert response.status_code == 200
    assert response.json() == {
        "health": {
            "status": "evidence_gap",
            "next_action": "Import facts and scan evidence before claiming readiness.",
        },
        "counts": {
            "devices": 0,
            "services": 0,
            "evidence": 0,
            "automation_jobs": 0,
        },
        "safety": {
            "execution_mode": "dry_run",
            "network_changes_require_approval": True,
            "offline_policy": "needs_human_power_on",
        },
    }
