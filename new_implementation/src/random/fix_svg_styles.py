#!/usr/bin/env python3
"""
Fix SVG styles for cairosvg compatibility.
This script removes CSS styles from the SVG file that cairosvg can't process.
"""

import re
import sys
import os

def clean_svg_styles(input_file, output_file):
    """Remove CSS styles from SVG file to make it compatible with cairosvg."""
    
    print(f"Cleaning SVG file: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove the entire style block
    # This regex matches the style block from <style type="text/css"><![CDATA[ to ]]></style>
    style_pattern = r'<style type="text/css"><!\[CDATA\[.*?\]\]></style>'
    cleaned_content = re.sub(style_pattern, '', content, flags=re.DOTALL)
    
    # Also remove any large black rectangles that might be covering the map
    # Look for rect elements with fill="black" and large dimensions
    black_rect_pattern = r'<rect[^>]*fill="black"[^>]*height="1360"[^>]*width="1835"[^>]*/>'
    cleaned_content = re.sub(black_rect_pattern, '', cleaned_content)
    
    # Write the cleaned content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(cleaned_content)
    
    print(f"Cleaned SVG saved to: {output_file}")
    
    # Show what was removed
    original_size = len(content)
    cleaned_size = len(cleaned_content)
    removed_size = original_size - cleaned_size
    
    print(f"Original size: {original_size:,} bytes")
    print(f"Cleaned size: {cleaned_size:,} bytes")
    print(f"Removed: {removed_size:,} bytes ({removed_size/original_size*100:.1f}%)")

def main():
    if len(sys.argv) != 3:
        print("Usage: python fix_svg_styles.py <input_svg> <output_svg>")
        print("Example: python fix_svg_styles.py maps/standard.svg maps/standard_cleaned.svg")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    clean_svg_styles(input_file, output_file)
    print("✅ SVG cleaning completed!")

if __name__ == "__main__":
    main() 