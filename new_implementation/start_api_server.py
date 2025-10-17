#!/usr/bin/env python3
"""
Simple script to start the API server for testing Telegram bot functionality.

Usage:
    python start_api_server.py

This will start the FastAPI server on localhost:8000
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Start the API server."""
    # Add src to Python path
    project_root = Path(__file__).parent
    src_path = project_root / "src"
    
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    
    # Set environment variables
    os.environ["PYTHONPATH"] = f"{src_path}:{os.environ.get('PYTHONPATH', '')}"
    
    print("🚀 Starting Diplomacy API Server...")
    print(f"   Project root: {project_root}")
    print(f"   Source path: {src_path}")
    print(f"   Python path: {sys.path[0]}")
    
    try:
        # Start the API server
        subprocess.run([
            sys.executable, "-m", "server.api"
        ], cwd=str(src_path))
    
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
