from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_SERVICES_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "services.yaml"


class Service(BaseModel):
    id: str
    name: str
    device_id: str
    type: str
    endpoint: str
    expected_status: str
    dependencies: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_services(services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH) -> list[Service]:
    parsed = _load_yaml(services_config_path)
    return [
        Service(
            id=str(raw_service["id"]),
            name=str(raw_service["name"]),
            device_id=str(raw_service["device_id"]),
            type=str(raw_service["type"]),
            endpoint=str(raw_service["endpoint"]),
            expected_status=str(raw_service["expected_status"]),
            dependencies=list(raw_service.get("dependencies", [])),
            tags=list(raw_service.get("tags", [])),
        )
        for raw_service in parsed.get("services", [])
    ]


def create_services_router(
    services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/services", tags=["services"])

    @router.get("", response_model=list[Service])
    def list_services() -> list[Service]:
        return load_services(services_config_path)

    return router
