import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.scheduler import evaluate_schedule_tick, load_scheduler


def write_scheduler_config(tmp_path: Path) -> Path:
    state_path = tmp_path / "scheduler-state.json"
    state_path.write_text(
        json.dumps(
            {
                "daily_device_check": {"consecutive_failures": 1, "last_status": "warning"},
                "weekly_report": {"consecutive_failures": 3, "last_status": "failed"},
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "scheduler.yaml"
    config_path.write_text(
        f"""
state_path: {state_path}
notification_hook: local_report_only
schedules:
  - id: daily_device_check
    label: Daily device check
    frequency: daily
    job_id: check_global_access
    observation_window_hours: 24
  - id: weekly_report
    label: Weekly report
    frequency: weekly
    report_type: current_ops_report
    observation_window_hours: 168
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_scheduler_loads_periodic_tasks_without_live_notifications(tmp_path: Path) -> None:
    config_path = write_scheduler_config(tmp_path)

    scheduler = load_scheduler(config_path)

    assert scheduler.notification_hook == "local_report_only"
    assert scheduler.schedules[0].frequency == "daily"
    assert scheduler.schedules[0].observation_window_hours == 24


def test_schedule_tick_dry_prevents_alert_storm_until_repeated_failures(tmp_path: Path) -> None:
    config_path = write_scheduler_config(tmp_path)

    first = evaluate_schedule_tick("daily_device_check", "warning", config_path)
    escalated = evaluate_schedule_tick("weekly_report", "failed", config_path)

    assert first.executed is False
    assert first.severity == "observe"
    assert first.notification_required is False
    assert escalated.severity == "major"
    assert escalated.notification_required is True


def test_scheduler_api_lists_and_dry_runs_tick(tmp_path: Path) -> None:
    config_path = write_scheduler_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            scheduler_config_path=config_path,
        )
    )

    schedules = client.get("/api/scheduler")
    tick = client.post("/api/scheduler/weekly_report/tick-dry", json={"status": "failed"})

    assert schedules.status_code == 200
    assert len(schedules.json()["schedules"]) == 2
    assert tick.status_code == 200
    assert tick.json()["notification_required"] is True
