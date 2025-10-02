#!/usr/bin/env python3
import sys

print("Testing map rendering...")

try:
    from src.engine.map import Map
    
    # Use command line argument if provided, otherwise default to standard.svg
    if len(sys.argv) > 1:
        svg_path = sys.argv[1]
    else:
        svg_path = 'maps/standard.svg'
    
    print(f"Rendering: {svg_path}")
    
    png_bytes = Map.render_board_png(svg_path, {})
    print(f"Success! Generated {len(png_bytes):,} bytes")
    
    # Save file
    import datetime
    import os
    os.makedirs("test_maps", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"test_maps/{timestamp}_simple_test_output.png"
    with open(output_file, 'wb') as f:
        f.write(png_bytes)
    print(f"Saved as: {output_file}")
    
    # Quick analysis with PIL
    from PIL import Image
    import io
    
    image = Image.open(io.BytesIO(png_bytes))
    print(f"Image size: {image.size}")
    print(f"Image mode: {image.mode}")
    
    # Convert to RGB and get some basic stats
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Sample some pixels
    width, height = image.size
    pixels = []
    for i in range(0, width, width//10):
        for j in range(0, height, height//10):
            pixels.append(image.getpixel((i, j)))
    
    # Check if most pixels are very dark (black issue)
    dark_count = 0
    for r, g, b in pixels:
        if r < 50 and g < 50 and b < 50:
            dark_count += 1
    
    dark_percentage = (dark_count / len(pixels)) * 100
    print(f"Dark pixels in sample: {dark_percentage:.1f}%")
    
    if dark_percentage > 70:
        print("❌ WARNING: Map appears to be mostly black!")
        print("   This suggests the CSS rendering issue is present.")
    else:
        print("✅ Map appears to have reasonable colors.")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc() 