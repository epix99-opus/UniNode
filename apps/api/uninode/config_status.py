from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "app.yaml"


class ConfigPathStatus(BaseModel):
    id: str
    path: str
    required: bool
    status: str
    next_action: str


class ExecutionStatus(BaseModel):
    default_mode: str
    require_approval_for_network_changes: bool


class OfflinePolicyStatus(BaseModel):
    default_offline_state: str
    treat_expected_offline_as_failure: bool


class ConfigStatus(BaseModel):
    ok: bool
    config_path: str
    errors: list[str]
    warnings: list[str]
    paths: list[ConfigPathStatus]
    execution: ExecutionStatus
    offline_policy: OfflinePolicyStatus


def _resolve_path(raw_path: str | None, config_path: Path) -> Path:
    if not raw_path:
        return Path("")
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def _path_status(path_id: str, path: Path, required: bool) -> ConfigPathStatus:
    exists = bool(str(path)) and path.exists()
    return ConfigPathStatus(
        id=path_id,
        path=str(path),
        required=required,
        status="present" if exists else "missing",
        next_action=(
            "No action required."
            if exists
            else "Create the path or update configs/app.yaml to the current location."
        ),
    )


def load_config_status(config_path: Path = DEFAULT_CONFIG_PATH) -> ConfigStatus:
    errors: list[str] = []
    warnings: list[str] = []
    if not config_path.exists():
        return ConfigStatus(
            ok=False,
            config_path=str(config_path),
            errors=["CONFIG_ERROR"],
            warnings=[],
            paths=[],
            execution=ExecutionStatus(
                default_mode="dry_run",
                require_approval_for_network_changes=True,
            ),
            offline_policy=OfflinePolicyStatus(
                default_offline_state="needs_human_power_on",
                treat_expected_offline_as_failure=False,
            ),
        )

    try:
        parsed = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return ConfigStatus(
            ok=False,
            config_path=str(config_path),
            errors=["CONFIG_ERROR"],
            warnings=[],
            paths=[],
            execution=ExecutionStatus(
                default_mode="dry_run",
                require_approval_for_network_changes=True,
            ),
            offline_policy=OfflinePolicyStatus(
                default_offline_state="needs_human_power_on",
                treat_expected_offline_as_failure=False,
            ),
        )

    storage = parsed.get("storage") or {}
    execution = parsed.get("execution") or {}
    offline_policy = parsed.get("offline_policy") or {}
    paths = [
        _path_status("workspace", _resolve_path(parsed.get("workspace"), config_path), True),
        _path_status("source_root", _resolve_path(parsed.get("source_root"), config_path), True),
        _path_status("audit_root", _resolve_path(parsed.get("audit_root"), config_path), True),
        _path_status("runtime_dir", _resolve_path(storage.get("runtime_dir"), config_path), False),
        _path_status("evidence_dir", _resolve_path(storage.get("evidence_dir"), config_path), False),
        _path_status("runs_dir", _resolve_path(storage.get("runs_dir"), config_path), False),
        _path_status("reports_dir", _resolve_path(storage.get("reports_dir"), config_path), False),
    ]

    missing_required = {path.id for path in paths if path.required and path.status == "missing"}
    missing_optional = {path.id for path in paths if not path.required and path.status == "missing"}
    if "source_root" in missing_required or "audit_root" in missing_required:
        errors.append("SOURCE_MISSING")
    if "workspace" in missing_required:
        errors.append("CONFIG_ERROR")

    # Missing paths are configuration/source gaps. They must not be reported as device failure.
    if missing_required:
        warnings.append("DEVICE_OFFLINE_EXPECTED")
    if missing_optional:
        warnings.append("PATH_MISSING")

    return ConfigStatus(
        ok=not errors and all(path.status == "present" for path in paths),
        config_path=str(config_path),
        errors=errors,
        warnings=warnings,
        paths=paths,
        execution=ExecutionStatus(
            default_mode=str(execution.get("default_mode", "dry_run")),
            require_approval_for_network_changes=bool(
                execution.get("require_approval_for_network_changes", True)
            ),
        ),
        offline_policy=OfflinePolicyStatus(
            default_offline_state=str(
                offline_policy.get("default_offline_state", "needs_human_power_on")
            ),
            treat_expected_offline_as_failure=bool(
                offline_policy.get("treat_expected_offline_as_failure", False)
            ),
        ),
    )


def create_config_router(config_path: Path = DEFAULT_CONFIG_PATH) -> APIRouter:
    router = APIRouter(prefix="/api/config", tags=["config"])

    @router.get("/status", response_model=ConfigStatus)
    def status() -> ConfigStatus:
        return load_config_status(config_path)

    return router
