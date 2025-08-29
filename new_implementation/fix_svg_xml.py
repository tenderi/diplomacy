#!/usr/bin/env python3
"""
Fix malformed XML in the SVG file that's causing parsing errors.
The issue is with malformed path elements that have unquoted or incorrectly formatted attributes.
"""

import re
import sys
import os
from datetime import datetime

def fix_svg_xml(input_file: str, output_file: str) -> None:
    """Fix malformed XML in SVG file."""
    
    print(f"🔧 Fixing malformed XML in: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    fixed_content = content
    
    # Fix malformed path elements with unquoted attributes
    # Pattern: <path class="..." d="..." id="..." fill=#F5DEB3 stroke=#8B4513 stroke-width=1>
    # Should be: <path class="..." d="..." id="..." fill="#F5DEB3" stroke="#8B4513" stroke-width="1">
    
    # Fix unquoted color values in path attributes
    fixed_content = re.sub(
        r'fill=([^"\s>]+)',
        r'fill="\1"',
        fixed_content
    )
    
    fixed_content = re.sub(
        r'stroke=([^"\s>]+)',
        r'stroke="\1"',
        fixed_content
    )
    
    # Fix any other unquoted attributes that might exist
    fixed_content = re.sub(
        r'(\w+)=([^"\s>]+)(?=\s|>)',
        r'\1="\2"',
        fixed_content
    )
    
    # Remove the problematic black background rectangle if it exists
    fixed_content = re.sub(
        r'<rect[^>]*fill="black"[^>]*height="1360"[^>]*width="1835"[^>]*/>',
        '<!-- Removed problematic black background rectangle -->',
        fixed_content
    )
    
    # Remove CSS styles that cairosvg can't process
    fixed_content = re.sub(
        r'<style type="text/css"><!\[CDATA\[.*?\]\]></style>',
        '<!-- CSS styles removed for cairosvg compatibility -->',
        fixed_content,
        flags=re.DOTALL
    )
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"✅ Fixed SVG saved to: {output_file}")
    
    # Show what was changed
    fixed_size = len(fixed_content)
    changed_size = abs(original_size - fixed_size)
    
    print(f"📊 Original size: {original_size:,} bytes")
    print(f"📊 Fixed size: {fixed_size:,} bytes")
    print(f"📊 Changed: {changed_size:,} bytes ({changed_size/original_size*100:.1f}%)")
    
    # Validate XML structure
    try:
        import xml.etree.ElementTree as ET
        ET.parse(output_file)
        print("✅ XML validation passed - file is well-formed")
    except Exception as e:
        print(f"❌ XML validation failed: {e}")
        return False
    
    return True

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fix_svg_xml.py <input_svg> <output_svg>")
        print("Example: python3 fix_svg_xml.py maps/standard.svg maps/standard_fixed.svg")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        sys.exit(1)
    
    # Create backup of original file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"{input_file}.backup_{timestamp}"
    os.system(f"cp '{input_file}' '{backup_file}'")
    print(f"💾 Backup created: {backup_file}")
    
    # Fix the SVG
    if fix_svg_xml(input_file, output_file):
        print(f"\n🎉 Successfully fixed SVG file!")
        print(f"   Input: {input_file}")
        print(f"   Output: {output_file}")
        print(f"   Backup: {backup_file}")
    else:
        print(f"\n❌ Failed to fix SVG file")
        sys.exit(1)

if __name__ == "__main__":
    main()
