#!/usr/bin/env python3
"""
Comprehensive test script for Telegram bot functionality via direct API calls.

This script demonstrates how to test all the Telegram bot features
using the REST API endpoints without needing an actual Telegram bot.

Usage:
    python test_telegram_bot_comprehensive.py

Prerequisites:
    1. Start the API server: python start_api_server.py
    2. Ensure PostgreSQL is running
    3. Set DIPLOMACY_API_URL environment variable if needed

Features tested:
    - User registration and management
    - Game creation and joining
    - Order submission and validation
    - Messaging system
    - Order history and game state
    - Health endpoints
    - Notification system
"""

import requests
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

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

def test_server_connection() -> bool:
    """Test if the API server is running."""
    print("🔌 Testing Server Connection...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API server is running and accessible")
            return True
        else:
            print(f"❌ API server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API server: {e}")
        print(f"   Make sure the server is running on {API_BASE_URL}")
        print(f"   Start it with: python start_api_server.py")
        return False

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
        user_data = result.get("user", {})
        print(f"   User: {user_data.get('full_name', 'Unknown')}")
        print(f"   Games: {len(user_data.get('games', []))}")
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
        players = result.get("players", [])
        print(f"   Players: {len(players)}")
        for player in players:
            print(f"     - {player.get('power', 'Unknown')}: {player.get('telegram_id', 'Unknown')}")
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
        print(f"   Year: {state.get('year', 'unknown')}")
        print(f"   Season: {state.get('season', 'unknown')}")
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
        print(f"   Submitted {len(orders)} orders")
    else:
        print(f"❌ Order submission failed: {result}")
        return False
    
    # Get orders for the game
    result = make_request("GET", f"/games/{TEST_GAME_ID}/orders")
    
    if result.get("status") == "ok":
        print("✅ Game orders retrieval successful")
        orders_data = result.get("orders", {})
        print(f"   Total orders: {len(orders_data)}")
        for power, power_orders in orders_data.items():
            print(f"     {power}: {len(power_orders)} orders")
    else:
        print(f"❌ Game orders retrieval failed: {result}")
        return False
    
    # Get orders for specific power
    result = make_request("GET", f"/games/{TEST_GAME_ID}/orders/FRANCE")
    
    if result.get("status") == "ok":
        print("✅ Power orders retrieval successful")
        power_orders = result.get("orders", [])
        print(f"   France orders: {len(power_orders)}")
        for order in power_orders:
            print(f"     - {order}")
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
        "text": "Test private message from API"
    })
    
    if result.get("status") == "ok":
        print("✅ Private message sent successfully")
    else:
        print(f"❌ Private message failed: {result}")
        return False
    
    # Send a broadcast message
    result = make_request("POST", f"/games/{TEST_GAME_ID}/broadcast", {
        "telegram_id": TEST_TELEGRAM_ID,
        "text": "Test broadcast message to all players from API"
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
        for msg in messages[-2:]:  # Show last 2 messages
            print(f"     - {msg.get('sender_power', 'Unknown')}: {msg.get('text', 'No text')[:50]}...")
    else:
        print(f"❌ Game messages retrieval failed: {result}")
        return False
    
    return True

def test_user_games() -> bool:
    """Test user games listing."""
    print("\n👤 Testing User Games...")
    
    # Get games for the user
    result = make_request("GET", f"/users/{TEST_TELEGRAM_ID}/games")
    
    if result.get("status") == "ok":
        print("✅ User games retrieval successful")
        games = result.get("games", [])
        print(f"   User is in {len(games)} games")
        for game in games:
            print(f"     - Game {game.get('game_id', 'Unknown')}: {game.get('power', 'Unknown')}")
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
        health_data = result.get("health", {})
        print(f"   Status: {health_data.get('status', 'unknown')}")
    else:
        print(f"❌ Health check failed: {result}")
        return False
    
    # Test scheduler status
    result = make_request("GET", "/scheduler/status")
    
    if result.get("status") == "ok":
        print("✅ Scheduler status check successful")
        scheduler_data = result.get("scheduler", {})
        print(f"   Status: {scheduler_data.get('status', 'unknown')}")
        return True
    else:
        print(f"❌ Scheduler status check failed: {result}")
        return False

def test_notification_api() -> bool:
    """Test the notification API endpoint."""
    print("\n🔔 Testing Notification API...")
    
    # Test notification endpoint
    notify_data = {
        "telegram_id": int(TEST_TELEGRAM_ID),
        "message": "Test notification from API - Telegram bot functionality working!"
    }
    
    try:
        response = requests.post(f"{NOTIFY_API_URL}/notify", json=notify_data, timeout=5)
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "ok":
            print("✅ Notification API test successful")
            print("   Note: This would send a message to the Telegram bot if it's running")
            return True
        else:
            print(f"❌ Notification API test failed: {result}")
            return False
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Notification API request failed: {e}")
        print("   Note: This requires the notification server to be running on port 8081")
        print("   Start it with: python -m server.telegram_bot")
        return False

def test_order_normalization():
    """Test order normalization functionality."""
    print("\n🔧 Testing Order Normalization...")
    
    try:
        from server.telegram_bot import normalize_order_provinces
        
        test_cases = [
            ("A PAR - BUR", "A PAR - BUR"),
            ("FRANCE A PAR - BUR", "A PAR - BUR"),
            ("ENGLAND F LON - ENG", "ENGLAND F LON - ENG"),  # Different power
            ("BUILD A PAR", "BUILD A PAR"),
            ("FRANCE BUILD A PAR", "BUILD A PAR"),
        ]
        
        passed = 0
        for input_order, expected in test_cases:
            result = normalize_order_provinces(input_order, "FRANCE")
            status = "✅" if result == expected else "❌"
            print(f"   {status} '{input_order}' → '{result}' (Expected: '{expected}')")
            if result == expected:
                passed += 1
        
        print(f"   📊 Order normalization: {passed}/{len(test_cases)} tests passed")
        return passed == len(test_cases)
    
    except ImportError as e:
        print(f"❌ Could not import normalize_order_provinces: {e}")
        return False

def main():
    """Run all API tests."""
    print("🚀 Starting Comprehensive Telegram Bot API Tests")
    print("=" * 60)
    print(f"   API Base URL: {API_BASE_URL}")
    print(f"   Notify API URL: {NOTIFY_API_URL}")
    print(f"   Test Telegram ID: {TEST_TELEGRAM_ID}")
    print("=" * 60)
    
    # Test results
    tests = [
        ("Server Connection", test_server_connection),
        ("User Registration", test_user_registration),
        ("Game Management", test_game_management),
        ("Order Submission", test_order_submission),
        ("Messaging", test_messaging),
        ("User Games", test_user_games),
        ("Order History", test_order_history),
        ("Health Endpoints", test_health_endpoints),
        ("Order Normalization", test_order_normalization),
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
            import traceback
            traceback.print_exc()
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Telegram bot API is working correctly.")
        print("\n💡 Next Steps:")
        print("   1. Set TELEGRAM_BOT_TOKEN environment variable")
        print("   2. Run: python -m server.telegram_bot")
        print("   3. Start a conversation with your bot on Telegram")
        print("   4. Use the bot commands to interact with the game")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        print("\n🔧 Troubleshooting:")
        print("   1. Make sure PostgreSQL is running")
        print("   2. Start the API server: python start_api_server.py")
        print("   3. Check database connection settings")
        print("   4. Verify all dependencies are installed")

if __name__ == "__main__":
    main()
