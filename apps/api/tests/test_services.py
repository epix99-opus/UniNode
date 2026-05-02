from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.services import load_services


def write_services_config(tmp_path: Path) -> Path:
    services_path = tmp_path / "services.yaml"
    services_path.write_text(
        """
services:
  - id: contabo_vless
    name: Contabo VLESS Reality
    device_id: contabo_vps
    type: vpn_subscription
    endpoint: vps:2053
    expected_status: configured
    dependencies: []
  - id: minipc_mihomo
    name: miniPC mihomo transparent gateway
    device_id: minipc_gateway
    type: transparent_gateway
    endpoint: 192.168.50.228:7890
    expected_status: expected_offline_until_powered
    dependencies: [contabo_vless]
""".strip(),
        encoding="utf-8",
    )
    return services_path


def test_load_services_from_yaml(tmp_path: Path) -> None:
    services_config = write_services_config(tmp_path)

    services = load_services(services_config)

    assert [service.id for service in services] == ["contabo_vless", "minipc_mihomo"]
    assert services[0].type == "vpn_subscription"
    assert services[1].device_id == "minipc_gateway"
    assert services[1].dependencies == ["contabo_vless"]


def test_services_api_lists_services(tmp_path: Path) -> None:
    services_config = write_services_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            services_config_path=services_config,
        )
    )

    response = client.get("/api/services")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "contabo_vless"
