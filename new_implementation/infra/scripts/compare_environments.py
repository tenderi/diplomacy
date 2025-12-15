#!/usr/bin/env python3
"""
Environment comparison tool for local vs remote environments.

This script compares the local development environment with a remote server
environment to detect differences that could cause deployment issues.
"""
import json
import os
import sys
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path


def get_python_version() -> str:
    """Get Python version."""
    return sys.version.split()[0]


def get_pip_packages() -> Dict[str, str]:
    """Get installed pip packages."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True
        )
        packages = json.loads(result.stdout)
        return {pkg["name"]: pkg["version"] for pkg in packages}
    except Exception as e:
        return {"error": str(e)}


def get_environment_variables() -> Dict[str, str]:
    """Get relevant environment variables."""
    relevant_vars = [
        "PYTHONPATH",
        "DIPLOMACY_MAP_PATH",
        "SQLALCHEMY_DATABASE_URL",
        "TELEGRAM_BOT_TOKEN",
        "PATH",
        "HOME",
        "USER",
    ]
    env_vars = {}
    for var in relevant_vars:
        value = os.environ.get(var)
        if value:
            # Sanitize sensitive values
            if "PASSWORD" in var or "TOKEN" in var or "SECRET" in var:
                env_vars[var] = "***REDACTED***"
            else:
                env_vars[var] = value
    return env_vars


def check_file_system_paths(base_path: str) -> Dict[str, Any]:
    """Check file system paths and permissions."""
    base = Path(base_path)
    checks = {
        "base_path": str(base.absolute()),
        "exists": base.exists(),
        "is_directory": base.is_dir() if base.exists() else False,
        "readable": os.access(base, os.R_OK) if base.exists() else False,
        "writable": os.access(base, os.W_OK) if base.exists() else False,
    }
    
    # Check important subdirectories
    important_dirs = ["src", "maps", "test_maps", "examples", "alembic"]
    subdirs = {}
    for dirname in important_dirs:
        dirpath = base / dirname
        subdirs[dirname] = {
            "exists": dirpath.exists(),
            "is_directory": dirpath.is_dir() if dirpath.exists() else False,
            "readable": os.access(dirpath, os.R_OK) if dirpath.exists() else False,
        }
    checks["subdirectories"] = subdirs
    
    # Check important files
    important_files = [
        "requirements.txt",
        "alembic.ini",
        "maps/standard.svg",
        "maps/v2.svg",
        "examples/demo_perfect_game.py",
    ]
    files = {}
    for filename in important_files:
        filepath = base / filename
        files[filename] = {
            "exists": filepath.exists(),
            "readable": os.access(filepath, os.R_OK) if filepath.exists() else False,
            "size": filepath.stat().st_size if filepath.exists() else 0,
        }
    checks["files"] = files
    
    return checks


def get_database_info() -> Dict[str, Any]:
    """Get database connection info (without sensitive data)."""
    db_url = os.environ.get("SQLALCHEMY_DATABASE_URL", "")
    if not db_url:
        return {"status": "not_configured"}
    
    # Parse connection string (sanitized)
    info = {"status": "configured"}
    if "postgresql" in db_url:
        # Extract non-sensitive parts
        if "@" in db_url:
            parts = db_url.split("@")
            if len(parts) > 1:
                host_part = parts[1].split("/")
                if len(host_part) > 0:
                    host_port = host_part[0].split(":")
                    info["host"] = host_port[0] if len(host_port) > 0 else "unknown"
                    info["port"] = host_port[1] if len(host_port) > 1 else "5432"
                if len(host_part) > 1:
                    info["database"] = host_part[1].split("?")[0]
    return info


def collect_local_environment(base_path: Optional[str] = None) -> Dict[str, Any]:
    """Collect local environment information."""
    if base_path is None:
        # Try to find project root
        script_dir = Path(__file__).parent
        base_path = script_dir.parent.parent.parent  # Go up from infra/scripts/
    
    return {
        "python_version": get_python_version(),
        "pip_packages": get_pip_packages(),
        "environment_variables": get_environment_variables(),
        "file_system": check_file_system_paths(str(base_path)),
        "database": get_database_info(),
        "working_directory": str(Path.cwd()),
    }


def compare_environments(local: Dict[str, Any], remote: Dict[str, Any]) -> Dict[str, Any]:
    """Compare local and remote environments."""
    differences = {
        "python_version": {
            "local": local.get("python_version"),
            "remote": remote.get("python_version"),
            "match": local.get("python_version") == remote.get("python_version"),
        },
        "pip_packages": {
            "local_count": len(local.get("pip_packages", {})),
            "remote_count": len(remote.get("pip_packages", {})),
            "missing_in_remote": [],
            "version_mismatches": [],
        },
        "file_system": {
            "base_path_match": local.get("file_system", {}).get("base_path") == remote.get("file_system", {}).get("base_path"),
            "missing_directories": [],
            "missing_files": [],
            "permission_issues": [],
        },
        "environment_variables": {
            "missing_in_remote": [],
            "different_values": [],
        },
    }
    
    # Compare pip packages
    local_packages = local.get("pip_packages", {})
    remote_packages = remote.get("pip_packages", {})
    
    for pkg_name, local_version in local_packages.items():
        if pkg_name == "error":
            continue
        if pkg_name not in remote_packages:
            differences["pip_packages"]["missing_in_remote"].append(pkg_name)
        elif remote_packages[pkg_name] != local_version:
            differences["pip_packages"]["version_mismatches"].append({
                "package": pkg_name,
                "local": local_version,
                "remote": remote_packages[pkg_name],
            })
    
    # Compare file system
    local_fs = local.get("file_system", {})
    remote_fs = remote.get("file_system", {})
    
    local_subdirs = local_fs.get("subdirectories", {})
    remote_subdirs = remote_fs.get("subdirectories", {})
    
    for dirname in local_subdirs:
        if dirname not in remote_subdirs:
            differences["file_system"]["missing_directories"].append(dirname)
        elif not remote_subdirs[dirname].get("exists"):
            differences["file_system"]["missing_directories"].append(dirname)
    
    local_files = local_fs.get("files", {})
    remote_files = remote_fs.get("files", {})
    
    for filename in local_files:
        if filename not in remote_files:
            differences["file_system"]["missing_files"].append(filename)
        elif not remote_files[filename].get("exists"):
            differences["file_system"]["missing_files"].append(filename)
    
    # Compare environment variables
    local_env = local.get("environment_variables", {})
    remote_env = remote.get("environment_variables", {})
    
    for var_name in local_env:
        if var_name not in remote_env:
            differences["environment_variables"]["missing_in_remote"].append(var_name)
        elif local_env[var_name] != remote_env[var_name]:
            differences["environment_variables"]["different_values"].append(var_name)
    
    return differences


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare local and remote environments")
    parser.add_argument("--remote-json", help="Path to remote environment JSON file")
    parser.add_argument("--output", help="Output file for comparison results")
    parser.add_argument("--base-path", help="Base path for local environment")
    
    args = parser.parse_args()
    
    # Collect local environment
    print("Collecting local environment...")
    local_env = collect_local_environment(args.base_path)
    
    if args.remote_json:
        # Load remote environment from file
        with open(args.remote_json, "r") as f:
            remote_env = json.load(f)
    else:
        # Just output local environment
        remote_env = None
    
    if remote_env:
        # Compare environments
        print("Comparing environments...")
        differences = compare_environments(local_env, remote_env)
        
        output = {
            "local": local_env,
            "remote": remote_env,
            "differences": differences,
        }
    else:
        output = {
            "local": local_env,
        }
    
    # Output results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"Results written to {args.output}")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

