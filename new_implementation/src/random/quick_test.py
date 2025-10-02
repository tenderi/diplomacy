#!/usr/bin/env python3
"""
Quick test to check map generation and color analysis.
"""

import os
import sys
from PIL import Image
import io
import numpy as np

def quick_color_test():
    """Quick test of map generation and color analysis."""
    
    print("🧪 Quick Map Generation Test")
    print("=" * 40)
    
    try:
        from src.engine.map import Map
        
        # Test map generation
        svg_path = "maps/standard.svg"
        print(f"📊 Rendering map from: {svg_path}")
        
        png_bytes = Map.render_board_png(svg_path, {})
        print(f"✅ Generated {len(png_bytes):,} bytes")
        
        # Save for inspection
        with open("quick_test_output.png", "wb") as f:
            f.write(png_bytes)
        print("💾 Saved as quick_test_output.png")
        
        # Quick color analysis
        image = Image.open(io.BytesIO(png_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        img_array = np.array(image)
        total_pixels = img_array.shape[0] * img_array.shape[1]
        
        # Check for black pixels
        black_mask = np.all(img_array < 50, axis=2)
        black_pixels = np.sum(black_mask)
        black_percentage = (black_pixels / total_pixels) * 100
        
        # Check average brightness
        avg_brightness = np.mean(img_array)
        
        print(f"\n📈 Quick Analysis:")
        print(f"   Image size: {image.size}")
        print(f"   Total pixels: {total_pixels:,}")
        print(f"   Black pixels: {black_percentage:.1f}%")
        print(f"   Average brightness: {avg_brightness:.1f}")
        
        # Quality check
        if black_percentage > 50:
            print(f"   ❌ TOO MANY BLACK PIXELS: {black_percentage:.1f}%")
            return False
        elif avg_brightness < 100:
            print(f"   ❌ TOO DARK: {avg_brightness:.1f}")
            return False
        else:
            print(f"   ✅ Map looks good!")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = quick_color_test()
    if success:
        print("\n🎉 Test PASSED!")
        sys.exit(0)
    else:
        print("\n💥 Test FAILED!")
        sys.exit(1) 