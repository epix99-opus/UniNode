from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_MIHOMO_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "mihomo.yaml"


class ProxyGroupStatus(BaseModel):
    name: str
    now: str
    type: str


class MihomoStatus(BaseModel):
    readonly: bool = True
    controller_status: str
    version: str | None = None
    proxy_groups: list[ProxyGroupStatus] = Field(default_factory=list)
    subscription_summary: dict[str, str] = Field(default_factory=dict)
    rule_hits_status: str
    collection_task_required: bool
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


def load_mihomo_status(
    mihomo_config_path: Path = DEFAULT_MIHOMO_CONFIG_PATH,
) -> MihomoStatus:
    config = _load_yaml(mihomo_config_path)
    snapshot_path = _resolve_path(config.get("controller_snapshot_path"), mihomo_config_path)
    hits_path = _resolve_path(config.get("hits_csv_path"), mihomo_config_path)
    hits_present = bool(hits_path and hits_path.exists() and hits_path.name != "hits.csv.template")

    if not snapshot_path or not snapshot_path.exists():
        return MihomoStatus(
            controller_status="unreachable_or_missing_snapshot",
            rule_hits_status="present" if hits_present else "missing",
            collection_task_required=not hits_present,
            next_action="Controller snapshot missing; device may be powered off or mihomo service not started.",
        )

    try:
        raw_status = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return MihomoStatus(
            controller_status="invalid_snapshot",
            rule_hits_status="present" if hits_present else "missing",
            collection_task_required=not hits_present,
            next_action="Regenerate readonly mihomo controller snapshot.",
        )

    proxy_groups = [
        ProxyGroupStatus(
            name=str(item.get("name", "unknown")),
            now=str(item.get("now", "")),
            type=str(item.get("type", "unknown")),
        )
        for item in raw_status.get("proxy_groups", [])
        if isinstance(item, dict)
    ]
    subscription = raw_status.get("subscription") if isinstance(raw_status.get("subscription"), dict) else {}
    return MihomoStatus(
        controller_status="snapshot_loaded",
        version=str(raw_status.get("version")) if raw_status.get("version") else None,
        proxy_groups=proxy_groups,
        subscription_summary={str(key): str(value) for key, value in subscription.items()},
        rule_hits_status="present" if hits_present else "missing",
        collection_task_required=not hits_present,
        next_action="Collect subscription rule hits." if not hits_present else "No action required.",
    )


def create_mihomo_router(
    mihomo_config_path: Path = DEFAULT_MIHOMO_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/mihomo", tags=["mihomo"])

    @router.get("/status", response_model=MihomoStatus)
    def status() -> MihomoStatus:
        return load_mihomo_status(mihomo_config_path)

    return router
