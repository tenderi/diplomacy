#!/usr/bin/env python3
"""
Automated test script to detect and verify map color rendering issues.
This script can be used to automatically test if SVG files render with proper colors.
"""

import sys
import os
import datetime
from pathlib import Path

def test_svg_rendering(svg_path: str, output_dir: str = "test_maps") -> dict:
    """
    Test SVG rendering and analyze the output image for color issues.
    
    Returns:
        dict: Test results including success status, dark pixel percentage, and file info
    """
    try:
        from src.engine.map import Map
        
        print(f"🔍 Testing SVG rendering: {svg_path}")
        
        # Render the SVG to PNG
        png_bytes = Map.render_board_png(svg_path, {})
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the rendered image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Path(svg_path).stem
        output_file = f"{output_dir}/{timestamp}_{filename}_test_output.png"
        
        with open(output_file, 'wb') as f:
            f.write(png_bytes)
        
        # Analyze the image
        from PIL import Image
        import io
        
        image = Image.open(io.BytesIO(png_bytes))
        
        # Convert to RGB for analysis
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Sample pixels across the image
        width, height = image.size
        pixels = []
        for i in range(0, width, width//20):  # Sample every 20th pixel
            for j in range(0, height, height//20):
                pixels.append(image.getpixel((i, j)))
        
        # Count dark pixels (very dark = potential black rendering issue)
        dark_count = 0
        for r, g, b in pixels:
            if r < 50 and g < 50 and b < 50:
                dark_count += 1
        
        dark_percentage = (dark_count / len(pixels)) * 100
        
        # Determine if the rendering is successful
        is_successful = dark_percentage < 70
        
        results = {
            'success': is_successful,
            'svg_path': svg_path,
            'output_file': output_file,
            'image_size': image.size,
            'image_mode': image.mode,
            'png_size_bytes': len(png_bytes),
            'dark_pixel_percentage': dark_percentage,
            'total_pixels_sampled': len(pixels),
            'dark_pixels_count': dark_count,
            'timestamp': timestamp
        }
        
        return results
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'svg_path': svg_path,
            'timestamp': datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        }

def print_test_results(results: dict) -> None:
    """Print formatted test results."""
    print(f"\n📊 Test Results for: {results['svg_path']}")
    print("=" * 60)
    
    if 'error' in results:
        print(f"❌ Test failed with error: {results['error']}")
        return
    
    print(f"✅ Rendering successful: {results['success']}")
    print(f"📁 Output file: {results['output_file']}")
    print(f"🖼️  Image size: {results['image_size']}")
    print(f"🎨 Image mode: {results['image_mode']}")
    print(f"💾 PNG size: {results['png_size_bytes']:,} bytes")
    print(f"🌑 Dark pixels: {results['dark_pixel_percentage']:.1f}% ({results['dark_pixels_count']}/{results['total_pixels_sampled']})")
    
    if results['success']:
        print("🎉 Map appears to have reasonable colors!")
    else:
        print("⚠️  Map appears to be mostly black - CSS rendering issue detected!")
    
    print(f"⏰ Test completed: {results['timestamp']}")

def main():
    """Main function to run map color tests."""
    print("🗺️  Map Color Rendering Test Suite")
    print("=" * 60)
    
    # Test files to check
    test_files = [
        'maps/standard.svg',  # Original with CSS (should fail)
        'maps/standard_fixed_comprehensive.svg'  # Fixed version (should pass)
    ]
    
    results = []
    
    for svg_file in test_files:
        if os.path.exists(svg_file):
            result = test_svg_rendering(svg_file)
            results.append(result)
            print_test_results(result)
        else:
            print(f"⚠️  File not found: {svg_file}")
    
    # Summary
    print("\n📋 Test Summary")
    print("=" * 60)
    successful_tests = sum(1 for r in results if r.get('success', False))
    total_tests = len(results)
    
    print(f"Total tests: {total_tests}")
    print(f"Successful: {successful_tests}")
    print(f"Failed: {total_tests - successful_tests}")
    
    if successful_tests == total_tests:
        print("🎉 All tests passed! Map rendering is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the results above for details.")

if __name__ == "__main__":
    main() 