from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_EXECUTOR_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "executor.yaml"
HIGH_RISK_TOKENS = {
    "rm",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "iptables",
    "nft",
    "ufw",
    "tailscale",
    "systemctl",
}


class AllowlistedCommand(BaseModel):
    id: str
    description: str
    command: list[str]
    mode: str = "readonly"
    timeout_seconds: int = 30


class ExecuteRequest(BaseModel):
    command_id: str
    approved: bool = False


class ExecuteResult(BaseModel):
    command_id: str
    status: str
    executed: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    blockers: list[str] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_commands(executor_config_path: Path) -> dict[str, AllowlistedCommand]:
    parsed = _load_yaml(executor_config_path)
    return {
        item["id"]: AllowlistedCommand(**item)
        for item in parsed.get("commands", [])
    }


def _is_high_risk(command: AllowlistedCommand) -> bool:
    tokens = {Path(token).name for token in command.command}
    if command.mode != "readonly":
        return True
    return bool(tokens & HIGH_RISK_TOKENS)


def execute_allowlisted_command(
    command_id: str,
    executor_config_path: Path = DEFAULT_EXECUTOR_CONFIG_PATH,
    approved: bool = False,
) -> ExecuteResult:
    commands = _load_commands(executor_config_path)
    command = commands.get(command_id)
    if command is None:
        return ExecuteResult(command_id=command_id, status="rejected", blockers=["not_allowlisted"])
    if _is_high_risk(command):
        return ExecuteResult(command_id=command_id, status="rejected", blockers=["high_risk_command"])
    if not approved:
        return ExecuteResult(command_id=command_id, status="approval_required", blockers=["approval_required"])

    try:
        completed = subprocess.run(
            command.command,
            capture_output=True,
            check=False,
            text=True,
            timeout=command.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecuteResult(
            command_id=command_id,
            status="timeout",
            executed=True,
            stdout=exc.stdout or "",
            stderr=exc.stderr or "",
            blockers=["timeout"],
        )

    return ExecuteResult(
        command_id=command_id,
        status="completed" if completed.returncode == 0 else "failed",
        executed=True,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
    )


def create_executor_router(
    executor_config_path: Path = DEFAULT_EXECUTOR_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/runs", tags=["runs"])

    @router.post("/execute", response_model=ExecuteResult)
    def execute(request: ExecuteRequest) -> ExecuteResult:
        return execute_allowlisted_command(request.command_id, executor_config_path, request.approved)

    return router
