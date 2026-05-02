from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_TAILSCALE_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "tailscale.yaml"


class TailscaleNode(BaseModel):
    hostname: str
    online: bool
    state: str
    tailscale_ips: list[str] = Field(default_factory=list)
    exit_node: bool = False
    key_expiry: str | None = None
    key_status: str = "unknown"


class TailscaleStatus(BaseModel):
    readonly: bool = True
    token_status: str
    config_gap: bool
    source: str
    nodes: list[TailscaleNode] = Field(default_factory=list)


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


def _key_status(key_expiry: str | None) -> str:
    if not key_expiry:
        return "unknown"
    try:
        expires_at = datetime.fromisoformat(key_expiry.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return "expired" if expires_at < datetime.now(timezone.utc) else "valid"


def _node_state(hostname: str, online: bool, expected_offline_hosts: set[str]) -> str:
    if online:
        return "online"
    return "expected_offline" if hostname in expected_offline_hosts else "unexpected_offline"


def _parse_nodes(raw_status: dict[str, Any], expected_offline_hosts: set[str]) -> list[TailscaleNode]:
    raw_nodes = []
    if isinstance(raw_status.get("Self"), dict):
        raw_nodes.append(raw_status["Self"])
    peer = raw_status.get("Peer") or {}
    if isinstance(peer, dict):
        raw_nodes.extend(item for item in peer.values() if isinstance(item, dict))

    nodes: list[TailscaleNode] = []
    for item in raw_nodes:
        hostname = str(item.get("HostName") or item.get("DNSName") or "unknown")
        online = bool(item.get("Online", False))
        key_expiry = item.get("KeyExpiry")
        nodes.append(
            TailscaleNode(
                hostname=hostname,
                online=online,
                state=_node_state(hostname, online, expected_offline_hosts),
                tailscale_ips=[str(ip) for ip in item.get("TailscaleIPs", [])],
                exit_node=bool(item.get("ExitNodeOption") or item.get("ExitNode")),
                key_expiry=str(key_expiry) if key_expiry else None,
                key_status=_key_status(str(key_expiry) if key_expiry else None),
            )
        )
    return nodes


def load_tailscale_status(
    tailscale_config_path: Path = DEFAULT_TAILSCALE_CONFIG_PATH,
) -> TailscaleStatus:
    config = _load_yaml(tailscale_config_path)
    token_env = str(config.get("api_token_env", "TAILSCALE_API_TOKEN"))
    token_status = "present" if os.environ.get(token_env) else "missing"
    status_path = _resolve_path(config.get("status_json_path"), tailscale_config_path)
    expected_offline_hosts = {str(host) for host in config.get("expected_offline_hosts", [])}
    raw_status: dict[str, Any] = {}
    source = "missing_status_json"

    if status_path and status_path.exists():
        try:
            raw_status = json.loads(status_path.read_text(encoding="utf-8"))
            source = str(status_path)
        except json.JSONDecodeError:
            source = "invalid_status_json"

    return TailscaleStatus(
        token_status=token_status,
        config_gap=token_status == "missing" or source != str(status_path),
        source=source,
        nodes=_parse_nodes(raw_status, expected_offline_hosts),
    )


def create_tailscale_router(
    tailscale_config_path: Path = DEFAULT_TAILSCALE_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/tailscale", tags=["tailscale"])

    @router.get("/status", response_model=TailscaleStatus)
    def status() -> TailscaleStatus:
        return load_tailscale_status(tailscale_config_path)

    return router
