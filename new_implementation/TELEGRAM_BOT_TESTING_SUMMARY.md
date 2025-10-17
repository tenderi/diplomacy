# Telegram Bot API Testing Guide

## 🎯 Overview

Yes, there are comprehensive ways to test Telegram bot functionalities with direct API calls! This guide shows you exactly how to test all the Telegram bot features without needing an actual Telegram bot running.

## 🚀 Available Testing Methods

### 1. **Direct REST API Testing** (Recommended)
Test all bot functionality through HTTP requests to the REST API endpoints.

**Files:**
- `test_telegram_bot_comprehensive.py` - Complete API test suite
- `start_api_server.py` - Start API server for testing
- `TESTING_TELEGRAM_BOT.md` - Detailed testing guide

**What it tests:**
- ✅ User registration and management
- ✅ Game creation and joining
- ✅ Order submission and validation
- ✅ Messaging system (private and broadcast)
- ✅ Order history and game state
- ✅ Health endpoints
- ✅ Order normalization
- ✅ Notification system

### 2. **Order Normalization Testing**
Test the core order processing functions used by the Telegram bot.

**Files:**
- `test_order_normalization.py` - Order normalization tests

**What it tests:**
- ✅ `normalize_order_provinces()` function
- ✅ Power name removal from orders
- ✅ Order format validation
- ✅ Edge cases and error handling

### 3. **Unit Testing** (Already Available)
Test individual bot functions in isolation.

**Files:**
- `src/tests/test_telegram_bot_enhanced.py` - Unit tests for bot functions
- `src/tests/test_integration.py` - Integration tests

## 📋 Complete API Endpoints Available

### Game Management
```bash
POST /games/create                    # Create new game
POST /games/{game_id}/join           # Join game as power
GET  /games/{game_id}/players        # List players
GET  /games/{game_id}/state          # Get game state
POST /games/{game_id}/quit           # Quit game
POST /games/{game_id}/replace        # Replace vacated power
```

### Orders
```bash
POST /games/set_orders               # Submit orders
GET  /games/{game_id}/orders         # Get all orders
GET  /games/{game_id}/orders/{power} # Get power orders
POST /games/{game_id}/orders/{power}/clear # Clear orders
GET  /games/{game_id}/orders/history # Get order history
```

### Messaging
```bash
POST /games/{game_id}/message        # Send private message
POST /games/{game_id}/broadcast      # Send broadcast message
GET  /games/{game_id}/messages       # Get game messages
```

### User Management
```bash
POST /users/persistent_register      # Register user
POST /users/register                  # Register session
GET  /users/{telegram_id}             # Get user info
GET  /users/{telegram_id}/games       # Get user games
```

### Health & Status
```bash
GET  /health                         # Health check
GET  /scheduler/status               # Scheduler status
```

### Notifications
```bash
POST /notify                         # Send notification (requires bot)
```

## 🛠️ How to Test

### Step 1: Start the API Server
```bash
cd /home/tenderi/diplomacy/new_implementation
python start_api_server.py
```
This starts the FastAPI server on `http://localhost:8000`.

### Step 2: Run Comprehensive Tests
```bash
python test_telegram_bot_comprehensive.py
```

### Step 3: Test Order Normalization
```bash
python test_order_normalization.py
```

## 📊 Example Test Output

```
🚀 Starting Comprehensive Telegram Bot API Tests
============================================================
   API Base URL: http://localhost:8000
   Notify API URL: http://localhost:8081
   Test Telegram ID: 123456789
============================================================

🔌 Testing Server Connection...
✅ API server is running and accessible

🔐 Testing User Registration...
✅ Persistent user registration successful
✅ In-memory user registration successful
✅ User info retrieval successful

🎮 Testing Game Management...
✅ Game creation successful: game_123
✅ Game join successful
✅ Game players retrieval successful
✅ Game state retrieval successful

📝 Testing Order Submission...
✅ Order submission successful
✅ Game orders retrieval successful
✅ Power orders retrieval successful

💬 Testing Messaging...
✅ Private message sent successfully
✅ Broadcast message sent successfully
✅ Game messages retrieval successful

📊 Test Results: 10/10 tests passed
🎉 All tests passed! Telegram bot API is working correctly.
```

## 🔧 Testing with Real Telegram Bot

Once you've verified the API works, you can test with an actual Telegram bot:

### 1. Set up Bot Token
```bash
export TELEGRAM_BOT_TOKEN="your_bot_token_here"
```

### 2. Start the Telegram Bot
```bash
python -m server.telegram_bot
```

### 3. Test Bot Commands
- Start conversation with your bot on Telegram
- Use commands: `/start`, `/register`, `/join`, `/orders`
- Test interactive features and menu buttons

## 🎯 Key Benefits of This Approach

### ✅ **Complete Coverage**
- Tests all bot functionality without Telegram dependency
- Validates API endpoints, order processing, messaging
- Covers edge cases and error scenarios

### ✅ **Development Friendly**
- No need for Telegram bot token during development
- Fast iteration and debugging
- Automated testing in CI/CD pipelines

### ✅ **Production Ready**
- Same API endpoints used by the actual bot
- Validates real-world usage scenarios
- Ensures reliability before deployment

### ✅ **Comprehensive Validation**
- User registration and authentication
- Game state management
- Order submission and validation
- Messaging and notifications
- Error handling and edge cases

## 🚀 Next Steps

1. **Run the tests** to verify everything works
2. **Start the API server** for interactive testing
3. **Set up a Telegram bot** for real-world testing
4. **Integrate with CI/CD** for automated testing

This comprehensive testing approach ensures your Telegram bot functionality is robust, reliable, and ready for production use!
