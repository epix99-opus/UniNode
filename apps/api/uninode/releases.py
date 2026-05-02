from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

DEFAULT_RELEASES_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "releases.yaml"


class ReleaseVersion(BaseModel):
    id: str
    target: str
    current_dir: str
    proposed_dir: str
    rollback_target: str
    required_preflight: list[str]


class ReleasePipeline(BaseModel):
    versions: list[ReleaseVersion]


class ReleaseDiff(BaseModel):
    release_id: str
    changed_files: list[str]
    diff: str


class PreflightRequest(BaseModel):
    checks: dict[str, bool] = {}


class PreflightResult(BaseModel):
    release_id: str
    status: str
    missing_checks: list[str]
    required_checks: list[str]


class DryRunReleaseAction(BaseModel):
    release_id: str
    action: str
    executed: bool = False
    rollback_target: str
    next_action: str


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _resolve_path(raw_path: str, config_path: Path) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (config_path.parent.parent / path).resolve()


def load_release_pipeline(config_path: Path = DEFAULT_RELEASES_CONFIG_PATH) -> ReleasePipeline:
    config = _load_yaml(config_path)
    return ReleasePipeline(
        versions=[
            ReleaseVersion(
                id=str(item.get("id")),
                target=str(item.get("target")),
                current_dir=str(item.get("current_dir")),
                proposed_dir=str(item.get("proposed_dir")),
                rollback_target=str(item.get("rollback_target")),
                required_preflight=[str(check) for check in item.get("required_preflight", [])],
            )
            for item in config.get("versions", [])
        ]
    )


def _find_release(release_id: str, config_path: Path) -> ReleaseVersion:
    for release in load_release_pipeline(config_path).versions:
        if release.id == release_id:
            return release
    raise KeyError(release_id)


def _file_map(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def build_release_diff(
    release_id: str,
    config_path: Path = DEFAULT_RELEASES_CONFIG_PATH,
) -> ReleaseDiff:
    release = _find_release(release_id, config_path)
    current = _file_map(_resolve_path(release.current_dir, config_path))
    proposed = _file_map(_resolve_path(release.proposed_dir, config_path))
    changed_files = sorted(
        file_name for file_name in set(current) | set(proposed) if current.get(file_name) != proposed.get(file_name)
    )
    diff_lines: list[str] = []
    for file_name in changed_files:
        diff_lines.extend(
            difflib.unified_diff(
                current.get(file_name, "").splitlines(),
                proposed.get(file_name, "").splitlines(),
                fromfile=f"current/{file_name}",
                tofile=f"proposed/{file_name}",
                lineterm="",
            )
        )
    return ReleaseDiff(release_id=release_id, changed_files=changed_files, diff="\n".join(diff_lines))


def evaluate_preflight(
    release_id: str,
    checks: dict[str, bool],
    config_path: Path = DEFAULT_RELEASES_CONFIG_PATH,
) -> PreflightResult:
    release = _find_release(release_id, config_path)
    missing = [check for check in release.required_preflight if checks.get(check) is not True]
    return PreflightResult(
        release_id=release_id,
        status="blocked" if missing else "pass",
        missing_checks=missing,
        required_checks=release.required_preflight,
    )


def release_action_dry(
    release_id: str,
    action: str,
    config_path: Path = DEFAULT_RELEASES_CONFIG_PATH,
) -> DryRunReleaseAction:
    release = _find_release(release_id, config_path)
    return DryRunReleaseAction(
        release_id=release_id,
        action=action,
        rollback_target=release.rollback_target,
        next_action="run_preflight_then_request_approval",
    )


def create_releases_router(config_path: Path = DEFAULT_RELEASES_CONFIG_PATH) -> APIRouter:
    router = APIRouter(prefix="/api/releases", tags=["releases"])

    @router.get("", response_model=ReleasePipeline)
    def versions() -> ReleasePipeline:
        return load_release_pipeline(config_path)

    @router.post("/{release_id}/diff", response_model=ReleaseDiff)
    def diff(release_id: str) -> ReleaseDiff:
        try:
            return build_release_diff(release_id, config_path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="release_not_found") from exc

    @router.post("/{release_id}/preflight", response_model=PreflightResult)
    def preflight(release_id: str, request: PreflightRequest) -> PreflightResult:
        try:
            return evaluate_preflight(release_id, request.checks, config_path)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="release_not_found") from exc

    @router.post("/{release_id}/publish-dry", response_model=DryRunReleaseAction)
    def publish_dry(release_id: str) -> DryRunReleaseAction:
        return release_action_dry(release_id, "publish_dry", config_path)

    @router.post("/{release_id}/rollback-dry", response_model=DryRunReleaseAction)
    def rollback_dry(release_id: str) -> DryRunReleaseAction:
        return release_action_dry(release_id, "rollback_dry", config_path)

    return router
