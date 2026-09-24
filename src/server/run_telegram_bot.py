#!/usr/bin/env python3
"""
Wrapper script to run the telegram bot with proper Python path setup.

This ensures the `src/` directory is on sys.path (equivalent to setting
PYTHONPATH=src) before delegating to the `server.telegram_bot` package's
__main__ entry point, exactly as `python -m server.telegram_bot` would.
"""
import os
import runpy
import sys

# Add the src directory to Python path to ensure package imports work,
# in case PYTHONPATH wasn't already set by the caller.
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

runpy.run_module("server.telegram_bot", run_name="__main__")
