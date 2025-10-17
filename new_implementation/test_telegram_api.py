#!/usr/bin/env python3
"""
Test script for Telegram bot functionality via direct API calls.

This script demonstrates how to test all the Telegram bot features
using the REST API endpoints without needing an actual Telegram bot.

Usage:
    python test_telegram_api.py

Prerequisites:
    1. Start the API server: python -m server.api
    2. Ensure PostgreSQL is running
    3. Set DIPLOMACY_API_URL environment variable if needed
"""

import requests
import json
import time
import os
from typing import Dict, Any, List

# Configuration
API_BASE_URL = os.environ.get("DIPLOMACY_API_URL", "http://localhost:8000")
NOTIFY_API_URL = os.environ.get("DIPLOMACY_NOTIFY_URL", "http://localhost:8081")

# Test user data
TEST_TELEGRAM_ID = "123456789"
TEST_USER_NAME = "Test User"
TEST_GAME_ID = None  # Will be set after game creation

def make_request(method: str, endpoint: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Make HTTP request and return JSON response."""
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url)
        elif method.upper() == "POST":
            response = requests.post(url, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"   Error details: {error_detail}")
            except:
                print(f"   Response text: {e.response.text}")
        return {"status": "error", "detail": str(e)}

def test_user_registration() -> bool:
    """Test user registration endpoints."""
    print("\n🔐 Testing User Registration...")
    
    # Test persistent user registration
    result = make_request("POST", "/users/persistent_register", {
        "telegram_id": TEST_TELEGRAM_ID,
        "full_name": TEST_USER_NAME
    })
    
    if result.get("status") == "ok":
        print("✅ Persistent user registration successful")
    else:
        print(f"❌ Persistent user registration failed: {result}")
        return False
    
    # Test in-memory user registration
    result = make_request("POST", "/users/register", {
        "telegram_id": TEST_TELEGRAM_ID,
        "full_name": TEST_USER_NAME
    })
    
    if result.get("status") == "ok":
        print("✅ In-memory user registration successful")
    else:
        print(f"❌ In-memory user registration failed: {result}")
        return False
    
    # Test getting user info
    result = make_request("GET", f"/users/{TEST_TELEGRAM_ID}")
    
    if result.get("status") == "ok":
        print("✅ User info retrieval successful")
        print(f"   User data: {result}")
    else:
        print(f"❌ User info retrieval failed: {result}")
        return False
    
    return True

def test_game_management() -> bool:
    """Test game creation and management."""
    print("\n🎮 Testing Game Management...")
    
    global TEST_GAME_ID
    
    # Create a new game
    result = make_request("POST", "/games/create", {
        "map_name": "standard"
    })
    
    if result.get("status") == "ok":
        TEST_GAME_ID = result.get("game_id")
        print(f"✅ Game creation successful: {TEST_GAME_ID}")
    else:
        print(f"❌ Game creation failed: {result}")
        return False
    
    # Join the game as France
    result = make_request("POST", f"/games/{TEST_GAME_ID}/join", {
        "telegram_id": TEST_TELEGRAM_ID,
        "game_id": int(TEST_GAME_ID),
        "power": "FRANCE"
    })
    
    if result.get("status") == "ok":
        print("✅ Game join successful")
    else:
        print(f"❌ Game join failed: {result}")
        return False
    
    # Get game players
    result = make_request("GET", f"/games/{TEST_GAME_ID}/players")
    
    if result.get("status") == "ok":
        print("✅ Game players retrieval successful")
        print(f"   Players: {result}")
    else:
        print(f"❌ Game players retrieval failed: {result}")
        return False
    
    # Get game state
    result = make_request("GET", f"/games/{TEST_GAME_ID}/state")
    
    if result.get("status") == "ok":
        print("✅ Game state retrieval successful")
        state = result.get("state", {})
        print(f"   Phase: {state.get('phase', 'unknown')}")
        print(f"   Turn: {state.get('turn', 'unknown')}")
    else:
        print(f"❌ Game state retrieval failed: {result}")
        return False
    
    return True

def test_order_submission() -> bool:
    """Test order submission and management."""
    print("\n📝 Testing Order Submission...")
    
    if not TEST_GAME_ID:
        print("❌ No game ID available for order testing")
        return False
    
    # Submit orders for France
    orders = [
        "A PAR - BUR",
        "A MAR H",
        "F BRE - ENG"
    ]
    
    result = make_request("POST", "/games/set_orders", {
        "game_id": TEST_GAME_ID,
        "power": "FRANCE",
        "orders": orders,
        "telegram_id": TEST_TELEGRAM_ID
    })
    
    if result.get("status") == "ok":
        print("✅ Order submission successful")
    else:
        print(f"❌ Order submission failed: {result}")
        return False
    
    # Get orders for the game
    result = make_request("GET", f"/games/{TEST_GAME_ID}/orders")
    
    if result.get("status") == "ok":
        print("✅ Game orders retrieval successful")
        orders_data = result.get("orders", {})
        print(f"   Orders: {orders_data}")
    else:
        print(f"❌ Game orders retrieval failed: {result}")
        return False
    
    # Get orders for specific power
    result = make_request("GET", f"/games/{TEST_GAME_ID}/orders/FRANCE")
    
    if result.get("status") == "ok":
        print("✅ Power orders retrieval successful")
        power_orders = result.get("orders", [])
        print(f"   France orders: {power_orders}")
    else:
        print(f"❌ Power orders retrieval failed: {result}")
        return False
    
    return True

def test_messaging() -> bool:
    """Test messaging functionality."""
    print("\n💬 Testing Messaging...")
    
    if not TEST_GAME_ID:
        print("❌ No game ID available for messaging testing")
        return False
    
    # Send a private message (to self for testing)
    result = make_request("POST", f"/games/{TEST_GAME_ID}/message", {
        "telegram_id": TEST_TELEGRAM_ID,
        "recipient_power": "FRANCE",
        "text": "Test private message"
    })
    
    if result.get("status") == "ok":
        print("✅ Private message sent successfully")
    else:
        print(f"❌ Private message failed: {result}")
        return False
    
    # Send a broadcast message
    result = make_request("POST", f"/games/{TEST_GAME_ID}/broadcast", {
        "telegram_id": TEST_TELEGRAM_ID,
        "text": "Test broadcast message to all players"
    })
    
    if result.get("status") == "ok":
        print("✅ Broadcast message sent successfully")
    else:
        print(f"❌ Broadcast message failed: {result}")
        return False
    
    # Get messages for the game
    result = make_request("GET", f"/games/{TEST_GAME_ID}/messages")
    
    if result.get("status") == "ok":
        print("✅ Game messages retrieval successful")
        messages = result.get("messages", [])
        print(f"   Messages count: {len(messages)}")
    else:
        print(f"❌ Game messages retrieval failed: {result}")
        return False
    
    return True

def test_notification_api() -> bool:
    """Test the notification API endpoint."""
    print("\n🔔 Testing Notification API...")
    
    # Test notification endpoint
    notify_data = {
        "telegram_id": int(TEST_TELEGRAM_ID),
        "message": "Test notification from API"
    }
    
    try:
        response = requests.post(f"{NOTIFY_API_URL}/notify", json=notify_data)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "ok":
            print("✅ Notification API test successful")
            return True
        else:
            print(f"❌ Notification API test failed: {result}")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Notification API request failed: {e}")
        print("   Note: This requires the notification server to be running on port 8081")
        return False

def test_user_games() -> bool:
    """Test user games listing."""
    print("\n👤 Testing User Games...")
    
    # Get games for the user
    result = make_request("GET", f"/users/{TEST_TELEGRAM_ID}/games")
    
    if result.get("status") == "ok":
        print("✅ User games retrieval successful")
        games = result.get("games", [])
        print(f"   User is in {len(games)} games")
        return True
    else:
        print(f"❌ User games retrieval failed: {result}")
        return False

def test_order_history() -> bool:
    """Test order history functionality."""
    print("\n📚 Testing Order History...")
    
    if not TEST_GAME_ID:
        print("❌ No game ID available for order history testing")
        return False
    
    # Get order history
    result = make_request("GET", f"/games/{TEST_GAME_ID}/orders/history")
    
    if result.get("status") == "ok":
        print("✅ Order history retrieval successful")
        history = result.get("history", {})
        print(f"   History entries: {len(history)}")
        return True
    else:
        print(f"❌ Order history retrieval failed: {result}")
        return False

def test_health_endpoints() -> bool:
    """Test health and status endpoints."""
    print("\n🏥 Testing Health Endpoints...")
    
    # Test health endpoint
    result = make_request("GET", "/health")
    
    if result.get("status") == "ok":
        print("✅ Health check successful")
    else:
        print(f"❌ Health check failed: {result}")
        return False
    
    # Test scheduler status
    result = make_request("GET", "/scheduler/status")
    
    if result.get("status") == "ok":
        print("✅ Scheduler status check successful")
        return True
    else:
        print(f"❌ Scheduler status check failed: {result}")
        return False

def main():
    """Run all API tests."""
    print("🚀 Starting Telegram Bot API Tests")
    print(f"   API Base URL: {API_BASE_URL}")
    print(f"   Notify API URL: {NOTIFY_API_URL}")
    print(f"   Test Telegram ID: {TEST_TELEGRAM_ID}")
    
    # Test results
    tests = [
        ("User Registration", test_user_registration),
        ("Game Management", test_game_management),
        ("Order Submission", test_order_submission),
        ("Messaging", test_messaging),
        ("User Games", test_user_games),
        ("Order History", test_order_history),
        ("Health Endpoints", test_health_endpoints),
        ("Notification API", test_notification_api),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Telegram bot API is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print(f"\n💡 To test with a real Telegram bot:")
    print(f"   1. Set TELEGRAM_BOT_TOKEN environment variable")
    print(f"   2. Run: python -m server.telegram_bot")
    print(f"   3. Start a conversation with your bot on Telegram")

if __name__ == "__main__":
    main()
