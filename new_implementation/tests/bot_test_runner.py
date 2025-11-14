#!/usr/bin/env python3
"""
Comprehensive Telegram Bot Testing Framework

This script allows you to test any Telegram bot functionality locally
without needing a bot token or manual testing.

Usage:
    python3 bot_test_runner.py --help
    python3 bot_test_runner.py --test selectunit
    python3 bot_test_runner.py --test all
    python3 bot_test_runner.py --test button_callbacks
"""

import sys
import os
import asyncio
import argparse
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List, Callable

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class TelegramBotTestFramework:
    def __init__(self):
        self.test_results = []
        self.mock_api_responses = {
            "user_games": {
                "games": [{"game_id": 14, "power": "GERMANY", "state": "active"}],
                "units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}
            },
            "no_games": {"games": []},
            "multiple_games": {
                "games": [
                    {"game_id": 14, "power": "GERMANY", "state": "active"},
                    {"game_id": 15, "power": "FRANCE", "state": "active"}
                ]
            },
            "game_state": {
                "units": {"GERMANY": ["A BER", "A MUN", "F KIE"]},
                "phase": "Movement",
                "season": "Spring",
                "year": 1901
            }
        }
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅" if success else "❌"
        message = f"{status} {test_name}"
        if details:
            message += f" - {details}"
        print(message)
        self.test_results.append((test_name, success, details))
    
    def create_mock_user(self, user_id: int = 8019538):
        """Create a mock user"""
        user = Mock()
        user.id = user_id
        user.username = "testuser"
        user.first_name = "Test"
        user.last_name = "User"
        return user
    
    def create_mock_message(self, text: str = "", user: Mock = None):
        """Create a mock message"""
        if user is None:
            user = self.create_mock_user()
        
        message = Mock()
        message.text = text
        message.from_user = user
        message.reply_text = AsyncMock()
        message.reply_photo = AsyncMock()
        return message
    
    def create_mock_callback_query(self, data: str, user: Mock = None):
        """Create a mock callback query"""
        if user is None:
            user = self.create_mock_user()
        
        callback_query = Mock()
        callback_query.data = data
        callback_query.from_user = user
        callback_query.edit_message_text = AsyncMock()
        callback_query.edit_message_reply_markup = AsyncMock()
        callback_query.answer = AsyncMock()
        return callback_query
    
    def create_mock_update(self, message: Mock = None, callback_query: Mock = None, effective_user: Mock = None):
        """Create a mock update"""
        update = Mock()
        update.message = message
        update.callback_query = callback_query
        update.effective_user = effective_user or (message.from_user if message else callback_query.from_user if callback_query else self.create_mock_user())
        return update
    
    def create_mock_context(self):
        """Create a mock context"""
        context = Mock()
        context.args = []
        context.user_data = {}
        return context
    
    async def test_function_with_contexts(self, func_name: str, test_scenarios: List[Dict[str, Any]]):
        """Test a function with multiple scenarios"""
        print(f"\n🧪 Testing {func_name}...")
        
        try:
            # Import the function
            import server.telegram_bot as telegram_bot
            func = getattr(telegram_bot, func_name)
        except (ImportError, AttributeError) as e:
            self.log_test(f"{func_name} import", False, f"Could not import: {str(e)}")
            return
        
        for scenario in test_scenarios:
            scenario_name = scenario.get("name", "Unknown")
            
            try:
                # Mock API responses
                api_response = scenario.get("api_response", self.mock_api_responses["user_games"])
                
                with patch('src.server.telegram_bot.api_get', return_value=api_response):
                    # Create mock objects
                    user = self.create_mock_user()
                    
                    if scenario.get("context") == "message":
                        message = self.create_mock_message(scenario.get("text", ""), user)
                        update = self.create_mock_update(message=message, effective_user=user)
                    elif scenario.get("context") == "callback":
                        callback_query = self.create_mock_callback_query(scenario.get("callback_data", ""), user)
                        update = self.create_mock_update(callback_query=callback_query, effective_user=user)
                    else:
                        update = self.create_mock_update(effective_user=user)
                    
                    context = self.create_mock_context()
                    
                    # Test the function
                    await func(update, context)
                    
                    # Check if appropriate method was called
                    success = False
                    if update.message and update.message.reply_text.called:
                        success = True
                    elif update.callback_query and update.callback_query.edit_message_text.called:
                        success = True
                    
                    self.log_test(f"{func_name}: {scenario_name}", success, 
                                "Function executed" if success else "No response generated")
                    
            except Exception as e:
                self.log_test(f"{func_name}: {scenario_name}", False, f"Exception: {str(e)}")
    
    async def test_selectunit(self):
        """Test the selectunit function"""
        scenarios = [
            {
                "name": "Message Context",
                "context": "message",
                "text": "/selectunit",
                "api_response": self.mock_api_responses["user_games"]
            },
            {
                "name": "Callback Context",
                "context": "callback", 
                "callback_data": "submit_orders_14_GERMANY",
                "api_response": self.mock_api_responses["user_games"]
            },
            {
                "name": "No Games",
                "context": "callback",
                "callback_data": "submit_orders_14_GERMANY", 
                "api_response": self.mock_api_responses["no_games"]
            },
            {
                "name": "Multiple Games",
                "context": "callback",
                "callback_data": "submit_orders_14_GERMANY",
                "api_response": self.mock_api_responses["multiple_games"]
            }
        ]
        
        await self.test_function_with_contexts("selectunit", scenarios)
    
    async def test_button_callback(self):
        """Test the button_callback function"""
        scenarios = [
            {
                "name": "Show Games List",
                "context": "callback",
                "callback_data": "show_games_list"
            },
            {
                "name": "Join Waiting List", 
                "context": "callback",
                "callback_data": "join_waiting_list"
            },
            {
                "name": "View Default Map",
                "context": "callback",
                "callback_data": "view_default_map"
            },
            {
                "name": "Run Perfect Demo",
                "context": "callback",
                "callback_data": "run_automated_demo"
            },
            {
                "name": "Submit Orders",
                "context": "callback",
                "callback_data": "submit_orders_14_GERMANY"
            },
            {
                "name": "Orders Menu",
                "context": "callback", 
                "callback_data": "orders_menu_14_GERMANY"
            }
        ]
        
        await self.test_function_with_contexts("button_callback", scenarios)
    
    async def test_help_command(self):
        """Test the help command"""
        scenarios = [
            {
                "name": "Help Command",
                "context": "message",
                "text": "/help"
            }
        ]
        
        await self.test_function_with_contexts("show_help", scenarios)
    
    async def test_api_functions(self):
        """Test API functions"""
        print("\n🧪 Testing API functions...")
        
        try:
            from server.telegram_bot.api_client import api_get, api_post
            
            with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
                # Mock successful responses
                mock_response = Mock()
                mock_response.json.return_value = {"success": True, "data": "test"}
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                mock_post.return_value = mock_response
                
                # Test api_get
                result = api_get("/test")
                self.log_test("api_get", result is not None, "Function executed successfully")
                
                # Test api_post
                result = api_post("/test", {"data": "test"})
                self.log_test("api_post", result is not None, "Function executed successfully")
                
        except Exception as e:
            self.log_test("API functions", False, f"Exception: {str(e)}")
    
    async def run_test_suite(self, test_name: str):
        """Run a specific test suite"""
        if test_name == "all":
            await self.test_selectunit()
            await self.test_button_callback()
            await self.test_help_command()
            await self.test_api_functions()
        elif test_name == "selectunit":
            await self.test_selectunit()
        elif test_name == "button_callbacks":
            await self.test_button_callback()
        elif test_name == "help":
            await self.test_help_command()
        elif test_name == "api":
            await self.test_api_functions()
        else:
            print(f"❌ Unknown test suite: {test_name}")
            return False
        
        return True
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY:")
        
        passed = sum(1 for _, success, _ in self.test_results if success)
        failed = sum(1 for _, success, _ in self.test_results if not success)
        total = len(self.test_results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        
        if total > 0:
            print(f"Success Rate: {(passed/total)*100:.1f}%")
        
        if failed > 0:
            print("\n❌ Failed Tests:")
            for test_name, success, details in self.test_results:
                if not success:
                    print(f"  {test_name}: {details}")
        
        return failed == 0

async def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Telegram Bot Testing Framework")
    parser.add_argument("--test", choices=["all", "selectunit", "button_callbacks", "help", "api"], 
                       default="all", help="Test suite to run")
    
    args = parser.parse_args()
    
    print("🚀 Telegram Bot Testing Framework")
    print("=" * 50)
    print(f"Running test suite: {args.test}")
    print("=" * 50)
    
    framework = TelegramBotTestFramework()
    success = await framework.run_test_suite(args.test)
    
    if success:
        all_passed = framework.print_summary()
        if all_passed:
            print("\n🎉 All tests passed!")
            return 0
        else:
            print("\n💥 Some tests failed!")
            return 1
    else:
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
