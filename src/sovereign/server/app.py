"""
src/sovereign/server/app.py
FastAPI application factory assembling all routes, middleware, WebSocket
endpoints, and static file serving.
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sovereign.server.config import HostHeaderMiddleware, ServerConfig
from sovereign.server.routes import (
    tasks_router,
    models_router,
    network_router,
    audit_router,
    preview_router,
    demos_router,
)
from sovereign.server.ws.trace import router as ws_trace_router
from sovereign.server.ws.network_stream import router as ws_network_router
from sovereign.server.ws.hitl_stream import router as ws_hitl_router
from sovereign.tools.schemas import UserRole

logger = logging.getLogger("sovereign.server.app")


def create_app(
    server_config: Optional[ServerConfig] = None,
    runtime=None,
    ledger=None,
    scheduler=None,
    policy_engine=None,
) -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.

    Args:
        server_config: Server binding and security configuration.
        runtime: AgentRuntime instance (optional, for task execution).
        ledger: AuditLedger instance (optional, for violation logging).
        scheduler: VRAMScheduler instance (optional, for VRAM metrics).
        policy_engine: NetworkPolicyEngine instance (optional).

    Returns:
        Configured FastAPI application instance.
    """
    if server_config is None:
        server_config = ServerConfig()

    app = FastAPI(
        title="Sovereign AI Workbench",
        description="Air-gapped industrial AI workbench API",
        version="0.1.0",
    )

    # Store shared state
    app.state.secret_key = server_config.secret_key
    if ledger is not None:
        app.state.audit_ledger = ledger
    if runtime is not None:
        app.state.runtime = runtime
    if scheduler is not None:
        app.state.scheduler = scheduler
    if policy_engine is not None:
        app.state.policy_engine = policy_engine

    # ── CORS Middleware ───────────────────────────────────────────────────
    # Restrict to localhost and intranet origins
    cors_origins = server_config.cors_origins or [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Host Header Middleware (DNS rebinding protection) ─────────────────
    app.add_middleware(
        HostHeaderMiddleware,
        allowed_hosts=server_config.allowed_hosts,
    )

    # ── REST API Routers ─────────────────────────────────────────────────
    app.include_router(tasks_router)
    app.include_router(models_router)
    app.include_router(network_router)
    app.include_router(audit_router)
    app.include_router(preview_router)
    app.include_router(demos_router)

    # ── WebSocket Routers ────────────────────────────────────────────────
    app.include_router(ws_trace_router)
    app.include_router(ws_network_router)
    app.include_router(ws_hitl_router)

    # ── Health and Identity Endpoints ────────────────────────────────────

    @app.get("/api/health", tags=["system"])
    async def health():
        """Service liveness check."""
        return {
            "status": "operational",
            "service": "Sovereign AI Workbench",
            "version": "0.1.0",
            "environment": "air-gap",
            "host": server_config.host,
        }

    @app.get("/api/me", tags=["system"])
    async def me(
        role: Optional[str] = None,
    ):
        """Return current user identity and role."""
        # In production, this reads from the auth middleware
        resolved_role = role or "auditor"
        try:
            user_role = UserRole(resolved_role)
        except ValueError:
            user_role = UserRole.AUDITOR

        return {
            "role": user_role.value,
            "permissions": {
                "can_submit_tasks": user_role in (UserRole.ADMIN, UserRole.ENGINEER),
                "can_approve_hitl": user_role in (UserRole.ADMIN, UserRole.ENGINEER),
                "can_register_models": user_role == UserRole.ADMIN,
                "can_view_audit": True,
                "can_view_network": True,
            },
        }

    # ── Static Files Mount & Root Route ──────────────────────────────────
    static_dir = server_config.static_dir
    if static_dir is None:
        static_dir = str(Path(__file__).parent / "static")

    static_path = Path(static_dir)
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

        @app.get("/", response_class=FileResponse, include_in_schema=False)
        async def root():
            index_path = static_path / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
            return {"message": "Sovereign AI Workbench API operational"}

    return app
