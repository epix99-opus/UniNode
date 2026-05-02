from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

DEFAULT_DEVICES_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "devices.yaml"


class Device(BaseModel):
    id: str
    name: str
    type: str
    role: str
    ip_lan: str | None = None
    ip_public: str | None = None
    ip_tailscale: str | None = None
    expected_online: bool = True
    power_state_assumption: str | None = None
    human_action: str | None = None
    status: str
    missing_facts: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _source_root_from_app_config(config_path: Path) -> Path | None:
    parsed = _load_yaml(config_path)
    raw_source_root = parsed.get("source_root")
    if not raw_source_root:
        return None
    source_root = Path(str(raw_source_root)).expanduser()
    if source_root.is_absolute():
        return source_root
    return (config_path.parent.parent / source_root).resolve()


def _load_network_facts(config_path: Path) -> dict[str, str]:
    source_root = _source_root_from_app_config(config_path)
    if source_root is None:
        return {}

    facts_path = source_root / "network-audit-2026Q2" / "network_facts.env"
    if not facts_path.exists():
        return {}

    facts: dict[str, str] = {}
    for line in facts_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        value_without_comment = value.split("#", 1)[0].strip()
        facts[key.strip()] = value_without_comment.strip('"').strip("'")
    return facts


def _fact_value(config: dict[str, Any], facts: dict[str, str], field: str) -> tuple[str | None, bool]:
    direct_value = config.get(field)
    fact_key = config.get(f"{field}_fact")
    value = direct_value if direct_value not in ("", None) else facts.get(str(fact_key), None)
    if value in ("", None):
        return None, bool(fact_key)
    return str(value), False


def _device_status(expected_online: bool) -> str:
    return "unknown" if expected_online else "needs_human_power_on"


def load_devices(
    config_path: Path,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
) -> list[Device]:
    facts = _load_network_facts(config_path)
    parsed = _load_yaml(devices_config_path)
    devices: list[Device] = []

    for raw_device in parsed.get("devices", []):
        missing_facts: list[str] = []
        ip_lan, missing_ip_lan = _fact_value(raw_device, facts, "ip_lan")
        ip_public, missing_ip_public = _fact_value(raw_device, facts, "ip_public")
        ip_tailscale, missing_ip_tailscale = _fact_value(raw_device, facts, "ip_tailscale")
        if missing_ip_lan:
            missing_facts.append("ip_lan")
        if missing_ip_public:
            missing_facts.append("ip_public")
        if missing_ip_tailscale:
            missing_facts.append("ip_tailscale")

        expected_online = bool(raw_device.get("expected_online", True))
        devices.append(
            Device(
                id=str(raw_device["id"]),
                name=str(raw_device["name"]),
                type=str(raw_device["type"]),
                role=str(raw_device["role"]),
                ip_lan=ip_lan,
                ip_public=ip_public,
                ip_tailscale=ip_tailscale,
                expected_online=expected_online,
                power_state_assumption=raw_device.get("power_state_assumption"),
                human_action=raw_device.get("human_action"),
                status=_device_status(expected_online),
                missing_facts=missing_facts,
                tags=list(raw_device.get("tags", [])),
            )
        )

    return devices


def create_devices_router(
    config_path: Path,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/devices", tags=["devices"])

    @router.get("", response_model=list[Device])
    def list_devices() -> list[Device]:
        return load_devices(config_path, devices_config_path)

    @router.get("/{device_id}", response_model=Device)
    def get_device(device_id: str) -> Device:
        for device in load_devices(config_path, devices_config_path):
            if device.id == device_id:
                return device
        raise HTTPException(status_code=404, detail="Device not found")

    return router
