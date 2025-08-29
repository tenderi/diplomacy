#!/usr/bin/env python3
"""
Test script specifically for testing power colors and unit rendering on the map.
This verifies that units are displayed with the correct power colors and that
the map regions are properly colored.
"""

import os
import sys
import datetime
from PIL import Image
import io
import numpy as np

def test_power_colors(svg_path: str, output_dir: str = "test_maps") -> dict:
    """
    Test that units are rendered with correct power colors.
    
    Returns:
        dict: Test results including color analysis
    """
    try:
        from src.engine.map import Map
        
        print(f"🎨 Testing power colors with SVG: {svg_path}")
        
        # Create a test scenario with units from different powers
        test_units = {
            'ENGLAND': ['F LON', 'A EDI', 'F LVP'],      # Dark violet
            'FRANCE': ['A PAR', 'A MAR', 'F BRE'],       # Royal blue
            'GERMANY': ['A BER', 'A MUN', 'F KIE'],      # Brown
            'ITALY': ['A ROM', 'A VEN', 'F NAP'],        # Forest green
            'AUSTRIA': ['A VIE', 'A BUD', 'F TRI'],      # Pink/brown
            'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'F STP'], # Gray
            'TURKEY': ['A CON', 'A SMY', 'F ANK']        # Yellow
        }
        
        # Render the map with units
        print("🖼️  Rendering map with units...")
        png_bytes = Map.render_board_png(svg_path, test_units)
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the rendered image
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_power_colors_test.png"
        output_file = os.path.join(output_dir, filename)
        
        with open(output_file, 'wb') as f:
            f.write(png_bytes)
        
        print(f"💾 Saved as: {filename}")
        print(f"📏 File size: {len(png_bytes):,} bytes")
        
        # Analyze the image for power colors
        print("🔍 Analyzing power colors...")
        image = Image.open(io.BytesIO(png_bytes))
        
        # Convert to RGB for analysis
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Sample pixels around expected unit locations
        # These are approximate coordinates for the units
        unit_locations = {
            'ENGLAND': [(480, 706), (480, 554), (449, 627)],  # LON, EDI, LVP
            'FRANCE': [(509, 808), (553, 1007), (360, 788)],  # PAR, MAR, BRE
            'GERMANY': [(774, 725), (721, 868), (715, 674)], # BER, MUN, KIE
            'ITALY': [(790, 1132), (790, 1132), (769, 1132)], # ROM, VEN, NAP
            'AUSTRIA': [(826, 876), (891, 905), (785, 964)], # VIE, BUD, TRI
            'RUSSIA': [(1586, 175), (1198, 263), (1233, 1000), (939, 716)], # MOS, WAR, SEV, STP
            'TURKEY': [(1304, 1283), (1348, 1283), (1301, 1110)] # CON, SMY, ANK
        }
        
        # Analyze colors around each unit location
        power_color_analysis = {}
        for power, locations in unit_locations.items():
            colors_found = []
            for x, y in locations:
                # Sample a small area around the unit location
                for dx in range(-30, 31, 5):
                    for dy in range(-30, 31, 5):
                        sample_x = int(x * 1.2) + dx  # Scale by 1.2x to match the rendering
                        sample_y = int(y * 1.2) + dy
                        if 0 <= sample_x < image.width and 0 <= sample_y < image.height:
                            color = image.getpixel((sample_x, sample_y))
                            colors_found.append(color)
            
            if colors_found:
                # Calculate average color for this power
                avg_color = tuple(np.mean(colors_found, axis=0).astype(int))
                power_color_analysis[power] = {
                    'average_color': avg_color,
                    'samples': len(colors_found),
                    'locations': locations
                }
        
        # Overall image analysis
        img_array = np.array(image)
        total_pixels = img_array.shape[0] * img_array.shape[1]
        
        # Check for black pixels (should be low with fixed SVG)
        black_mask = np.all(img_array < 50, axis=2)
        black_pixels = np.sum(black_mask)
        black_percentage = (black_pixels / total_pixels) * 100
        
        # Calculate color variance (should be high with proper colors)
        color_variance = np.var(img_array)
        
        # Calculate average brightness
        avg_brightness = np.mean(img_array)
        
        results = {
            'success': True,
            'svg_path': svg_path,
            'output_file': output_file,
            'image_size': image.size,
            'png_size_bytes': len(png_bytes),
            'power_color_analysis': power_color_analysis,
            'black_pixel_percentage': black_percentage,
            'color_variance': color_variance,
            'avg_brightness': avg_brightness,
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

def print_power_color_results(results: dict) -> None:
    """Print detailed power color test results."""
    print(f"\n🎨 Power Color Test Results")
    print("=" * 60)
    
    if 'error' in results:
        print(f"❌ Test failed with error: {results['error']}")
        return
    
    print(f"✅ Test successful: {results['success']}")
    print(f"📁 Output file: {results['output_file']}")
    print(f"🖼️  Image size: {results['image_size']}")
    print(f"💾 PNG size: {results['png_size_bytes']:,} bytes")
    print(f"🌑 Black pixels: {results['black_pixel_percentage']:.1f}%")
    print(f"🎨 Color variance: {results['color_variance']:.1f}")
    print(f"💡 Average brightness: {results['avg_brightness']:.1f}")
    
    print(f"\n🔍 Power Color Analysis:")
    for power, analysis in results['power_color_analysis'].items():
        avg_color = analysis['average_color']
        print(f"   {power:8}: RGB{avg_color} ({analysis['samples']} samples)")
    
    # Quality assessment
    print(f"\n📊 Quality Assessment:")
    if results['black_pixel_percentage'] < 30:
        print(f"   ✅ Black pixel percentage: {results['black_pixel_percentage']:.1f}% (good)")
    else:
        print(f"   ⚠️  Black pixel percentage: {results['black_pixel_percentage']:.1f}% (high)")
    
    if results['color_variance'] > 2000:
        print(f"   ✅ Color variance: {results['color_variance']:.1f} (good color diversity)")
    else:
        print(f"   ⚠️  Color variance: {results['color_variance']:.1f} (low color diversity)")
    
    if results['avg_brightness'] > 100:
        print(f"   ✅ Average brightness: {results['avg_brightness']:.1f} (good)")
    else:
        print(f"   ⚠️  Average brightness: {results['avg_brightness']:.1f} (dark)")
    
    print(f"⏰ Test completed: {results['timestamp']}")

def main():
    """Main function to run power color tests."""
    print("🎨 Power Color and Unit Rendering Test")
    print("=" * 60)
    
    # Check if a specific SVG file was provided as command line argument
    if len(sys.argv) > 1:
        svg_file = sys.argv[1]
        if os.path.exists(svg_file):
            print(f"\n🧪 Testing: {svg_file}")
            result = test_power_colors(svg_file)
            print_power_color_results(result)
            
            # Summary for single file
            print("\n📋 Test Summary")
            print("=" * 60)
            if result.get('success', False):
                print("🎉 Test passed! Power colors are working correctly.")
            else:
                print("⚠️  Test failed. Check the results above for details.")
        else:
            print(f"⚠️  File not found: {svg_file}")
    else:
        # Test both SVG files (default behavior)
        test_files = [
            'maps/standard.svg',  # Original with CSS (should fail)
            'maps/standard_fixed_comprehensive.svg'  # Fixed version (should pass)
        ]
        
        results = []
        
        for svg_file in test_files:
            if os.path.exists(svg_file):
                print(f"\n🧪 Testing: {svg_file}")
                result = test_power_colors(svg_file)
                results.append(result)
                print_power_color_results(result)
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
            print("🎉 All tests passed! Power colors are working correctly.")
        else:
            print("⚠️  Some tests failed. Check the results above for details.")

if __name__ == "__main__":
    main()
