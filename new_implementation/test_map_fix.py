#!/usr/bin/env python3
"""
Simple test to verify map generation fix
"""

import os
import sys

print("Testing map generation fix...")

# Test 1: Check if the fixed SVG file exists
svg_path = "maps/standard_fixed.svg"
if os.path.exists(svg_path):
    print(f"✅ {svg_path} exists")
else:
    print(f"❌ {svg_path} not found")
    sys.exit(1)

# Test 2: Check if the telegram bot changes are in place
telegram_bot_path = "src/server/telegram_bot.py"
if os.path.exists(telegram_bot_path):
    with open(telegram_bot_path, 'r') as f:
        content = f.read()
        if "standard_fixed.svg" in content:
            print("✅ Telegram bot updated to use standard_fixed.svg")
        else:
            print("❌ Telegram bot not updated")
else:
    print(f"❌ {telegram_bot_path} not found")

# Test 3: Check if the environment variable configuration is in place
if "DIPLOMACY_MAP_PATH" in content:
    print("✅ Environment variable configuration added")
else:
    print("❌ Environment variable configuration missing")

print("\nMap generation fix verification complete!") 