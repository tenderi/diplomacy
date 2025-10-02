#!/usr/bin/env python3
"""
Fix SVG CSS rendering issue by removing CSS styles and applying colors directly as attributes.
This fixes the black picture issue when rendering with cairosvg.
"""

import re
import sys
import os
from datetime import datetime

def fix_svg_css(input_file: str, output_file: str) -> None:
    """Remove CSS styles and apply colors directly as attributes."""
    
    print(f"🔧 Fixing CSS rendering issue in: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    fixed_content = content
    
    # Remove the entire CSS style section
    css_pattern = r'<style type="text/css"><!\[CDATA\[.*?\]\]></style>'
    fixed_content = re.sub(css_pattern, '', fixed_content, flags=re.DOTALL)
    
    # Apply colors directly to elements based on their class
    # Replace class="nopower" with fill="antiquewhite" stroke="#000000" stroke-width="1"
    fixed_content = re.sub(r'class="nopower"', 'fill="antiquewhite" stroke="#000000" stroke-width="1"', fixed_content)
    
    # Replace class="water" with fill="#c5dfea" stroke="#000000" stroke-width="1"
    fixed_content = re.sub(r'class="water"', 'fill="#c5dfea" stroke="#000000" stroke-width="1"', fixed_content)
    
    # Replace class="impassable" with fill="#353433" stroke="#000000" stroke-width="1"
    fixed_content = re.sub(r'class="impassable"', 'fill="#353433" stroke="#000000" stroke-width="1"', fixed_content)
    
    # Replace class="neutral" with fill="lightgray" stroke="#000000" stroke-width="1"
    fixed_content = re.sub(r'class="neutral"', 'fill="lightgray" stroke="#000000" stroke-width="1"', fixed_content)
    
    # Replace power-specific classes with their colors
    power_colors = {
        'class="austria"': 'fill="#c48f85" stroke="#000000" stroke-width="1"',
        'class="england"': 'fill="darkviolet" stroke="#000000" stroke-width="1"',
        'class="france"': 'fill="royalblue" stroke="#000000" stroke-width="1"',
        'class="germany"': 'fill="#a08a75" stroke="#000000" stroke-width="1"',
        'class="italy"': 'fill="forestgreen" stroke="#000000" stroke-width="1"',
        'class="russia"': 'fill="#757d91" stroke="#000000" stroke-width="1"',
        'class="turkey"': 'fill="#b9a61c" stroke="#000000" stroke-width="1"'
    }
    
    for old_class, new_attrs in power_colors.items():
        fixed_content = fixed_content.replace(old_class, new_attrs)
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    final_size = len(fixed_content)
    reduction = original_size - final_size
    
    print(f"✅ Fixed SVG saved to: {output_file}")
    print(f"📊 Size reduction: {reduction:,} bytes ({reduction/original_size*100:.1f}%)")
    print(f"🔍 CSS styles removed and colors applied directly")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fix_svg_css.py <input_svg> <output_svg>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    try:
        fix_svg_css(input_file, output_file)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
