from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from uninode.agents import create_agents_router
from uninode.auth import create_auth_router
from uninode.config_status import DEFAULT_CONFIG_PATH, create_config_router
from uninode.console import router as console_router
from uninode.dashboard import create_dashboard_router
from uninode.devices import DEFAULT_DEVICES_CONFIG_PATH, create_devices_router
from uninode.evidence import create_evidence_router
from uninode.executor import DEFAULT_EXECUTOR_CONFIG_PATH, create_executor_router
from uninode.gates import create_gates_router
from uninode.jobs import DEFAULT_AUTOMATIONS_CONFIG_PATH, create_jobs_router
from uninode.reports import create_reports_router
from uninode.security import create_security_router
from uninode.services import DEFAULT_SERVICES_CONFIG_PATH, create_services_router
from uninode.storage import DEFAULT_DATABASE_PATH, initialize_database
from uninode.tailscale import DEFAULT_TAILSCALE_CONFIG_PATH, create_tailscale_router
from uninode.topology import DEFAULT_TOPOLOGY_CONFIG_PATH, create_topology_router


def create_app(
    database_path: Path = DEFAULT_DATABASE_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
    devices_config_path: Path = DEFAULT_DEVICES_CONFIG_PATH,
    services_config_path: Path = DEFAULT_SERVICES_CONFIG_PATH,
    topology_config_path: Path = DEFAULT_TOPOLOGY_CONFIG_PATH,
    automations_config_path: Path = DEFAULT_AUTOMATIONS_CONFIG_PATH,
    executor_config_path: Path = DEFAULT_EXECUTOR_CONFIG_PATH,
    tailscale_config_path: Path = DEFAULT_TAILSCALE_CONFIG_PATH,
) -> FastAPI:
    initialize_database(database_path)
    app = FastAPI(
        title="UniNode Ops Console API",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:43110", "http://localhost:43110"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "uninode-api",
        }

    app.include_router(create_auth_router(database_path))
    app.include_router(create_config_router(config_path))
    app.include_router(create_devices_router(config_path, devices_config_path))
    app.include_router(create_services_router(services_config_path))
    app.include_router(create_evidence_router(config_path))
    app.include_router(create_security_router(config_path))
    app.include_router(create_topology_router(topology_config_path))
    app.include_router(create_dashboard_router(config_path, devices_config_path, services_config_path))
    app.include_router(create_gates_router(config_path, devices_config_path))
    app.include_router(create_jobs_router(config_path, devices_config_path, automations_config_path))
    app.include_router(create_agents_router(config_path, devices_config_path, automations_config_path))
    app.include_router(create_reports_router(config_path, devices_config_path, services_config_path))
    app.include_router(create_executor_router(executor_config_path))
    app.include_router(create_tailscale_router(tailscale_config_path))
    app.include_router(console_router)
    return app


app = create_app()
