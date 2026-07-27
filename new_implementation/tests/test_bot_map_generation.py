#!/usr/bin/env python3
"""
Test bot map generation through API
"""

import sys
import os
import requests
import json

# Add the src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_bot_map_generation():
    """Test map generation through the bot's API"""
    print("🧪 Testing Bot Map Generation...")
    print("=" * 50)
    
    try:
        # Start the server if it's not running
        from server.server import Server
        server = Server()
        
        # Create a test game
        print("🎮 Creating test game...")
        result = server.process_command("CREATE_GAME standard")
        game_id = result["game_id"] if isinstance(result, dict) else result
        print(f"✅ Created game {game_id}")
        
        # Add a player
        print("👤 Adding player...")
        server.process_command(f"ADD_PLAYER {game_id} GERMANY")
        print("✅ Added GERMANY player")
        
        # Get game state
        print("📊 Getting game state...")
        result = server.process_command(f"GET_GAME_STATE {game_id}")
        game_state = result.get("state", result) if isinstance(result, dict) else result
        print(f"✅ Game state: {json.dumps(game_state, indent=2)}")
        
        # Generate map using the same code the bot uses
        print("🗺️ Generating map...")
        from rendering.map import Map
        
        # Build the renderer's {power: ["A PAR", "F KIE", ...]} from the new view.
        units = {
            power: [f"{u['kind']} {u['location'].split('/')[0]}" for u in ulist]
            for power, ulist in game_state.get("units_by_power", {}).items()
        }

        # Get phase information
        phase_info = {
            "year": str(game_state.get("year", 1901)),
            "season": game_state.get("season", "SPRING"),
            "phase": game_state.get("phase_type", "MOVEMENT"),
            "phase_code": game_state.get("phase", "S1901M")
        }

        # Generate map (same as bot)
        svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        img_bytes = Map.render_board_png(svg_path, units, phase_info=phase_info)
        
        # Save the map to test_maps folder
        test_maps_dir = os.path.join(os.path.dirname(__file__), "test_maps")
        os.makedirs(test_maps_dir, exist_ok=True)
        map_filename = f"bot_test_map_{game_id}.png"
        output_path = os.path.join(test_maps_dir, map_filename)
        with open(output_path, 'wb') as f:
            f.write(img_bytes)
        
        print(f"✅ Map generated: {output_path}")
        print(f"📊 Map size: {len(img_bytes)} bytes")
        print(f"📊 Units: {units}")
        print(f"📊 Phase: {phase_info}")
        
        # Clean up
        server.process_command(f"DELETE_GAME {game_id}")
        print("🧹 Cleaned up test game")
        
        assert True, "Test completed successfully"
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        test_bot_map_generation()
        print("\n🎉 Bot map generation test completed!")
        print("💡 Check test_maps/bot_test_map_*.png file")
    except Exception:
        print("\n💥 Bot map generation test failed!")
        sys.exit(1)
