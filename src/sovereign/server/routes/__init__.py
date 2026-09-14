"""
src/sovereign/server/routes/__init__.py
REST API routes package for the Sovereign server.
"""
from sovereign.server.routes.tasks import router as tasks_router
from sovereign.server.routes.models import router as models_router
from sovereign.server.routes.network import router as network_router
from sovereign.server.routes.audit import router as audit_router
from sovereign.server.routes.preview import router as preview_router
from sovereign.server.routes.demos import router as demos_router

__all__ = [
    "tasks_router",
    "models_router",
    "network_router",
    "audit_router",
    "preview_router",
    "demos_router",
]
