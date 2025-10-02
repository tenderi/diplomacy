#!/usr/bin/env python3
"""
Map configuration file for easy switching between different map options.
"""

# Map Configuration Options
MAP_OPTIONS = {
    'v2_professional': {
        'name': 'V2 Professional Map',
        'path': 'maps/v2/Vector files for printing & editing/Diplomacy Map (v2).svg',
        'description': 'Professional-grade map with excellent quality and no CSS issues',
        'recommended': True
    },
    'standard_fixed': {
        'name': 'Fixed Standard Map',
        'path': 'maps/standard_fixed_comprehensive.svg',
        'description': 'Original map with CSS issues fixed',
        'recommended': False
    },
    'standard_original': {
        'name': 'Original Standard Map',
        'path': 'maps/standard.svg',
        'description': 'Original map with CSS issues (broken rendering)',
        'recommended': False
    }
}

# Default map selection
DEFAULT_MAP = 'v2_professional'

def get_map_path(map_key: str = None) -> str:
    """
    Get the SVG file path for the specified map.
    
    Args:
        map_key: Key from MAP_OPTIONS, or None for default
        
    Returns:
        SVG file path
    """
    if map_key is None:
        map_key = DEFAULT_MAP
    
    if map_key not in MAP_OPTIONS:
        print(f"⚠️  Unknown map key: {map_key}")
        print(f"Available options: {list(MAP_OPTIONS.keys())}")
        map_key = DEFAULT_MAP
        print(f"Using default: {map_key}")
    
    return MAP_OPTIONS[map_key]['path']

def list_maps() -> None:
    """List all available map options with details."""
    print("🗺️  Available Map Options")
    print("=" * 60)
    
    for key, config in MAP_OPTIONS.items():
        status = "✅ RECOMMENDED" if config['recommended'] else "⚠️  Alternative"
        print(f"\n{key}:")
        print(f"  Name: {config['name']}")
        print(f"  Path: {config['path']}")
        print(f"  Status: {status}")
        print(f"  Description: {config['description']}")

def get_current_map_info() -> dict:
    """Get information about the currently selected map."""
    return MAP_OPTIONS[DEFAULT_MAP]

if __name__ == "__main__":
    # Show available maps when run directly
    list_maps()
    print(f"\n🎯 Current default: {get_current_map_info()['name']}")
    print(f"📁 Path: {get_map_path()}")
