"""
Health check endpoints for the API server.

These endpoints provide information about the server's health status,
environment configuration, and system state.
"""
from fastapi import APIRouter
from typing import Dict, Any
import os
import sys
from pathlib import Path

router = APIRouter()


@router.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.
    
    Returns:
        Simple status indicating the API is running
    """
    return {
        "status": "ok",
        "service": "diplomacy-api"
    }


@router.get("/health/environment")
def environment_health() -> Dict[str, Any]:
    """
    Detailed environment health check.
    
    Returns:
        Dictionary containing:
        - Environment info (Python version, paths)
        - File system checks (map files, directories)
        - Database connectivity status
        - Configuration validation
    """
    result: Dict[str, Any] = {
        "status": "ok",
        "environment": {},
        "file_system": {},
        "configuration": {},
        "issues": []
    }
    
    # Environment info
    result["environment"] = {
        "python_version": sys.version.split()[0],
        "python_path": sys.executable,
        "working_directory": str(Path.cwd()),
        "pythonpath": os.environ.get("PYTHONPATH", "not set"),
    }
    
    # Find project root
    project_root = None
    possible_roots = [
        "/opt/diplomacy",
        Path(__file__).parent.parent.parent.parent,
        Path.cwd(),
    ]
    
    for root in possible_roots:
        root_path = Path(root).resolve()
        if root_path.exists() and root_path.is_dir():
            if (root_path / "src").exists() or (root_path / "requirements.txt").exists():
                project_root = root_path
                break
    
    if project_root:
        result["environment"]["project_root"] = str(project_root)
        
        # File system checks
        result["file_system"] = {
            "project_root_exists": True,
            "src_directory": {
                "exists": (project_root / "src").exists(),
                "readable": os.access(project_root / "src", os.R_OK) if (project_root / "src").exists() else False,
            },
            "maps_directory": {
                "exists": (project_root / "maps").exists(),
                "readable": os.access(project_root / "maps", os.R_OK) if (project_root / "maps").exists() else False,
            },
            "test_maps_directory": {
                "exists": (project_root / "test_maps").exists(),
                "writable": os.access(project_root / "test_maps", os.W_OK) if (project_root / "test_maps").exists() else False,
            },
            "map_files": {
                "standard_svg": {
                    "exists": (project_root / "maps" / "standard.svg").exists(),
                    "readable": os.access(project_root / "maps" / "standard.svg", os.R_OK) if (project_root / "maps" / "standard.svg").exists() else False,
                },
                "v2_svg": {
                    "exists": (project_root / "maps" / "v2.svg").exists(),
                    "readable": os.access(project_root / "maps" / "v2.svg", os.R_OK) if (project_root / "maps" / "v2.svg").exists() else False,
                },
            },
        }
        
        # Check for issues
        if not (project_root / "src").exists():
            result["issues"].append("src directory not found")
            result["status"] = "error"
        
        if not (project_root / "maps").exists():
            result["issues"].append("maps directory not found")
            result["status"] = "error"
        
        if not (project_root / "maps" / "standard.svg").exists():
            result["issues"].append("standard.svg map file not found")
            result["status"] = "error"
    else:
        result["file_system"]["project_root_exists"] = False
        result["issues"].append("Could not determine project root")
        result["status"] = "error"
    
    # Configuration checks
    result["configuration"] = {
        "sqlalchemy_database_url": "set" if os.environ.get("SQLALCHEMY_DATABASE_URL") else "not set",
        "telegram_bot_token": "set" if os.environ.get("TELEGRAM_BOT_TOKEN") else "not set",
        "diplomacy_map_path": os.environ.get("DIPLOMACY_MAP_PATH", "not set (using default)"),
    }
    
    # Database connectivity (try to import and check)
    try:
        from engine.database import db_service
        # Try to get a connection
        if hasattr(db_service, 'engine') and db_service.engine:
            result["database"] = {
                "status": "connected",
                "engine": str(type(db_service.engine).__name__),
            }
        else:
            result["database"] = {
                "status": "not_initialized",
            }
            result["issues"].append("Database engine not initialized")
    except Exception as e:
        result["database"] = {
            "status": "error",
            "error": str(e),
        }
        result["issues"].append(f"Database connection error: {e}")
        result["status"] = "error"
    
    return result

