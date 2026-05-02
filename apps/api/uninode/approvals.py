from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel

DEFAULT_APPROVALS_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "approvals.yaml"


class PermissionResult(BaseModel):
    role: str
    action: str
    allowed: bool
    requires_approval: bool
    reason: str


class ApprovalPolicy(BaseModel):
    roles: dict[str, dict[str, list[str]]]
    approval_required_actions: list[str]
    key_store: dict[str, Any]


class ApprovalRequestIn(BaseModel):
    role: str
    action: str
    target: str


class ApprovalRequest(BaseModel):
    id: str
    role: str
    action: str
    target: str
    status: str
    requires_approval: bool
    reason: str
    created_at: str


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_path(raw_path: str | None, config_path: Path) -> Path:
    if not raw_path:
        return (config_path.parent.parent / "data" / "audit" / "approvals.jsonl").resolve()
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def load_approval_policy(config_path: Path = DEFAULT_APPROVALS_CONFIG_PATH) -> ApprovalPolicy:
    config = _load_yaml(config_path)
    return ApprovalPolicy(
        roles=config.get("roles", {}),
        approval_required_actions=[str(action) for action in config.get("approval_required_actions", [])],
        key_store=config.get("key_store", {"provider": "local_file_reference", "secret_material_allowed_in_api": False}),
    )


def evaluate_permission(
    role: str,
    action: str,
    config_path: Path = DEFAULT_APPROVALS_CONFIG_PATH,
) -> PermissionResult:
    policy = load_approval_policy(config_path)
    allowed_actions = set(policy.roles.get(role, {}).get("allowed_actions", []))
    requires_approval = action in policy.approval_required_actions
    if action not in allowed_actions:
        return PermissionResult(
            role=role,
            action=action,
            allowed=False,
            requires_approval=requires_approval,
            reason="action_not_allowed_for_role",
        )
    return PermissionResult(
        role=role,
        action=action,
        allowed=not requires_approval,
        requires_approval=requires_approval,
        reason="approval_required" if requires_approval else "allowed",
    )


def _append_audit(record: dict[str, Any], config_path: Path) -> None:
    config = _load_yaml(config_path)
    audit_path = _resolve_path(config.get("audit_log_path"), config_path)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def create_approval_request(
    role: str,
    action: str,
    target: str,
    config_path: Path = DEFAULT_APPROVALS_CONFIG_PATH,
) -> ApprovalRequest:
    permission = evaluate_permission(role, action, config_path)
    created_at = datetime.now(timezone.utc).isoformat()
    request = ApprovalRequest(
        id=f"{created_at}_{role}_{action}",
        role=role,
        action=action,
        target=target,
        status="pending_approval" if permission.reason == "approval_required" else "blocked",
        requires_approval=permission.requires_approval,
        reason=permission.reason,
        created_at=created_at,
    )
    _append_audit(request.model_dump(), config_path)
    return request


def load_audit_log(config_path: Path = DEFAULT_APPROVALS_CONFIG_PATH) -> list[dict[str, Any]]:
    config = _load_yaml(config_path)
    audit_path = _resolve_path(config.get("audit_log_path"), config_path)
    if not audit_path.exists():
        return []
    return [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def create_approvals_router(config_path: Path = DEFAULT_APPROVALS_CONFIG_PATH) -> APIRouter:
    router = APIRouter(prefix="/api/approvals", tags=["approvals"])

    @router.get("/policy", response_model=ApprovalPolicy)
    def policy() -> ApprovalPolicy:
        return load_approval_policy(config_path)

    @router.post("/requests", response_model=ApprovalRequest)
    def create_request(request: ApprovalRequestIn) -> ApprovalRequest:
        return create_approval_request(request.role, request.action, request.target, config_path)

    @router.get("/audit-log")
    def audit_log() -> list[dict[str, Any]]:
        return load_audit_log(config_path)

    return router
