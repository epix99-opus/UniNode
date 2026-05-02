from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_AGENT_REGISTRY_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "agents.yaml"


class RegisteredAgent(BaseModel):
    id: str
    name: str
    endpoint: str
    status: str
    capabilities: list[str] = Field(default_factory=list)
    health_snapshot_path: str


class AgentRegistry(BaseModel):
    agents: list[RegisteredAgent]
    task_handoff: dict[str, Any]


class AgentArchiveRequest(BaseModel):
    output: dict[str, Any]


class ArchivedAgentOutput(BaseModel):
    agent_id: str
    path: str
    validity: str = "agent_archived"


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


def _agent_status(snapshot_path: Path | None) -> str:
    if not snapshot_path or not snapshot_path.exists():
        return "offline"
    try:
        parsed = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "unknown"
    return "online" if parsed.get("online") is True else "offline"


def load_agent_registry(
    registry_config_path: Path = DEFAULT_AGENT_REGISTRY_CONFIG_PATH,
) -> AgentRegistry:
    config = _load_yaml(registry_config_path)
    agents = []
    for item in config.get("agents", []):
        snapshot_path = _resolve_path(item.get("health_snapshot_path"), registry_config_path)
        agents.append(
            RegisteredAgent(
                id=str(item.get("id")),
                name=str(item.get("name")),
                endpoint=str(item.get("endpoint", "not_registered")),
                status=_agent_status(snapshot_path),
                capabilities=[str(capability) for capability in item.get("capabilities", [])],
                health_snapshot_path=str(snapshot_path) if snapshot_path else "",
            )
        )
    return AgentRegistry(
        agents=agents,
        task_handoff={
            "allowed_modes": ["readonly", "dry_run"],
            "denied_actions": ["network_write", "secret_print", "production_config_change"],
            "context_sources": ["facts", "evidence", "reports"],
        },
    )


def archive_agent_output(
    agent_id: str,
    output: dict[str, Any],
    registry_config_path: Path = DEFAULT_AGENT_REGISTRY_CONFIG_PATH,
) -> ArchivedAgentOutput:
    config = _load_yaml(registry_config_path)
    archive_dir = _resolve_path(config.get("archive_dir"), registry_config_path)
    if archive_dir is None:
        archive_dir = registry_config_path.parent.parent / "data" / "evidence" / "agents" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = archive_dir / f"{timestamp}_{agent_id}.json"
    path.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")
    return ArchivedAgentOutput(agent_id=agent_id, path=str(path))


def create_agent_registry_router(
    registry_config_path: Path = DEFAULT_AGENT_REGISTRY_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/agents", tags=["agent-registry"])

    @router.get("/registry", response_model=AgentRegistry)
    def registry() -> AgentRegistry:
        return load_agent_registry(registry_config_path)

    @router.post("/{agent_id}/archive-output", response_model=ArchivedAgentOutput)
    def archive(agent_id: str, request: AgentArchiveRequest) -> ArchivedAgentOutput:
        return archive_agent_output(agent_id, request.output, registry_config_path)

    return router
