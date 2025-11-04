#!/usr/bin/env python3
"""
Mock Telegram Bot Testing Script

This script simulates Telegram bot interactions to test functionality
without needing a real bot token or manual testing.
"""

import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock Telegram Bot API classes
class MockUser:
    def __init__(self, user_id: int, username: str = "testuser"):
        self.id = user_id
        self.username = username
        self.first_name = "Test"
        self.last_name = "User"

class MockMessage:
    def __init__(self, text: str = "", user: MockUser = None):
        self.text = text
        self.from_user = user
        self.reply_text = AsyncMock()
        self.reply_photo = AsyncMock()

class MockCallbackQuery:
    def __init__(self, data: str, user: MockUser = None):
        self.data = data
        self.from_user = user
        self.edit_message_text = AsyncMock()
        self.edit_message_reply_markup = AsyncMock()
        self.answer = AsyncMock()

class MockUpdate:
    def __init__(self, message: MockMessage = None, callback_query: MockCallbackQuery = None, effective_user: MockUser = None):
        self.message = message
        self.callback_query = callback_query
        self.effective_user = effective_user or (message.from_user if message else callback_query.from_user if callback_query else None)

class MockContext:
    def __init__(self):
        self.args = []
        self.user_data = {}

class TelegramBotTester:
    def __init__(self):
        self.test_user = MockUser(8019538, "testuser")  # Use admin user ID
        self.results = []
        
    def log_result(self, test_name: str, success: bool, message: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append(f"{status} {test_name}: {message}")
        print(f"{status} {test_name}: {message}")
    
    async def test_command(self, command_func, update: MockUpdate, context: MockContext, test_name: str):
        """Test a single command function"""
        try:
            await command_func(update, context)
            self.log_result(test_name, True, "Command executed successfully")
            return True
        except Exception as e:
            self.log_result(test_name, False, f"Error: {str(e)}")
            return False
    
    async def test_help_command(self):
        """Test the /help command"""
        print("\n🧪 Testing /help command...")
        
        # Mock the telegram bot imports
        with patch.dict('sys.modules', {
            'telegram': Mock(),
            'telegram.ext': Mock(),
            'telegram.update': Mock(),
            'telegram.callbackquery': Mock(),
            'telegram.inlinekeyboardbutton': Mock(),
            'telegram.inlinekeyboardmarkup': Mock(),
            'telegram.keyboardbutton': Mock(),
            'telegram.replykeyboardmarkup': Mock(),
        }):
            # Import the bot functions
            from server.telegram_bot.ui import show_help
            
            # Create mock update and context
            message = MockMessage("/help", self.test_user)
            update = MockUpdate(message=message, effective_user=self.test_user)
            context = MockContext()
            
            # Test the command
            await self.test_command(show_help, update, context, "Help Command")
    
    async def test_selectunit_command(self):
        """Test the /selectunit command"""
        print("\n🧪 Testing /selectunit command...")
        
        with patch.dict('sys.modules', {
            'telegram': Mock(),
            'telegram.ext': Mock(),
            'telegram.update': Mock(),
            'telegram.callbackquery': Mock(),
            'telegram.inlinekeyboardbutton': Mock(),
            'telegram.inlinekeyboardmarkup': Mock(),
            'telegram.keyboardbutton': Mock(),
            'telegram.replykeyboardmarkup': Mock(),
        }):
            from server.telegram_bot.orders import selectunit
            
            # Test with message
            message = MockMessage("/selectunit", self.test_user)
            update = MockUpdate(message=message, effective_user=self.test_user)
            context = MockContext()
            
            await self.test_command(selectunit, update, context, "Selectunit Command (Message)")
            
            # Test with callback query
            callback_query = MockCallbackQuery("submit_orders_14_GERMANY", self.test_user)
            update = MockUpdate(callback_query=callback_query, effective_user=self.test_user)
            
            await self.test_command(selectunit, update, context, "Selectunit Command (Callback)")
    
    async def test_button_callbacks(self):
        """Test button callback handlers"""
        print("\n🧪 Testing button callbacks...")
        
        with patch.dict('sys.modules', {
            'telegram': Mock(),
            'telegram.ext': Mock(),
            'telegram.update': Mock(),
            'telegram.callbackquery': Mock(),
            'telegram.inlinekeyboardbutton': Mock(),
            'telegram.inlinekeyboardmarkup': Mock(),
            'telegram.keyboardbutton': Mock(),
            'telegram.replykeyboardmarkup': Mock(),
        }):
            from server.telegram_bot import button_callback
            
            # Test various callback data
            test_callbacks = [
                ("show_games_list", "Show Games List"),
                ("join_waiting_list", "Join Waiting List"),
                ("view_default_map", "View Default Map"),
                ("run_automated_demo", "Run Automated Demo"),
                ("submit_orders_14_GERMANY", "Submit Orders Callback"),
                ("orders_menu_14_GERMANY", "Orders Menu Callback"),
            ]
            
            for callback_data, test_name in test_callbacks:
                callback_query = MockCallbackQuery(callback_data, self.test_user)
                update = MockUpdate(callback_query=callback_query, effective_user=self.test_user)
                context = MockContext()
                
                await self.test_command(button_callback, update, context, f"Callback: {test_name}")
    
    async def test_api_integration(self):
        """Test API integration functions"""
        print("\n🧪 Testing API integration...")
        
        # Mock the API functions
        with patch('src.server.telegram_bot.api_get') as mock_api_get, \
             patch('src.server.telegram_bot.api_post') as mock_api_post:
            
            # Mock successful API responses
            mock_api_get.return_value = {
                "games": [{"game_id": 14, "power": "GERMANY", "state": "active"}],
                "units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}
            }
            mock_api_post.return_value = {"success": True}
            
            from server.telegram_bot.orders import selectunit
            
            # Test with mocked API
            message = MockMessage("/selectunit", self.test_user)
            update = MockUpdate(message=message, effective_user=self.test_user)
            context = MockContext()
            
            await self.test_command(selectunit, update, context, "API Integration Test")
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Telegram Bot Tests...")
        print("=" * 50)
        
        # Run individual test suites
        await self.test_help_command()
        await self.test_selectunit_command()
        await self.test_button_callbacks()
        await self.test_api_integration()
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 TEST SUMMARY:")
        passed = sum(1 for result in self.results if "✅ PASS" in result)
        failed = sum(1 for result in self.results if "❌ FAIL" in result)
        total = len(self.results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Success Rate: {(passed/total)*100:.1f}%" if total > 0 else "No tests run")
        
        if failed > 0:
            print("\n❌ Failed Tests:")
            for result in self.results:
                if "❌ FAIL" in result:
                    print(f"  {result}")
        
        return failed == 0

async def main():
    """Main test runner"""
    tester = TelegramBotTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
