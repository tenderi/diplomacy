#!/usr/bin/env python3
"""
Test script for Telegram bot order normalization functionality.

This script tests the order normalization functions that are used
by the Telegram bot to clean and validate user input.

Usage:
    python test_order_normalization.py
"""

import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from server.telegram_bot import normalize_order_provinces

def test_order_normalization():
    """Test order normalization functionality."""
    print("🧪 Testing Order Normalization Functions")
    print("=" * 50)
    
    # Test cases for order normalization
    test_cases = [
        # Basic normalization
        ("A PAR - BUR", "A PAR - BUR"),
        ("F LON - ENG", "F LON - ENG"),
        ("A BER H", "A BER H"),
        
        # Power name removal
        ("FRANCE A PAR - BUR", "A PAR - BUR"),
        ("ENGLAND F LON - ENG", "F LON - ENG"),
        ("GERMANY A BER H", "A BER H"),
        
        # Mixed case handling
        ("a par - bur", "A PAR - BUR"),
        ("f lon - eng", "F LON - ENG"),
        ("A BER h", "A BER H"),
        
        # Support orders
        ("A PAR S A MAR - BUR", "A PAR S A MAR - BUR"),
        ("FRANCE A PAR S A MAR - BUR", "A PAR S A MAR - BUR"),
        
        # Convoy orders
        ("F ENG C A LON - BRE", "F ENG C A LON - BRE"),
        ("ENGLAND F ENG C A LON - BRE", "F ENG C A LON - BRE"),
        
        # Build/Destroy orders
        ("BUILD A PAR", "BUILD A PAR"),
        ("DESTROY A MAR", "DESTROY A MAR"),
        ("FRANCE BUILD A PAR", "BUILD A PAR"),
        
        # Edge cases
        ("", ""),
        ("A", "A"),
        ("FRANCE", ""),
    ]
    
    print("\n📝 Testing normalize_order_provinces:")
    passed = 0
    total = len(test_cases)
    
    for input_order, expected in test_cases:
        try:
            result = normalize_order_provinces(input_order, "FRANCE")
            status = "✅" if result == expected else "❌"
            print(f"{status} Input: '{input_order}' → Output: '{result}' (Expected: '{expected}')")
            if result == expected:
                passed += 1
        except Exception as e:
            print(f"❌ Input: '{input_order}' → Error: {e}")
    
    print(f"\n📊 normalize_order_provinces: {passed}/{total} tests passed")
    
    # Overall results
    print(f"\n🎯 Overall Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All order normalization tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

def test_order_validation():
    """Test order validation functionality."""
    print("\n🔍 Testing Order Validation")
    print("=" * 50)
    
    # Import order parser
    try:
        from engine.order import OrderParser
        parser = OrderParser()
        
        # Test valid orders
        valid_orders = [
            "A PAR - BUR",
            "F LON - ENG", 
            "A BER H",
            "A PAR S A MAR - BUR",
            "F ENG C A LON - BRE",
            "BUILD A PAR",
            "DESTROY A MAR"
        ]
        
        print("\n✅ Testing Valid Orders:")
        for order in valid_orders:
            try:
                parsed = parser.parse_order(order, "FRANCE")
                print(f"   ✅ '{order}' → Valid")
            except Exception as e:
                print(f"   ❌ '{order}' → Error: {e}")
        
        # Test invalid orders
        invalid_orders = [
            "INVALID ORDER",
            "A PAR - INVALID_PROVINCE",
            "F LON - LAND_PROVINCE",
            "A PAR S INVALID_UNIT - BUR",
        ]
        
        print("\n❌ Testing Invalid Orders:")
        for order in invalid_orders:
            try:
                parsed = parser.parse_order(order, "FRANCE")
                print(f"   ⚠️  '{order}' → Unexpectedly valid: {parsed}")
            except Exception as e:
                print(f"   ✅ '{order}' → Correctly rejected: {e}")
    
    except ImportError as e:
        print(f"❌ Could not import OrderParser: {e}")
        print("   This requires the game engine to be properly set up")

def main():
    """Run all normalization tests."""
    print("🚀 Starting Order Normalization Tests")
    print("=" * 50)
    
    try:
        test_order_normalization()
        test_order_validation()
        
        print("\n💡 Usage Notes:")
        print("   - normalize_order_provinces removes power names from orders")
        print("   - This function is used by the Telegram bot to clean user input")
        print("   - It prepares orders for the game engine by removing redundant power names")
        
    except Exception as e:
        print(f"❌ Test suite crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
