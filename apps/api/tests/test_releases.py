from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.releases import build_release_diff, evaluate_preflight, load_release_pipeline


def write_release_config(tmp_path: Path) -> Path:
    current = tmp_path / "current"
    proposed = tmp_path / "proposed"
    current.mkdir()
    proposed.mkdir()
    (current / "mihomo.yaml").write_text("rule: old\n", encoding="utf-8")
    (proposed / "mihomo.yaml").write_text("rule: new\n", encoding="utf-8")
    config_path = tmp_path / "releases.yaml"
    config_path.write_text(
        f"""
versions:
  - id: mihomo_rules_v1
    target: mihomo
    current_dir: {current}
    proposed_dir: {proposed}
    rollback_target: mihomo_rules_previous
    required_preflight: [secret_scan, rule_coverage, live_hit_evidence]
""".strip(),
        encoding="utf-8",
    )
    return config_path


def test_release_pipeline_loads_versioned_targets(tmp_path: Path) -> None:
    config_path = write_release_config(tmp_path)

    pipeline = load_release_pipeline(config_path)

    assert pipeline.versions[0].id == "mihomo_rules_v1"
    assert pipeline.versions[0].rollback_target == "mihomo_rules_previous"


def test_release_diff_viewer_reports_changed_files(tmp_path: Path) -> None:
    config_path = write_release_config(tmp_path)

    diff = build_release_diff("mihomo_rules_v1", config_path)

    assert diff.changed_files == ["mihomo.yaml"]
    assert "-rule: old" in diff.diff
    assert "+rule: new" in diff.diff


def test_preflight_blocks_without_all_evidence(tmp_path: Path) -> None:
    config_path = write_release_config(tmp_path)

    blocked = evaluate_preflight("mihomo_rules_v1", {}, config_path)
    passed = evaluate_preflight(
        "mihomo_rules_v1",
        {"secret_scan": True, "rule_coverage": True, "live_hit_evidence": True},
        config_path,
    )

    assert blocked.status == "blocked"
    assert "secret_scan" in blocked.missing_checks
    assert passed.status == "pass"


def test_release_api_diff_preflight_publish_and_rollback_are_dry_run(tmp_path: Path) -> None:
    config_path = write_release_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            releases_config_path=config_path,
        )
    )

    versions = client.get("/api/releases")
    diff = client.post("/api/releases/mihomo_rules_v1/diff")
    preflight = client.post(
        "/api/releases/mihomo_rules_v1/preflight",
        json={"checks": {"secret_scan": True, "rule_coverage": True, "live_hit_evidence": True}},
    )
    publish = client.post("/api/releases/mihomo_rules_v1/publish-dry")
    rollback = client.post("/api/releases/mihomo_rules_v1/rollback-dry")

    assert versions.status_code == 200
    assert diff.json()["changed_files"] == ["mihomo.yaml"]
    assert preflight.json()["status"] == "pass"
    assert publish.json()["executed"] is False
    assert rollback.json()["rollback_target"] == "mihomo_rules_previous"
