#!/usr/bin/env python3
"""
Wrapper script to run the telegram bot with proper Python path setup.
This ensures all imports work correctly, including relative imports.
"""
import sys
import os
import importlib
import importlib.util

# Add the src directory to Python path to ensure package imports work
src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Change to the server directory so imports work correctly
server_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(server_dir)

# CRITICAL: Ensure 'server' package is registered in sys.modules BEFORE loading any modules
# This is necessary so that when server.server is imported, Python knows 'server' is a package
# and relative imports (like 'from .errors import ...') will work
if 'server' not in sys.modules:
    # Create a minimal package module for 'server'
    server_pkg = importlib.util.module_from_spec(
        importlib.util.spec_from_file_location("server", os.path.join(server_dir, "__init__.py"))
    )
    server_pkg.__path__ = [server_dir]
    server_pkg.__package__ = 'server'
    sys.modules['server'] = server_pkg

# Ensure server.telegram_bot package (directory) is importable
# This is needed because telegram_bot.py imports from server.telegram_bot.config
try:
    importlib.import_module('server.telegram_bot')
except ImportError:
    # If it fails, that's okay - we'll try to load it anyway
    pass

# Now load telegram_bot.py as a module
telegram_bot_path = os.path.join(server_dir, "telegram_bot.py")
spec = importlib.util.spec_from_file_location("__main__", telegram_bot_path)
telegram_bot = importlib.util.module_from_spec(spec)

# Critical: Set __package__ so relative imports in imported modules (like server.server) work
telegram_bot.__package__ = 'server'
# Set __name__ to '__main__' so it behaves like a script
telegram_bot.__name__ = '__main__'

# Ensure that when server.server is imported, it knows server is a package
# Register it so Python treats it as part of the server package
if 'server.server' not in sys.modules:
    # Pre-import server.server to ensure it's loaded with proper package context
    # This ensures relative imports work
    try:
        importlib.import_module('server.server')
    except ImportError:
        # If direct import fails, we'll try loading it manually
        pass

# Don't register telegram_bot in sys.modules with a conflicting name
# Just execute it directly
spec.loader.exec_module(telegram_bot)

# Run main if it exists
if hasattr(telegram_bot, 'main'):
    telegram_bot.main()

