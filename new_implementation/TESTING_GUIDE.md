# Telegram Bot Testing Guide

This guide explains how to test Telegram bot functionality locally without needing a bot token or manual testing.

## 🧪 Available Test Scripts

### 1. **bot_test_runner.py** - Comprehensive Testing Framework
The main testing framework that can test any bot functionality.

**Usage:**
```bash
# Test everything
python3 bot_test_runner.py --test all

# Test specific functionality
python3 bot_test_runner.py --test selectunit
python3 bot_test_runner.py --test button_callbacks
python3 bot_test_runner.py --test help
python3 bot_test_runner.py --test api
```

**What it tests:**
- ✅ `/selectunit` command (both message and callback contexts)
- ✅ Button callbacks (Submit Interactive Orders, etc.)
- ✅ Help command
- ✅ API functions
- ✅ Error scenarios (no games, multiple games)

### 2. **test_selectunit_fix.py** - Focused Fix Verification
Specifically tests the "Submit Interactive Orders" button fix.

**Usage:**
```bash
python3 test_selectunit_fix.py
```

**What it verifies:**
- ✅ Button press now works (no more "nothing happens")
- ✅ Shows unit selection menu
- ✅ Handles all scenarios correctly

## 🎯 How to Use for Development

### Before Making Changes:
```bash
python3 bot_test_runner.py --test all
```
This gives you a baseline of what's working.

### After Making Changes:
```bash
python3 bot_test_runner.py --test all
```
This verifies your changes didn't break anything.

### Testing Specific Features:
```bash
# If you modified the selectunit function
python3 bot_test_runner.py --test selectunit

# If you added new buttons
python3 bot_test_runner.py --test button_callbacks
```

## 📊 Understanding Test Results

**Success Rate:** Percentage of tests that passed
- 100% = Everything working perfectly
- 90%+ = Minor issues, mostly working
- <90% = Significant issues need attention

**Failed Tests:** Shows exactly what's broken
- Exception messages help identify the problem
- "No response generated" means function didn't call reply methods

## 🔧 Adding New Tests

To test a new function, add it to `bot_test_runner.py`:

```python
async def test_my_new_function(self):
    """Test my new function"""
    scenarios = [
        {
            "name": "Normal Case",
            "context": "message",
            "text": "/mycommand"
        }
    ]
    await self.test_function_with_contexts("my_new_function", scenarios)
```

## 💡 Benefits

1. **No Bot Token Required** - Test locally without Telegram API
2. **Fast Feedback** - Know immediately if changes work
3. **Comprehensive Coverage** - Tests multiple scenarios automatically
4. **Regression Prevention** - Catch bugs before they reach users
5. **Development Speed** - No more manual testing for every change

## 🚀 Quick Start

```bash
# Test the current state
python3 bot_test_runner.py --test all

# If you're working on selectunit specifically
python3 test_selectunit_fix.py

# Test just button functionality
python3 bot_test_runner.py --test button_callbacks
```

This testing framework eliminates the need for tedious manual testing and gives you confidence that your changes work correctly!
