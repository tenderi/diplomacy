"""
Province name mapping for Diplomacy orders.

This module provides mappings between common province abbreviations
and the standard province names used in the game engine.
Based on provinces_spec.md specification.
"""

# Province mapping from provinces_spec.md
# Format: {abbreviation: (full_name, province_type)}
PROVINCE_MAPPING = {
    # Sea provinces
    "ADR": ("Adriatic Sea", "sea"),
    "AEG": ("Aegean Sea", "sea"),
    "BAL": ("Baltic Sea", "sea"),
    "BAR": ("Barents Sea", "sea"),
    "BLA": ("Black Sea", "sea"),
    "BOT": ("Gulf of Bothnia", "sea"),
    "EAS": ("Eastern Mediterranean", "sea"),
    "ENG": ("English Channel", "sea"),
    "GOL": ("Gulf of Lyon", "sea"),
    "HEL": ("Helgoland Bight", "sea"),
    "ION": ("Ionian Sea", "sea"),
    "IRI": ("Irish Sea", "sea"),
    "MAO": ("Mid-Atlantic Ocean", "sea"),
    "NAO": ("North Atlantic Ocean", "sea"),
    "NTH": ("North Sea", "sea"),
    "NWG": ("Norwegian Sea", "sea"),
    "SKA": ("Skagerrak", "sea"),
    "TYS": ("Tyrrhenian Sea", "sea"),
    "WES": ("Western Mediterranean", "sea"),
    
    # Land provinces
    "ALB": ("Albania", "land"),
    "ANK": ("Ankara", "land"),
    "APU": ("Apulia", "land"),
    "ARM": ("Armenia", "land"),
    "BOH": ("Bohemia", "land"),
    "BUD": ("Budapest", "land"),
    "BUR": ("Burgundy", "land"),
    "GAL": ("Galicia", "land"),
    "MOS": ("Moscow", "land"),
    "MUN": ("Munich", "land"),
    "SIL": ("Silesia", "land"),
    "SYR": ("Syria", "land"),
    "TYR": ("Tyrolia", "land"),
    "UKR": ("Ukraine", "land"),
    "VIE": ("Vienna", "land"),
    "WAR": ("Warsaw", "land"),
    
    # Coastal provinces (land provinces that fleets can enter)
    "BEL": ("Belgium", "coastal"),
    "BER": ("Berlin", "coastal"),
    "BRE": ("Brest", "coastal"),
    "BUL": ("Bulgaria", "coastal"),
    "CLY": ("Clyde", "coastal"),
    "CON": ("Constantinople", "coastal"),
    "DEN": ("Denmark", "coastal"),
    "EDI": ("Edinburgh", "coastal"),
    "FIN": ("Finland", "coastal"),
    "GAS": ("Gascony", "coastal"),
    "GRE": ("Greece", "coastal"),
    "HOL": ("Holland", "coastal"),
    "KIE": ("Kiel", "coastal"),
    "LON": ("London", "coastal"),
    "LVP": ("Liverpool", "coastal"),
    "LVN": ("Livonia", "coastal"),
    "MAR": ("Marseilles", "coastal"),
    "NAP": ("Naples", "coastal"),
    "NWY": ("Norway", "coastal"),
    "PAR": ("Paris", "coastal"),
    "PIC": ("Picardy", "coastal"),
    "PIE": ("Piedmont", "coastal"),
    "POR": ("Portugal", "coastal"),
    "PRU": ("Prussia", "coastal"),
    "ROM": ("Rome", "coastal"),
    "RUH": ("Ruhr", "coastal"),
    "RUM": ("Rumania", "coastal"),
    "SER": ("Serbia", "coastal"),
    "SEV": ("Sevastopol", "coastal"),
    "SMY": ("Smyrna", "coastal"),
    "SPA": ("Spain", "coastal"),
    "SPA/NC": ("Spain North Coast", "coastal"),
    "SPA/SC": ("Spain South Coast", "coastal"),
    "STP": ("St Petersburg", "coastal"),
    "STP/NC": ("St Petersburg North Coast", "coastal"),
    "STP/SC": ("St Petersburg South Coast", "coastal"),
    "BUL/EC": ("Bulgaria East Coast", "coastal"),
    "BUL/SC": ("Bulgaria South Coast", "coastal"),
    "SWE": ("Sweden", "coastal"),
    "TRI": ("Trieste", "coastal"),
    "TUN": ("Tunis", "coastal"),
    "TUS": ("Tuscany", "coastal"),
    "VEN": ("Venice", "coastal"),
    "WAL": ("Wales", "coastal"),
    "YOR": ("Yorkshire", "coastal"),
}

# Alternative abbreviations mapping
# Format: {alternative: standard_abbreviation}
ALTERNATIVE_MAPPING = {
    # Adriatic Sea
    "adriatic": "ADR",
    
    # Aegean Sea
    "aegean": "AEG",
    
    # Baltic Sea
    "baltic": "BAL",
    
    # Barents Sea
    "barents": "BAR",
    
    # Black Sea
    "black": "BLA",
    
    # Gulf of Bothnia
    "gob": "BOT",
    "both": "BOT",
    "gulfofb": "BOT",
    "bothnia": "BOT",
    
    # Eastern Mediterranean
    "emed": "EAS",
    "east": "EAS",
    "eastern": "EAS",
    "eastmed": "EAS",
    "ems": "EAS",
    "eme": "EAS",
    
    # English Channel
    "english": "ENG",
    "channel": "ENG",
    "ech": "ENG",
    
    # Gulf of Lyon
    "lyo": "GOL",
    "gulfofl": "GOL",
    "lyon": "GOL",
    
    # Helgoland Bight
    "helgoland": "HEL",
    
    # Ionian Sea
    "ionian": "ION",
    
    # Irish Sea
    "irish": "IRI",
    
    # Mid-Atlantic Ocean
    "midatlanticocean": "MAO",
    "midatlantic": "MAO",
    "mid": "MAO",
    "mat": "MAO",
    
    # North Atlantic Ocean
    "nat": "NAO",
    
    # North Africa
    "nora": "NAF",
    
    # North Sea
    "norsea": "NTH",
    "nts": "NTH",
    
    # Norway
    "nor": "NWY",
    "norw": "NWY",
    
    # Norwegian Sea
    "norwsea": "NWG",
    "nrg": "NWG",
    "norwegian": "NWG",
    
    # Liverpool
    "livp": "LVP",
    "lpl": "LVP",
    
    # Livonia
    "livo": "LVN",
    "lvo": "LVN",
    "lva": "LVN",
    
    # Marseilles
    "mars": "MAR",
    
    # Picardy
    "pic": "PIC",
    
    # Piedmont
    "pid": "PIE",
    
    # Portugal
    "port": "POR",
    
    # Prussia
    "prus": "PRU",
    
    # Rumania
    "romania": "RUM",
    
    # Serbia
    "serb": "SER",
    
    # Sevastopol
    "sevastapol": "SEV",
    
    # Skagerrak
    "skagerrack": "SKA",
    "skag": "SKA",
    
    # Tyrrhenian Sea
    "tyrr": "TYS",
    "tyrrhenian": "TYS",
    "tyn": "TYS",
    "tyh": "TYS",
    
    # Tyrolia
    "trl": "TYR",
    "tyl": "TYR",
    
    # Western Mediterranean
    "wmed": "WES",
    "west": "WES",
    "western": "WES",
    "westmed": "WES",
    "wms": "WES",
    "wme": "WES",
    
    # Yorkshire
    "york": "YOR",
    "yonkers": "YOR",
}


def normalize_province_name(province_name: str) -> str:
    """
    Normalize a province name to the standard format.
    
    Args:
        province_name: The province name to normalize (case-insensitive)
        
    Returns:
        The normalized province name in uppercase
        
    Examples:
        normalize_province_name("ber") -> "BER"
        normalize_province_name("silesia") -> "SIL"
        normalize_province_name("SIL") -> "SIL"
    """
    if not province_name:
        return province_name
    
    # Convert to uppercase
    normalized = province_name.upper().strip()
    
    # Check if it's already a standard name
    if normalized in PROVINCE_MAPPING:
        return normalized
    
    # Check if it's an alternative abbreviation (case-insensitive)
    if normalized.lower() in ALTERNATIVE_MAPPING:
        return ALTERNATIVE_MAPPING[normalized.lower()]
    
    # If not found, return the uppercase version
    # This allows for custom province names or future additions
    return normalized


def get_province_info(province_name: str) -> tuple:
    """
    Get province information (full name and type).
    
    Args:
        province_name: The province abbreviation
        
    Returns:
        Tuple of (full_name, province_type) or (None, None) if not found
    """
    normalized = normalize_province_name(province_name)
    if normalized in PROVINCE_MAPPING:
        return PROVINCE_MAPPING[normalized]
    return None, None


def get_all_province_names() -> list:
    """
    Get all standard province abbreviations.
    
    Returns:
        List of all province abbreviations
    """
    return list(PROVINCE_MAPPING.keys())


def get_sea_provinces() -> list:
    """
    Get all sea province abbreviations.
    
    Returns:
        List of sea province abbreviations
    """
    return [abbr for abbr, (_, prov_type) in PROVINCE_MAPPING.items() if prov_type == "sea"]


def get_land_provinces() -> list:
    """
    Get all land province abbreviations.
    
    Returns:
        List of land province abbreviations
    """
    return [abbr for abbr, (_, prov_type) in PROVINCE_MAPPING.items() if prov_type == "land"]


def get_coastal_provinces() -> list:
    """
    Get all coastal province abbreviations.
    
    Returns:
        List of coastal province abbreviations
    """
    return [abbr for abbr, (_, prov_type) in PROVINCE_MAPPING.items() if prov_type == "coastal"]


def is_sea_province(province_name: str) -> bool:
    """
    Check if a province is a sea province.
    
    Args:
        province_name: The province abbreviation
        
    Returns:
        True if it's a sea province, False otherwise
    """
    _, prov_type = get_province_info(province_name)
    return prov_type == "sea"


def is_land_province(province_name: str) -> bool:
    """
    Check if a province is a land province.
    
    Args:
        province_name: The province abbreviation
        
    Returns:
        True if it's a land province, False otherwise
    """
    _, prov_type = get_province_info(province_name)
    return prov_type == "land"


def is_coastal_province(province_name: str) -> bool:
    """
    Check if a province is a coastal province.
    
    Args:
        province_name: The province abbreviation
        
    Returns:
        True if it's a coastal province, False otherwise
    """
    _, prov_type = get_province_info(province_name)
    return prov_type == "coastal"