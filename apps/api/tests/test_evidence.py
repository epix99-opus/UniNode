import json
from pathlib import Path

from fastapi.testclient import TestClient

from uninode.evidence import scan_evidence
from uninode.main import create_app


EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def write_app_config(tmp_path: Path, audit_root: Path) -> Path:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {audit_root.parent}
audit_root: {audit_root}
storage:
  runtime_dir: {tmp_path / "data"}
execution:
  default_mode: dry_run
""".strip(),
        encoding="utf-8",
    )
    return config_path


def make_fixture_audit_root(tmp_path: Path) -> Path:
    audit_root = tmp_path / "source" / "network-audit-2026Q2"
    (audit_root / "bench" / "bad").mkdir(parents=True)
    (audit_root / "bench" / "good").mkdir(parents=True)
    (audit_root / "mobile-compare" / "manual").mkdir(parents=True)
    (audit_root / "subscription-hits").mkdir(parents=True)
    (audit_root / "fingerprints" / "epix").mkdir(parents=True)

    (audit_root / "bench" / "bad" / "pc_direct.json").write_text(
        json.dumps({"scenario": "pc_direct", "cachefly_100m": "NA"}),
        encoding="utf-8",
    )
    (audit_root / "bench" / "good" / "pc_direct.json").write_text(
        json.dumps({"scenario": "pc_direct", "cachefly_100m": "HTTP 200"}),
        encoding="utf-8",
    )
    (audit_root / "bench" / "bad" / "broken.json").write_text("{", encoding="utf-8")
    (audit_root / "mobile-compare" / "manual" / "compare_result.json").write_text(
        json.dumps({"bottleneck_hint": {"value": "insufficient_data"}}),
        encoding="utf-8",
    )
    (audit_root / "subscription-hits" / "hits.csv.template").write_text(
        "client,rule,hit_count\n",
        encoding="utf-8",
    )
    (audit_root / "fingerprints" / "epix" / "fingerprint.sha256").write_text(
        EMPTY_SHA256,
        encoding="utf-8",
    )
    return audit_root


def test_scan_evidence_classifies_blockers(tmp_path: Path) -> None:
    audit_root = make_fixture_audit_root(tmp_path)
    config_path = write_app_config(tmp_path, audit_root)

    evidence = scan_evidence(config_path)
    by_path = {item.source_path: item for item in evidence}

    assert by_path["bench/bad/pc_direct.json"].validity == "invalid"
    assert by_path["bench/good/pc_direct.json"].validity == "valid"
    assert by_path["bench/bad/broken.json"].validity == "invalid_json"
    assert by_path["mobile-compare/manual/compare_result.json"].validity == "blocked"
    assert by_path["subscription-hits/hits.csv.template"].validity == "template_only"
    assert by_path["fingerprints/epix/fingerprint.sha256"].validity == "suspicious"


def test_evidence_api_returns_list_and_summary(tmp_path: Path) -> None:
    audit_root = make_fixture_audit_root(tmp_path)
    config_path = write_app_config(tmp_path, audit_root)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
        )
    )

    list_response = client.get("/api/evidence")
    summary_response = client.get("/api/evidence/summary")

    assert list_response.status_code == 200
    assert len(list_response.json()) == 6
    assert summary_response.status_code == 200
    assert summary_response.json()["by_validity"]["valid"] == 1
    assert summary_response.json()["by_validity"]["template_only"] == 1
    assert summary_response.json()["blocked_count"] == 5
