#!/usr/bin/env python3
"""
Script to fix SVG styling by converting CSS classes to inline styles.
This addresses the issue where cairosvg doesn't properly process CSS styles.
"""

import re
import sys

def fix_svg_styles(svg_content):
    """Convert CSS classes to inline styles in SVG content."""
    
    # CSS class to style mappings
    style_mappings = {
        'nopower': 'fill="antiquewhite" stroke="#000000" stroke-width="1"',
        'water': 'fill="#c5dfea" stroke="#000000" stroke-width="1"',
        'neutral': 'fill="lightgray" stroke="#000000" stroke-width="1"',
        'austria': 'fill="#c48f85" stroke="#000000" stroke-width="1"',
        'england': 'fill="darkviolet" stroke="#000000" stroke-width="1"',
        'france': 'fill="royalblue" stroke="#000000" stroke-width="1"',
        'germany': 'fill="#a08a75" stroke="#000000" stroke-width="1"',
        'italy': 'fill="forestgreen" stroke="#000000" stroke-width="1"',
        'russia': 'fill="#757d91" stroke="#000000" stroke-width="1"',
        'turkey': 'fill="#b9a61c" stroke="#000000" stroke-width="1"',
        'impassable': 'fill="black" stroke="#000000" stroke-width="1"',
    }
    
    # Replace class attributes with inline styles
    for class_name, style_attr in style_mappings.items():
        # Pattern to match class="classname" and replace with style attributes
        pattern = rf'class="{class_name}"'
        replacement = style_attr
        svg_content = re.sub(pattern, replacement, svg_content)
    
    return svg_content

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fix_svg_styles.py <input_svg> <output_svg>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        
        fixed_content = fix_svg_styles(svg_content)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print(f"Successfully converted {input_file} to {output_file}")
        print("CSS classes have been converted to inline styles.")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 