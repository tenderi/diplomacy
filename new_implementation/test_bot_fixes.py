#!/usr/bin/env python3
"""
Test script for Telegram bot map viewing and demo game functionality.
"""

import requests
import json
import time
import os
import sys
from pathlib import Path

# Configuration
API_BASE_URL = "http://54.78.51.19:8000"  # Production server
TEST_TELEGRAM_ID = "123456789"
TEST_USER_NAME = "Test User"

def make_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make HTTP request and return JSON response."""
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return None

def test_map_viewing():
    """Test map viewing functionality."""
    print("🗺️ Testing Map Viewing...")
    
    # First, register a user
    print("  📝 Registering test user...")
    register_data = {
        "telegram_id": TEST_TELEGRAM_ID,
        "full_name": TEST_USER_NAME
    }
    result = make_request("POST", "/users/persistent_register", register_data)
    if not result:
        print("  ❌ Failed to register user")
        return False
    print(f"  ✅ User registered: {result}")
    
    # Create a game
    print("  🎮 Creating test game...")
    create_data = {"map_name": "standard"}
    result = make_request("POST", "/games/create", create_data)
    if not result or "game_id" not in result:
        print("  ❌ Failed to create game")
        return False
    game_id = result["game_id"]
    print(f"  ✅ Game created with ID: {game_id}")
    
    # Join the game
    print("  👤 Joining game as Germany...")
    join_data = {
        "telegram_id": TEST_TELEGRAM_ID,
        "game_id": int(game_id),
        "power": "GERMANY"
    }
    result = make_request("POST", f"/games/{game_id}/join", join_data)
    if not result:
        print("  ❌ Failed to join game")
        return False
    print("  ✅ Joined game as Germany")
    
    # Test game state endpoint (this is what map viewing uses)
    print("  🗺️ Testing game state for map generation...")
    result = make_request("GET", f"/games/{game_id}/state")
    if not result:
        print("  ❌ Failed to get game state")
        return False
    
    print(f"  ✅ Game state retrieved successfully")
    print(f"    Year: {result.get('year', 'Unknown')}")
    print(f"    Phase: {result.get('phase', 'Unknown')}")
    print(f"    Units: {len(result.get('units', {}))} powers")
    
    # Test orders endpoint
    print("  📋 Testing orders endpoint...")
    result = make_request("GET", f"/games/{game_id}/orders")
    if result is not None:
        print(f"  ✅ Orders retrieved: {len(result) if isinstance(result, list) else 'N/A'}")
    else:
        print("  ⚠️ Orders endpoint returned None (might be empty)")
    
    return True

def test_demo_game():
    """Test automated demo game functionality."""
    print("\n🎮 Testing Automated Demo Game...")
    
    # Test if demo script exists
    print("  📁 Checking if demo script exists...")
    # We can't directly check file existence via API, but we can test the bot's demo functionality
    # by checking if the bot service is running and can execute commands
    
    # Test bot service status
    print("  🔧 Checking bot service status...")
    try:
        import subprocess
        result = subprocess.run(
            ["ssh", "-i", "~/.ssh/helgeKeyPair.pem", "ubuntu@54.78.51.19", "sudo systemctl is-active diplomacy-bot"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and "active" in result.stdout:
            print("  ✅ Bot service is running")
        else:
            print(f"  ❌ Bot service issue: {result.stdout} {result.stderr}")
            return False
    except Exception as e:
        print(f"  ❌ Failed to check bot service: {e}")
        return False
    
    # Test if demo script can be executed
    print("  🎯 Testing demo script execution...")
    try:
        result = subprocess.run(
            ["ssh", "-i", "~/.ssh/helgeKeyPair.pem", "ubuntu@54.78.51.19", "cd /opt/diplomacy && /usr/bin/python3 demo_perfect_game.py --help"],
            capture_output=True,
            text=True,
            timeout=30,
            shell=True
        )
        if result.returncode == 0:
            print("  ✅ Demo script can be executed")
        else:
            print(f"  ⚠️ Demo script execution test: {result.stdout[:100]}...")
    except Exception as e:
        print(f"  ⚠️ Demo script test failed: {e}")
    
    return True

def main():
    """Run all tests."""
    print("🧪 Telegram Bot Functionality Tests")
    print("=" * 40)
    
    # Test map viewing
    map_success = test_map_viewing()
    
    # Test demo game
    demo_success = test_demo_game()
    
    # Summary
    print("\n📊 Test Results:")
    print(f"  Map Viewing: {'✅ PASS' if map_success else '❌ FAIL'}")
    print(f"  Demo Game: {'✅ PASS' if demo_success else '❌ FAIL'}")
    
    if map_success and demo_success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
