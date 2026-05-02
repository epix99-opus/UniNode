from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from uninode.config_status import DEFAULT_CONFIG_PATH
from uninode.devices import DEFAULT_DEVICES_CONFIG_PATH, load_devices
from uninode.evidence import Evidence, scan_evidence
from uninode.security import scan_security_findings


class GateEvaluateRequest(BaseModel):
    action_type: str = "readonly"


class GateResult(BaseModel):
    id: str
    label: str
    status: str
    detail: str


class GateEvaluation(BaseModel):
    action_type: str
    allowed: bool
    gates: list[GateResult]


def _has_evidence(evidence: list[Evidence], evidence_type: str) -> bool:
    return any(item.type == evidence_type for item in evidence)


def _gate(
    gate_id: str,
    label: str,
    failed: bool,
    detail: str,
    warn: bool = False,
) -> GateResult:
    status = "fail" if failed else "warn" if warn else "pass"
    return GateResult(id=gate_id, label=label, status=status, detail=detail)


def evaluate_gates(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    action_type: str = "readonly",
) -> GateEvaluation:
    evidence = scan_evidence(config_path)
    findings = scan_security_findings(config_path)
    devices = load_devices(config_path, devices_config_path)
    expected_offline = [
        device
        for device in devices
        if device.status == "needs_human_power_on"
    ]

    gates = [
        _gate(
            "no_invalid_json",
            "No invalid JSON evidence",
            any(item.validity == "invalid_json" for item in evidence),
            "Invalid JSON evidence blocks readiness.",
        ),
        _gate(
            "no_na_fields",
            "No NA fields in bench evidence",
            any(item.validity == "invalid" and item.type == "bench_json" for item in evidence),
            "NA bench values block readiness.",
        ),
        _gate(
            "mobile_has_valid_samples",
            "Mobile compare has valid samples",
            any("mobile_insufficient_data" in item.blockers for item in evidence)
            or not _has_evidence(evidence, "mobile_compare_json"),
            "Mobile insufficient_data blocks readiness.",
        ),
        _gate(
            "subscription_live_hits_present",
            "Subscription live hits are present",
            any(item.validity == "template_only" and item.type == "subscription_hit" for item in evidence)
            or not _has_evidence(evidence, "subscription_hit"),
            "Template-only subscription hits are not live evidence.",
        ),
        _gate(
            "fingerprint_non_empty",
            "Fingerprint is non-empty",
            any("empty_fingerprint" in item.blockers for item in evidence)
            or not _has_evidence(evidence, "fingerprint"),
            "Empty SHA-256 fingerprints block readiness.",
        ),
        _gate(
            "secret_scan_pass",
            "Secret scan passes",
            bool(findings),
            "Secret findings block publish and execution.",
        ),
    ]

    needs_device_online = action_type not in {"readonly", "dry_run"}
    gates.append(
        _gate(
            "device_offline_policy",
            "Device offline policy",
            bool(expected_offline) and needs_device_online,
            "Expected-offline devices require human power-on before execution.",
            warn=bool(expected_offline) and not needs_device_online,
        )
    )
    allowed = not any(gate.status == "fail" for gate in gates)
    return GateEvaluation(action_type=action_type, allowed=allowed, gates=gates)


def create_gates_router(
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
) -> APIRouter:
    router = APIRouter(prefix="/api/gates", tags=["gates"])

    @router.post("/evaluate", response_model=GateEvaluation)
    def evaluate(request: GateEvaluateRequest) -> GateEvaluation:
        return evaluate_gates(config_path, devices_config_path, request.action_type)

    return router
