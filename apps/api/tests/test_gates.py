import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.gates import evaluate_gates
from uninode.main import create_app


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def write_gate_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source_root = tmp_path / "source"
    audit_root = source_root / "network-audit-2026Q2"
    (audit_root / "bench" / "batch").mkdir(parents=True)
    (audit_root / "mobile-compare" / "manual").mkdir(parents=True)
    (audit_root / "subscription-hits").mkdir(parents=True)
    (audit_root / "fingerprints").mkdir(parents=True)
    (audit_root / "bench" / "batch" / "pc_direct.json").write_text(
        json.dumps({"cachefly_100m": "NA"}),
        encoding="utf-8",
    )
    (audit_root / "mobile-compare" / "manual" / "compare_result.json").write_text(
        json.dumps({"bottleneck_hint": {"value": "insufficient_data"}}),
        encoding="utf-8",
    )
    (audit_root / "subscription-hits" / "hits.csv.template").write_text(
        "template\n",
        encoding="utf-8",
    )
    (audit_root / "fingerprints" / "empty.sha256").write_text(EMPTY_SHA256, encoding="utf-8")

    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {audit_root}
security:
  secrets_policy_path: {tmp_path / "secrets.policy.yaml"}
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
    (source_root / "secrets.env").write_text("TOKEN=secret\n", encoding="utf-8")

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
    return config_path, devices_path


def test_gate_engine_blocks_evidence_and_warns_expected_offline_for_readonly(tmp_path: Path) -> None:
    config_path, devices_path = write_gate_fixture(tmp_path)

    result = evaluate_gates(config_path, devices_path, action_type="readonly")
    gates = {gate.id: gate for gate in result.gates}

    assert result.allowed is False
    assert gates["no_na_fields"].status == "fail"
    assert gates["mobile_has_valid_samples"].status == "fail"
    assert gates["subscription_live_hits_present"].status == "fail"
    assert gates["fingerprint_non_empty"].status == "fail"
    assert gates["secret_scan_pass"].status == "fail"
    assert gates["device_offline_policy"].status == "warn"


def test_gate_engine_blocks_expected_offline_for_execute(tmp_path: Path) -> None:
    config_path, devices_path = write_gate_fixture(tmp_path)

    result = evaluate_gates(config_path, devices_path, action_type="execute")
    gates = {gate.id: gate for gate in result.gates}

    assert result.allowed is False
    assert gates["device_offline_policy"].status == "fail"


def test_gates_api_evaluates_requested_action_type(tmp_path: Path) -> None:
    config_path, devices_path = write_gate_fixture(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
            devices_config_path=devices_path,
        )
    )

    response = client.post("/api/gates/evaluate", json={"action_type": "execute"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["allowed"] is False
    assert any(
        gate["id"] == "device_offline_policy" and gate["status"] == "fail"
        for gate in payload["gates"]
    )
