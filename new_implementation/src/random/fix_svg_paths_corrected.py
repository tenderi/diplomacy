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
    
    # Count matches before replacement
    matches = len(re.findall(pattern, fixed_content))
    print(f"Found {matches} malformed path elements to fix")
    
    # Apply the fix
    fixed_content = re.sub(pattern, replacement, fixed_content)
    
    # Also fix any remaining paths that end with > instead of />
    pattern2 = r'(<path[^>]*>)(?!\s*/>)'
    replacement2 = r'\1/>'
    
    matches2 = len(re.findall(pattern2, fixed_content))
    print(f"Found {matches2} additional path elements to fix")
    
    fixed_content = re.sub(pattern2, replacement2, fixed_content)
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    final_size = len(fixed_content)
    print(f"✅ Fixed SVG saved to: {output_file}")
    print(f"📊 Size: {original_size} → {final_size} bytes")
    
    # Verify the fix by checking if there are any remaining malformed paths
    remaining_matches = len(re.findall(pattern, fixed_content))
    if remaining_matches == 0:
        print("✅ All malformed path elements have been fixed!")
    else:
        print(f"⚠️  Warning: {remaining_matches} malformed path elements remain")

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 fix_svg_paths_corrected.py <input_svg> <output_svg>")
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