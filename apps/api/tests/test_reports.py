import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.reports import generate_report


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def write_report_fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    source_root = tmp_path / "source"
    audit_root = source_root / "network-audit-2026Q2"
    (audit_root / "mobile-compare" / "manual").mkdir(parents=True)
    (audit_root / "subscription-hits").mkdir(parents=True)
    (audit_root / "fingerprints").mkdir(parents=True)
    (audit_root / "mobile-compare" / "manual" / "compare_result.json").write_text(
        json.dumps({"bottleneck_hint": {"value": "insufficient_data"}}),
        encoding="utf-8",
    )
    (audit_root / "subscription-hits" / "hits.csv.template").write_text("template\n", encoding="utf-8")
    (audit_root / "fingerprints" / "empty.sha256").write_text(EMPTY_SHA256, encoding="utf-8")
    source_root.mkdir(exist_ok=True)
    (source_root / "secrets.env").write_text("TOKEN=super-secret-token\n", encoding="utf-8")

    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {audit_root}
security:
  secrets_policy_path: {tmp_path / "secrets.policy.yaml"}
storage:
  reports_dir: {tmp_path / "Docs"}
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "secrets.policy.yaml").write_text(
        """
scan:
  include_extensions: [.env]
patterns:
  - id: token
    label: Token
    regex: '(?i)token\\s*=\\s*[^\\s]+'
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
""".strip(),
        encoding="utf-8",
    )
    services_path = tmp_path / "services.yaml"
    services_path.write_text("services: []\n", encoding="utf-8")
    return config_path, devices_path, services_path


def test_generate_report_writes_redacted_markdown_with_evidence_paths(tmp_path: Path) -> None:
    config_path, devices_path, services_path = write_report_fixtures(tmp_path)

    report = generate_report("current_ops_report", config_path, devices_path, services_path)

    assert report.report_type == "current_ops_report"
    assert report.path.endswith("current_ops_report.md")
    assert Path(report.path).exists()
    assert "mobile-compare/manual/compare_result.json" in report.content
    assert "super-secret-token" not in report.content
    assert "TOKEN=" not in report.content
    assert "temporary_offline" in report.content
    assert "insufficient_evidence" in report.content
    assert "real_failure" in report.content


def test_reports_api_generates_security_report(tmp_path: Path) -> None:
    config_path, devices_path, services_path = write_report_fixtures(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
            devices_config_path=devices_path,
            services_config_path=services_path,
        )
    )

    response = client.post("/api/reports/security_report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report_type"] == "security_report"
    assert payload["redaction_applied"] is True
    assert "super-secret-token" not in payload["content"]
