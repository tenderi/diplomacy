#!/usr/bin/env python3
"""
Test script to verify the selectunit fix works correctly.

This script simulates the exact scenario you encountered:
1. User clicks "Submit Interactive Orders" button
2. Bot should show unit selection menu
3. No more "nothing happens" issue
"""

import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

class SelectunitFixTester:
    def __init__(self):
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅" if success else "❌"
        message = f"{status} {test_name}"
        if details:
            message += f" - {details}"
        print(message)
        self.test_results.append((test_name, success, details))
    
    async def test_callback_query_context(self):
        """Test that selectunit works with callback query context (button press)"""
        print("\n🧪 Testing selectunit with callback query context...")
        
        try:
            # Mock the API response
            mock_api_response = {
                "games": [{"game_id": 14, "power": "GERMANY", "state": "active"}],
                "units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}
            }
            
            # Mock the API call
            with patch('src.server.telegram_bot.api_get', return_value=mock_api_response):
                # Import the selectunit function
                from server.telegram_bot import selectunit
                
                # Create mock objects that simulate a callback query (button press)
                class MockUser:
                    def __init__(self):
                        self.id = 8019538
                
                class MockCallbackQuery:
                    def __init__(self):
                        self.data = "submit_orders_14_GERMANY"
                        self.from_user = MockUser()
                        self.edit_message_text = AsyncMock()
                
                class MockUpdate:
                    def __init__(self):
                        self.effective_user = MockUser()
                        self.message = None  # No message for callback query
                        self.callback_query = MockCallbackQuery()
                
                class MockContext:
                    def __init__(self):
                        self.args = []
                        self.user_data = {}
                
                # Test the function
                update = MockUpdate()
                context = MockContext()
                
                # This should NOT fail silently anymore
                await selectunit(update, context)
                
                # Check if edit_message_text was called (indicating success)
                if update.callback_query.edit_message_text.called:
                    self.log_test("Callback Query Context", True, "edit_message_text was called")
                else:
                    self.log_test("Callback Query Context", False, "edit_message_text was not called")
                    
        except Exception as e:
            self.log_test("Callback Query Context", False, f"Exception: {str(e)}")
    
    async def test_message_context(self):
        """Test that selectunit still works with message context (/selectunit command)"""
        print("\n🧪 Testing selectunit with message context...")
        
        try:
            # Mock the API response
            mock_api_response = {
                "games": [{"game_id": 14, "power": "GERMANY", "state": "active"}],
                "units": {"GERMANY": ["A BER", "A MUN", "F KIE"]}
            }
            
            # Mock the API call
            with patch('src.server.telegram_bot.api_get', return_value=mock_api_response):
                from server.telegram_bot import selectunit
                
                # Create mock objects that simulate a message (/selectunit command)
                class MockUser:
                    def __init__(self):
                        self.id = 8019538
                
                class MockMessage:
                    def __init__(self):
                        self.text = "/selectunit"
                        self.from_user = MockUser()
                        self.reply_text = AsyncMock()
                
                class MockUpdate:
                    def __init__(self):
                        self.effective_user = MockUser()
                        self.message = MockMessage()
                        self.callback_query = None
                
                class MockContext:
                    def __init__(self):
                        self.args = []
                        self.user_data = {}
                
                # Test the function
                update = MockUpdate()
                context = MockContext()
                
                await selectunit(update, context)
                
                # Check if reply_text was called (indicating success)
                if update.message.reply_text.called:
                    self.log_test("Message Context", True, "reply_text was called")
                else:
                    self.log_test("Message Context", False, "reply_text was not called")
                    
        except Exception as e:
            self.log_test("Message Context", False, f"Exception: {str(e)}")
    
    async def test_no_games_scenario(self):
        """Test selectunit when user has no games"""
        print("\n🧪 Testing selectunit with no games...")
        
        try:
            # Mock empty API response
            mock_api_response = {"games": []}
            
            with patch('src.server.telegram_bot.api_get', return_value=mock_api_response):
                from server.telegram_bot import selectunit
                
                class MockUser:
                    def __init__(self):
                        self.id = 8019538
                
                class MockCallbackQuery:
                    def __init__(self):
                        self.data = "submit_orders_14_GERMANY"
                        self.from_user = MockUser()
                        self.edit_message_text = AsyncMock()
                
                class MockUpdate:
                    def __init__(self):
                        self.effective_user = MockUser()
                        self.message = None
                        self.callback_query = MockCallbackQuery()
                
                class MockContext:
                    def __init__(self):
                        self.args = []
                        self.user_data = {}
                
                update = MockUpdate()
                context = MockContext()
                
                await selectunit(update, context)
                
                # Should show "no games" message
                if update.callback_query.edit_message_text.called:
                    self.log_test("No Games Scenario", True, "Appropriate message shown")
                else:
                    self.log_test("No Games Scenario", False, "No message shown")
                    
        except Exception as e:
            self.log_test("No Games Scenario", False, f"Exception: {str(e)}")
    
    async def test_multiple_games_scenario(self):
        """Test selectunit when user has multiple games"""
        print("\n🧪 Testing selectunit with multiple games...")
        
        try:
            # Mock multiple games response
            mock_api_response = {
                "games": [
                    {"game_id": 14, "power": "GERMANY", "state": "active"},
                    {"game_id": 15, "power": "FRANCE", "state": "active"}
                ]
            }
            
            with patch('src.server.telegram_bot.api_get', return_value=mock_api_response):
                from server.telegram_bot import selectunit
                
                class MockUser:
                    def __init__(self):
                        self.id = 8019538
                
                class MockCallbackQuery:
                    def __init__(self):
                        self.data = "submit_orders_14_GERMANY"
                        self.from_user = MockUser()
                        self.edit_message_text = AsyncMock()
                
                class MockUpdate:
                    def __init__(self):
                        self.effective_user = MockUser()
                        self.message = None
                        self.callback_query = MockCallbackQuery()
                
                class MockContext:
                    def __init__(self):
                        self.args = []
                        self.user_data = {}
                
                update = MockUpdate()
                context = MockContext()
                
                await selectunit(update, context)
                
                # Should show "multiple games" message
                if update.callback_query.edit_message_text.called:
                    self.log_test("Multiple Games Scenario", True, "Appropriate message shown")
                else:
                    self.log_test("Multiple Games Scenario", False, "No message shown")
                    
        except Exception as e:
            self.log_test("Multiple Games Scenario", False, f"Exception: {str(e)}")
    
    async def run_all_tests(self):
        """Run all tests"""
        print("🚀 Testing Selectunit Fix...")
        print("=" * 50)
        print("This test verifies that the 'Submit Interactive Orders' button")
        print("now works correctly and doesn't fail silently.")
        print("=" * 50)
        
        await self.test_callback_query_context()
        await self.test_message_context()
        await self.test_no_games_scenario()
        await self.test_multiple_games_scenario()
        
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
            for test_name, success, details in self.test_results:
                if not success:
                    print(f"  {test_name}: {details}")
        
        return failed == 0

async def main():
    """Main test runner"""
    tester = SelectunitFixTester()
    success = await tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! The selectunit fix is working correctly.")
        print("💡 The 'Submit Interactive Orders' button should now work properly.")
        return 0
    else:
        print("\n💥 Some tests failed! The fix may need more work.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
