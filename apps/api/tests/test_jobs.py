from pathlib import Path

from fastapi.testclient import TestClient

from uninode.jobs import load_jobs, run_job_dry
from uninode.main import create_app


def write_job_fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    automations_path = tmp_path / "automations.yaml"
    automations_path.write_text(
        """
jobs:
  - id: check_global_access
    title: Check global access
    category: readonly_check
    mode: dry_run
    target_devices: [minipc_gateway, contabo_vps]
    precheck:
      - Confirm no production network changes will be made.
    steps:
      - Inspect configured VPN subscription evidence.
      - Check gateway path facts.
    gates: [no_na_fields, subscription_live_hits_present, device_offline_policy]
    evidence_required: [bench_json, subscription_hit]
""".strip(),
        encoding="utf-8",
    )
    devices_path = tmp_path / "devices.yaml"
    devices_path.write_text(
        """
devices:
  - id: minipc_gateway
    name: backup-gateway miniPC
    type: edge_node
    role: transparent_gateway
    expected_online: false
    human_action: power_on_if_check_required
    tags: [gateway]
  - id: contabo_vps
    name: Contabo VPS
    type: vps
    role: vpn_subscription_public_exit
    expected_online: true
    tags: [global_access]
""".strip(),
        encoding="utf-8",
    )
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {tmp_path / "source"}
audit_root: {tmp_path / "source" / "network-audit-2026Q2"}
""".strip(),
        encoding="utf-8",
    )
    return config_path, devices_path, automations_path


def test_load_jobs_requires_precheck_steps_gates_and_evidence(tmp_path: Path) -> None:
    _, _, automations_path = write_job_fixtures(tmp_path)

    jobs = load_jobs(automations_path)

    assert jobs[0].id == "check_global_access"
    assert jobs[0].precheck
    assert jobs[0].steps
    assert jobs[0].gates
    assert jobs[0].evidence_required


def test_run_job_dry_generates_plan_without_execution_and_keeps_human_actions(tmp_path: Path) -> None:
    config_path, devices_path, automations_path = write_job_fixtures(tmp_path)

    result = run_job_dry("check_global_access", config_path, devices_path, automations_path)

    assert result.status == "dry_run_ready"
    assert result.executed is False
    assert "power_on_if_check_required" in result.human_actions
    assert result.steps[0].command == "DRY_RUN_ONLY"


def test_jobs_api_lists_and_dry_runs_job(tmp_path: Path) -> None:
    config_path, devices_path, automations_path = write_job_fixtures(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
            devices_config_path=devices_path,
            automations_config_path=automations_path,
        )
    )

    list_response = client.get("/api/jobs")
    dry_response = client.post("/api/jobs/check_global_access/run-dry")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "check_global_access"
    assert dry_response.status_code == 200
    assert dry_response.json()["executed"] is False
    assert "power_on_if_check_required" in dry_response.json()["human_actions"]
