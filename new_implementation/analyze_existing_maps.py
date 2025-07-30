#!/usr/bin/env python3
"""
Analyze existing test map files to check color distribution.
"""

import os
import numpy as np
from PIL import Image

def analyze_existing_map(file_path: str) -> dict:
    """Analyze the color distribution of an existing PNG file."""
    
    print(f"Analyzing: {file_path}")
    
    # Open image with PIL
    image = Image.open(file_path)
    
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
    
    return {
        'file_path': file_path,
        'total_pixels': total_pixels,
        'black_pixels': black_pixels,
        'black_percentage': black_percentage,
        'dark_pixels': dark_pixels,
        'dark_percentage': dark_percentage,
        'white_pixels': white_pixels,
        'white_percentage': white_percentage,
        'avg_brightness': avg_brightness,
        'color_variance': color_variance,
        'image_size': (image.width, image.height)
    }

def main():
    """Analyze all existing test map files."""
    
    print("🔍 Analyzing Existing Test Map Files")
    print("=" * 50)
    
    test_maps_dir = "test_maps"
    if not os.path.exists(test_maps_dir):
        print(f"❌ Test maps directory not found: {test_maps_dir}")
        return
    
    # Find all PNG files
    png_files = [f for f in os.listdir(test_maps_dir) if f.endswith('.png')]
    
    if not png_files:
        print(f"❌ No PNG files found in {test_maps_dir}")
        return
    
    print(f"Found {len(png_files)} PNG files:")
    
    all_results = []
    
    for png_file in png_files:
        file_path = os.path.join(test_maps_dir, png_file)
        try:
            result = analyze_existing_map(file_path)
            all_results.append(result)
            
            print(f"\n📊 Results for {png_file}:")
            print(f"   Image size: {result['image_size']}")
            print(f"   Total pixels: {result['total_pixels']:,}")
            print(f"   Black pixels: {result['black_percentage']:.1f}%")
            print(f"   Dark pixels: {result['dark_percentage']:.1f}%")
            print(f"   White pixels: {result['white_percentage']:.1f}%")
            print(f"   Average brightness: {result['avg_brightness']:.1f}")
            print(f"   Color variance: {result['color_variance']:.1f}")
            
            # Quality assessment
            black_threshold = 20.0
            dark_threshold = 40.0
            brightness_threshold = 100.0
            
            if result['black_percentage'] <= black_threshold:
                print(f"   ✅ Black pixels: {result['black_percentage']:.1f}% (≤ {black_threshold}%)")
            else:
                print(f"   ❌ Black pixels: {result['black_percentage']:.1f}% (> {black_threshold}%)")
            
            if result['dark_percentage'] <= dark_threshold:
                print(f"   ✅ Dark pixels: {result['dark_percentage']:.1f}% (≤ {dark_threshold}%)")
            else:
                print(f"   ❌ Dark pixels: {result['dark_percentage']:.1f}% (> {dark_threshold}%)")
            
            if result['avg_brightness'] >= brightness_threshold:
                print(f"   ✅ Average brightness: {result['avg_brightness']:.1f} (≥ {brightness_threshold})")
            else:
                print(f"   ❌ Average brightness: {result['avg_brightness']:.1f} (< {brightness_threshold})")
                
        except Exception as e:
            print(f"❌ Error analyzing {png_file}: {e}")
    
    # Summary
    print(f"\n📈 Summary:")
    print(f"   Total files analyzed: {len(all_results)}")
    
    if all_results:
        avg_black = sum(r['black_percentage'] for r in all_results) / len(all_results)
        avg_dark = sum(r['dark_percentage'] for r in all_results) / len(all_results)
        avg_brightness = sum(r['avg_brightness'] for r in all_results) / len(all_results)
        
        print(f"   Average black pixels: {avg_black:.1f}%")
        print(f"   Average dark pixels: {avg_dark:.1f}%")
        print(f"   Average brightness: {avg_brightness:.1f}")
        
        # Overall assessment
        if avg_black <= 20.0 and avg_dark <= 40.0 and avg_brightness >= 100.0:
            print(f"   ✅ Overall: Maps have good color distribution!")
        else:
            print(f"   ❌ Overall: Maps have color distribution issues!")

if __name__ == "__main__":
    main() 