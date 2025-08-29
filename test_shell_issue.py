#!/usr/bin/env python3
"""
Test script to check map generation without terminal commands.
This bypasses the shell hanging issue.
"""

import os
import sys
import subprocess

def test_map_generation():
    """Test map generation using subprocess to avoid shell hanging."""
    
    print("🧪 Testing Map Generation (Bypassing Shell Issue)")
    print("=" * 50)
    
    # Set up environment
    env = os.environ.copy()
    env['QT_QPA_PLATFORM'] = 'offscreen'
    env['PYTHONPATH'] = 'new_implementation/src'
    
    # Change to the correct directory
    os.chdir('new_implementation')
    
    # Test the map generation
    try:
        cmd = [
            sys.executable, '-c',
            'from src.engine.map import Map; '
            'result = Map.render_board_png("maps/standard.svg", {}); '
            'print(f"Generated {len(result):,} bytes"); '
            'open("test_shell_bypass.png", "wb").write(result); '
            'print("✅ Map generation successful!")'
        ]
        
        print("Running map generation test...")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        
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
    test_map_generation() 