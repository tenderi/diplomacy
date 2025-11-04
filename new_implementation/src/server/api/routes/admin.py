"""
Admin API routes.

This module contains all administrative endpoints for managing games, users, caches, and system status.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
import os

from ..shared import db_service, server, logger, ADMIN_TOKEN
from ...response_cache import get_cache_stats, clear_response_cache, invalidate_cache

router = APIRouter()

# --- Admin Endpoints ---
@router.post("/admin/delete_all_games")
def admin_delete_all_games() -> Dict[str, Any]:
    """Delete all games (admin only)"""
    try:
        # Count games before deletion
        games_count = db_service.get_game_count()
        
        # Delete all games and related data in correct order (respecting foreign key constraints)
        db_service.delete_all_orders()
        db_service.delete_all_game_snapshots()
        db_service.delete_all_players()
        db_service.delete_all_messages()
        db_service.delete_all_game_history()
        db_service.delete_all_games()
        
        # Note: We do NOT delete users - they should be preserved for future games
        db_service.commit()
        
        # Clear in-memory server games
        server.games.clear()
        
        return {
            "status": "ok", 
            "message": "All games deleted successfully",
            "deleted_count": games_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/games_count")
def admin_get_games_count() -> Dict[str, Any]:
    """Get count of active games (admin only)"""
    try:
        count = db_service.get_game_count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/users_count")
def admin_get_users_count() -> Dict[str, Any]:
    """Get count of registered users (admin only)"""
    try:
        count = db_service.get_user_count()
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/cleanup_old_maps")
def cleanup_old_maps() -> Dict[str, Any]:
    """Clean up map images older than 24 hours (admin only)"""
    try:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        old_snapshots = db_service.get_game_snapshots_with_old_map_images(cutoff_time)
        
        cleaned_count = 0
        for snapshot in old_snapshots:
            map_path = snapshot.map_image_path  # type: ignore
            if map_path and os.path.exists(map_path):
                try:
                    os.remove(map_path)
                    cleaned_count += 1
                except Exception as e:
                    logger.warning(f"Error removing {map_path}: {e}")
        
        return {
            "status": "ok",
            "message": f"Cleaned up {cleaned_count} old map images",
            "cleaned_count": cleaned_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/map_cache_stats")
def get_map_cache_stats() -> Dict[str, Any]:
    """Get map cache statistics for monitoring."""
    try:
        from engine.map import Map
        stats = Map.get_cache_stats()
        return {
            "status": "ok",
            "cache_stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/clear_map_cache")
def clear_map_cache() -> Dict[str, Any]:
    """Clear all cached maps."""
    try:
        from engine.map import Map
        Map.clear_map_cache()
        return {
            "status": "ok",
            "message": "Map cache cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/preload_maps")
def preload_common_maps() -> Dict[str, Any]:
    """Preload common map configurations for better performance."""
    try:
        from engine.map import Map
        Map.preload_common_maps()
        return {
            "status": "ok",
            "message": "Common maps preloaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/connection_pool_status")
def get_connection_pool_status() -> Dict[str, Any]:
    """Get database connection pool status for monitoring."""
    try:
        return {
            "status": "ok",
            "pool_status": "N/A (DAL-managed)",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/connection_pool_reset")
def reset_connection_pool() -> Dict[str, Any]:
    """Reset database connection pool (use with caution)."""
    try:
        return {
            "status": "ok",
            "message": "Connection pool reset (simulated)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/response_cache_stats")
def get_response_cache_stats() -> Dict[str, Any]:
    """Get response cache statistics for monitoring."""
    try:
        stats = get_cache_stats()
        return {
            "status": "ok",
            "cache_stats": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/clear_response_cache")
def clear_response_cache_endpoint() -> Dict[str, Any]:
    """Clear all cached API responses."""
    try:
        clear_response_cache()
        return {
            "status": "ok",
            "message": "Response cache cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/admin/invalidate_cache/{game_id}")
def invalidate_game_cache(game_id: str) -> Dict[str, Any]:
    """Invalidate all cache entries for a specific game."""
    try:
        invalidate_cache(f"games/{game_id}")
        return {
            "status": "ok",
            "message": f"Cache invalidated for game {game_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

