#!/usr/bin/env python3
"""
Simple Telegram Bot Function Testing

Tests core bot functions without requiring Telegram API or bot token.
"""

import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class BotFunctionTester:
    def __init__(self):
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, error: str = ""):
        """Log test result"""
        status = "✅" if success else "❌"
        message = f"{status} {test_name}"
        if error:
            message += f" - {error}"
        print(message)
        self.test_results.append((test_name, success, error))
    
    async def test_selectunit_function(self):
        """Test the selectunit function with mocked dependencies"""
        print("\n🧪 Testing selectunit function...")
        
        try:
            # Mock all the Telegram imports
            mock_modules = {
                'telegram': Mock(),
                'telegram.ext': Mock(),
                'telegram.update': Mock(),
                'telegram.callbackquery': Mock(),
                'telegram.inlinekeyboardbutton': Mock(),
                'telegram.inlinekeyboardmarkup': Mock(),
                'telegram.keyboardbutton': Mock(),
                'telegram.replykeyboardmarkup': Mock(),
            }
            
            with patch.dict('sys.modules', mock_modules):
                # Mock the API functions
                with patch('src.server.telegram_bot.api_get') as mock_api_get:
                    # Mock successful API response
                    mock_api_get.return_value = {
                        "games": [{"game_id": 14, "power": "GERMANY", "state": "active"}],
                        "units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}
                    }
                    
                    # Import the function
                    from server.telegram_bot import selectunit
                    
                    # Create mock update objects
                    class MockUser:
                        def __init__(self):
                            self.id = 8019538
                    
                    class MockMessage:
                        def __init__(self):
                            self.text = "/selectunit"
                            self.from_user = MockUser()
                            self.reply_text = AsyncMock()
                    
                    class MockCallbackQuery:
                        def __init__(self):
                            self.data = "submit_orders_14_GERMANY"
                            self.from_user = MockUser()
                            self.edit_message_text = AsyncMock()
                    
                    class MockUpdate:
                        def __init__(self, has_message=True):
                            self.effective_user = MockUser()
                            if has_message:
                                self.message = MockMessage()
                                self.callback_query = None
                            else:
                                self.message = None
                                self.callback_query = MockCallbackQuery()
                    
                    class MockContext:
                        def __init__(self):
                            self.args = []
                            self.user_data = {}
                    
                    # Test with message context
                    update = MockUpdate(has_message=True)
                    context = MockContext()
                    
                    await selectunit(update, context)
                    self.log_test("selectunit with message", True)
                    
                    # Test with callback context
                    update = MockUpdate(has_message=False)
                    await selectunit(update, context)
                    self.log_test("selectunit with callback", True)
                    
        except Exception as e:
            self.log_test("selectunit function", False, str(e))
    
    async def test_button_callback_function(self):
        """Test the button_callback function"""
        print("\n🧪 Testing button_callback function...")
        
        try:
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
                
                # Create mock objects
                class MockUser:
                    def __init__(self):
                        self.id = 8019538
                
                class MockCallbackQuery:
                    def __init__(self, data):
                        self.data = data
                        self.from_user = MockUser()
                        self.edit_message_text = AsyncMock()
                
                class MockUpdate:
                    def __init__(self, callback_data):
                        self.callback_query = MockCallbackQuery(callback_data)
                        self.effective_user = MockUser()
                
                class MockContext:
                    def __init__(self):
                        self.args = []
                        self.user_data = {}
                
                # Test various callback types
                test_callbacks = [
                    "show_games_list",
                    "join_waiting_list", 
                    "view_default_map",
                    "run_automated_demo",
                    "submit_orders_14_GERMANY",
                    "orders_menu_14_GERMANY"
                ]
                
                for callback_data in test_callbacks:
                    update = MockUpdate(callback_data)
                    context = MockContext()
                    
                    try:
                        await button_callback(update, context)
                        self.log_test(f"button_callback: {callback_data}", True)
                    except Exception as e:
                        self.log_test(f"button_callback: {callback_data}", False, str(e))
                        
        except Exception as e:
            self.log_test("button_callback function", False, str(e))
    
    async def test_api_functions(self):
        """Test API integration functions"""
        print("\n🧪 Testing API functions...")
        
        try:
            # Test API functions directly
            from server.telegram_bot import api_get, api_post
            
            # Mock requests
            with patch('requests.get') as mock_get, patch('requests.post') as mock_post:
                # Mock successful responses
                mock_response = Mock()
                mock_response.json.return_value = {"success": True, "data": "test"}
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                mock_post.return_value = mock_response
                
                # Test api_get
                result = api_get("/test")
                self.log_test("api_get function", result is not None)
                
                # Test api_post
                result = api_post("/test", {"data": "test"})
                self.log_test("api_post function", result is not None)
                
        except Exception as e:
            self.log_test("API functions", False, str(e))
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Starting Bot Function Tests...")
        print("=" * 50)
        
        await self.test_selectunit_function()
        await self.test_button_callback_function()
        await self.test_api_functions()
        
        # Print summary
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
            for test_name, success, error in self.test_results:
                if not success:
                    print(f"  {test_name}: {error}")
        
        return failed == 0

async def main():
    """Main test runner"""
    tester = BotFunctionTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n💥 Some tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
