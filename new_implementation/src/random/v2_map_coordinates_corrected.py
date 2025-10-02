#!/usr/bin/env python3
"""
V2 Map Coordinates - Projection Corrected
Automatically corrected for map projection distortion.
"""

# V2 Map Province Coordinates (projection-corrected)
V2_PROVINCE_COORDINATES = {
    'LON': (638, 835),
    'EDI': (626, 652),
    'LVP': (587, 706),
    'YOR': (625, 789),
    'WAL': (572, 807),
    'CLY': (594, 634),
    'PAR': (647, 1005),
    'MAR': (670, 1149),
    'BRE': (562, 979),
    'PIC': (665, 935),
    'BUR': (701, 1053),
    'GAS': (560, 1106),
    'BER': (991, 850),
    'MUN': (885, 986),
    'KIE': (891, 858),
    'RUH': (821, 930),
    'BOH': (1008, 986),
    'SIL': (1021, 911),
    'PRU': (1125, 830),
    'ROM': (932, 1274),
    'VEN': (890, 1148),
    'NAP': (996, 1315),
    'TUS': (880, 1214),
    'PIE': (811, 1133),
    'APU': (1037, 1323),
    'VIE': (1028, 1068),
    'BUD': (1171, 1088),
    'TRI': (1047, 1163),
    'TYR': (937, 1074),
    'GAL': (1231, 993),
    'MOS': (1630, 759),
    'WAR': (1210, 900),
    'SEV': (1776, 1063),
    'STP': (1460, 566),
    'UKR': (1405, 946),
    'LIV': (1268, 735),
    'FIN': (1268, 459),
    'CON': (1422, 1348),
    'SMY': (1553, 1401),
    'ANK': (1611, 1300),
    'ARM': (1821, 1300),
    'SYR': (1738, 1500),
    'DEN': (896, 723),
    'HOL': (780, 857),
    'BEL': (735, 905),
    'SPA': (405, 1245),
    'POR': (261, 1217),
    'SWE': (1043, 560),
    'NOR': (932, 540),
    'TUN': (795, 1500),
    'NAF': (427, 1509),
    'NTH': (739, 714),
    'ENG': (513, 899),
    'IRI': (443, 826),
    'MAO': (237, 972),
    'NAO': (310, 576),
    'NWG': (779, 339),
    'BAR': (1407, 191),
    'BOT': (1134, 632),
    'BAL': (1082, 758),
    'SKA': (908, 668),
    'HEL': (796, 781),
    'BLA': (1568, 1193),
    'AEG': (1316, 1458),
    'ION': (1056, 1516),
    'ADR': (1010, 1252),
    'TYS': (863, 1361),
    'WES': (578, 1375),
    'EAS': (1450, 1551),
    'LYO': (669, 1252),
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
