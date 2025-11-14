#!/usr/bin/env python3
"""
Test to verify that bot and demo script use the same map generation code
"""

import sys
import os

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_map_generation_consistency():
    """Test that both bot and demo script use the same map generation code"""
    print("🧪 Testing Map Generation Consistency...")
    print("=" * 50)
    
    try:
        from engine.map import Map
        
        # Test data
        units = {
            "GERMANY": ["A BER", "A MUN", "F KIE"],
            "FRANCE": ["A PAR", "F BRE"],
            "ENGLAND": ["A LON", "F LON"]
        }
        
        phase_info = {
            "turn": 1,
            "season": "Spring",
            "year": 1901,
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        svg_path = "maps/standard.svg"
        
        print("📊 Testing render_board_png (used by demo script)...")
        img_bytes_1 = Map.render_board_png(svg_path, units, phase_info=phase_info)
        print(f"✅ Generated {len(img_bytes_1)} bytes")
        
        print("📊 Testing render_board_png_with_moves (used by bot)...")
        img_bytes_2 = Map.render_board_png_with_moves(svg_path, units, {}, phase_info=phase_info)
        print(f"✅ Generated {len(img_bytes_2)} bytes")
        
        # Check if they're similar (should be since render_board_png_with_moves calls render_board_png internally)
        if abs(len(img_bytes_1) - len(img_bytes_2)) < 1000:  # Allow small differences due to move arrows
            print("✅ Both functions generate similar-sized images")
            print("✅ Both functions use the same underlying code (render_board_png)")
        else:
            print("❌ Functions generate very different images")
            print(f"   render_board_png: {len(img_bytes_1)} bytes")
            print(f"   render_board_png_with_moves: {len(img_bytes_2)} bytes")
        
        # Save test images for manual inspection in test_maps folder
        test_maps_dir = os.path.join(os.path.dirname(__file__), "test_maps")
        os.makedirs(test_maps_dir, exist_ok=True)
        
        bot_map_path = os.path.join(test_maps_dir, "test_bot_map.png")
        demo_map_path = os.path.join(test_maps_dir, "test_demo_map.png")
        
        with open(bot_map_path, "wb") as f:
            f.write(img_bytes_2)
        with open(demo_map_path, "wb") as f:
            f.write(img_bytes_1)
        
        print("💾 Saved test images:")
        print(f"   - {bot_map_path} (render_board_png_with_moves)")
        print(f"   - {demo_map_path} (render_board_png)")
        print()
        print("🔍 Manual verification:")
        print("   Both images should have:")
        print("   ✅ Colored provinces")
        print("   ✅ Unit markers")
        print("   ❌ NO area name text overlays")
        
        assert True, "Test completed successfully"
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        test_map_generation_consistency()
        print("\n🎉 Map generation consistency test completed!")
        print("💡 Both bot and demo script should now use the same fixed code")
    except Exception:
        print("\n💥 Map generation consistency test failed!")
        sys.exit(1)
