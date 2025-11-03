"""
Map representation for Diplomacy.
- Represents provinces, supply centers, adjacency, and coasts.
- Loads map data (for now, hardcoded for classic map; later, can load from file).
- Includes comprehensive map caching for performance optimization.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
import os
import json
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
import cairosvg  # type: ignore
from io import BytesIO
import hashlib
import time
from functools import lru_cache

class Province:
    """Represents a province on the Diplomacy map."""
    def __init__(self, name: str, is_supply_center: bool = False, coasts: Optional[List[str]] = None, type_: str = 'land') -> None:
        self.name: str = name
        self.is_supply_center: bool = is_supply_center
        self.coasts: List[str] = coasts or []
        self.adjacent: Set[str] = set()
        self.type: str = type_  # 'land', 'water', or 'coast'

    def add_adjacent(self, province: str) -> None:
        self.adjacent.add(province)

class MapCache:
    """Comprehensive map caching system for performance optimization."""
    
    def __init__(self, max_size: int = 100, cache_dir: str = "/tmp/diplomacy_map_cache"):
        self.max_size = max_size
        self.cache_dir = cache_dir
        self.cache: Dict[str, Tuple[bytes, float]] = {}  # key -> (image_bytes, timestamp)
        self.access_times: Dict[str, float] = {}  # key -> last_access_time
        
        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)
        
        # Load existing cache files
        self._load_cache_from_disk()
    
    def _generate_cache_key(self, svg_path: str, units: dict, phase_info: dict = None, 
                           orders: dict = None, moves: dict = None) -> str:
        """Generate a unique cache key for map parameters."""
        # Create a deterministic hash of all parameters
        key_data = {
            "svg_path": svg_path,
            "units": units,
            "phase_info": phase_info,
            "orders": orders,
            "moves": moves
        }
        
        # Convert to JSON string and hash
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _load_cache_from_disk(self) -> None:
        """Load cache metadata from disk on startup."""
        try:
            cache_meta_file = os.path.join(self.cache_dir, "cache_meta.json")
            if os.path.exists(cache_meta_file):
                with open(cache_meta_file, 'r') as f:
                    meta_data = json.load(f)
                    self.access_times = meta_data.get("access_times", {})
        except Exception as e:
            print(f"Warning: Could not load cache metadata: {e}")
    
    def _save_cache_metadata(self) -> None:
        """Save cache metadata to disk."""
        try:
            cache_meta_file = os.path.join(self.cache_dir, "cache_meta.json")
            meta_data = {
                "access_times": self.access_times,
                "cache_size": len(self.cache)
            }
            with open(cache_meta_file, 'w') as f:
                json.dump(meta_data, f)
        except Exception as e:
            print(f"Warning: Could not save cache metadata: {e}")
    
    def get(self, cache_key: str) -> Optional[bytes]:
        """Get cached map image if available."""
        if cache_key in self.cache:
            # Update access time
            self.access_times[cache_key] = time.time()
            
            # Try to load from disk if not in memory
            if cache_key not in self.cache or self.cache[cache_key][0] is None:
                cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'rb') as f:
                            img_bytes = f.read()
                            self.cache[cache_key] = (img_bytes, time.time())
                            return img_bytes
                    except Exception as e:
                        print(f"Warning: Could not load cached image {cache_key}: {e}")
            
            return self.cache[cache_key][0]
        
        return None
    
    def put(self, cache_key: str, img_bytes: bytes) -> None:
        """Cache map image."""
        current_time = time.time()
        
        # Store in memory
        self.cache[cache_key] = (img_bytes, current_time)
        self.access_times[cache_key] = current_time
        
        # Save to disk
        try:
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
            with open(cache_file, 'wb') as f:
                f.write(img_bytes)
        except Exception as e:
            print(f"Warning: Could not save cached image {cache_key}: {e}")
        
        # Cleanup if cache is too large
        self._cleanup_cache()
        
        # Save metadata
        self._save_cache_metadata()
    
    def _cleanup_cache(self) -> None:
        """Remove least recently used items if cache is too large."""
        if len(self.cache) <= self.max_size:
            return
        
        # Sort by access time (oldest first)
        sorted_items = sorted(self.access_times.items(), key=lambda x: x[1])
        
        # Remove oldest items
        items_to_remove = len(self.cache) - self.max_size
        for i in range(items_to_remove):
            key_to_remove = sorted_items[i][0]
            
            # Remove from memory
            if key_to_remove in self.cache:
                del self.cache[key_to_remove]
            
            # Remove from disk
            cache_file = os.path.join(self.cache_dir, f"{key_to_remove}.png")
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            except Exception as e:
                print(f"Warning: Could not remove cache file {cache_file}: {e}")
            
            # Remove from access times
            if key_to_remove in self.access_times:
                del self.access_times[key_to_remove]
    
    def clear(self) -> None:
        """Clear all cached maps."""
        self.cache.clear()
        self.access_times.clear()
        
        # Remove all cache files
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.png') or filename == 'cache_meta.json':
                    file_path = os.path.join(self.cache_dir, filename)
                    os.remove(file_path)
        except Exception as e:
            print(f"Warning: Could not clear cache directory: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(len(img_bytes) for img_bytes, _ in self.cache.values())
        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "total_bytes": total_size,
            "cache_dir": self.cache_dir,
            "oldest_access": min(self.access_times.values()) if self.access_times else None,
            "newest_access": max(self.access_times.values()) if self.access_times else None
        }

# Global SVG parsing cache
_svg_cache: Dict[str, Tuple[ET.ElementTree, Dict[str, Tuple[float, float]]]] = {}
_font_cache: Optional[ImageFont.ImageFont] = None

# Global map cache instance
_map_cache = MapCache()

class Map:
    """Represents the Diplomacy map, including provinces and their adjacencies."""
    
    # List of water provinces (sea/ocean spaces)
    WATER_PROVINCES = {
        "ADR", "AEG", "BAL", "BAR", "BLA", "BOT", "EAS", "ENG", "HEL", "ION", "IRI", "MAO", "NAO", "NTH", "NWG", "SKA", "TYS", "WES"
    }
    
    def __init__(self, map_name: str = 'standard') -> None:
        self.provinces: Dict[str, Province] = {}
        self.supply_centers: Set[str] = set()
        self.map_name: str = map_name
        self._init_map(map_name)

    def _init_map(self, map_name: str) -> None:
        if map_name == 'standard':
            self._init_classic_map()
        else:
            # Load map from file for variants
            map_dir = os.path.join(os.path.dirname(__file__), '../../maps')
            map_file = os.path.join(map_dir, f'{map_name}.json')
            if not os.path.isfile(map_file):
                raise FileNotFoundError(f"Map file '{map_file}' not found for variant '{map_name}'")
            with open(map_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Expecting JSON: {"provinces": {name: {"is_supply_center": bool, "adjacent": [str], "coasts": [str]}}}
            for name, info in data["provinces"].items():
                prov = Province(name, is_supply_center=info.get("is_supply_center", False), coasts=info.get("coasts", []))
                self.provinces[name] = prov
                if prov.is_supply_center:
                    self.supply_centers.add(name)
            # Add adjacencies
            for name, info in data["provinces"].items():
                for adj in info.get("adjacent", []):
                    if adj in self.provinces:
                        self.provinces[name].add_adjacent(adj)
                        self.provinces[adj].add_adjacent(name)

    def _init_classic_map(self) -> None:
        # Always use the hardcoded standard map for reliability
        self._init_hardcoded_standard_map()

    def _parse_map_file(self, map_file_path: str) -> None:
        """Parse a .map file from the old implementation."""
        with open(map_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse supply centers from the power definitions
        supply_centers: set[str] = set()
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('//') and '(' in line and ')' in line:
                # This is a power definition line like "AUSTRIA     (AUSTRIAN)     BUD TRI VIE"
                if line.count('(') == 1 and line.count(')') == 1:
                    parts = line.split(')')
                    if len(parts) == 2:
                        centers_part = parts[1].strip()
                        if centers_part:
                            centers = centers_part.split()
                            # Normalize supply center names to uppercase
                            supply_centers.update([center.upper() for center in centers])

        # Parse adjacencies
        adjacencies: dict[str, list[str]] = {}
        for line in lines:
            line = line.strip()
            if line.startswith('LAND ') or line.startswith('COAST ') or line.startswith('WATER '):
                # Parse adjacency line like "LAND     SIL        ABUTS    BER BOH GAL MUN PRU WAR"
                parts = line.split()
                if len(parts) >= 4 and parts[2] == 'ABUTS':
                    province = parts[1].upper()  # Normalize to uppercase
                    adjacent_provinces = [adj.upper() for adj in parts[3:]]  # Normalize to uppercase
                    adjacencies[province] = adjacent_provinces

        # Create provinces
        for province in adjacencies:
            is_supply_center = province in supply_centers
            self.provinces[province] = Province(province, is_supply_center=is_supply_center)
            if is_supply_center:
                self.supply_centers.add(province)
        for province, adjacent_list in adjacencies.items():
            for adj in adjacent_list:
                if adj in self.provinces:
                    self.provinces[province].add_adjacent(adj)
                    self.provinces[adj].add_adjacent(province)

    def _init_hardcoded_standard_map(self) -> None:
        """Fallback hardcoded standard map data using province mapping."""
        from .province_mapping import get_sea_provinces, get_coastal_provinces, get_land_provinces
        
        # Get province types from the mapping system
        water_provinces = set(get_sea_provinces())
        coastal_provinces = set(get_coastal_provinces())
        land_provinces = set(get_land_provinces())
        province_data = [
            # Power home centers
            ("BUD", True, ["GAL", "RUM", "SER", "TRI", "VIE"]),
            ("TRI", True, ["ADR", "ALB", "BUD", "TYR", "VEN", "VIE"]),
            ("VIE", True, ["BOH", "BUD", "GAL", "TRI", "TYR"]),
            ("EDI", True, ["CLY", "NTH", "YOR"]),
            ("LON", True, ["ENG", "NTH", "WAL", "YOR"]),
            ("LVP", True, ["CLY", "IRI", "NAO", "WAL", "YOR"]),
            ("BRE", True, ["ENG", "GAS", "MAO", "PAR", "PIC"]),
            ("MAR", True, ["BUR", "GAS", "GOL", "PIE", "SPA"]),
            ("PAR", True, ["BRE", "BUR", "GAS", "PIC"]),
            ("BER", True, ["BAL", "KIE", "MUN", "PRU", "SIL"]),
            ("KIE", True, ["BAL", "BER", "DEN", "HEL", "HOL", "MUN", "RUH"]),
            ("MUN", True, ["BER", "BOH", "BUR", "KIE", "RUH", "SIL", "TYR"]),
            ("NAP", True, ["APU", "ION", "ROM", "TYS"]),
            ("ROM", True, ["APU", "NAP", "TUS", "TYS", "VEN"]),
            ("VEN", True, ["ADR", "APU", "PIE", "ROM", "TRI", "TUS", "TYR"]),
            ("MOS", True, ["LVN", "SEV", "STP", "UKR", "WAR"]),
            ("SEV", True, ["ARM", "BLA", "MOS", "RUM", "UKR"]),
            ("STP", True, ["BAR", "BOT", "FIN", "LVN", "MOS", "NWY"]),
            ("WAR", True, ["GAL", "LVN", "MOS", "PRU", "SIL", "UKR"]),
            ("ANK", True, ["ARM", "BLA", "CON", "SMY"]),
            ("CON", True, ["AEG", "ANK", "BLA", "BUL", "SMY"]),
            ("SMY", True, ["AEG", "ANK", "CON", "EAS", "SYR"]),
            # Non-supply center provinces
            ("ADR", False, ["ALB", "APU", "ION", "TRI", "VEN"]),
            ("AEG", False, ["BUL", "CON", "EAS", "GRE", "ION", "SMY"]),
            ("ALB", False, ["ADR", "GRE", "ION", "SER", "TRI"]),
            ("APU", False, ["ADR", "ION", "NAP", "ROM", "VEN"]),
            ("ARM", False, ["ANK", "BLA", "SEV", "SMY", "SYR"]),
            ("BAL", False, ["BER", "BOT", "DEN", "KIE", "LVN", "PRU", "SWE"]),
            ("BAR", False, ["NWY", "STP"]),
            ("BLA", False, ["ANK", "ARM", "BUL", "CON", "RUM", "SEV"]),
            ("BOH", False, ["GAL", "MUN", "SIL", "TYR", "VIE"]),
            ("BOT", False, ["BAL", "FIN", "LVN", "STP", "SWE"]),
            ("BUL", False, ["AEG", "BLA", "CON", "GRE", "RUM", "SER"]),
            ("BUR", False, ["BEL", "GAS", "MAR", "MUN", "PAR", "PIC", "RUH"]),
            ("CLY", False, ["EDI", "IRI", "LVP", "NAO", "NWG"]),
            ("DEN", False, ["BAL", "HEL", "KIE", "NTH", "SKA", "SWE"]),
            ("EAS", False, ["AEG", "ION", "SMY", "SYR"]),
            ("ENG", False, ["BRE", "IRI", "LON", "MAO", "NTH", "PIC", "WAL"]),
            ("FIN", False, ["BOT", "NWY", "STP", "SWE"]),
            ("GAL", False, ["BOH", "BUD", "RUM", "SIL", "UKR", "VIE", "WAR"]),
            ("GAS", False, ["BRE", "BUR", "MAR", "PAR", "SPA"]),
            ("GOL", False, ["MAR", "PIE", "SPA", "TUS", "TYS", "WES"]),
            ("GRE", False, ["AEG", "ALB", "BUL", "ION", "SER"]),
            ("HEL", False, ["DEN", "HOL", "KIE", "NTH"]),
            ("ION", False, ["ADR", "AEG", "ALB", "APU", "EAS", "GRE", "NAP", "TUN", "TYS"]),
            ("IRI", False, ["CLY", "ENG", "LVP", "MAO", "NAO", "WAL"]),
            ("LVN", False, ["BAL", "BOT", "MOS", "PRU", "STP", "WAR"]),
            ("MAO", False, ["BRE", "ENG", "IRI", "NAO", "POR", "SPA", "WES"]),
            ("NAO", False, ["CLY", "IRI", "LVP", "MAO", "NWG"]),
            ("NTH", False, ["DEN", "EDI", "ENG", "HEL", "HOL", "LON", "NWY", "SKA", "YOR"]),
            ("NWG", False, ["BAR", "CLY", "NAO", "NWY", "STP"]),
            ("NWY", False, ["BAR", "FIN", "NTH", "NWG", "SKA", "STP", "SWE"]),
            ("PIC", False, ["BEL", "BRE", "BUR", "ENG", "PAR"]),
            ("PIE", False, ["GOL", "MAR", "TUS", "TYR", "VEN"]),
            ("PRU", False, ["BAL", "BER", "LVN", "SIL", "WAR"]),
            ("RUH", False, ["BEL", "BUR", "HOL", "KIE", "MUN"]),
            ("RUM", False, ["BLA", "BUD", "BUL", "GAL", "SEV", "SER", "UKR"]),
            ("SER", False, ["ALB", "BUD", "BUL", "GRE", "RUM", "TRI"]),
            ("SIL", False, ["BER", "BOH", "GAL", "MUN", "PRU", "WAR"]),
            ("SKA", False, ["DEN", "NTH", "NWY", "SWE"]),
            ("SYR", False, ["ARM", "EAS", "SMY"]),
            ("TUS", False, ["GOL", "PIE", "ROM", "TYS", "VEN"]),
            ("TYR", False, ["BOH", "MUN", "PIE", "TRI", "VEN", "VIE"]),
            ("TYS", False, ["GOL", "ION", "NAP", "ROM", "TUN", "TUS", "WES"]),
            ("UKR", False, ["GAL", "MOS", "RUM", "SEV", "WAR"]),
            ("WAL", False, ["ENG", "IRI", "LON", "LVP", "YOR"]),
            ("WES", False, ["GOL", "MAO", "NAF", "SPA", "TUN", "TYS"]),
            ("YOR", False, ["EDI", "LON", "LVP", "NTH", "WAL"]),
            # Neutral supply centers
            ("BEL", True, ["BUR", "HOL", "PIC", "RUH"]),
            ("DEN", True, ["BAL", "HEL", "KIE", "NTH", "SKA", "SWE"]),
            ("GRE", True, ["AEG", "ALB", "BUL", "ION", "SER"]),
            ("HOL", True, ["BEL", "HEL", "KIE", "NTH", "RUH"]),
            ("NWY", True, ["BAR", "FIN", "NTH", "NWG", "SKA", "STP", "SWE"]),
            ("POR", True, ["MAO", "SPA"]),
            ("RUM", True, ["BLA", "BUD", "BUL", "GAL", "SEV", "SER", "UKR"]),
            ("SER", True, ["ALB", "BUD", "BUL", "GRE", "RUM", "TRI"]),
            ("SPA", True, ["GAS", "GOL", "MAO", "MAR", "POR", "WES"]),
            ("SWE", True, ["BAL", "BOT", "DEN", "FIN", "NWY", "SKA"]),
            ("TUN", True, ["ION", "NAF", "TYS", "WES"]),
        ]

        # Create provinces
        for name, is_sc, adjacents in province_data:
            if name in water_provinces:
                type_ = 'sea'  # Sea provinces should be 'sea', not 'water'
            elif name in coastal_provinces:
                type_ = 'coastal'
            elif name in land_provinces:
                type_ = 'land'
            else:
                # Default to land if not found in mapping
                type_ = 'land'
            self.provinces[name] = Province(name, is_supply_center=is_sc, type_=type_)
            if is_sc:
                self.supply_centers.add(name)

        # Set up adjacencies (ensure bidirectional)
        for name, _, adjacents in province_data:
            for adj in adjacents:
                if adj in self.provinces:
                    self.provinces[name].add_adjacent(adj)
                    self.provinces[adj].add_adjacent(name)

    @staticmethod
    def _get_cached_svg_data(svg_path: str) -> Tuple[ET.ElementTree, Dict[str, Tuple[float, float]]]:
        """Get cached SVG data or parse and cache it."""
        global _svg_cache
        
        if svg_path not in _svg_cache:
            # Resolve SVG path with fallbacks for tests/env
            import os
            if not os.path.exists(svg_path):
                fallback = os.environ.get("DIPLOMACY_MAP_PATH")
                if fallback and os.path.exists(fallback):
                    svg_path = fallback
                else:
                    candidates = [
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "maps", "standard.svg")),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src", "tests", "maps", "standard.svg")),
                        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "maps", "standard.svg")),
                    ]
                    for c in candidates:
                        if os.path.exists(c):
                            svg_path = c
                            break
            # Parse SVG and extract coordinates
            tree = ET.parse(svg_path)
            root = tree.getroot()
            
            # Check if this is the V2 map (doesn't have jdipNS structure)
            if 'v2' in svg_path.lower():
                try:
                    from v2_map_coordinates import get_all_v2_coordinates
                    coords = get_all_v2_coordinates()
                except ImportError:
                    print("⚠️  Warning: v2_map_coordinates module not found, using fallback coordinates")
                    # Fallback coordinates for V2 map
                    coords = {
                        'LON': (1921, 2378), 'PAR': (1948, 2859), 'BER': (2960, 2423),
                        'VIE': (3074, 3039), 'MOS': (4849, 2167), 'ROM': (2793, 3613),
                        'CON': (4233, 3821), 'EDI': (1886, 1866), 'MAR': (2020, 3265),
                        'MUN': (2645, 2808), 'BUD': (3497, 3099), 'WAR': (3612, 2564),
                        'VEN': (2662, 3265), 'SMY': (4609, 3974), 'STP': (4347, 1624),
                        'KIE': (2662, 2448), 'TRI': (3130, 3306), 'SEV': (5268, 3021),
                        'NAP': (2980, 3732), 'ANK': (4785, 3682), 'LVP': (1767, 2022),
                        'BRE': (1697, 2782), 'BOH': (3012, 2808), 'GAL': (3673, 2825),
                        'UKR': (4186, 2698), 'TYR': (2801, 3055), 'ARM': (5392, 3676),
                        'PIC': (2000, 2665), 'SIL': (3052, 2597), 'PRU': (3360, 2367),
                        'LIV': (3783, 2096), 'FIN': (3781, 1321), 'SYR': (5143, 4231)
                    }
            else:
                # Use jdipNS coordinates - these are the correct coordinate system
                coords = {}
                ns = {'jdipNS': 'svg.dtd'}
                
                for prov in root.findall('.//jdipNS:PROVINCE', ns):
                    name = prov.attrib.get('name')
                    unit = prov.find('jdipNS:UNIT', ns)
                    if name and unit is not None:
                        x = float(unit.attrib.get('x', '0'))
                        y = float(unit.attrib.get('y', '0'))
                        coords[name.upper()] = (x, y)
            
            # Cache the parsed data
            _svg_cache[svg_path] = (tree, coords)
        
        return _svg_cache[svg_path]

    @staticmethod
    def get_svg_province_coordinates(svg_path: str) -> dict:
        """
        Parse the SVG file and extract province coordinates for unit placement.
        Returns a dict: {province_name: (x, y)}
        Uses jdipNS coordinates which are the correct coordinate system.
        Optimized with caching to avoid repeated parsing.
        """
        _, coords = Map._get_cached_svg_data(svg_path)
        return coords

    @staticmethod
    def _get_cached_font(size: int) -> ImageFont.ImageFont:
        """Get cached font or load and cache it."""
        global _font_cache
        
        # For now, we'll cache one font size (30) which is most commonly used
        # In the future, we could extend this to cache multiple sizes
        if _font_cache is None:
            try:
                _font_cache = ImageFont.truetype("DejaVuSans-Bold.ttf", 30)
            except Exception:
                _font_cache = ImageFont.load_default()
        
        # Return cached font if size matches, otherwise load new one
        if size == 30:
            return _font_cache
        else:
            try:
                return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
            except Exception:
                return ImageFont.load_default()

    @staticmethod
    def _color_provinces_by_power_with_transparency(bg_image, units, power_colors, svg_path, supply_center_control=None, current_phase=None, color_only_supply_centers=False, supply_centers_set=None):
        """Color provinces using proper transparency with separate overlay layer.
        
        Args:
            bg_image: Background image to color
            units: Dictionary mapping powers to their unit lists
            power_colors: Dictionary mapping power names to colors
            svg_path: Path to SVG map file
            supply_center_control: Dictionary mapping supply center provinces to controlling powers
            current_phase: Current game phase (for future use)
            color_only_supply_centers: If True, only color supply center provinces
            supply_centers_set: Set of supply center province names (required if color_only_supply_centers is True)
        """
        try:
            # Use cached SVG data instead of parsing again
            tree, jdip_coords = Map._get_cached_svg_data(svg_path)
            root = tree.getroot()
            
            # Create a separate transparent overlay layer
            overlay = Image.new('RGBA', bg_image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            
            # Define namespace for SVG elements
            namespaces = {'svg': 'http://www.w3.org/2000/svg'}
            
            # Find all path elements with id attributes (these are provinces)
            all_paths = root.findall('.//svg:path[@id]', namespaces)
            if not all_paths:
                all_paths = root.findall('.//path[@id]')
            
            # Find SVG paths for provinces (these are the actual province shapes)
            province_paths = []
            for path in all_paths:
                province_id = path.get('id')
                if province_id and province_id.startswith('_'):
                    province_paths.append(path)
            
            # Create a map of province names to power colors
            province_power_map = {}
            
            # First, add supply center control colors (if provided)
            if supply_center_control:
                for province, power in supply_center_control.items():
                    color = power_colors.get(power.upper(), "black")
                    province_power_map[province.upper()] = color
            
            # Then, add unit location colors (overrides supply center colors for occupied provinces)
            for power, unit_list in units.items():
                color = power_colors.get(power.upper(), "black")
                for unit in unit_list:
                    parts = unit.split()
                    if len(parts) == 2:
                        prov = parts[1].upper()
                        # Only override if this is not a dislodged unit
                        if not prov.startswith("DISLODGED_"):
                            province_power_map[prov] = color
            
            # Get supply centers set if filtering is enabled
            if color_only_supply_centers:
                if supply_centers_set is None:
                    # Try to get supply centers from Map instance if available
                    try:
                        map_instance = Map("standard")
                        supply_centers_set = set(map_instance.get_supply_centers())
                    except:
                        supply_centers_set = set()  # Fallback: empty set
                # Filter province_power_map to only include supply centers
                province_power_map = {prov: color for prov, color in province_power_map.items() 
                                    if prov in supply_centers_set}
            
            # Color each province based on power control using SVG paths
            for path_elem in province_paths:
                province_id = path_elem.get('id')
                if province_id:
                    # Remove underscore prefix and convert to uppercase
                    normalized_id = province_id.lstrip('_').upper()
                    
                    if normalized_id in province_power_map:
                        # If color_only_supply_centers is enabled, skip non-supply-center provinces
                        if color_only_supply_centers:
                            if supply_centers_set and normalized_id not in supply_centers_set:
                                continue
                        
                        # Get the power color for this province
                        power_color = province_power_map[normalized_id]
                        
                        # Convert color to RGB for proper transparency
                        rgb_color = Map._hex_to_rgb(power_color)
                        
                        # Determine opacity based on province type
                        base_opacity = 90  # 90/255 ≈ 0.35 (35% opacity)
                        if normalized_id in Map.WATER_PROVINCES:
                            # Decrease opacity by 40% for water provinces (40% of base opacity)
                            opacity = max(0, int(base_opacity * 0.60))  # 60% of base opacity = 40% reduction
                        else:
                            opacity = base_opacity
                        
                        transparent_color = (*rgb_color, opacity)
                        
                        # Parse and fill the SVG path with correct coordinate alignment
                        path_data = path_elem.get('d')
                        if path_data:
                            # Apply correct transform to align SVG paths with jdipNS coordinates
                            Map._fill_svg_path_with_transform(overlay_draw, path_data, transparent_color, power_color, 195, 169)
            
            # Composite the overlay onto the background image using proper alpha compositing
            bg_image.paste(overlay, (0, 0), overlay)
                    
        except Exception as e:
            print(f"Warning: Could not parse SVG for province coloring: {e}")
            # Fallback: continue without province coloring

    @staticmethod
    def _color_provinces_by_power(draw, units, power_colors, svg_path):
        """Color provinces based on power control by parsing SVG paths with correct coordinate alignment."""
        try:
            import xml.etree.ElementTree as ET
            
            # Parse the SVG file
            tree = ET.parse(svg_path)
            root = tree.getroot()
            
            # Define namespace for SVG elements
            namespaces = {'svg': 'http://www.w3.org/2000/svg'}
            
            # Find all path elements with id attributes (these are provinces)
            # Prioritize paths without underscores (actual province areas)
            province_paths = []
            
            # First, get all paths
            all_paths = root.findall('.//svg:path[@id]', namespaces)
            if not all_paths:
                all_paths = root.findall('.//path[@id]')
            
            # Get jdipNS coordinates for reference, but color actual SVG province paths
            ns = {'jdipNS': 'svg.dtd'}
            jdip_coords = {}
            for prov in root.findall('.//jdipNS:PROVINCE', ns):
                name = prov.attrib.get('name')
                unit = prov.find('jdipNS:UNIT', ns)
                if name and unit is not None:
                    x = float(unit.attrib.get('x', '0'))
                    y = float(unit.attrib.get('y', '0'))
                    jdip_coords[name.upper()] = (x, y)
            
            # Find SVG paths for provinces (these are the actual province shapes)
            province_paths = []
            for path in all_paths:
                province_id = path.get('id')
                if province_id and province_id.startswith('_'):
                    # Use paths with underscores - these are the actual province areas
                    province_paths.append(path)
            
            # Create a map of province names to power colors
            province_power_map = {}
            for power, unit_list in units.items():
                color = power_colors.get(power.upper(), "black")
                for unit in unit_list:
                    parts = unit.split()
                    if len(parts) == 2:
                        prov = parts[1].upper()
                        province_power_map[prov] = color
            
            # Color each province based on power control using SVG paths
            for path_elem in province_paths:
                province_id = path_elem.get('id')
                if province_id:
                    # Remove underscore prefix and convert to uppercase
                    normalized_id = province_id.lstrip('_').upper()
                    
                    if normalized_id in province_power_map:
                        # Get the power color for this province
                        power_color = province_power_map[normalized_id]
                        
                        # Convert color to RGB and apply 10% opacity by scaling RGB values
                        # This avoids alpha transparency issues while keeping map details visible
                        rgb_color = Map._hex_to_rgb(power_color)
                        opacity_factor = 0.10  # 10% opacity - much lighter to preserve map details
                        solid_color = tuple(int(c * opacity_factor) for c in rgb_color)
                        
                        # Parse and fill the SVG path with correct coordinate alignment
                        path_data = path_elem.get('d')
                        if path_data:
                            # Apply correct transform to align SVG paths with jdipNS coordinates
                            # Based on investigation: average offset is (-251.2, -174.2)
                            # Fine-tuned: X offset 195, Y offset 169 (reduced by 5 as it was too far down)
                            Map._fill_svg_path_with_transform(draw, path_data, solid_color, power_color, 195, 169)
                            
                            # Add province name label to the colored area
                            if normalized_id in jdip_coords:
                                x, y = jdip_coords[normalized_id]
                                # Draw province name in white with black outline for visibility
                                font = None
                                try:
                                    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
                                except Exception:
                                    font = ImageFont.load_default()
                                
                                # Draw text with black outline
                                text = normalized_id
                                bbox = draw.textbbox((0, 0), text, font=font)
                                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                                
                                # Draw black outline
                                for dx in [-1, 0, 1]:
                                    for dy in [-1, 0, 1]:
                                        if dx != 0 or dy != 0:
                                            draw.text((x - w/2 + dx, y - h/2 + dy), text, fill="black", font=font)
                                
                                # Draw white text on top
                                draw.text((x - w/2, y - h/2), text, fill="white", font=font)
                    
        except Exception as e:
            print(f"Warning: Could not parse SVG for province coloring: {e}")
            # Fallback: continue without province coloring
    
    @staticmethod
    def _fill_svg_path_with_transform(draw, path_data, fill_color, stroke_color, offset_x, offset_y):
        """Fill an SVG path with coordinate transform to compensate for SVG group transforms."""
        try:
            # Parse the path data to extract coordinates
            commands = []
            current_x, current_y = 0, 0
            
            # Split path data into commands
            import re
            path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)
            
            for cmd, params in path_commands:
                cmd = cmd.upper()
                if cmd == 'M':  # Move to
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 2:
                        current_x, current_y = float(coords[0]), float(coords[1])
                        commands.append(('M', current_x, current_y))
                elif cmd == 'L':  # Line to
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 2:
                        current_x, current_y = float(coords[0]), float(coords[1])
                        commands.append(('L', current_x, current_y))
                elif cmd == 'C':  # Cubic Bezier curve
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 6:  # C x1 y1 x2 y2 x y
                        # For simplicity, we'll use the end point of the curve
                        current_x, current_y = float(coords[4]), float(coords[5])
                        commands.append(('L', current_x, current_y))
                elif cmd == 'Z':  # Close path
                    commands.append(('Z',))
            
            # Apply inverse transform to compensate for SVG group transform
            if len(commands) > 2:
                points = []
                for cmd in commands:
                    if cmd[0] in ['M', 'L']:
                        # Apply inverse transform: subtract the offset to compensate for translate(-195 -170)
                        x = cmd[1] - offset_x
                        y = cmd[2] - offset_y
                        points.append((x, y))
                
                if len(points) > 2:
                    # Draw the filled polygon with transformed coordinates
                    draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)
                    
        except Exception as e:
            print(f"Warning: Could not fill SVG path with transform: {e}")
            # Fallback: continue without path filling

    @staticmethod
    def _fill_svg_path_direct(draw, path_data, fill_color, stroke_color):
        """Fill an SVG path using SVG coordinates directly - NO SCALING."""
        try:
            # Parse the path data to extract coordinates
            commands = []
            current_x, current_y = 0, 0
            
            # Split path data into commands
            import re
            path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)
            
            for cmd, params in path_commands:
                cmd = cmd.upper()
                if cmd == 'M':  # Move to
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 2:
                        current_x, current_y = float(coords[0]), float(coords[1])
                        commands.append(('M', current_x, current_y))
                elif cmd == 'L':  # Line to
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 2:
                        current_x, current_y = float(coords[0]), float(coords[1])
                        commands.append(('L', current_x, current_y))
                elif cmd == 'C':  # Cubic Bezier curve
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 6:  # C x1 y1 x2 y2 x y
                        # For simplicity, we'll use the end point of the curve
                        current_x, current_y = float(coords[4]), float(coords[5])
                        commands.append(('L', current_x, current_y))
                elif cmd == 'Z':  # Close path
                    commands.append(('Z',))
            
            # NO SCALING - use SVG coordinates directly as they are
            # This should restore the working state from before I added scaling
            
            if len(commands) > 2:
                points = []
                for cmd in commands:
                    if cmd[0] in ['M', 'L']:
                        # Use SVG coordinates directly - no transformation
                        x = cmd[1]
                        y = cmd[2]
                        points.append((x, y))
                
                if len(points) > 2:
                    # Draw the filled polygon with direct SVG coordinates
                    draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)
                    
        except Exception as e:
            print(f"Warning: Could not fill SVG path with direct coordinates: {e}")
            # Fallback: continue without path filling

    @staticmethod
    def _fill_svg_path(draw, path_data, fill_color, stroke_color):
        """Fill an SVG path on the PIL ImageDraw object."""
        try:
            # This is a simplified SVG path parser
            # For a production system, you'd want a proper SVG path library
            
            # Parse the path data to extract coordinates
            # SVG paths use commands like M (move), L (line), C (curve), Z (close)
            # For now, we'll implement a basic parser for simple paths
            
            commands = []
            current_x, current_y = 0, 0
            
            # Split path data into commands
            import re
            path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)
            
            for cmd, params in path_commands:
                cmd = cmd.upper()
                if cmd == 'M':  # Move to
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 2:
                        current_x, current_y = float(coords[0]), float(coords[1])
                        commands.append(('M', current_x, current_y))
                elif cmd == 'L':  # Line to
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 2:
                        current_x, current_y = float(coords[0]), float(coords[1])
                        commands.append(('L', current_x, current_y))
                elif cmd == 'C':  # Cubic Bezier curve
                    coords = re.findall(r'(-?\d+\.?\d*)', params)
                    if len(coords) >= 6:  # C x1 y1 x2 y2 x y
                        # For simplicity, we'll use the end point of the curve
                        current_x, current_y = float(coords[4]), float(coords[5])
                        commands.append(('L', current_x, current_y))
                elif cmd == 'Z':  # Close path
                    commands.append(('Z',))
            
            # Convert SVG coordinates to PIL coordinates
            # NO SCALING - PNG size matches SVG size exactly
            
            # For now, let's use a simple approach: create a polygon from the path
            if len(commands) > 2:
                points = []
                for cmd in commands:
                    if cmd[0] in ['M', 'L']:
                        # NO SCALING - use SVG coordinates directly
                        x = cmd[1]
                        y = cmd[2]
                        points.append((x, y))
                
                if len(points) > 2:
                    # Draw the filled polygon
                    draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)
                    
        except Exception as e:
            print(f"Warning: Could not fill SVG path: {e}")
            # Fallback: continue without path filling

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        """Convert hex color string to RGB tuple."""
        # Handle named colors
        color_map = {
            "darkviolet": (148, 0, 211),
            "royalblue": (65, 105, 225),
            "forestgreen": (34, 139, 34),
            "black": (0, 0, 0)
        }
        
        if hex_color in color_map:
            return color_map[hex_color]
        
        # Handle hex colors
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]
        
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except (ValueError, IndexError):
            # Fallback to black if parsing fails
            return (0, 0, 0)

    @staticmethod
    def render_board_png(svg_path: str, units: dict, output_path: str = None, phase_info: dict = None, supply_center_control: dict = None, color_only_supply_centers: bool = False) -> bytes:
        """Render board PNG with comprehensive caching for performance optimization."""
        if svg_path is None:
            raise ValueError("svg_path must not be None")
        # Fallback if provided path does not exist (common in tests)
        try:
            import os
            if not os.path.exists(svg_path):
                # Try environment override
                fallback = os.environ.get("DIPLOMACY_MAP_PATH")
                if fallback and os.path.exists(fallback):
                    svg_path = fallback
                else:
                    # Try common repo locations
                    candidates = [
                        os.path.join(os.path.dirname(__file__), "..", "tests", "maps", "standard.svg"),
                        os.path.join(os.path.dirname(__file__), "..", "..", "src", "tests", "maps", "standard.svg"),
                        os.path.join(os.path.dirname(__file__), "..", "..", "maps", "standard.svg"),
                    ]
                    for c in candidates:
                        c = os.path.abspath(c)
                        if os.path.exists(c):
                            svg_path = c
                            break
        except Exception:
            pass
        
        # Generate cache key for this map configuration
        cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info)
        
        # Try to get from cache first
        cached_img = _map_cache.get(cache_key)
        if cached_img is not None:
            # Cache hit - return cached image
            if isinstance(output_path, str) and output_path:
                with open(output_path, 'wb') as f:
                    f.write(cached_img)
            return cached_img
        
        # Cache miss - generate new map
        # Optimize for empty maps (no units) - skip expensive operations
        if not units:
            # For empty maps, just convert SVG to PNG and add phase info
            png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=1835, output_height=1360)  # type: ignore
            if png_bytes is None:
                raise ValueError("cairosvg.svg2png returned None")
            bg = Image.open(BytesIO(png_bytes)).convert("RGBA")  # type: ignore
            
            # Add phase information if provided
            if phase_info:
                draw = ImageDraw.Draw(bg)
                Map._draw_phase_info(draw, phase_info, bg.size)
            
            # Save or return PNG
            if isinstance(output_path, str) and output_path:
                try:
                    import os
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                except Exception:
                    pass
                bg.save(output_path, format="PNG")
            output = BytesIO()
            bg.save(output, format="PNG")
            img_bytes = output.getvalue()
            
            # Cache the generated image
            _map_cache.put(cache_key, img_bytes)
            
            return img_bytes
        
        # Full map generation for maps with units
        # 1. Convert SVG to PNG (background) with EXACT SVG size - NO SCALING
        # The SVG has viewBox="0 0 1835 1360" - use exact size to avoid coordinate scaling issues
        # This gives us 1835x1360 pixels - no scaling, coordinates match exactly
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=1835, output_height=1360)  # type: ignore
        if png_bytes is None:
            raise ValueError("cairosvg.svg2png returned None")
        bg = Image.open(BytesIO(png_bytes)).convert("RGBA")  # type: ignore
        draw = ImageDraw.Draw(bg)
        # 2. Get province coordinates (cached)
        coords = Map.get_svg_province_coordinates(svg_path)
        # 3. Define power colors (fallbacks)
        power_colors = {
            "AUSTRIA": "#c48f85",
            "ENGLAND": "darkviolet",
            "FRANCE": "royalblue",
            "GERMANY": "#a08a75",
            "ITALY": "forestgreen",
            "RUSSIA": "#757d91",
            "TURKEY": "#b9a61c",
        }
        # 4. Draw units with province coloring
        font = Map._get_cached_font(30)  # Font size for army/fleet markers
        
        # Get supply centers set if filtering is enabled
        supply_centers_set = None
        if color_only_supply_centers:
            try:
                map_instance = Map("standard")
                supply_centers_set = set(map_instance.get_supply_centers())
            except:
                supply_centers_set = set()
        
        # First pass: Color provinces based on power control using proper transparency
        Map._color_provinces_by_power_with_transparency(bg, units, power_colors, svg_path, supply_center_control, phase_info.get('phase') if phase_info else None, color_only_supply_centers, supply_centers_set)
        
        # Second pass: Draw units on top
        for power, unit_list in units.items():
            color = power_colors.get(power.upper(), "black")
            for unit in unit_list:
                parts = unit.split()
                if len(parts) != 2:
                    continue
                unit_type, prov = parts
                prov = prov.upper()
                
                # Handle dislodged units
                is_dislodged = prov.startswith("DISLODGED_")
                if is_dislodged:
                    # Extract original province name for coordinates
                    original_prov = prov.replace("DISLODGED_", "")
                    if original_prov not in coords:
                        continue
                    x, y = coords[original_prov]
                    # Offset dislodged unit position
                    x += 20
                    y += 20
                else:
                    if prov not in coords:
                        continue
                    x, y = coords[prov]
                
                # NO SCALING - use SVG coordinates directly
                # All coordinates are now in the same coordinate system (no scaling needed)
                
                # Draw unit circle with different styling for dislodged units
                r = 14  # Reduced by 30% from 28 to 20 (28 * 0.7 = 19.6, rounded to 20)
                if is_dislodged:
                    # Semi-transparent circle with dashed border for dislodged units
                    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="red", width=2)
                    # Add "D" marker for dislodged
                    dislodged_font = Map._get_cached_font(20)
                    draw.text((x + r - 5, y - r + 5), "D", fill="red", font=dislodged_font)
                else:
                    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="black", width=3)
                
                # Draw unit type letter
                text = unit_type
                bbox = draw.textbbox((0, 0), text, font=font)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((x - w/2, y - h/2), text, fill="white", font=font)
        
        # 5. Add phase information to bottom right corner
        if phase_info:
            Map._draw_phase_info(draw, phase_info, bg.size)
        
        # 6. Save or return PNG
        if isinstance(output_path, str) and output_path:
            try:
                import os
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
            except Exception:
                pass
            bg.save(output_path, format="PNG")
        output = BytesIO()
        bg.save(output, format="PNG")
        img_bytes = output.getvalue()
        
        # Cache the generated image
        _map_cache.put(cache_key, img_bytes)
        
        return img_bytes

    @staticmethod
    def _draw_phase_info(draw: ImageDraw.Draw, phase_info: dict, image_size: tuple) -> None:
        """Draw phase information overlay according to visualization spec.
        
        Format: "Year Season Phase" (e.g., "1901 Spring Movement")
        Includes phase code (e.g., "S1901M") if available
        Position: top-right corner (per spec)
        Font size: 16 points (within 14-18 range)
        """
        try:
            # Use font size 16 (within 14-18 point range from spec)
            phase_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        except Exception:
            phase_font = ImageFont.load_default()
        
        # Extract phase information
        year = phase_info.get("year", "1901")
        season = phase_info.get("season", "Spring")
        phase = phase_info.get("phase", "Movement")
        phase_code = phase_info.get("phase_code", "")
        turn = phase_info.get("turn", None)
        
        # Create phase text: "Year Season Phase" format
        phase_text = f"{year} {season} {phase}"
        
        # Add phase code if available
        if phase_code:
            phase_text = f"{phase_code} - {phase_text}"
        
        # Add turn number if available and useful
        if turn and turn > 1:
            phase_text = f"{phase_text} (Turn {turn})"
        
        # Calculate position (top-right corner with padding)
        width, height = image_size
        padding = 15
        
        # Get text dimensions
        bbox = draw.textbbox((0, 0), phase_text, font=phase_font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Position in top-right corner
        x = width - text_width - padding
        y = padding
        
        # Draw background rectangle for better readability
        bg_padding = 6
        draw.rectangle([
            x - bg_padding, 
            y - bg_padding, 
            x + text_width + bg_padding, 
            y + text_height + bg_padding
        ], fill=(0, 0, 0, 200))  # Semi-transparent black background (more opaque for readability)
        
        # Draw phase text in white for contrast
        draw.text((x, y), phase_text, fill="white", font=phase_font)
        
    @staticmethod
    def render_board_png_with_orders(svg_path: str, units: dict, orders: dict, phase_info: dict = None, output_path: str = None, supply_center_control: dict = None, color_only_supply_centers: bool = False) -> bytes:
        """
        Render map with comprehensive order visualization and caching.
        
        Args:
            svg_path: Path to SVG map file
            units: Dictionary of power -> list of units
            orders: Dictionary of power -> list of order dictionaries
            phase_info: Dictionary with turn/season/phase information
            output_path: Optional output file path
            
        Returns:
            PNG image bytes
        """
        if svg_path is None:
            raise ValueError("svg_path must not be None")
        
        # Generate cache key for this map configuration with orders
        cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info, orders=orders)
        
        # Try to get from cache first
        cached_img = _map_cache.get(cache_key)
        if cached_img is not None:
            # Cache hit - return cached image
            if isinstance(output_path, str) and output_path:
                with open(output_path, 'wb') as f:
                    f.write(cached_img)
            return cached_img
        
        # Cache miss - generate new map
        # First render the base map
        base_img_bytes = Map.render_board_png(svg_path, units, output_path, phase_info=phase_info, supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers)
        bg = Image.open(BytesIO(base_img_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(bg)
        
        # Get province coordinates for order visualization
        coords = Map.get_svg_province_coordinates(svg_path)
        
        # Define power colors
        power_colors = {
            "AUSTRIA": "#c48f85",
            "ENGLAND": "darkviolet", 
            "FRANCE": "royalblue",
            "GERMANY": "#a08a75",
            "ITALY": "forestgreen",
            "RUSSIA": "#757d91",
            "TURKEY": "#b9a61c",
        }
        
        # Draw order visualizations
        Map._draw_comprehensive_order_visualization(draw, orders, coords, power_colors)
        
        # Save or return PNG
        if isinstance(output_path, str) and output_path:
            bg.save(output_path, format="PNG")
        output = BytesIO()
        bg.save(output, format="PNG")
        img_bytes = output.getvalue()
        
        # Cache the generated image
        _map_cache.put(cache_key, img_bytes)
        
        return img_bytes

    @staticmethod
    def render_board_png_orders(svg_path: str, units: dict, orders: dict, phase_info: dict = None, output_path: str = None, supply_center_control: dict = None, color_only_supply_centers: bool = False) -> bytes:
        """
        Render orders map PNG showing all submitted orders before adjudication.
        
        This is an alias for render_board_png_with_orders but with a clearer name for the orders map type.
        
        Args:
            svg_path: Path to SVG map file
            units: Dictionary of power -> list of units
            orders: Dictionary of power -> list of order dictionaries (with status="pending")
            phase_info: Dictionary with turn/season/phase information
            output_path: Optional output file path
            supply_center_control: Dictionary of province -> power controlling supply center
            color_only_supply_centers: If True, only color supply center provinces
            
        Returns:
            PNG image bytes
        """
        # Ensure all orders have status="pending" for orders map
        pending_orders = {}
        for power, power_orders in orders.items():
            pending_orders[power] = []
            for order in power_orders:
                order_copy = order.copy()
                order_copy["status"] = "pending"  # Orders map shows pending status
                pending_orders[power].append(order_copy)
        
        return Map.render_board_png_with_orders(
            svg_path, units, pending_orders, phase_info, output_path, supply_center_control, color_only_supply_centers
        )

    @staticmethod
    def render_board_png_resolution(svg_path: str, units: dict, orders: dict, resolution_data: dict, phase_info: dict = None, output_path: str = None, supply_center_control: dict = None, color_only_supply_centers: bool = False) -> bytes:
        """
        Render resolution map PNG showing order results, conflicts, and dislodgements after adjudication.
        
        Args:
            svg_path: Path to SVG map file
            units: Dictionary of power -> list of units (after adjudication, includes dislodged units)
            orders: Dictionary of power -> list of order dictionaries (with final status)
            resolution_data: Dictionary containing conflict and resolution information:
                {
                    "conflicts": [
                        {
                            "province": "BUR",
                            "attackers": ["FRANCE", "GERMANY"],
                            "defender": "AUSTRIA",
                            "strengths": {"FRANCE": 2, "GERMANY": 1, "AUSTRIA": 1},
                            "result": "standoff|victory|bounce"
                        }
                    ],
                    "dislodgements": [
                        {
                            "unit": "A BUR",
                            "dislodged_by": "A PAR",
                            "retreat_options": ["BEL", "PIC"]
                        }
                    ]
                }
            phase_info: Dictionary with turn/season/phase information
            output_path: Optional output file path
            supply_center_control: Dictionary of province -> power controlling supply center
            
        Returns:
            PNG image bytes
        """
        if svg_path is None:
            raise ValueError("svg_path must not be None")
        
        # Generate cache key including resolution data
        cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info, orders=orders)
        cache_key += hashlib.md5(json.dumps(resolution_data, sort_keys=True).encode()).hexdigest()[:8]
        
        # Try to get from cache first
        cached_img = _map_cache.get(cache_key)
        if cached_img is not None:
            if isinstance(output_path, str) and output_path:
                with open(output_path, 'wb') as f:
                    f.write(cached_img)
            return cached_img
        
        # Cache miss - generate new map
        # First render the base map with final unit positions (including dislodged units)
        base_img_bytes = Map.render_board_png(svg_path, units, output_path, phase_info=phase_info, supply_center_control=supply_center_control, color_only_supply_centers=color_only_supply_centers)
        bg = Image.open(BytesIO(base_img_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(bg)
        
        # Get province coordinates
        coords = Map.get_svg_province_coordinates(svg_path)
        
        # Define power colors
        power_colors = {
            "AUSTRIA": "#c48f85",
            "ENGLAND": "darkviolet", 
            "FRANCE": "royalblue",
            "GERMANY": "#a08a75",
            "ITALY": "forestgreen",
            "RUSSIA": "#757d91",
            "TURKEY": "#b9a61c",
        }
        
        # Draw order visualizations with status indicators
        Map._draw_comprehensive_order_visualization(draw, orders, coords, power_colors)
        
        # Draw conflict markers
        conflicts = resolution_data.get("conflicts", [])
        for conflict in conflicts:
            province = conflict.get("province")
            strengths = conflict.get("strengths", {})
            result = conflict.get("result", "")
            
            if result == "standoff":
                Map._draw_standoff_indicator(draw, province, coords)
            else:
                Map._draw_conflict_marker(draw, province, strengths, result, coords)
        
        # Note: Dislodged units are already drawn by render_board_png with offset and D marker
        
        # Save or return PNG
        if isinstance(output_path, str) and output_path:
            bg.save(output_path, format="PNG")
        output = BytesIO()
        bg.save(output, format="PNG")
        img_bytes = output.getvalue()
        
        # Cache the generated image
        _map_cache.put(cache_key, img_bytes)
        
        return img_bytes

    @staticmethod
    def render_board_png_with_moves(svg_path: str, units: dict, moves: dict, phase_info: dict = None, output_path: str = None, supply_center_control: dict = None) -> bytes:
        """
        Render map with moves dictionary format visualization and caching.
        
        Args:
            svg_path: Path to SVG map file
            units: Dictionary of power -> list of units
            moves: Dictionary of power -> moves dictionary with successful/failed/bounced/etc
            phase_info: Dictionary with turn/season/phase information
            output_path: Optional output file path
            
        Returns:
            PNG image bytes
        """
        if svg_path is None:
            raise ValueError("svg_path must not be None")
        
        # Generate cache key for this map configuration with moves
        cache_key = _map_cache._generate_cache_key(svg_path, units, phase_info, moves=moves)
        
        # Try to get from cache first
        cached_img = _map_cache.get(cache_key)
        if cached_img is not None:
            # Cache hit - return cached image
            if isinstance(output_path, str) and output_path:
                with open(output_path, 'wb') as f:
                    f.write(cached_img)
            return cached_img
        
        # Cache miss - generate new map
        # First render the base map
        base_img_bytes = Map.render_board_png(svg_path, units, output_path, phase_info=phase_info, supply_center_control=supply_center_control)
        bg = Image.open(BytesIO(base_img_bytes)).convert("RGBA")
        draw = ImageDraw.Draw(bg)
        
        # Get province coordinates for move visualization
        coords = Map.get_svg_province_coordinates(svg_path)
        
        # Define power colors
        power_colors = {
            "AUSTRIA": "#c48f85",
            "ENGLAND": "darkviolet", 
            "FRANCE": "royalblue",
            "GERMANY": "#a08a75",
            "ITALY": "forestgreen",
            "RUSSIA": "#757d91",
            "TURKEY": "#b9a61c",
        }
        
        # Draw moves visualization
        Map._draw_moves_visualization(draw, moves, coords, power_colors)
        
        # Save or return PNG
        if isinstance(output_path, str) and output_path:
            bg.save(output_path, format="PNG")
        output = BytesIO()
        bg.save(output, format="PNG")
        img_bytes = output.getvalue()
        
        # Cache the generated image
        _map_cache.put(cache_key, img_bytes)
        
        return img_bytes

    @staticmethod
    def _draw_move_visualization(draw, orders: list, coords: dict, power_colors: dict):
        """Draw move arrows and support indicators on the map"""
        for order_data in orders:
            if "order" not in order_data:
                continue
                
            order_text = order_data["order"]
            power = order_data.get("power", "UNKNOWN")
            color = power_colors.get(power.upper(), "black")
            
            # Parse different types of orders
            parts = order_text.split()
            if len(parts) < 3:
                continue
                
            unit = f"{parts[1]} {parts[2]}"  # e.g., "A PAR"
            
            # Move orders (A PAR - BUR)
            if len(parts) >= 5 and parts[3] == "-":
                from_prov = parts[2].upper()
                to_prov = parts[4].upper()
                if from_prov in coords and to_prov in coords:
                    Map._draw_move_arrow(draw, coords[from_prov], coords[to_prov], color)
            
            # Support orders (A PAR S A BUR - MUN)
            elif len(parts) >= 7 and parts[3] == "S":
                # Support move: A PAR S A BUR - MUN
                if len(parts) >= 7 and parts[5] == "-":
                    supporter_prov = parts[2].upper()
                    supported_from = parts[4].upper()
                    supported_to = parts[6].upper()
                    
                    if (supporter_prov in coords and 
                        supported_from in coords and 
                        supported_to in coords):
                        Map._draw_support_arrow(draw, coords[supporter_prov], 
                                              coords[supported_from], coords[supported_to], color)
                # Support hold: A PAR S A BUR
                elif len(parts) >= 5:
                    supporter_prov = parts[2].upper()
                    supported_prov = parts[4].upper()
                    if supporter_prov in coords and supported_prov in coords:
                        Map._draw_support_hold(draw, coords[supporter_prov], 
                                             coords[supported_prov], color)

    @staticmethod
    def _draw_move_arrow(draw, from_coord, to_coord, color):
        """Draw an arrow for a move order"""
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Draw arrow line
        draw.line([from_x, from_y, to_x, to_y], fill=color, width=3)
        
        # Draw arrowhead
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        arrow_length = 15
        arrow_angle = math.pi / 6  # 30 degrees
        
        # Calculate arrowhead points
        head_x1 = to_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = to_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = to_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = to_y - arrow_length * math.sin(angle + arrow_angle)
        
        # Draw arrowhead
        draw.line([to_x, to_y, head_x1, head_y1], fill=color, width=3)
        draw.line([to_x, to_y, head_x2, head_y2], fill=color, width=3)

    @staticmethod
    def _draw_support_arrow(draw, supporter_coord, supported_from_coord, supported_to_coord, color):
        """Draw support for a move"""
        supp_x, supp_y = supporter_coord
        from_x, from_y = supported_from_coord
        to_x, to_y = supported_to_coord
        
        # Draw curved support line
        mid_x = (supp_x + from_x) / 2
        mid_y = (supp_y + from_y) / 2
        
        # Draw curved line using quadratic bezier
        import math
        control_x = mid_x + 20
        control_y = mid_y + 20
        
        # Simple curved line approximation
        steps = 20
        for i in range(steps):
            t1 = i / steps
            t2 = (i + 1) / steps
            
            x1 = (1-t1)**2 * supp_x + 2*(1-t1)*t1 * control_x + t1**2 * from_x
            y1 = (1-t1)**2 * supp_y + 2*(1-t1)*t1 * control_y + t1**2 * from_y
            x2 = (1-t2)**2 * supp_x + 2*(1-t2)*t2 * control_x + t2**2 * from_x
            y2 = (1-t2)**2 * supp_y + 2*(1-t2)*t2 * control_y + t2**2 * from_y
            
            draw.line([x1, y1, x2, y2], fill=color, width=2)
        
        # Draw "S" indicator
        draw.text((mid_x, mid_y), "S", fill=color, font=ImageFont.load_default())

    @staticmethod
    def _draw_support_hold(draw, supporter_coord, supported_coord, color):
        """Draw support for a hold"""
        supp_x, supp_y = supporter_coord
        supped_x, supped_y = supported_coord
        
        # Draw straight support line
        draw.line([supp_x, supp_y, supped_x, supped_y], fill=color, width=2)
        
        # Draw "S" indicator at midpoint
        mid_x = (supp_x + supped_x) / 2
        mid_y = (supp_y + supped_y) / 2
        draw.text((mid_x, mid_y), "S", fill=color, font=ImageFont.load_default())

    def get_province(self, name: str) -> Optional[Province]:
        return self.provinces.get(name)

    def is_adjacent(self, from_prov: str, to_prov: str) -> bool:
        return to_prov in self.provinces[from_prov].adjacent

    def get_supply_centers(self) -> Set[str]:
        return self.supply_centers

    def get_locations(self) -> List[str]:
        return list(self.provinces.keys())

    def get_adjacency(self, location: str) -> List[str]:
        prov = self.get_province(location)
        if prov:
            print(f"DEBUG: get_adjacency({location}) -> {prov.adjacent}")
            return list(prov.adjacent)
        print(f"DEBUG: get_adjacency({location}) -> [] (not found)")
        return []

    def validate_location(self, location: str) -> bool:
        return location in self.provinces
    
    @staticmethod
    def get_cache_stats() -> Dict[str, Any]:
        """Get map cache statistics."""
        return _map_cache.get_stats()
    
    @staticmethod
    def clear_map_cache() -> None:
        """Clear all cached maps."""
        _map_cache.clear()
    
    @staticmethod
    def preload_common_maps() -> None:
        """Preload common map configurations for better performance."""
        svg_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        
        # Preload empty map (most common)
        empty_units = {}
        empty_phase_info = {
            "year": "1901",
            "season": "Spring",
            "phase": "Movement",
            "phase_code": "S1901M"
        }
        
        try:
            Map.render_board_png(svg_path, empty_units, phase_info=empty_phase_info)
            print("✅ Preloaded empty map")
        except Exception as e:
            print(f"⚠️  Could not preload empty map: {e}")
        
        # Preload starting positions map
        starting_units = {
            "AUSTRIA": ["A VIE", "A BUD", "F TRI"],
            "ENGLAND": ["F LON", "F EDI", "A LVP"],
            "FRANCE": ["A PAR", "A MAR", "F BRE"],
            "GERMANY": ["A BER", "A MUN", "F KIE"],
            "ITALY": ["A ROM", "A VEN", "F NAP"],
            "RUSSIA": ["A MOS", "A WAR", "F STP", "A SEV"],
            "TURKEY": ["A CON", "A SMY", "F ANK"]
        }
        
        try:
            Map.render_board_png(svg_path, starting_units, phase_info=empty_phase_info)
            print("✅ Preloaded starting positions map")
        except Exception as e:
            print(f"⚠️  Could not preload starting positions map: {e}")
    
    @staticmethod
    def _draw_comprehensive_order_visualization(draw, orders: dict, coords: dict, power_colors: dict):
        """
        Draw comprehensive order visualization based on orders dictionary format.
        
        Args:
            draw: PIL ImageDraw object
            orders: Dictionary of power -> list of order dictionaries
            coords: Dictionary of province -> (x, y) coordinates
            power_colors: Dictionary of power -> color
        """
        for power, power_orders in orders.items():
            color = power_colors.get(power.upper(), "black")
            
            for order in power_orders:
                order_type = order.get("type", "")
                unit = order.get("unit", "")
                target = order.get("target", "")
                status = order.get("status", "success")
                reason = order.get("reason", "")
                
                # Extract province from unit (e.g., "A PAR" -> "PAR")
                unit_province = unit.split()[-1] if unit else ""
                
                if order_type == "move":
                    Map._draw_movement_order(draw, unit_province, target, color, status, coords)
                elif order_type == "hold":
                    Map._draw_hold_order(draw, unit_province, color, status, coords)
                elif order_type == "support":
                    supporting = order.get("supporting", "")
                    Map._draw_support_order(draw, unit_province, supporting, color, status, coords)
                elif order_type == "convoy":
                    via = order.get("via", [])
                    Map._draw_convoy_order(draw, unit_province, target, via, color, status, coords)
                elif order_type == "retreat":
                    Map._draw_retreat_order(draw, unit_province, target, color, status, coords)
                elif order_type == "build":
                    Map._draw_build_order(draw, target, color, status, coords)
                elif order_type == "destroy":
                    Map._draw_destroy_order(draw, unit_province, color, coords)

    @staticmethod
    def _draw_moves_visualization(draw, moves: dict, coords: dict, power_colors: dict):
        """
        Draw moves visualization based on moves dictionary format.
        
        Args:
            draw: PIL ImageDraw object
            moves: Dictionary of power -> moves dictionary
            coords: Dictionary of province -> (x, y) coordinates
            power_colors: Dictionary of power -> color
        """
        for power, power_moves in moves.items():
            color = power_colors.get(power.upper(), "black")
            
            # Draw successful moves
            for move in power_moves.get("successful", []):
                if isinstance(move, dict):
                    unit = move.get("unit", "")
                    target = move.get("target", "")
                    if unit and target:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            from_province = unit_parts[1]
                            Map._draw_movement_order(draw, from_province, target, color, "success", coords)
                else:
                    # Handle legacy string format
                    parts = move.split()
                    if len(parts) >= 4:
                        Map._draw_movement_order(draw, parts[1], parts[3], color, "success", coords)
            
            # Draw failed moves
            for move in power_moves.get("failed", []):
                if isinstance(move, dict):
                    unit = move.get("unit", "")
                    target = move.get("target", "")
                    if unit and target:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            from_province = unit_parts[1]
                            Map._draw_movement_order(draw, from_province, target, color, "failed", coords)
                else:
                    # Handle legacy string format
                    parts = move.split()
                    if len(parts) >= 4:
                        Map._draw_movement_order(draw, parts[1], parts[3], color, "failed", coords)
            
            # Draw bounced moves
            for move in power_moves.get("bounced", []):
                if isinstance(move, dict):
                    unit = move.get("unit", "")
                    target = move.get("target", "")
                    if unit and target:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            from_province = unit_parts[1]
                            Map._draw_movement_order(draw, from_province, target, color, "bounced", coords)
                else:
                    # Handle legacy string format
                    parts = move.split()
                    if len(parts) >= 4:
                        Map._draw_movement_order(draw, parts[1], parts[3], color, "bounced", coords)
            
            # Draw holds
            for hold in power_moves.get("holds", []):
                if isinstance(hold, dict):
                    unit = hold.get("unit", "")
                    if unit:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            province = unit_parts[1]
                            Map._draw_hold_order(draw, province, color, "success", coords)
                else:
                    # Handle legacy string format
                    province = hold.split()[-1]
                    Map._draw_hold_order(draw, province, color, "success", coords)
            
            # Draw supports
            for support in power_moves.get("supports", []):
                if isinstance(support, dict):
                    unit = support.get("unit", "")
                    supporting = support.get("supporting", "")
                    target = support.get("target", "")
                    if unit and supporting and target:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            supporter = unit_parts[1]
                            Map._draw_support_order(draw, supporter, f"{supporting} - {target}", color, "success", coords)
                else:
                    # Handle legacy string format
                    parts = support.split()
                    if len(parts) >= 4:
                        supporter = parts[1]
                        supported_move = " ".join(parts[3:])
                        Map._draw_support_order(draw, supporter, supported_move, color, "success", coords)
            
            # Draw convoys
            for convoy in power_moves.get("convoys", []):
                if isinstance(convoy, dict):
                    unit = convoy.get("unit", "")
                    convoyed_unit = convoy.get("convoyed_unit", "")
                    target = convoy.get("target", "")
                    if unit and convoyed_unit and target:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            convoyer = unit_parts[1]
                            convoyed_parts = convoyed_unit.split()
                            if len(convoyed_parts) >= 2:
                                convoyed_province = convoyed_parts[1]
                                Map._draw_convoy_order(draw, convoyer, convoyed_province, [], color, "success", coords)
                else:
                    # Handle legacy string format
                    parts = convoy.split()
                    if len(parts) >= 4:
                        convoyer = parts[1]
                        convoyed_move = " ".join(parts[3:])
                        convoyed_parts = convoyed_move.split()
                        if len(convoyed_parts) >= 3:
                            Map._draw_convoy_order(draw, convoyer, convoyed_parts[2], [], color, "success", coords)
            
            # Draw builds
            for build in power_moves.get("builds", []):
                if isinstance(build, dict):
                    unit = build.get("unit", "")
                    if unit:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            province = unit_parts[1]
                            Map._draw_build_order(draw, province, color, "success", coords)
                else:
                    # Handle legacy string format
                    province = build.split()[-1]
                    Map._draw_build_order(draw, province, color, "success", coords)
            
            # Draw destroys
            for destroy in power_moves.get("destroys", []):
                if isinstance(destroy, dict):
                    unit = destroy.get("unit", "")
                    if unit:
                        unit_parts = unit.split()
                        if len(unit_parts) >= 2:
                            province = unit_parts[1]
                            Map._draw_destroy_order(draw, province, color, coords)
                else:
                    # Handle legacy string format
                    province = destroy.split()[-1]
                    Map._draw_destroy_order(draw, province, color, coords)

    @staticmethod
    def _draw_movement_order(draw, from_province: str, to_province: str, color: str, status: str, coords: dict):
        """Draw movement order arrow with status indicators"""
        if from_province not in coords or to_province not in coords:
            return
            
        from_coord = coords[from_province]
        to_coord = coords[to_province]
        
        # Choose arrow style based on status
        if status == "success" or status == "pending":
            Map._draw_arrow(draw, from_coord, to_coord, color, width=3, style="solid")
            # Add success checkmark at arrow tip
            if status == "success":
                Map._draw_checkmark(draw, to_coord, "green")
        elif status == "failed":
            Map._draw_arrow(draw, from_coord, to_coord, "red", width=2, style="dashed")
            # Add failure X at arrow tip
            Map._draw_status_x(draw, to_coord, "red")
        elif status == "bounced":
            # Draw curved return arrow for bounce
            Map._draw_bounce_arrow(draw, from_coord, to_coord, "orange", width=2)
            # Add bounce indicator at destination
            Map._draw_status_x(draw, to_coord, "orange")

    @staticmethod
    def _draw_hold_order(draw, province: str, color: str, status: str, coords: dict):
        """Draw hold order circle"""
        if province not in coords:
            return
            
        coord = coords[province]
        
        # Choose circle style based on status
        if status == "success":
            Map._draw_circle(draw, coord, color, width=2, style="solid")
        else:
            Map._draw_circle(draw, coord, "red", width=2, style="dashed")

    @staticmethod
    def _draw_support_order(draw, supporter_province: str, supported_move: str, color: str, status: str, coords: dict):
        """Draw support order (circle + arrow) with support cut indicators"""
        if supporter_province not in coords:
            return
            
        supporter_coord = coords[supporter_province]
        
        # Draw circle around supporting unit
        if status == "success":
            Map._draw_circle(draw, supporter_coord, color, width=2, style="solid")
        else:
            Map._draw_circle(draw, supporter_coord, "red", width=2, style="dashed")
        
        # Parse supported move and draw arrow
        parts = supported_move.split()
        if len(parts) >= 3 and parts[1] == "-":
            supported_to = parts[2]
            if supported_to in coords:
                supported_coord = coords[supported_to]
                if status == "success":
                    # Draw dashed support line (different from movement)
                    Map._draw_arrow(draw, supporter_coord, supported_coord, color, width=2, style="dashed")
                else:
                    # Draw support line with cut indicator
                    Map._draw_arrow(draw, supporter_coord, supported_coord, "red", width=2, style="dashed")
                    # Draw red X through support line to indicate cut
                    Map._draw_support_cut_indicator(draw, supporter_coord, supported_coord)
        elif len(parts) >= 2:
            # Support hold - just show circle and connection line
            supported_prov = parts[-1] if len(parts) == 2 else parts[1]
            if supported_prov in coords:
                supported_coord = coords[supported_prov]
                if status == "success":
                    Map._draw_arrow(draw, supporter_coord, supported_coord, color, width=2, style="dashed")
                else:
                    Map._draw_arrow(draw, supporter_coord, supported_coord, "red", width=2, style="dashed")
                    Map._draw_support_cut_indicator(draw, supporter_coord, supported_coord)

    @staticmethod
    def _draw_convoy_order(draw, convoyer_province: str, convoyed_to: str, via_route: list, color: str, status: str, coords: dict):
        """Draw convoy order (curved arrow through convoy chain)"""
        if convoyer_province not in coords or convoyed_to not in coords:
            return
            
        convoyer_coord = coords[convoyer_province]
        convoyed_coord = coords[convoyed_to]
        
        # Draw curved arrow through convoy route
        if status == "success":
            Map._draw_curved_arrow(draw, convoyer_coord, convoyed_coord, color, width=2, style="solid")
        else:
            Map._draw_curved_arrow(draw, convoyer_coord, convoyed_coord, "red", width=2, style="dashed")

    @staticmethod
    def _draw_build_order(draw, province: str, color: str, status: str, coords: dict):
        """Draw build order (glowing circle)"""
        if province not in coords:
            return
            
        coord = coords[province]
        
        if status == "success":
            # Draw glowing circle with enhanced brightness
            Map._draw_glowing_circle(draw, coord, color, width=4)
        else:
            # Draw red cross for failed build
            Map._draw_cross(draw, coord, "red", width=4)

    @staticmethod
    def _draw_destroy_order(draw, province: str, color: str, coords: dict):
        """Draw destroy order (red cross)"""
        if province not in coords:
            return
            
        coord = coords[province]
        Map._draw_cross(draw, coord, "red", width=4)
    
    @staticmethod
    def _draw_retreat_order(draw, from_province: str, to_province: str, color: str, status: str, coords: dict):
        """Draw retreat order (dotted arrow, red if invalid)"""
        if from_province not in coords or to_province not in coords:
            return
            
        from_coord = coords[from_province]
        to_coord = coords[to_province]
        
        # Use dotted line style for retreat
        retreat_color = "red" if status == "failed" else color
        Map._draw_dotted_arrow(draw, from_coord, to_coord, retreat_color, width=2)
        
        # Add failure indicator if invalid retreat
        if status == "failed":
            Map._draw_status_x(draw, to_coord, "red")
    
    @staticmethod
    def _draw_conflict_marker(draw, province: str, strengths: dict, result: str, coords: dict):
        """Draw conflict marker for battles"""
        if province not in coords:
            return
            
        coord = coords[province]
        x, y = coord
        
        # Draw conflict marker (star or special symbol)
        marker_size = 20
        Map._draw_star(draw, (x, y), marker_size, "red", "yellow")
        
        # Add strength indicator if available
        if strengths:
            max_strength = max(strengths.values())
            # Draw strength number
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
            except Exception:
                font = ImageFont.load_default()
            draw.text((x + marker_size + 5, y - 10), str(max_strength), fill="black", font=font)
    
    @staticmethod
    def _draw_standoff_indicator(draw, province: str, coords: dict):
        """Draw standoff indicator (equal strength conflict)"""
        if province not in coords:
            return
            
        coord = coords[province]
        x, y = coord
        
        # Draw special standoff marker (circle with equal sign)
        radius = 15
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline="orange", width=3)
        # Draw equal sign
        draw.line([x - 8, y - 3, x + 8, y - 3], fill="orange", width=2)
        draw.line([x - 8, y + 3, x + 8, y + 3], fill="orange", width=2)
    
    @staticmethod
    def _draw_bounce_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2):
        """Draw curved return arrow for bounced moves"""
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Calculate midpoint
        mid_x = (from_x + to_x) / 2
        mid_y = (from_y + to_y) / 2
        
        # Calculate perpendicular offset for curve
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        perp_angle = angle + math.pi / 2
        offset = 40  # Larger offset for bounce curve
        
        control_x = mid_x + offset * math.cos(perp_angle)
        control_y = mid_y + offset * math.sin(perp_angle)
        
        # Draw curved line showing bounce
        steps = 30
        points = []
        for i in range(steps + 1):
            t = i / steps
            x = (1-t)**2 * from_x + 2*(1-t)*t * control_x + t**2 * to_x
            y = (1-t)**2 * from_y + 2*(1-t)*t * control_y + t**2 * to_y
            points.append((x, y))
        
        # Draw the curve
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=color, width=width)
        
        # Draw arrowhead at destination (pointing back)
        angle_to_dest = math.atan2(to_y - control_y, to_x - control_x)
        arrow_length = 12
        arrow_angle = math.pi / 6
        head_x1 = to_x - arrow_length * math.cos(angle_to_dest - arrow_angle)
        head_y1 = to_y - arrow_length * math.sin(angle_to_dest - arrow_angle)
        head_x2 = to_x - arrow_length * math.cos(angle_to_dest + arrow_angle)
        head_y2 = to_y - arrow_length * math.sin(angle_to_dest + arrow_angle)
        draw.polygon([to_x, to_y, head_x1, head_y1, head_x2, head_y2], fill=color)
    
    @staticmethod
    def _draw_dotted_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2):
        """Draw dotted arrow for retreat orders"""
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Draw dotted line
        import math
        length = math.sqrt((to_x - from_x)**2 + (to_y - from_y)**2)
        if length == 0:
            return
        
        dot_spacing = 8
        num_dots = int(length / dot_spacing)
        dx = (to_x - from_x) / num_dots if num_dots > 0 else 0
        dy = (to_y - from_y) / num_dots if num_dots > 0 else 0
        
        for i in range(0, num_dots, 2):
            x1 = from_x + i * dx
            y1 = from_y + i * dy
            x2 = from_x + (i + 1) * dx if i + 1 < num_dots else to_x
            y2 = from_y + (i + 1) * dy if i + 1 < num_dots else to_y
            draw.line([x1, y1, x2, y2], fill=color, width=width)
        
        # Draw arrowhead
        angle = math.atan2(to_y - from_y, to_x - from_x)
        arrow_length = 12
        arrow_angle = math.pi / 6
        head_x1 = to_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = to_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = to_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = to_y - arrow_length * math.sin(angle + arrow_angle)
        draw.polygon([to_x, to_y, head_x1, head_y1, head_x2, head_y2], fill=color)
    
    @staticmethod
    def _draw_checkmark(draw, coord: tuple, color: str = "green"):
        """Draw success checkmark at coordinate"""
        x, y = coord
        size = 12
        
        # Draw checkmark (check shape)
        check_points = [
            (x - size, y),
            (x - size // 3, y + size // 2),
            (x + size, y - size // 2)
        ]
        draw.line([check_points[0], check_points[1], check_points[2]], fill=color, width=3)
    
    @staticmethod
    def _draw_status_x(draw, coord: tuple, color: str = "red"):
        """Draw failure X marker at coordinate"""
        x, y = coord
        size = 10
        
        # Draw X
        draw.line([x - size, y - size, x + size, y + size], fill=color, width=3)
        draw.line([x - size, y + size, x + size, y - size], fill=color, width=3)
    
    @staticmethod
    def _draw_support_cut_indicator(draw, from_coord: tuple, to_coord: tuple):
        """Draw red X through support line to indicate support was cut"""
        # Draw X at midpoint of support line
        mid_x = (from_coord[0] + to_coord[0]) / 2
        mid_y = (from_coord[1] + to_coord[1]) / 2
        Map._draw_status_x(draw, (mid_x, mid_y), "red")
    
    @staticmethod
    def _draw_star(draw, coord: tuple, size: int, outline_color: str, fill_color: str):
        """Draw star shape for conflict markers"""
        import math
        x, y = coord
        
        # Create 5-pointed star
        outer_radius = size
        inner_radius = size * 0.4
        
        points = []
        for i in range(10):
            angle = i * math.pi / 5 - math.pi / 2  # Start at top
            radius = outer_radius if i % 2 == 0 else inner_radius
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py))
        
        # Draw filled star
        if len(points) > 2:
            draw.polygon(points, fill=fill_color, outline=outline_color, width=2)

    @staticmethod
    def _convert_color_to_rgb(color: str) -> str:
        """Convert hex color to RGB tuple or return named color as-is"""
        if color.startswith('#'):
            # Convert hex to RGB tuple
            hex_color = color.lstrip('#')
            if len(hex_color) == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                return (r, g, b)
        return color  # Return named colors as-is

    @staticmethod
    def _draw_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: int = 3, style: str = "solid"):
        """Draw arrow between two coordinates"""
        # Convert color to RGB if needed
        rgb_color = Map._convert_color_to_rgb(color)
        
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Draw arrow line
        if style == "dashed":
            Map._draw_dashed_line(draw, from_x, from_y, to_x, to_y, rgb_color, width)
        else:
            draw.line([from_x, from_y, to_x, to_y], fill=rgb_color, width=width)
        
        # Draw arrowhead
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        arrow_length = 15
        arrow_angle = math.pi / 6  # 30 degrees
        
        # Calculate arrowhead points
        head_x1 = to_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = to_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = to_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = to_y - arrow_length * math.sin(angle + arrow_angle)
        
        # Draw arrowhead
        draw.polygon([to_x, to_y, head_x1, head_y1, head_x2, head_y2], fill=rgb_color)

    @staticmethod
    def _draw_circle(draw, coord: tuple, color: str, width: int = 2, style: str = "solid"):
        """Draw circle around coordinate"""
        x, y = coord
        radius = 15
        
        if style == "dashed":
            Map._draw_dashed_circle(draw, x, y, radius, color, width)
        else:
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)

    @staticmethod
    def _draw_glowing_circle(draw, coord: tuple, color: str, width: int = 4):
        """Draw glowing circle for build orders"""
        x, y = coord
        radius = 20
        
        # Draw outer glow (lighter color)
        glow_color = Map._lighten_color(color)
        draw.ellipse([x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2], outline=glow_color, width=width)
        
        # Draw inner circle
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)

    @staticmethod
    def _draw_cross(draw, coord: tuple, color: str, width: int = 4):
        """Draw red cross for destroy orders"""
        x, y = coord
        size = 15
        
        # Draw X
        draw.line([x - size, y - size, x + size, y + size], fill=color, width=width)
        draw.line([x - size, y + size, x + size, y - size], fill=color, width=width)

    @staticmethod
    def _draw_curved_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2, style: str = "solid"):
        """Draw curved arrow for convoy orders"""
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Calculate control point for curve
        mid_x = (from_x + to_x) / 2
        mid_y = (from_y + to_y) / 2
        
        # Offset control point to create curve
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        perp_angle = angle + math.pi / 2
        offset = 30
        
        control_x = mid_x + offset * math.cos(perp_angle)
        control_y = mid_y + offset * math.sin(perp_angle)
        
        # Draw curved line using quadratic bezier
        steps = 20
        for i in range(steps):
            t1 = i / steps
            t2 = (i + 1) / steps
            
            x1 = (1-t1)**2 * from_x + 2*(1-t1)*t1 * control_x + t1**2 * to_x
            y1 = (1-t1)**2 * from_y + 2*(1-t1)*t1 * control_y + t1**2 * to_y
            x2 = (1-t2)**2 * from_x + 2*(1-t2)*t2 * control_x + t2**2 * to_x
            y2 = (1-t2)**2 * from_y + 2*(1-t2)*t2 * control_y + t2**2 * to_y
            
            if style == "dashed" and i % 2 == 0:
                continue
            draw.line([x1, y1, x2, y2], fill=color, width=width)
        
        # Draw arrowhead at destination
        Map._draw_arrow(draw, (control_x, control_y), to_coord, color, width, style)

    @staticmethod
    def _draw_dashed_line(draw, x1: int, y1: int, x2: int, y2: int, color: str, width: int):
        """Draw dashed line"""
        import math
        length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        dash_length = 10
        gap_length = 5
        
        if length == 0:
            return
            
        # Calculate unit vector
        dx = (x2 - x1) / length
        dy = (y2 - y1) / length
        
        # Draw dashes
        current_length = 0
        while current_length < length:
            start_x = x1 + current_length * dx
            start_y = y1 + current_length * dy
            end_length = min(current_length + dash_length, length)
            end_x = x1 + end_length * dx
            end_y = y1 + end_length * dy
            
            draw.line([start_x, start_y, end_x, end_y], fill=color, width=width)
            current_length += dash_length + gap_length

    @staticmethod
    def _draw_dashed_circle(draw, x: int, y: int, radius: int, color: str, width: int):
        """Draw dashed circle"""
        import math
        num_segments = 24
        dash_length = 2
        gap_length = 2
        
        for i in range(0, num_segments, 2):
            start_angle = 2 * math.pi * i / num_segments
            end_angle = 2 * math.pi * (i + dash_length) / num_segments
            
            start_x = x + radius * math.cos(start_angle)
            start_y = y + radius * math.sin(start_angle)
            end_x = x + radius * math.cos(end_angle)
            end_y = y + radius * math.sin(end_angle)
            
            draw.line([start_x, start_y, end_x, end_y], fill=color, width=width)

    @staticmethod
    def _lighten_color(color: str) -> str:
        """Lighten a color for glow effects"""
        # Simple color lightening - add white component
        if color.startswith("#"):
            # Convert hex to RGB
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            
            # Lighten by adding white
            r = min(255, int(r + (255 - r) * 0.5))
            g = min(255, int(g + (255 - g) * 0.5))
            b = min(255, int(b + (255 - b) * 0.5))
            
            return f"#{r:02x}{g:02x}{b:02x}"
        else:
            # For named colors, return a lighter version
            light_colors = {
                "red": "#ff8080",
                "blue": "#8080ff",
                "green": "#80ff80",
                "yellow": "#ffff80",
                "purple": "#ff80ff",
                "orange": "#ffc080",
                "brown": "#d4a574",
            }
            return light_colors.get(color.lower(), color)
