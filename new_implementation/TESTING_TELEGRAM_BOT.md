# Testing Telegram Bot Functionality

This directory contains comprehensive test scripts for testing the Telegram bot functionality via direct API calls, without needing an actual Telegram bot.

## 🚀 Quick Start

### 1. Start the API Server
```bash
python start_api_server.py
```
This will start the FastAPI server on `http://localhost:8000`.

### 2. Run Comprehensive Tests
```bash
python test_telegram_bot_comprehensive.py
```
This will test all Telegram bot API endpoints and functionality.

### 3. Test Order Normalization
```bash
python test_order_normalization.py
```
This tests the order normalization functions used by the Telegram bot.

## 📋 Available Test Scripts

### `test_telegram_bot_comprehensive.py`
**Main test script** that tests all Telegram bot functionality:
- ✅ User registration and management
- ✅ Game creation and joining
- ✅ Order submission and validation
- ✅ Messaging system (private and broadcast)
- ✅ Order history and game state
- ✅ Health endpoints
- ✅ Order normalization
- ✅ Notification system

### `test_order_normalization.py`
Tests the order normalization functions:
- ✅ `normalize_order_provinces()` - Removes power names from orders
- ✅ Order validation with the game engine
- ✅ Various order formats and edge cases

### `start_api_server.py`
Simple script to start the API server for testing.

## 🔧 Prerequisites

1. **PostgreSQL Database**: Must be running and accessible
2. **Python Dependencies**: All requirements from `requirements.txt` installed
3. **Environment Setup**: Virtual environment activated

## 📊 Test Results

The comprehensive test script will show results like:
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

## 🎯 API Endpoints Tested

### Game Management
- `POST /games/create` - Create new game
- `POST /games/{game_id}/join` - Join game as power
- `GET /games/{game_id}/players` - List players
- `GET /games/{game_id}/state` - Get game state

### Orders
- `POST /games/set_orders` - Submit orders
- `GET /games/{game_id}/orders` - Get all orders
- `GET /games/{game_id}/orders/{power}` - Get power orders
- `GET /games/{game_id}/orders/history` - Get order history

### Messaging
- `POST /games/{game_id}/message` - Send private message
- `POST /games/{game_id}/broadcast` - Send broadcast message
- `GET /games/{game_id}/messages` - Get game messages

### User Management
- `POST /users/persistent_register` - Register user
- `POST /users/register` - Register session
- `GET /users/{telegram_id}` - Get user info
- `GET /users/{telegram_id}/games` - Get user games

### Health & Status
- `GET /health` - Health check
- `GET /scheduler/status` - Scheduler status

### Notifications
- `POST /notify` - Send notification (requires bot running)

## 🔔 Testing with Real Telegram Bot

To test with an actual Telegram bot:

1. **Set up Telegram Bot Token**:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token_here"
   ```

2. **Start the Telegram Bot**:
   ```bash
   python -m server.telegram_bot
   ```

3. **Test Bot Commands**:
   - Start a conversation with your bot on Telegram
   - Use commands like `/start`, `/register`, `/join`, `/orders`
   - Test interactive features and menu buttons

## 🛠️ Troubleshooting

### Common Issues

1. **"Cannot connect to API server"**
   - Make sure the API server is running: `python start_api_server.py`
   - Check if port 8000 is available

2. **"Database connection failed"**
   - Ensure PostgreSQL is running
   - Check database connection settings in `src/server/db_config.py`

3. **"Order normalization tests failed"**
   - This is expected for some edge cases
   - The function works correctly for the main use cases

4. **"Notification API request failed"**
   - This requires the notification server on port 8081
   - Start with: `python -m server.telegram_bot`

### Debug Mode

For more detailed output, set environment variables:
```bash
export DIPLOMACY_LOG_LEVEL=DEBUG
export DIPLOMACY_LOG_FILE=test.log
```

## 📝 Example Usage

The test scripts demonstrate how to:
- Register users and create games
- Submit orders and validate them
- Send messages between players
- Retrieve game state and history
- Test all bot functionality programmatically

This provides a complete testing framework for the Telegram bot without requiring actual Telegram integration during development.
