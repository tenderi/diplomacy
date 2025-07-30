#!/usr/bin/env python3
"""
Comprehensive test to verify map generation color distribution.
Ensures generated maps don't have more than 20% black pixels.
"""

import os
import sys
import numpy as np
from PIL import Image
import io
import datetime

def analyze_map_colors(png_bytes: bytes) -> dict:
    """Analyze the color distribution of a PNG image."""
    
    # Open image with PIL
    image = Image.open(io.BytesIO(png_bytes))
    
    # Convert to RGB if not already
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Convert to numpy array for analysis
    img_array = np.array(image)
    
    # Calculate total pixels
    total_pixels = img_array.shape[0] * img_array.shape[1]
    
    # Calculate black pixels (very dark - RGB all below 50)
    black_mask = np.all(img_array < 50, axis=2)
    black_pixels = np.sum(black_mask)
    black_percentage = (black_pixels / total_pixels) * 100
    
    # Calculate dark pixels (broader definition - average RGB below 100)
    dark_mask = np.mean(img_array, axis=2) < 100
    dark_pixels = np.sum(dark_mask)
    dark_percentage = (dark_pixels / total_pixels) * 100
    
    # Calculate white/light pixels (RGB all above 200)
    white_mask = np.all(img_array > 200, axis=2)
    white_pixels = np.sum(white_mask)
    white_percentage = (white_pixels / total_pixels) * 100
    
    # Calculate average brightness
    avg_brightness = np.mean(img_array)
    
    # Calculate color variance (higher = more colorful)
    color_variance = np.var(img_array)
    
    # Sample some pixels for detailed analysis
    width, height = image.size
    sample_pixels = []
    for i in range(0, width, max(1, width//20)):
        for j in range(0, height, max(1, height//20)):
            sample_pixels.append(image.getpixel((i, j)))
    
    return {
        'total_pixels': total_pixels,
        'black_pixels': black_pixels,
        'black_percentage': black_percentage,
        'dark_pixels': dark_pixels,
        'dark_percentage': dark_percentage,
        'white_pixels': white_pixels,
        'white_percentage': white_percentage,
        'avg_brightness': avg_brightness,
        'color_variance': color_variance,
        'image_size': (image.width, image.height),
        'sample_pixels': sample_pixels
    }

def test_map_generation():
    """Test map generation and analyze color distribution."""
    
    print("🧪 Testing Map Generation Color Distribution")
    print("=" * 60)
    
    try:
        from src.engine.map import Map
        
        # Test with the fixed SVG file
        svg_path = "maps/standard.svg"
        if not os.path.exists(svg_path):
            print(f"❌ SVG file not found: {svg_path}")
            return False
        
        print(f"📊 Rendering map from: {svg_path}")
        png_bytes = Map.render_board_png(svg_path, {})
        
        # Analyze colors
        analysis = analyze_map_colors(png_bytes)
        
        print(f"\n📈 Color Analysis Results:")
        print(f"   Image size: {analysis['image_size']}")
        print(f"   Total pixels: {analysis['total_pixels']:,}")
        print(f"   File size: {len(png_bytes):,} bytes")
        print(f"   Black pixels: {analysis['black_percentage']:.1f}%")
        print(f"   Dark pixels: {analysis['dark_percentage']:.1f}%")
        print(f"   White pixels: {analysis['white_percentage']:.1f}%")
        print(f"   Average brightness: {analysis['avg_brightness']:.1f}")
        print(f"   Color variance: {analysis['color_variance']:.1f}")
        
        # Save for inspection
        os.makedirs("test_maps", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_maps/{timestamp}_color_test_output.png"
        with open(output_file, "wb") as f:
            f.write(png_bytes)
        print(f"   Saved as: {output_file}")
        
        # Test criteria
        black_threshold = 20.0  # Maximum 20% black pixels
        dark_threshold = 40.0   # Maximum 40% dark pixels
        brightness_threshold = 100.0  # Minimum average brightness
        
        print(f"\n🎯 Quality Checks:")
        
        # Check black pixel percentage
        if analysis['black_percentage'] <= black_threshold:
            print(f"   ✅ Black pixels: {analysis['black_percentage']:.1f}% (≤ {black_threshold}%)")
        else:
            print(f"   ❌ Black pixels: {analysis['black_percentage']:.1f}% (> {black_threshold}%)")
            return False
        
        # Check dark pixel percentage
        if analysis['dark_percentage'] <= dark_threshold:
            print(f"   ✅ Dark pixels: {analysis['dark_percentage']:.1f}% (≤ {dark_threshold}%)")
        else:
            print(f"   ❌ Dark pixels: {analysis['dark_percentage']:.1f}% (> {dark_threshold}%)")
            return False
        
        # Check average brightness
        if analysis['avg_brightness'] >= brightness_threshold:
            print(f"   ✅ Average brightness: {analysis['avg_brightness']:.1f} (≥ {brightness_threshold})")
        else:
            print(f"   ❌ Average brightness: {analysis['avg_brightness']:.1f} (< {brightness_threshold})")
            return False
        
        # Check color variance (should be reasonable)
        if analysis['color_variance'] > 1000:  # Arbitrary threshold for colorful images
            print(f"   ✅ Color variance: {analysis['color_variance']:.1f} (good color distribution)")
        else:
            print(f"   ⚠️  Color variance: {analysis['color_variance']:.1f} (low color variation)")
        
        print(f"\n✅ Map generation test PASSED!")
        print(f"   The generated map has reasonable color distribution.")
        return True
        
    except Exception as e:
        print(f"❌ Error during map generation test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_old_vs_new_comparison():
    """Compare old vs new SVG files if available."""
    
    print(f"\n🔄 Comparing SVG Files")
    print("=" * 40)
    
    old_svg = "maps/standard.svg"
            new_svg = "maps/standard.svg"
    
    if os.path.exists(old_svg) and os.path.exists(new_svg):
        print(f"   Found both SVG files:")
        print(f"   - Old: {old_svg}")
        print(f"   - New: {new_svg}")
        
        # Check for CSS styles
        with open(old_svg, 'r') as f:
            old_content = f.read()
        with open(new_svg, 'r') as f:
            new_content = f.read()
        
        old_css = old_content.count('style type="text/css"')
        new_css = new_content.count('style type="text/css"')
        
        print(f"   - CSS style blocks in old: {old_css}")
        print(f"   - CSS style blocks in new: {new_css}")
        
        # Check for black rectangles
        old_black_rect = old_content.count('rect fill="black" height="1360" width="1835"')
        new_black_rect = new_content.count('rect fill="black" height="1360" width="1835"')
        
        print(f"   - Problematic black rectangles in old: {old_black_rect}")
        print(f"   - Problematic black rectangles in new: {new_black_rect}")
        
        if new_css == 0 and new_black_rect == 0:
            print(f"   ✅ New SVG file is properly fixed!")
        else:
            print(f"   ⚠️  New SVG file may still have issues")
    else:
        print(f"   ⚠️  Cannot compare - missing SVG files")

if __name__ == "__main__":
    print("Starting comprehensive map generation color test...")
    
    # Test SVG file comparison
    test_old_vs_new_comparison()
    
    # Test map generation and color analysis
    success = test_map_generation()
    
    if success:
        print(f"\n🎉 All tests PASSED! Map generation is working correctly.")
        sys.exit(0)
    else:
        print(f"\n💥 Tests FAILED! Map generation has issues.")
        sys.exit(1) 