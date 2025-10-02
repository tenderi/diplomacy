#!/usr/bin/env python3
"""
Comprehensive fix for SVG CSS rendering issue by removing CSS styles and applying colors directly as attributes.
This fixes the black picture issue when rendering with cairosvg.
"""

import re
import sys
import os
from datetime import datetime

def fix_svg_css_comprehensive(input_file: str, output_file: str) -> None:
    """Remove CSS styles and apply colors directly as attributes for ALL elements."""
    
    print(f"🔧 Comprehensive CSS fix for: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    fixed_content = content
    
    # Remove the entire CSS style section
    css_pattern = r'<style type="text/css"><!\[CDATA\[.*?\]\]></style>'
    fixed_content = re.sub(css_pattern, '', fixed_content, flags=re.DOTALL)
    
    # Define all CSS class replacements
    class_replacements = {
        # Map elements
        'class="nopower"': 'fill="antiquewhite" stroke="#000000" stroke-width="1"',
        'class="water"': 'fill="#c5dfea" stroke="#000000" stroke-width="1"',
        'class="impassable"': 'fill="#353433" stroke="#000000" stroke-width="1"',
        'class="neutral"': 'fill="lightgray" stroke="#000000" stroke-width="1"',
        
        # Power-specific classes
        'class="austria"': 'fill="#c48f85" stroke="#000000" stroke-width="1"',
        'class="england"': 'fill="darkviolet" stroke="#000000" stroke-width="1"',
        'class="france"': 'fill="royalblue" stroke="#000000" stroke-width="1"',
        'class="germany"': 'fill="#a08a75" stroke="#000000" stroke-width="1"',
        'class="italy"': 'fill="forestgreen" stroke="#000000" stroke-width="1"',
        'class="russia"': 'fill="#757d91" stroke="#000000" stroke-width="1"',
        'class="turkey"': 'fill="#b9a61c" stroke="#000000" stroke-width="1"',
        
        # Text elements
        'class="labeltext24"': 'text-anchor="middle" stroke-width="0.1" stroke="black" fill="black" font-family="serif,sans-serif" font-style="italic" font-size="1.4em"',
        'class="labeltext18"': 'text-anchor="middle" stroke-width="0.1" stroke="black" fill="black" font-family="serif,sans-serif" font-style="italic" font-size="1.1em"',
        'class="currentnotetext"': 'font-family="serif,sans-serif" font-size="1.5em" fill="black" stroke="black"',
        'class="currentphasetext"': 'font-family="serif,sans-serif" font-size="2.5em" fill="black" stroke="black"',
        
        # UI elements
        'class="currentnoterect"': 'fill="#c5dfea"',
        'class="invisibleContent"': 'stroke="#000000" fill="#000000" fill-opacity="0.0" opacity="0.0"',
        'class="shadow"': 'fill="black" opacity="0.3"',
        
        # Unit colors
        'class="unitaustria"': 'fill="red" fill-opacity="0.85"',
        'class="unitengland"': 'fill="mediumpurple" fill-opacity="0.85"',
        'class="unitfrance"': 'fill="deepskyblue" fill-opacity="0.85"',
        'class="unitgermany"': 'fill="dimgray" fill-opacity="0.85"',
        'class="unititaly"': 'fill="olive" fill-opacity="0.85"',
        'class="unitrussia"': 'fill="white" fill-opacity="1.0"',
        'class="unitturkey"': 'fill="yellow" fill-opacity="0.85"',
        
        # Order drawing styles
        'class="supportorder"': 'stroke-width="6" fill="none" stroke-dasharray="5,5"',
        'class="convoyorder"': 'stroke-dasharray="15,5" stroke-width="6" fill="none"',
        'class="shadowdash"': 'stroke-width="10" fill="none" stroke="black" opacity="0.45"',
        'class="varwidthorder"': 'fill="none"',
        'class="varwidthshadow"': 'fill="none" stroke="black"'
    }
    
    # Apply all replacements
    for old_class, new_attrs in class_replacements.items():
        fixed_content = fixed_content.replace(old_class, new_attrs)
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    final_size = len(fixed_content)
    reduction = original_size - final_size
    
    print(f"✅ Comprehensive CSS fix saved to: {output_file}")
    print(f"📊 Size reduction: {reduction:,} bytes ({reduction/original_size*100:.1f}%)")
    print(f"🔍 All CSS styles removed and colors applied directly")
    
    # Count remaining class attributes
    remaining_classes = len(re.findall(r'class="', fixed_content))
    if remaining_classes > 0:
        print(f"⚠️  Warning: {remaining_classes} class attributes still remain")
    else:
        print(f"✅ All class attributes successfully replaced")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fix_svg_css_comprehensive.py <input_svg> <output_svg>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    try:
        fix_svg_css_comprehensive(input_file, output_file)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
