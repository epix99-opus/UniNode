from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DEFAULT_SCHEDULER_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "scheduler.yaml"


class Schedule(BaseModel):
    id: str
    label: str
    frequency: str
    job_id: str | None = None
    report_type: str | None = None
    observation_window_hours: int


class SchedulerState(BaseModel):
    consecutive_failures: int = 0
    last_status: str = "unknown"


class SchedulerConfig(BaseModel):
    schedules: list[Schedule]
    notification_hook: str


class ScheduleTickRequest(BaseModel):
    status: str = "ok"


class ScheduleTickResult(BaseModel):
    schedule_id: str
    status: str
    executed: bool = False
    consecutive_failures: int
    severity: str
    notification_required: bool
    next_action: str


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_path(raw_path: str | None, config_path: Path) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def _state_for(schedule_id: str, config: dict[str, Any], config_path: Path) -> SchedulerState:
    state_path = _resolve_path(config.get("state_path"), config_path)
    if not state_path or not state_path.exists():
        return SchedulerState()
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return SchedulerState()
    raw_state = parsed.get(schedule_id, {})
    return SchedulerState(
        consecutive_failures=int(raw_state.get("consecutive_failures", 0)),
        last_status=str(raw_state.get("last_status", "unknown")),
    )


def load_scheduler(config_path: Path = DEFAULT_SCHEDULER_CONFIG_PATH) -> SchedulerConfig:
    config = _load_yaml(config_path)
    return SchedulerConfig(
        schedules=[
            Schedule(
                id=str(item.get("id")),
                label=str(item.get("label")),
                frequency=str(item.get("frequency")),
                job_id=item.get("job_id"),
                report_type=item.get("report_type"),
                observation_window_hours=int(item.get("observation_window_hours", 24)),
            )
            for item in config.get("schedules", [])
        ],
        notification_hook=str(config.get("notification_hook", "local_report_only")),
    )


def _find_schedule(schedule_id: str, config_path: Path) -> Schedule:
    for schedule in load_scheduler(config_path).schedules:
        if schedule.id == schedule_id:
            return schedule
    raise KeyError(schedule_id)


def evaluate_schedule_tick(
    schedule_id: str,
    status: str,
    config_path: Path = DEFAULT_SCHEDULER_CONFIG_PATH,
) -> ScheduleTickResult:
    config = _load_yaml(config_path)
    schedule = _find_schedule(schedule_id, config_path)
    state = _state_for(schedule_id, config, config_path)
    failed = status in {"warning", "failed"}
    consecutive_failures = state.consecutive_failures + 1 if failed else 0

    if not failed:
        severity = "ok"
        notification_required = False
        next_action = "record_success"
    elif consecutive_failures < 3:
        severity = "observe"
        notification_required = False
        next_action = f"observe_for_{schedule.observation_window_hours}h"
    else:
        severity = "major"
        notification_required = True
        next_action = "create_incident_or_report"

    return ScheduleTickResult(
        schedule_id=schedule_id,
        status=status,
        consecutive_failures=consecutive_failures,
        severity=severity,
        notification_required=notification_required,
        next_action=next_action,
    )


def create_scheduler_router(config_path: Path = DEFAULT_SCHEDULER_CONFIG_PATH) -> APIRouter:
    router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

    @router.get("", response_model=SchedulerConfig)
    def get_scheduler() -> SchedulerConfig:
        return load_scheduler(config_path)

    @router.post("/{schedule_id}/tick-dry", response_model=ScheduleTickResult)
    def tick(schedule_id: str, request: ScheduleTickRequest) -> ScheduleTickResult:
        try:
            return evaluate_schedule_tick(schedule_id, request.status, config_path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="schedule_not_found") from exc

    return router
