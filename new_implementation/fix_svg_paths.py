#!/usr/bin/env python3
"""
Fix SVG paths by adding explicit fill and stroke attributes.
This script adds explicit styling to SVG paths that rely on CSS classes.
"""

import re
import sys
import os

def fix_svg_paths(input_file, output_file):
    """Add explicit fill and stroke attributes to SVG paths."""
    
    print(f"Fixing SVG paths: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Define color mappings for different classes
    color_mappings = {
        'water': 'fill="#87CEEB" stroke="#4682B4" stroke-width="1"',  # Light blue water
        'nopower': 'fill="#F5DEB3" stroke="#8B4513" stroke-width="1"',  # Light brown land
        'neutral': 'fill="#D3D3D3" stroke="#696969" stroke-width="1"',  # Light gray neutral
        'impassable': 'fill="#696969" stroke="#2F4F4F" stroke-width="1"',  # Dark gray impassable
    }
    
    # Fix paths with class attributes
    for class_name, attributes in color_mappings.items():
        # Pattern to match path elements with specific class
        pattern = rf'<path class="{class_name}"([^>]*)>'
        replacement = rf'<path class="{class_name}"\1 {attributes}>'
        content = re.sub(pattern, replacement, content)
    
    # Fix paths without class (default to land)
    pattern = r'<path([^>]*class="[^"]*"[^>]*)>'
    if not re.search(pattern, content):
        # If no class attribute found, add default styling to all paths
        pattern = r'<path([^>]*)>'
        replacement = r'<path\1 fill="#F5DEB3" stroke="#8B4513" stroke-width="1">'
        content = re.sub(pattern, replacement, content)
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"Fixed SVG saved to: {output_file}")
    
    # Show what was changed
    original_size = len(content)
    print(f"File size: {original_size:,} bytes")

def main():
    if len(sys.argv) != 3:
        print("Usage: python fix_svg_paths.py <input_svg> <output_svg>")
        print("Example: python fix_svg_paths.py maps/standard.svg maps/standard_fixed.svg")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    fix_svg_paths(input_file, output_file)
    print("✅ SVG path fixing completed!")

if __name__ == "__main__":
    main() 