#!/usr/bin/env python3
"""
Final test script for map generation using subprocess with proper shell config.
"""

import os
import sys
import subprocess

def test_map_generation_final():
    """Test map generation with proper shell configuration."""
    
    print("🧪 Final Map Generation Test")
    print("=" * 40)
    
    # Set up environment
    env = os.environ.copy()
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONPATH'] = 'new_implementation/src'
    env['TERM'] = 'dumb'  # Disable terminal features
    env['BASH_ENV'] = ''  # Disable bash environment
    
    # Change to the correct directory
    os.chdir('new_implementation')
    
    # Test the map generation
    try:
        cmd = [
            '/bin/bash', '-c',
            'cd /home/helgejalonen/diplomacy/new_implementation && '
            'QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -c "'
            'from src.engine.map import Map; '
            'result = Map.render_board_png(\"maps/standard.svg\", {}); '
            'print(f\"Generated {len(result):,} bytes\"); '
            'open(\"test_final_map.png\", \"wb\").write(result); '
            'print(\"✅ Map generation successful!\")"'
        ]
        
        print("Running final map generation test...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ SUCCESS: Map generation worked!")
            print(f"Output: {result.stdout}")
            if result.stderr:
                print(f"Warnings: {result.stderr}")
        else:
            print("❌ FAILED: Map generation failed!")
            print(f"Error: {result.stderr}")
            print(f"Return code: {result.returncode}")
            
    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT: Command took too long")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    test_map_generation_final() 