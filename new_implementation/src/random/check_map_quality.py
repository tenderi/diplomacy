#!/usr/bin/env python3
"""
Simple script to check map rendering quality by analyzing color distribution.
"""

import os
import sys
from PIL import Image
import io
import numpy as np


def analyze_image_colors(png_bytes: bytes) -> dict:
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
    
    # Calculate white/light pixels (RGB all above 200)
    white_mask = np.all(img_array > 200, axis=2)
    white_pixels = np.sum(white_mask)
    white_percentage = (white_pixels / total_pixels) * 100
    
    # Calculate dark pixels (broader definition - average RGB below 100)
    dark_mask = np.mean(img_array, axis=2) < 100
    dark_pixels = np.sum(dark_mask)
    dark_percentage = (dark_pixels / total_pixels) * 100
    
    # Calculate average brightness
    avg_brightness = np.mean(img_array)
    
    # Calculate color variance (higher = more colorful)
    color_variance = np.var(img_array)
    
    return {
        'total_pixels': total_pixels,
        'black_pixels': black_pixels,
        'black_percentage': black_percentage,
        'white_pixels': white_pixels,
        'white_percentage': white_percentage,
        'dark_pixels': dark_pixels,
        'dark_percentage': dark_percentage,
        'avg_brightness': avg_brightness,
        'color_variance': color_variance,
        'image_size': (image.width, image.height)
    }


def test_current_rendering():
    """Test the current cairosvg rendering"""
    
    print("🧪 Testing Current Map Rendering Quality")
    print("=" * 50)
    
    # Test cairosvg (current method)
    try:
        from src.engine.map import Map
        
        svg_path = "maps/standard.svg"
        if not os.path.exists(svg_path):
            print(f"❌ SVG file not found: {svg_path}")
            return
        
        print("📊 Rendering with CairoSVG...")
        png_bytes = Map.render_board_png(svg_path, {})
        
        # Analyze colors
        analysis = analyze_image_colors(png_bytes)
        
        print(f"\n📈 Analysis Results:")
        print(f"   Image size: {analysis['image_size']}")
        print(f"   Total pixels: {analysis['total_pixels']:,}")
        print(f"   File size: {len(png_bytes):,} bytes")
        print(f"   Black pixels: {analysis['black_percentage']:.1f}%")
        print(f"   Dark pixels: {analysis['dark_percentage']:.1f}%")
        print(f"   White pixels: {analysis['white_percentage']:.1f}%")
        print(f"   Average brightness: {analysis['avg_brightness']:.1f}")
        print(f"   Color variance: {analysis['color_variance']:.1f}")
        
        # Save for inspection
        import datetime
        os.makedirs("test_maps", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_maps/{timestamp}_current_rendering.png"
        with open(output_file, "wb") as f:
            f.write(png_bytes)
        print(f"   💾 Saved as: {output_file}")
        
        # Quality assessment
        print(f"\n🎯 Quality Assessment:")
        
        # Check if too black
        if analysis['black_percentage'] > 60:
            print(f"   ❌ FAIL: Map is too black ({analysis['black_percentage']:.1f}%)")
            print(f"      This suggests the CSS rendering issue is present.")
        else:
            print(f"   ✅ PASS: Black percentage is acceptable ({analysis['black_percentage']:.1f}%)")
        
        # Check color variance
        if analysis['color_variance'] < 1000:
            print(f"   ❌ FAIL: Poor color variance ({analysis['color_variance']:.1f})")
            print(f"      Map appears to be mostly one color.")
        else:
            print(f"   ✅ PASS: Good color variance ({analysis['color_variance']:.1f})")
        
        # Check brightness
        if analysis['avg_brightness'] < 80:
            print(f"   ❌ FAIL: Map is too dark ({analysis['avg_brightness']:.1f})")
            print(f"      Expected a brighter map.")
        else:
            print(f"   ✅ PASS: Brightness is acceptable ({analysis['avg_brightness']:.1f})")
        
        # Overall assessment
        issues = 0
        if analysis['black_percentage'] > 60:
            issues += 1
        if analysis['color_variance'] < 1000:
            issues += 1
        if analysis['avg_brightness'] < 80:
            issues += 1
        
        print(f"\n🏆 Overall Result:")
        if issues == 0:
            print(f"   ✅ EXCELLENT: Map rendering is working correctly!")
        elif issues == 1:
            print(f"   ⚠️  FAIR: Map has minor rendering issues.")
        else:
            print(f"   ❌ POOR: Map has significant rendering issues.")
            print(f"      Consider using browser-based rendering instead.")
        
    except Exception as e:
        print(f"❌ Error testing current rendering: {e}")
        import traceback
        traceback.print_exc()


def test_browser_rendering():
    """Test browser-based rendering if available"""
    
    print(f"\n🌐 Testing Browser-Based Rendering")
    print("=" * 50)
    
    try:
        from src.engine.map_browser import render_board_png_auto, is_browser_rendering_available
        
        if not is_browser_rendering_available():
            print("❌ Browser rendering not available")
            print("   Install Chrome/Chromium and ChromeDriver to enable it.")
            return
        
        svg_path = "maps/standard.svg"
        if not os.path.exists(svg_path):
            print(f"❌ SVG file not found: {svg_path}")
            return
        
        print("📊 Rendering with Browser...")
        png_bytes = render_board_png_auto(svg_path, {})
        
        # Analyze colors
        analysis = analyze_image_colors(png_bytes)
        
        print(f"\n📈 Analysis Results:")
        print(f"   Image size: {analysis['image_size']}")
        print(f"   Total pixels: {analysis['total_pixels']:,}")
        print(f"   File size: {len(png_bytes):,} bytes")
        print(f"   Black pixels: {analysis['black_percentage']:.1f}%")
        print(f"   Dark pixels: {analysis['dark_percentage']:.1f}%")
        print(f"   White pixels: {analysis['white_percentage']:.1f}%")
        print(f"   Average brightness: {analysis['avg_brightness']:.1f}")
        print(f"   Color variance: {analysis['color_variance']:.1f}")
        
        # Save for inspection
        import datetime
        os.makedirs("test_maps", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_maps/{timestamp}_browser_rendering.png"
        with open(output_file, "wb") as f:
            f.write(png_bytes)
        print(f"   💾 Saved as: {output_file}")
        
        # Browser rendering should be much better
        print(f"\n🎯 Quality Assessment:")
        
        if analysis['black_percentage'] < 30:
            print(f"   ✅ EXCELLENT: Low black percentage ({analysis['black_percentage']:.1f}%)")
        else:
            print(f"   ❌ FAIL: Still too black ({analysis['black_percentage']:.1f}%)")
        
        if analysis['color_variance'] > 2000:
            print(f"   ✅ EXCELLENT: Great color variance ({analysis['color_variance']:.1f})")
        else:
            print(f"   ❌ FAIL: Poor color variance ({analysis['color_variance']:.1f})")
        
        if analysis['avg_brightness'] > 120:
            print(f"   ✅ EXCELLENT: Good brightness ({analysis['avg_brightness']:.1f})")
        else:
            print(f"   ❌ FAIL: Too dark ({analysis['avg_brightness']:.1f})")
        
    except ImportError:
        print("❌ Browser rendering module not available")
    except Exception as e:
        print(f"❌ Error testing browser rendering: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🗺️  Diplomacy Map Rendering Quality Checker")
    print("=" * 60)
    
    # Test current rendering
    test_current_rendering()
    
    # Test browser rendering if available
    test_browser_rendering()
    
    print(f"\n✅ Quality check complete!")
    print(f"📁 Check the generated PNG files to visually inspect the results.") 