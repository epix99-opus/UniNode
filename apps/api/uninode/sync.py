from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_SYNC_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "sync.yaml"


class SyncServiceStatus(BaseModel):
    id: str
    endpoint: str
    selected: bool
    reachable: bool
    status: str
    snapshot_path: str


class SyncStatus(BaseModel):
    readonly: bool = True
    selected: str
    overall_status: str
    services: list[SyncServiceStatus] = Field(default_factory=list)
    last_sync_at: str | None = None
    backup_marker_status: str
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


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def load_sync_status(sync_config_path: Path = DEFAULT_SYNC_CONFIG_PATH) -> SyncStatus:
    config = _load_yaml(sync_config_path)
    selected = str(config.get("selected") or "none")
    services_config = config.get("services") or {}
    backup_marker_path = _resolve_path(config.get("backup_marker_path"), sync_config_path)
    backup_marker = _load_json(backup_marker_path)
    backup_marker_status = "present" if backup_marker else "missing"
    last_sync_at = backup_marker.get("last_sync_at") if backup_marker else None

    services: list[SyncServiceStatus] = []
    for service_id, service_config in services_config.items():
        snapshot_path = _resolve_path(service_config.get("health_snapshot_path"), sync_config_path)
        snapshot = _load_json(snapshot_path)
        service_selected = selected == service_id
        reachable = bool(snapshot)
        if selected == "none":
            status = "not_selected"
        elif service_selected and reachable:
            status = "healthy"
        elif service_selected:
            status = "unreachable_or_missing_snapshot"
        else:
            status = "available_not_selected"
        services.append(
            SyncServiceStatus(
                id=str(service_id),
                endpoint=str(service_config.get("endpoint", "not_configured")),
                selected=service_selected,
                reachable=reachable,
                status=status,
                snapshot_path=str(snapshot_path) if snapshot_path else "",
            )
        )

    if selected == "none":
        overall_status = "sync_service_not_selected"
        next_action = "Choose WebDAV, Syncthing, or CouchDB/LiveSync before claiming sync readiness."
    elif any(service.selected and service.status == "healthy" for service in services) and backup_marker:
        overall_status = "healthy"
        next_action = "No action required."
    else:
        overall_status = "evidence_gap"
        next_action = "Collect selected sync service health and backup marker evidence."

    return SyncStatus(
        selected=selected,
        overall_status=overall_status,
        services=services,
        last_sync_at=str(last_sync_at) if last_sync_at else None,
        backup_marker_status=backup_marker_status,
        next_action=next_action,
    )


def create_sync_router(sync_config_path: Path = DEFAULT_SYNC_CONFIG_PATH) -> APIRouter:
    router = APIRouter(prefix="/api/sync", tags=["sync"])

    @router.get("/status", response_model=SyncStatus)
    def status() -> SyncStatus:
        return load_sync_status(sync_config_path)

    return router
