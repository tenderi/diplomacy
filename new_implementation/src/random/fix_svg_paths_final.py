#!/usr/bin/env python3
"""
Fix malformed path elements in the SVG file.
The issue is that some path elements are missing proper closing tags and have malformed attributes.
"""

import re
import sys
import os
from datetime import datetime

def fix_svg_paths(input_file: str, output_file: str) -> None:
    """Fix malformed path elements in SVG file."""
    
    print(f"🔧 Fixing malformed path elements in: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_size = len(content)
    fixed_content = content
    
    # Fix paths that end with stroke-width="1"> instead of stroke-width="1"/>
    # We need to be more specific to avoid double replacements
    pattern = r'(<path[^>]*stroke-width="1">)(?!\s*/>)'
    replacement = r'\1/>'
    fixed_content = re.sub(pattern, replacement, fixed_content)
    
    # Also fix any paths that might have been corrupted with double />/>
    fixed_content = re.sub(r'/>/>', r'/>', fixed_content)
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    final_size = len(fixed_content)
    changes = original_size - final_size
    
    print(f"✅ Fixed SVG file saved to: {output_file}")
    print(f"📊 Original size: {original_size:,} bytes")
    print(f"📊 Final size: {final_size:,} bytes")
    print(f"📊 Changes: {changes:,} bytes")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fix_svg_paths_final.py <input_svg> <output_svg>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file '{input_file}' does not exist")
        sys.exit(1)
    
    try:
        fix_svg_paths(input_file, output_file)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 