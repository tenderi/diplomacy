"""
API route modules.

This package contains route modules organized by functionality:
- games: Game management endpoints
- orders: Order submission and retrieval
- users: User registration and session management
- messages: Private and broadcast messaging
- maps: Map image generation
- admin: Administrative endpoints
- dashboard: Dashboard API endpoints
"""
from . import games, orders, users, messages, maps, admin, dashboard, channels

__all__ = ["games", "orders", "users", "messages", "maps", "admin", "dashboard", "channels"]
