from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.security import redact_text, scan_security_findings


def write_app_config(tmp_path: Path, source_root: Path, policy_path: Path) -> Path:
    config_path = tmp_path / "app.yaml"
    config_path.write_text(
        f"""
version: 1
workspace: {tmp_path}
source_root: {source_root}
audit_root: {source_root / "network-audit-2026Q2"}
security:
  secrets_policy_path: {policy_path}
  redact_secrets: true
  block_publish_on_secret_findings: true
  secret_values_allowed_in_reports: false
""".strip(),
        encoding="utf-8",
    )
    return config_path


def write_policy(tmp_path: Path) -> Path:
    policy_path = tmp_path / "secrets.policy.yaml"
    policy_path.write_text(
        """
scan:
  include_extensions:
    - .env
    - .yaml
    - .sh
  ignore_dirs:
    - .git
    - node_modules
patterns:
  - id: uuid
    label: UUID
    regex: '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
  - id: password
    label: Password
    regex: '(?i)password\\s*=\\s*[^\\s]+'
  - id: private_key
    label: Private key
    regex: '-----BEGIN [A-Z ]*PRIVATE KEY-----'
  - id: token
    label: Token
    regex: '(?i)token\\s*=\\s*[^\\s]+'
  - id: auth_key
    label: Auth key
    regex: '(?i)auth[_-]?key\\s*=\\s*[^\\s]+'
  - id: subscription_url
    label: Subscription URL
    regex: 'https?://[^\\s]*(?:token|uuid|sub|subscribe)[^\\s]*'
""".strip(),
        encoding="utf-8",
    )
    return policy_path


def make_sensitive_source(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    source_root = tmp_path / "source"
    source_root.mkdir()
    secrets = {
        "uuid": "123e4567-e89b-12d3-a456-426614174000",
        "password": "password=CorrectHorseBatteryStaple",
        "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----",
        "token": "token=ghp_superSecretToken",
        "auth_key": "auth_key=tskey-auth-superSecret",
        "subscription_url": "https://example.com/subscribe?token=secret-token&uuid=123e4567-e89b-12d3-a456-426614174000",
    }
    (source_root / "network_facts.env").write_text("\n".join(secrets.values()), encoding="utf-8")
    return source_root, secrets


def test_redact_text_masks_secret_values() -> None:
    redacted = redact_text("token=ghp_superSecretToken password=CorrectHorseBatteryStaple")

    assert "ghp_superSecretToken" not in redacted
    assert "CorrectHorseBatteryStaple" not in redacted
    assert "[REDACTED]" in redacted


def test_security_scan_finds_and_redacts_sensitive_patterns(tmp_path: Path) -> None:
    source_root, secrets = make_sensitive_source(tmp_path)
    policy_path = write_policy(tmp_path)
    config_path = write_app_config(tmp_path, source_root, policy_path)

    findings = scan_security_findings(config_path)
    finding_types = {finding.type for finding in findings}
    joined_payload = " ".join(finding.redacted_excerpt for finding in findings)

    assert {"uuid", "password", "private_key", "token", "auth_key", "subscription_url"} <= finding_types
    assert all(finding.severity == "blocker" for finding in findings)
    for raw_secret in secrets.values():
        assert raw_secret not in joined_payload
    assert "[REDACTED]" in joined_payload


def test_security_api_returns_redacted_findings(tmp_path: Path) -> None:
    source_root, secrets = make_sensitive_source(tmp_path)
    policy_path = write_policy(tmp_path)
    config_path = write_app_config(tmp_path, source_root, policy_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            config_path=config_path,
        )
    )

    response = client.get("/api/security/findings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["blocked"] is True
    assert payload["total"] >= 6
    dumped = str(payload)
    for raw_secret in secrets.values():
        assert raw_secret not in dumped
