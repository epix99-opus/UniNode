import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.agent_registry import archive_agent_output, load_agent_registry
from uninode.main import create_app


def write_registry_config(tmp_path: Path) -> Path:
    openclaw_health = tmp_path / "openclaw-health.json"
    openclaw_health.write_text(json.dumps({"online": True, "version": "0.1.0"}), encoding="utf-8")
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        f"""
agents:
  - id: openclaw
    name: OpenClaw
    endpoint: http://127.0.0.1:17888
    health_snapshot_path: {openclaw_health}
    capabilities: [readonly_diagnostics, evidence_review]
  - id: hermes
    name: Hermes
    endpoint: http://127.0.0.1:17889
    health_snapshot_path: {tmp_path / "missing-hermes.json"}
    capabilities: [report_review, human_handoff]
archive_dir: {tmp_path / "agent-evidence"}
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_agent_registry_reports_online_state_and_capabilities(tmp_path: Path) -> None:
    config_path = write_registry_config(tmp_path)

    registry = load_agent_registry(config_path)
    agents = {agent.id: agent for agent in registry.agents}

    assert agents["openclaw"].status == "online"
    assert "readonly_diagnostics" in agents["openclaw"].capabilities
    assert agents["hermes"].status == "offline"
    assert registry.task_handoff["allowed_modes"] == ["readonly", "dry_run"]


def test_agent_output_archives_as_evidence(tmp_path: Path) -> None:
    config_path = write_registry_config(tmp_path)

    archived = archive_agent_output(
        "openclaw",
        {"findings": ["ok"], "evidence_paths": ["data/evidence/example.json"]},
        config_path,
    )

    assert archived.validity == "agent_archived"
    assert Path(archived.path).exists()
    assert "openclaw" in Path(archived.path).name


def test_agent_registry_api_lists_and_archives_output(tmp_path: Path) -> None:
    config_path = write_registry_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            agent_registry_config_path=config_path,
        )
    )

    list_response = client.get("/api/agents/registry")
    archive_response = client.post(
        "/api/agents/openclaw/archive-output",
        json={"output": {"findings": ["ok"], "evidence_paths": ["data/evidence/example.json"]}},
    )

    assert list_response.status_code == 200
    assert list_response.json()["agents"][0]["status"] == "online"
    assert archive_response.status_code == 200
    assert archive_response.json()["validity"] == "agent_archived"
