from pathlib import Path

from fastapi.testclient import TestClient

from uninode.main import create_app
from uninode.topology import load_topology


def write_topology_config(tmp_path: Path) -> Path:
    topology_path = tmp_path / "topology.yaml"
    topology_path.write_text(
        """
layers:
  - id: physical
    name: Physical LAN
  - id: tailscale
    name: Tailscale overlay
  - id: nas_sync
    name: NAS and Obsidian sync
nodes:
  - id: huawei_main_router
    label: Huawei
    type: device
    device_id: huawei_main_router
    layers: [physical]
    status: online
  - id: asus_freesky
    label: ASUS
    type: device
    device_id: asus_freesky
    layers: [physical]
    status: online
  - id: minipc_gateway
    label: miniPC
    type: device
    device_id: minipc_gateway
    layers: [physical, tailscale]
    status: needs_human_power_on
    hint: power_on_if_check_required
  - id: epixnas_rpi
    label: EpixNAS
    type: device
    device_id: epixnas_rpi
    layers: [physical, tailscale, nas_sync]
    status: needs_human_power_on
    hint: power_on_if_check_required
  - id: contabo_vps
    label: Contabo VPS
    type: device
    device_id: contabo_vps
    layers: [physical, tailscale]
    status: online
edges:
  - id: huawei_to_asus
    source: huawei_main_router
    target: asus_freesky
    layer: physical
    label: upstream
  - id: asus_to_minipc
    source: asus_freesky
    target: minipc_gateway
    layer: physical
    label: LAN
  - id: asus_to_epixnas
    source: asus_freesky
    target: epixnas_rpi
    layer: physical
    label: LAN
  - id: minipc_to_vps
    source: minipc_gateway
    target: contabo_vps
    layer: tailscale
    label: exit path
  - id: epixnas_to_obsidian
    source: epixnas_rpi
    target: minipc_gateway
    layer: nas_sync
    label: sync placeholder
""".strip(),
        encoding="utf-8",
    )
    return topology_path


def test_load_topology_filters_layer_without_dropping_offline_nodes(tmp_path: Path) -> None:
    topology_path = write_topology_config(tmp_path)

    graph = load_topology(topology_path, layer="physical")

    node_ids = {node.id for node in graph.nodes}
    edge_ids = {edge.id for edge in graph.edges}
    minipc = next(node for node in graph.nodes if node.id == "minipc_gateway")

    assert {"huawei_main_router", "asus_freesky", "minipc_gateway", "epixnas_rpi"} <= node_ids
    assert {"huawei_to_asus", "asus_to_minipc", "asus_to_epixnas"} <= edge_ids
    assert minipc.status == "needs_human_power_on"
    assert minipc.hint == "power_on_if_check_required"


def test_topology_api_returns_requested_layer(tmp_path: Path) -> None:
    topology_path = write_topology_config(tmp_path)
    client = TestClient(
        create_app(
            database_path=tmp_path / "uninode-test.db",
            topology_config_path=topology_path,
        )
    )

    response = client.get("/api/topology?layer=tailscale")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_layer"] == "tailscale"
    assert any(edge["id"] == "minipc_to_vps" for edge in payload["edges"])
    assert any(node["status"] == "needs_human_power_on" for node in payload["nodes"])
