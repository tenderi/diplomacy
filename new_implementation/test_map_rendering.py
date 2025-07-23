#!/usr/bin/env python3
"""
Pytest tests for map rendering quality.
Tests both cairosvg and browser-based rendering to detect color issues.
"""

import pytest
import os
from PIL import Image
import io
import numpy as np


def analyze_image_colors(png_bytes: bytes) -> dict:
    """
    Analyze the color distribution of a PNG image.
    
    :param png_bytes: PNG image as bytes
    :return: Dictionary with color analysis
    """
    # Open image with PIL
    image = Image.open(io.BytesIO(png_bytes))
    
    # Convert to RGB if not already
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Convert to numpy array for analysis
    img_array = np.array(image)
    
    # Calculate total pixels
    total_pixels = img_array.shape[0] * img_array.shape[1]
    
    # Define color thresholds
    # Black: RGB values all below 50
    # White/Light: RGB values all above 200
    # Dark: Average RGB below 100
    
    # Calculate black pixels (very dark)
    black_mask = np.all(img_array < 50, axis=2)
    black_pixels = np.sum(black_mask)
    black_percentage = (black_pixels / total_pixels) * 100
    
    # Calculate white/light pixels
    white_mask = np.all(img_array > 200, axis=2)
    white_pixels = np.sum(white_mask)
    white_percentage = (white_pixels / total_pixels) * 100
    
    # Calculate dark pixels (broader definition)
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


def test_cairosvg_map_rendering_quality():
    """Test that cairosvg rendering produces a reasonable color distribution."""
    
    # Import the original map rendering
    from src.engine.map import Map
    
    svg_path = "maps/standard.svg"
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG file not found: {svg_path}")
    
    # Render with cairosvg (current method)
    try:
        png_bytes = Map.render_board_png(svg_path, {})
    except Exception as e:
        pytest.fail(f"CairoSVG rendering failed: {e}")
    
    # Analyze colors
    analysis = analyze_image_colors(png_bytes)
    
    print(f"\n📊 CairoSVG Analysis:")
    print(f"   Image size: {analysis['image_size']}")
    print(f"   Total pixels: {analysis['total_pixels']:,}")
    print(f"   Black pixels: {analysis['black_percentage']:.1f}%")
    print(f"   Dark pixels: {analysis['dark_percentage']:.1f}%")
    print(f"   White pixels: {analysis['white_percentage']:.1f}%")
    print(f"   Average brightness: {analysis['avg_brightness']:.1f}")
    print(f"   Color variance: {analysis['color_variance']:.1f}")
    
    # Save for manual inspection
    import datetime
    import os
    os.makedirs("test_maps", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_maps/{timestamp}_cairosvg_output.png"
    with open(output_file, "wb") as f:
        f.write(png_bytes)
    print(f"   💾 Saved as: {output_file}")
    
    # Test assertions
    assert analysis['total_pixels'] > 0, "Image should have pixels"
    assert len(png_bytes) > 1000, "PNG should be reasonably sized (>1KB)"
    
    # Main test: Map should NOT be mostly black
    assert analysis['black_percentage'] < 60.0, (
        f"Map is too black! {analysis['black_percentage']:.1f}% black pixels. "
        f"This suggests the CSS rendering issue is present."
    )
    
    # Map should have reasonable color variance (not all one color)
    assert analysis['color_variance'] > 1000, (
        f"Map has too little color variance ({analysis['color_variance']:.1f}). "
        f"This suggests poor rendering quality."
    )
    
    # Average brightness should be reasonable (not too dark)
    assert analysis['avg_brightness'] > 80, (
        f"Map is too dark (avg brightness: {analysis['avg_brightness']:.1f}). "
        f"Expected a brighter, more colorful map."
    )


@pytest.mark.skipif(not os.path.exists("src/engine/map_browser.py"), 
                   reason="Browser rendering module not available")
def test_browser_map_rendering_quality():
    """Test that browser-based rendering produces better color distribution."""
    
    try:
        from src.engine.map_browser import render_board_png_auto, is_browser_rendering_available
    except ImportError:
        pytest.skip("Browser rendering module not available")
    
    if not is_browser_rendering_available():
        pytest.skip("Browser rendering dependencies not available")
    
    svg_path = "maps/standard.svg"
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG file not found: {svg_path}")
    
    # Render with browser
    try:
        png_bytes = render_board_png_auto(svg_path, {})
    except Exception as e:
        pytest.fail(f"Browser rendering failed: {e}")
    
    # Analyze colors
    analysis = analyze_image_colors(png_bytes)
    
    print(f"\n📊 Browser Analysis:")
    print(f"   Image size: {analysis['image_size']}")
    print(f"   Total pixels: {analysis['total_pixels']:,}")
    print(f"   Black pixels: {analysis['black_percentage']:.1f}%")
    print(f"   Dark pixels: {analysis['dark_percentage']:.1f}%")
    print(f"   White pixels: {analysis['white_percentage']:.1f}%")
    print(f"   Average brightness: {analysis['avg_brightness']:.1f}")
    print(f"   Color variance: {analysis['color_variance']:.1f}")
    
    # Save for manual inspection
    import datetime
    import os
    os.makedirs("test_maps", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_maps/{timestamp}_browser_output.png"
    with open(output_file, "wb") as f:
        f.write(png_bytes)
    print(f"   💾 Saved as: {output_file}")
    
    # Test assertions
    assert analysis['total_pixels'] > 0, "Image should have pixels"
    assert len(png_bytes) > 1000, "PNG should be reasonably sized (>1KB)"
    
    # Browser rendering should be MUCH better
    assert analysis['black_percentage'] < 30.0, (
        f"Browser-rendered map is too black! {analysis['black_percentage']:.1f}% black pixels."
    )
    
    # Should have good color variance
    assert analysis['color_variance'] > 2000, (
        f"Browser-rendered map has poor color variance ({analysis['color_variance']:.1f})."
    )
    
    # Should be brighter
    assert analysis['avg_brightness'] > 120, (
        f"Browser-rendered map is too dark (avg brightness: {analysis['avg_brightness']:.1f})."
    )


def test_compare_rendering_methods():
    """Compare cairosvg vs browser rendering quality."""
    
    svg_path = "maps/standard.svg"
    if not os.path.exists(svg_path):
        pytest.skip(f"SVG file not found: {svg_path}")
    
    results = {}
    
    # Test cairosvg
    try:
        from src.engine.map import Map
        png_bytes = Map.render_board_png(svg_path, {})
        results['cairosvg'] = analyze_image_colors(png_bytes)
        import datetime
        import os
        os.makedirs("test_maps", exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with open(f"test_maps/{timestamp}_comparison_cairosvg.png", "wb") as f:
            f.write(png_bytes)
    except Exception as e:
        print(f"⚠️  CairoSVG failed: {e}")
        results['cairosvg'] = None
    
    # Test browser (if available)
    try:
        from src.engine.map_browser import render_board_png_auto, is_browser_rendering_available
        if is_browser_rendering_available():
            png_bytes = render_board_png_auto(svg_path, {})
            results['browser'] = analyze_image_colors(png_bytes)
            with open(f"test_maps/{timestamp}_comparison_browser.png", "wb") as f:
                f.write(png_bytes)
        else:
            print("⚠️  Browser rendering not available")
            results['browser'] = None
    except Exception as e:
        print(f"⚠️  Browser rendering failed: {e}")
        results['browser'] = None
    
    # Print comparison
    print(f"\n📊 Rendering Comparison:")
    print(f"{'Method':<12} {'Black%':<8} {'Bright':<8} {'Variance':<10} {'Status'}")
    print(f"{'-'*50}")
    
    for method, analysis in results.items():
        if analysis:
            status = "✅ GOOD" if analysis['black_percentage'] < 60 else "❌ BAD"
            print(f"{method:<12} {analysis['black_percentage']:<8.1f} "
                  f"{analysis['avg_brightness']:<8.1f} {analysis['color_variance']:<10.1f} {status}")
        else:
            print(f"{method:<12} {'N/A':<8} {'N/A':<8} {'N/A':<10} ❌ FAILED")
    
    # At least one method should work well
    good_methods = [method for method, analysis in results.items() 
                   if analysis and analysis['black_percentage'] < 60]
    
    assert len(good_methods) > 0, (
        "No rendering method produces acceptable results! "
        f"All methods produce maps that are too black."
    )
    
    print(f"\n✅ {len(good_methods)} method(s) produce good results: {', '.join(good_methods)}")


if __name__ == "__main__":
    # Allow running tests directly
    import sys
    sys.exit(pytest.main([__file__, "-v", "-s"])) 