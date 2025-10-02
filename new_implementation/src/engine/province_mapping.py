"""
Province name mapping for Diplomacy orders.

This module provides mappings between common province abbreviations
and the standard province names used in the game engine.
"""

# Common province name mappings
# Key: common abbreviation, Value: standard province name
PROVINCE_MAPPING = {
    # Germany
    "BER": "BER",  # Berlin
    "KIE": "KIE",  # Kiel
    "MUN": "MUN",  # Munich
    "RUH": "RUH",  # Ruhr
    "SIL": "SIL",  # Silesia
    "PRU": "PRU",  # Prussia
    
    # France
    "PAR": "PAR",  # Paris
    "MAR": "MAR",  # Marseilles
    "BRE": "BRE",  # Brest
    "BUR": "BUR",  # Burgundy
    "GAS": "GAS",  # Gascony
    "PIC": "PIC",  # Picardy
    
    # England
    "LON": "LON",  # London
    "EDI": "EDI",  # Edinburgh
    "LVP": "LVP",  # Liverpool
    "YOR": "YOR",  # Yorkshire
    "WAL": "WAL",  # Wales
    
    # Austria
    "VIE": "VIE",  # Vienna
    "BUD": "BUD",  # Budapest
    "TRI": "TRI",  # Trieste
    "BOH": "BOH",  # Bohemia
    "GAL": "GAL",  # Galicia
    "TYR": "TYR",  # Tyrolia
    
    # Italy
    "ROM": "ROM",  # Rome
    "VEN": "VEN",  # Venice
    "NAP": "NAP",  # Naples
    "PIE": "PIE",  # Piedmont
    "TUS": "TUS",  # Tuscany
    "APU": "APU",  # Apulia
    
    # Russia
    "MOS": "MOS",  # Moscow
    "STP": "STP",  # St. Petersburg
    "WAR": "WAR",  # Warsaw
    "SEV": "SEV",  # Sevastopol
    "UKR": "UKR",  # Ukraine
    "FIN": "FIN",  # Finland
    "LIV": "LIV",  # Livonia
    
    # Turkey
    "CON": "CON",  # Constantinople
    "SMY": "SMY",  # Smyrna
    "ANK": "ANK",  # Ankara
    "ARM": "ARM",  # Armenia
    "SYR": "SYR",  # Syria
    
    # Neutral territories
    "BEL": "BEL",  # Belgium
    "DEN": "DEN",  # Denmark
    "GRE": "GRE",  # Greece
    "HOL": "HOL",  # Holland
    "NWY": "NWY",  # Norway
    "POR": "POR",  # Portugal
    "RUM": "RUM",  # Rumania
    "SER": "SER",  # Serbia
    "SPA": "SPA",  # Spain
    "SWE": "SWE",  # Sweden
    "TUN": "TUN",  # Tunisia
    
    # Sea provinces
    "ADR": "ADR",  # Adriatic Sea
    "AEG": "AEG",  # Aegean Sea
    "BAL": "BAL",  # Baltic Sea
    "BAR": "BAR",  # Barents Sea
    "BLA": "BLA",  # Black Sea
    "BOT": "BOT",  # Gulf of Bothnia
    "EAS": "EAS",  # Eastern Mediterranean
    "ENG": "ENG",  # English Channel
    "GOL": "GOL",  # Gulf of Lyon
    "HEL": "HEL",  # Heligoland Bight
    "ION": "ION",  # Ionian Sea
    "IRI": "IRI",  # Irish Sea
    "MAO": "MAO",  # Mid-Atlantic Ocean
    "NAF": "NAF",  # North Africa
    "NTH": "NTH",  # North Sea
    "NWG": "NWG",  # Norwegian Sea
    "SKA": "SKA",  # Skagerrak
    "TYS": "TYS",  # Tyrrhenian Sea
    "WES": "WES",  # Western Mediterranean
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
    if normalized in PROVINCE_MAPPING.values():
        return normalized
    
    # Check if it's a common abbreviation
    if normalized in PROVINCE_MAPPING:
        return PROVINCE_MAPPING[normalized]
    
    # If not found, return the uppercase version
    # This allows for custom province names or future additions
    return normalized


def get_all_province_names() -> list:
    """
    Get all valid province names.
    
    Returns:
        List of all standard province names
    """
    return list(PROVINCE_MAPPING.values())


def is_valid_province(province_name: str) -> bool:
    """
    Check if a province name is valid.
    
    Args:
        province_name: The province name to check
        
    Returns:
        True if the province name is valid, False otherwise
    """
    normalized = normalize_province_name(province_name)
    return normalized in PROVINCE_MAPPING.values()


if __name__ == "__main__":
    # Test the mapping
    test_cases = [
        "ber", "BER", "Berlin",
        "sil", "SIL", "Silesia", 
        "lon", "LON", "London",
        "par", "PAR", "Paris",
        "unknown", "UNKNOWN", "Unknown"
    ]
    
    print("Testing province name normalization:")
    for test in test_cases:
        result = normalize_province_name(test)
        print(f"  '{test}' -> '{result}'")
    
    print(f"\nTotal provinces: {len(get_all_province_names())}")
    print(f"Is 'BER' valid? {is_valid_province('BER')}")
    print(f"Is 'INVALID' valid? {is_valid_province('INVALID')}")
