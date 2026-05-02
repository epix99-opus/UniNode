from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from pydantic import BaseModel, Field

DEFAULT_TOPOLOGY_CONFIG_PATH = Path(__file__).resolve().parents[3] / "configs" / "topology.yaml"


class TopologyLayer(BaseModel):
    id: str
    name: str


class TopologyNode(BaseModel):
    id: str
    label: str
    type: str
    layers: list[str] = Field(default_factory=list)
    status: str = "unknown"
    hint: str | None = None
    device_id: str | None = None
    service_id: str | None = None


class TopologyEdge(BaseModel):
    id: str
    source: str
    target: str
    layer: str
    label: str


class TopologyGraph(BaseModel):
    active_layer: str
    layers: list[TopologyLayer]
    nodes: list[TopologyNode]
    edges: list[TopologyEdge]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_topology(
    topology_config_path: Path = DEFAULT_TOPOLOGY_CONFIG_PATH,
    layer: str = "physical",
) -> TopologyGraph:
    parsed = _load_yaml(topology_config_path)
    layers = [TopologyLayer(**item) for item in parsed.get("layers", [])]
    all_nodes = [TopologyNode(**item) for item in parsed.get("nodes", [])]
    all_edges = [TopologyEdge(**item) for item in parsed.get("edges", [])]

    edges = [edge for edge in all_edges if edge.layer == layer]
    edge_node_ids = {edge.source for edge in edges} | {edge.target for edge in edges}
    nodes = [
        node
        for node in all_nodes
        if layer in node.layers or node.id in edge_node_ids
    ]
    return TopologyGraph(
        active_layer=layer,
        layers=layers,
        nodes=nodes,
        edges=edges,
    )


def create_topology_router(topology_config_path: Path = DEFAULT_TOPOLOGY_CONFIG_PATH) -> APIRouter:
    router = APIRouter(prefix="/api/topology", tags=["topology"])

    @router.get("", response_model=TopologyGraph)
    def topology(layer: str = "physical") -> TopologyGraph:
        return load_topology(topology_config_path, layer=layer)

    return router
