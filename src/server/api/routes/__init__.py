"""
API route modules.

This package contains route modules organized by functionality:
- games: Game management endpoints
- orders: Order submission and retrieval
- users: User registration and session management
- messages: Private and broadcast messaging
- maps: Map image generation
- admin: Administrative endpoints
"""
from . import games, orders, users, messages, maps, admin, channels, tournaments

__all__ = ["games", "orders", "users", "messages", "maps", "admin", "channels", "tournaments"]
