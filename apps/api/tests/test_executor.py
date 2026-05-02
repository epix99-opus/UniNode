from pathlib import Path

from fastapi.testclient import TestClient

from uninode.executor import execute_allowlisted_command
from uninode.main import create_app


def write_executor_config(tmp_path: Path) -> Path:
    script_path = tmp_path / "bench_throughput.sh"
    script_path.write_text("#!/bin/sh\necho bench-ok\n", encoding="utf-8")
    script_path.chmod(0o755)
    config_path = tmp_path / "executor.yaml"
    config_path.write_text(
        f"""
commands:
  - id: bench_throughput
    description: Readonly throughput bench
    command: [{script_path}]
    mode: readonly
    timeout_seconds: 5
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_executor_requires_approval_before_running_allowlisted_command(tmp_path: Path) -> None:
    config_path = write_executor_config(tmp_path)

    result = execute_allowlisted_command("bench_throughput", config_path, approved=False)

    assert result.status == "approval_required"
    assert result.executed is False
    assert result.exit_code is None


def test_executor_runs_approved_readonly_allowlisted_command(tmp_path: Path) -> None:
    config_path = write_executor_config(tmp_path)

    result = execute_allowlisted_command("bench_throughput", config_path, approved=True)

    assert result.status == "completed"
    assert result.executed is True
    assert result.exit_code == 0
    assert "bench-ok" in result.stdout


def test_executor_rejects_high_risk_commands(tmp_path: Path) -> None:
    config_path = tmp_path / "executor.yaml"
    config_path.write_text(
        """
commands:
  - id: dangerous
    description: Dangerous production write
    command: [rm, -rf, /]
    mode: write
    timeout_seconds: 5
""".strip(),
        encoding="utf-8",
    )

    result = execute_allowlisted_command("dangerous", config_path, approved=True)

    assert result.status == "rejected"
    assert result.executed is False
    assert "high_risk_command" in result.blockers


def test_executor_api_captures_stdout_for_approved_readonly_command(tmp_path: Path) -> None:
    executor_config_path = write_executor_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            executor_config_path=executor_config_path,
        )
    )

    response = client.post("/api/runs/execute", json={"command_id": "bench_throughput", "approved": True})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["executed"] is True
    assert payload["stdout"].strip() == "bench-ok"
