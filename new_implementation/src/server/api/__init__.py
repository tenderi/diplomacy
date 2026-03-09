"""
API route modules for Diplomacy server.

This package contains route modules organized by functionality:
- routes.games - Game management endpoints
- routes.orders - Order submission and retrieval
- routes.users - User management
- routes.messages - Messaging between players
- routes.admin - Administrative endpoints
- routes.maps - Map generation endpoints
- routes.dashboard - Dashboard API endpoints

The main FastAPI app is re-exported here for backward compatibility (lazy to avoid circular import).
"""
from .shared import deadline_scheduler, process_due_deadlines, ADMIN_TOKEN

__all__ = ["app", "deadline_scheduler", "process_due_deadlines", "ADMIN_TOKEN"]


def __getattr__(name: str):
    """Lazy import of app to avoid circular import with _api_module."""
    if name == "app":
        from .._api_module import app
        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
