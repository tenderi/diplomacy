#!/usr/bin/env python3
"""
V2 Map Coordinate System
Since the V2 map doesn't have the game-specific XML structure with jdipNS:PROVINCE elements,
we need to manually map province names to their approximate center coordinates.
"""

# V2 Map Province Coordinates (approximate centers based on visual layout)
# The V2 map has viewBox="0 0 7016 4960" - professional cartographic dimensions
V2_PROVINCE_COORDINATES = {
    # England
    'LON': (2050, 2540),  # London
    'EDI': (2015, 1990),  # Edinburgh
    'LVP': (1890, 2150),  # Liverpool
    'YOR': (2010, 2400),  # Yorkshire
    'WAL': (1845, 2455),  # Wales
    'CLY': (1915, 1935),  # Clyde
    
    # France
    'PAR': (2080, 3050),  # Paris
    'MAR': (2155, 3480),  # Marseilles
    'BRE': (1815, 2970),  # Brest
    'PIC': (2135, 2840),  # Picardy
    'BUR': (2250, 3195),  # Burgundy
    'GAS': (1810, 3350),  # Gascony
    
    # Germany
    'BER': (3160, 2585),  # Berlin
    'MUN': (2825, 2995),  # Munich
    'KIE': (2845, 2610),  # Kiel
    'RUH': (2625, 2825),  # Ruhr
    'BOH': (3215, 2995),  # Bohemia
    'SIL': (3255, 2770),  # Silesia
    'PRU': (3585, 2525),  # Prussia
    
    # Italy
    'ROM': (2980, 3855),  # Rome
    'VEN': (2845, 3480),  # Venice
    'NAP': (3180, 3975),  # Naples
    'TUS': (2815, 3675),  # Tuscany
    'PIE': (2595, 3435),  # Piedmont
    'APU': (3310, 4000),  # Apulia
    
    # Austria
    'VIE': (3280, 3240),  # Vienna
    'BUD': (3730, 3300),  # Budapest
    'TRI': (3340, 3525),  # Trieste
    'TYR': (2990, 3260),  # Tyrolia
    'GAL': (3920, 3015),  # Galicia
    'BOH': (3215, 2995),  # Bohemia (shared with Germany)
    
    # Russia
    'MOS': (5175, 2310),  # Moscow
    'WAR': (3855, 2735),  # Warsaw
    'SEV': (5625, 3220),  # Sevastopol
    'STP': (4640, 1730),  # St. Petersburg
    'UKR': (4470, 2875),  # Ukraine
    'LIV': (4040, 2235),  # Livonia
    'FIN': (4035, 1410),  # Finland
    
    # Turkey
    'CON': (4515, 4070),  # Constantinople
    'SMY': (4920, 4225),  # Smyrna
    'ANK': (5105, 3925),  # Ankara
    'ARM': (5755, 3920),  # Armenia
    'SYR': (5490, 4510),  # Syria
    
    # Neutral/Other
    'DEN': (2860, 2200),  # Denmark
    'HOL': (2495, 2605),  # Holland
    'BEL': (2355, 2750),  # Belgium
    'SPA': (1335, 3760),  # Spain
    'POR': (890, 3675),   # Portugal
    'SWE': (3325, 1710),  # Sweden
    'NOR': (2975, 1650),  # Norway
    'TUN': (2555, 4515),  # Tunisia
    'NAF': (1415, 4535),  # North Africa
    
    # Sea Areas
    'NTH': (2365, 2175),  # North Sea
    'ENG': (1660, 2730),  # English Channel
    'IRI': (1445, 2510),  # Irish Sea
    'MAO': (810, 2945),   # Mid Atlantic Ocean
    'NAO': (1035, 1765),  # North Atlantic Ocean
    'NWG': (2500, 1055),  # Norwegian Sea
    'BAR': (4465, 620),   # Barents Sea
    'BOT': (3615, 1925),  # Gulf of Bothnia
    'BAL': (3450, 2305),  # Baltic Sea
    'SKA': (2900, 2035),  # Skagerrak
    'HEL': (2545, 2375),  # Heligoland Bight
    'BLA': (4975, 3610),  # Black Sea
    'AEG': (4180, 4395),  # Aegean Sea
    'ION': (3370, 4565),  # Ionian Sea
    'ADR': (3225, 3790),  # Adriatic Sea
    'TYS': (2765, 4110),  # Tyrrhenian Sea
    'WES': (1875, 4145),  # West Mediterranean Sea
    'EAS': (4595, 4665),  # East Mediterranean Sea
    'LYO': (2155, 3785),  # Gulf of Lyons
}

def get_v2_province_coordinates(province_name: str) -> tuple:
    """
    Get the coordinates for a province on the V2 map.
    
    Args:
        province_name: Province abbreviation (e.g., 'LON', 'PAR')
        
    Returns:
        Tuple of (x, y) coordinates, or None if not found
    """
    return V2_PROVINCE_COORDINATES.get(province_name.upper())

def get_all_v2_coordinates() -> dict:
    """
    Get all V2 map coordinates.
    
    Returns:
        Dictionary mapping province names to coordinates
    """
    return V2_PROVINCE_COORDINATES.copy()

def get_v2_scaling_factors() -> tuple:
    """
    Get the correct scaling factors for V2 map coordinates.
    
    Returns:
        Tuple of (x_scale, y_scale) for converting V2 coordinates to target output
    """
    # V2 map viewBox: 7016x4960
    # Target output: 2202x1632 pixels
    x_scale = 2202 / 7016  # ≈ 0.314
    y_scale = 1632 / 4960  # ≈ 0.329
    return (x_scale, y_scale)

def scale_v2_coordinates(x: float, y: float) -> tuple:
    """
    Scale V2 map coordinates to target output dimensions.
    
    Args:
        x: X coordinate in V2 map space (0-7016)
        y: Y coordinate in V2 map space (0-4960)
        
    Returns:
        Tuple of (scaled_x, scaled_y) for target output (2202x1632)
    """
    x_scale, y_scale = get_v2_scaling_factors()
    scaled_x = int(x * x_scale)
    scaled_y = int(y * y_scale)
    return (scaled_x, scaled_y)

def list_v2_provinces() -> None:
    """List all available provinces on the V2 map."""
    print("🗺️  V2 Map Available Provinces")
    print("=" * 60)
    
    # Group by power for better organization
    powers = {
        'England': ['LON', 'EDI', 'LVP', 'YOR', 'WAL', 'CLY'],
        'France': ['PAR', 'MAR', 'BRE', 'PIC', 'BUR', 'GAS'],
        'Germany': ['BER', 'MUN', 'KIE', 'RUH', 'BOH', 'SIL', 'PRU'],
        'Italy': ['ROM', 'VEN', 'NAP', 'TUS', 'PIE', 'APU'],
        'Austria': ['VIE', 'BUD', 'TRI', 'TYR', 'GAL'],
        'Russia': ['MOS', 'WAR', 'SEV', 'STP', 'UKR', 'LIV', 'FIN'],
        'Turkey': ['CON', 'SMY', 'ANK', 'ARM', 'SYR'],
        'Neutral': ['DEN', 'HOL', 'BEL', 'SPA', 'POR', 'SWE', 'NOR', 'TUN', 'NAF'],
        'Sea Areas': ['NTH', 'ENG', 'IRI', 'MAO', 'NAO', 'NWG', 'BAR', 'BOT', 'BAL', 'SKA', 'HEL', 'BLA', 'AEG', 'ION', 'ADR', 'TYS', 'WES', 'EAS', 'LYO']
    }
    
    for power, provinces in powers.items():
        print(f"\n{power}:")
        for prov in provinces:
            coords = V2_PROVINCE_COORDINATES[prov]
            scaled_coords = scale_v2_coordinates(coords[0], coords[1])
            print(f"  {prov:4}: V2({coords[0]:4}, {coords[1]:4}) -> Output({scaled_coords[0]:4}, {scaled_coords[1]:4})")
    
    print(f"\n📊 Total: {len(V2_PROVINCE_COORDINATES)} provinces/areas")
    print(f"🗺️  V2 Map viewBox: 7016x4960")
    print(f"🎯 Target output: 2202x1632 pixels")
    x_scale, y_scale = get_v2_scaling_factors()
    print(f"📏 Scaling factors: X={x_scale:.3f}, Y={y_scale:.3f}")

if __name__ == "__main__":
    list_v2_provinces()
