from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from uninode.config_status import DEFAULT_CONFIG_PATH
from uninode.devices import DEFAULT_DEVICES_CONFIG_PATH, load_devices
from uninode.evidence import scan_evidence, summarize_evidence
from uninode.security import scan_security_findings
from uninode.services import DEFAULT_SERVICES_CONFIG_PATH, load_services


class DashboardCard(BaseModel):
    id: str
    title: str
    status: str
    count: int = 0
    detail: str


class DashboardSummary(BaseModel):
    overall_status: str
    human_actions: list[str] = Field(default_factory=list)
    cards: list[DashboardCard]


def _status_for_services(service_types: set[str], statuses: set[str]) -> str:
    if not service_types:
        return "missing"
    if "missing_fact" in statuses or "missing_design_choice" in statuses:
        return "evidence_gap"
    if "expected_offline_until_powered" in statuses:
        return "needs_human_power_on"
    return "configured"


def build_dashboard_summary(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH,
) -> DashboardSummary:
    devices = load_devices(config_path, devices_config_path)
    services = load_services(services_config_path)
    evidence_summary = summarize_evidence(scan_evidence(config_path))
    security_findings = scan_security_findings(config_path)

    human_actions = sorted(
        {
            device.human_action
            for device in devices
            if device.human_action and device.status == "needs_human_power_on"
        }
    )
    device_status = "needs_human_power_on" if human_actions else "ready"
    service_statuses_by_type = {
        service_type: {
            service.expected_status for service in services if service.type == service_type
        }
        for service_type in {service.type for service in services}
    }
    cards = [
        DashboardCard(
            id="devices",
            title="Devices",
            status=device_status,
            count=len(devices),
            detail="Offline devices require human power-on checks." if human_actions else "Device inventory loaded.",
        ),
        DashboardCard(
            id="global_access",
            title="Global Access",
            status=_status_for_services(
                {"vpn_subscription", "transparent_gateway"},
                service_statuses_by_type.get("vpn_subscription", set())
                | service_statuses_by_type.get("transparent_gateway", set()),
            ),
            count=sum(service.type in {"vpn_subscription", "transparent_gateway"} for service in services),
            detail="VPN subscriptions and gateway services are tracked.",
        ),
        DashboardCard(
            id="tailscale",
            title="Tailscale",
            status=_status_for_services(
                {"tailscale"},
                service_statuses_by_type.get("tailscale", set()),
            ),
            count=sum(service.type == "tailscale" for service in services),
            detail="Tailscale exit-node readiness depends on collected facts.",
        ),
        DashboardCard(
            id="nas_obsidian",
            title="NAS / Obsidian",
            status=_status_for_services(
                {"nas", "obsidian_sync"},
                service_statuses_by_type.get("nas", set())
                | service_statuses_by_type.get("obsidian_sync", set()),
            ),
            count=sum(service.type in {"nas", "obsidian_sync"} for service in services),
            detail="NAS and Obsidian sync remain visible even when offline.",
        ),
        DashboardCard(
            id="agents",
            title="Agent Collaboration",
            status=_status_for_services(
                {"agent_node"},
                service_statuses_by_type.get("agent_node", set()),
            ),
            count=sum(service.type == "agent_node" for service in services),
            detail="OpenClaw and Hermes are placeholders until registered.",
        ),
        DashboardCard(
            id="evidence",
            title="Evidence",
            status="evidence_gap" if evidence_summary.blocked_count else "ready",
            count=evidence_summary.total,
            detail=f"{evidence_summary.blocked_count} evidence item(s) block readiness.",
        ),
        DashboardCard(
            id="security",
            title="Security Risk",
            status="security_blocked" if security_findings else "ready",
            count=len(security_findings),
            detail="Secret findings are redacted and block publish actions."
            if security_findings
            else "No secret findings.",
        ),
        DashboardCard(
            id="human_actions",
            title="Human Actions",
            status="needs_human_action" if human_actions else "ready",
            count=len(human_actions),
            detail=", ".join(human_actions) if human_actions else "No manual action required.",
        ),
    ]
    overall_status = "blocked" if any(
        card.status in {"security_blocked", "evidence_gap"} for card in cards
    ) else "ready"
    return DashboardSummary(
        overall_status=overall_status,
        human_actions=human_actions,
        cards=cards,
    )


def create_dashboard_router(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

    @router.get("/summary", response_model=DashboardSummary)
    def summary() -> DashboardSummary:
        return build_dashboard_summary(config_path, devices_config_path, services_config_path)

    return router
