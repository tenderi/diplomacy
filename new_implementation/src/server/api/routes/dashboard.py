"""
Dashboard API routes.

This module contains endpoints for the admin dashboard, including service management,
database inspection, and logging.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import subprocess
import re
from datetime import datetime
from sqlalchemy import text

from ..shared import db_service

router = APIRouter()

# Allowed service names for security
ALLOWED_SERVICES = ["diplomacy", "diplomacy-bot"]

# Allowed database tables for dashboard
ALLOWED_TABLES = ["games", "players", "users", "orders", "messages", "game_snapshots", "turn_history"]

def _get_service_status(service_name: str) -> Dict[str, Any]:
    """Get status information for a systemd service."""
    if service_name not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service name: {service_name}")
    
    SYSTEMCTL_PATH = "/usr/bin/systemctl"
    SUDO_PATH = "/usr/bin/sudo"
    PATH_ENV = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin"}
    
    try:
        # Check if service is active
        result = subprocess.run(
            [SUDO_PATH, SYSTEMCTL_PATH, "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=5,
            env=PATH_ENV
        )
        is_active = result.stdout.strip() == "active" if result.returncode == 0 else False
        
        # Get detailed status
        status_result = subprocess.run(
            [SUDO_PATH, SYSTEMCTL_PATH, "status", service_name, "--no-pager", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            env=PATH_ENV
        )
        
        status_output = status_result.stdout
        active_since = None
        if is_active:
            since_match = re.search(r"Active:.*since (.+?)\n", status_output)
            if since_match:
                active_since = since_match.group(1).strip()
        
        return {
            "name": service_name,
            "status": "active" if is_active else "inactive",
            "is_active": is_active,
            "active_since": active_since,
            "status_output": status_output[:500] if status_output else ""
        }
    except subprocess.TimeoutExpired:
        return {
            "name": service_name,
            "status": "unknown",
            "is_active": False,
            "active_since": None,
            "error": "Timeout checking service status"
        }
    except Exception as e:
        return {
            "name": service_name,
            "status": "error",
            "is_active": False,
            "active_since": None,
            "error": str(e)
        }

class RestartServiceRequest:
    service: str

@router.get("/dashboard/api/services/status")
def get_services_status() -> Dict[str, Any]:
    """Get status of all managed services."""
    try:
        services = []
        for service_name in ALLOWED_SERVICES:
            services.append(_get_service_status(service_name))
        return {"services": services}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/dashboard/api/services/restart")
def restart_service(req: Dict[str, str]) -> Dict[str, Any]:
    """Restart a systemd service."""
    service_name = req.get("service")
    if not service_name or service_name not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service name: {service_name}. Allowed: {ALLOWED_SERVICES}")
    
    SYSTEMCTL_PATH = "/usr/bin/systemctl"
    SUDO_PATH = "/usr/bin/sudo"
    PATH_ENV = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin"}
    
    try:
        result = subprocess.run(
            [SUDO_PATH, SYSTEMCTL_PATH, "restart", service_name],
            capture_output=True,
            text=True,
            timeout=10,
            env=PATH_ENV
        )
        if result.returncode == 0:
            import time
            time.sleep(1)
            status = _get_service_status(service_name)
            return {
                "status": "ok",
                "service": service_name,
                "message": f"Service {service_name} restarted successfully",
                "service_status": status
            }
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to restart service: {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout restarting service")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/api/logs/{service}")
def get_service_logs(service: str, lines: int = 100) -> Dict[str, Any]:
    """Get logs for a systemd service."""
    if service not in ALLOWED_SERVICES:
        raise HTTPException(status_code=400, detail=f"Invalid service name: {service}")
    
    JOURNALCTL_PATH = "/usr/bin/journalctl"
    SUDO_PATH = "/usr/bin/sudo"
    PATH_ENV = {"PATH": "/usr/bin:/usr/sbin:/bin:/sbin"}
    
    try:
        lines = min(max(lines, 1), 1000)
        
        result = subprocess.run(
            [SUDO_PATH, JOURNALCTL_PATH, "-u", service, "--no-pager", "-n", str(lines)],
            capture_output=True,
            text=True,
            timeout=10,
            env=PATH_ENV
        )
        
        if result.returncode == 0:
            log_lines = result.stdout.strip().split('\n')
            return {
                "service": service,
                "lines": len(log_lines),
                "logs": log_lines
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to get logs: {result.stderr}")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Timeout getting logs")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/api/database/tables")
def get_database_tables() -> Dict[str, Any]:
    """Get list of all database tables."""
    try:
        session = db_service.session_factory()
        try:
            query = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            result = session.execute(query)
            tables = [row[0] for row in result] if result else []
            return {"tables": tables}
        finally:
            session.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/api/database/table/{table_name}")
def get_table_data(table_name: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    """Get data from a database table."""
    if table_name not in ALLOWED_TABLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid table name: {table_name}. Allowed: {ALLOWED_TABLES}"
        )
    
    limit = min(max(limit, 1), 1000)
    offset = max(offset, 0)
    
    try:
        session = db_service.session_factory()
        try:
            # Get table schema
            schema_query = text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = :table_name
                ORDER BY ordinal_position
            """)
            schema_result = session.execute(schema_query, {"table_name": table_name})
            columns = [
                {"name": row[0], "type": row[1], "nullable": row[2] == "YES"}
                for row in schema_result
            ]
            
            # Get row count
            count_query = text(f"SELECT COUNT(*) FROM {table_name}")
            count_result = session.execute(count_query)
            total_rows = count_result.scalar() if count_result else 0
            
            # Get table data
            data_query = text(f"SELECT * FROM {table_name} LIMIT :limit_val OFFSET :offset_val")
            data_result = session.execute(data_query, {"limit_val": limit, "offset_val": offset})
            
            # Convert rows to dicts
            rows = []
            if columns:
                column_names = [col["name"] for col in columns]
                for row in data_result:
                    row_dict = {}
                    for i, col_name in enumerate(column_names):
                        if i < len(row):
                            value = row[i]
                            if isinstance(value, datetime):
                                row_dict[col_name] = value.isoformat()
                            elif value is None:
                                row_dict[col_name] = None
                            else:
                                row_dict[col_name] = str(value)
                        else:
                            row_dict[col_name] = None
                    rows.append(row_dict)
            
            return {
                "table_name": table_name,
                "columns": columns,
                "total_rows": total_rows,
                "limit": limit,
                "offset": offset,
                "rows": rows
            }
        finally:
            session.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/dashboard/api/database/stats")
def get_database_stats() -> Dict[str, Any]:
    """Get database statistics."""
    try:
        session = db_service.session_factory()
        try:
            stats: Dict[str, Any] = {}
            
            # Total games
            games_query = text("SELECT COUNT(*) FROM games")
            games_result = session.execute(games_query)
            stats["total_games"] = games_result.scalar() or 0
            
            # Active games
            active_query = text("SELECT COUNT(*) FROM games WHERE status = 'active'")
            active_result = session.execute(active_query)
            stats["active_games"] = active_result.scalar() or 0
            
            # Total players
            players_query = text("SELECT COUNT(*) FROM players")
            players_result = session.execute(players_query)
            stats["total_players"] = players_result.scalar() or 0
            
            # Total users
            users_query = text("SELECT COUNT(*) FROM users")
            users_result = session.execute(users_query)
            stats["total_users"] = users_result.scalar() or 0
            
            # Total orders
            orders_query = text("SELECT COUNT(*) FROM orders")
            orders_result = session.execute(orders_query)
            stats["total_orders"] = orders_result.scalar() or 0
            
            # Recent activity
            recent_query = text("""
                SELECT COUNT(*) FROM games 
                WHERE updated_at > NOW() - INTERVAL '24 hours'
            """)
            recent_result = session.execute(recent_query)
            stats["recent_activity"] = recent_result.scalar() or 0
            
            return stats
        finally:
            session.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

