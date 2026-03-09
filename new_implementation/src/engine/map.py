"""
Map representation for Diplomacy.
- Represents provinces, supply centers, adjacency, and coasts.
- Loads map data from standard.map file as the single source of truth.
- Includes comprehensive map caching for performance optimization.
"""

from typing import Dict, List, Set, Optional, Tuple, Any
import os
import json
import math
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageChops
import cairosvg  # type: ignore
from io import BytesIO
import hashlib
import time
from functools import lru_cache
import logging

# Module-level logger for static methods
logger = logging.getLogger("diplomacy.engine.map")

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
        self.logger = logging.getLogger("diplomacy.engine.map.cache")
        
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
            self.logger.warning(f"Could not load cache metadata: {e}")
    
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
            self.logger.warning(f"Could not save cache metadata: {e}")
    
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
                        self.logger.warning(f"Could not load cached image {cache_key}: {e}")
            
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
            self.logger.warning(f"Could not save cached image {cache_key}: {e}")
        
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
                self.logger.warning(f"Could not remove cache file {cache_file}: {e}")
            
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
            self.logger.warning(f"Could not clear cache directory: {e}")
    
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

# Import visualization configuration
from .visualization_config import get_config

# Get global config instance
_viz_config = get_config()


KNOWN_POWER_NAMES = frozenset({"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"})


def _get_power_colors_dict() -> Dict[str, str]:
    """Get power colors dictionary from config."""
    power_colors = {}
    for power in KNOWN_POWER_NAMES:
        power_colors[power] = _viz_config.get_power_color(power)
    return power_colors


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
        self.logger = logging.getLogger("diplomacy.engine.map")
        self._init_map(map_name)

    def _init_map(self, map_name: str) -> None:
        if map_name == 'standard' or map_name == 'standard-v2':
            # standard-v2 uses the same game logic as standard, just different visual appearance
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
        """Initialize standard map by parsing standard.map file as the single source of truth."""
        # Use standard.map as the authoritative source for adjacencies
        map_dir = os.path.join(os.path.dirname(__file__), '../../maps')
        map_file = os.path.join(map_dir, 'standard.map')
        
        if not os.path.isfile(map_file):
            raise FileNotFoundError(
                f"standard.map not found at {map_file}. "
                f"This file is required as the single source of truth for province adjacencies."
            )
        
        try:
            self._parse_map_file(map_file)
            self.logger.info(f"Successfully loaded standard map from {map_file}")
        except Exception as e:
            self.logger.error(f"Failed to parse standard.map: {e}")
            raise RuntimeError(
                f"Failed to parse standard.map at {map_file}. "
                f"This file is required and must be valid. Error: {e}"
            ) from e

    def _parse_map_file(self, map_file_path: str) -> None:
        """
        Parse a .map file as the single source of truth for province adjacencies.
        
        Handles:
        - Province types from LAND/COAST/WATER prefixes
        - Case-insensitive province names (normalizes to uppercase)
        - Multi-coast provinces (BUL/EC, BUL/SC, STP/NC, STP/SC, SPA/NC, SPA/SC)
        - Supply centers from power definitions
        - Bidirectional adjacencies
        """
        from .province_mapping import get_sea_provinces, get_coastal_provinces, get_land_provinces
        
        with open(map_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Get province type mappings for validation
        water_provinces = set(get_sea_provinces())
        coastal_provinces = set(get_coastal_provinces())
        land_provinces = set(get_land_provinces())

        # Parse supply centers from the power definitions
        supply_centers: set[str] = set()
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Parse power definition lines like "AUSTRIA     (AUSTRIAN)     BUD TRI VIE"
            if '(' in line and ')' in line and not line.startswith('LAND') and not line.startswith('COAST') and not line.startswith('WATER'):
                if line.count('(') == 1 and line.count(')') == 1:
                    parts = line.split(')')
                    if len(parts) == 2:
                        centers_part = parts[1].strip()
                        if centers_part:
                            centers = centers_part.split()
                            # Normalize supply center names to uppercase
                            supply_centers.update([center.upper() for center in centers])

        # Parse adjacencies and province types
        adjacencies: dict[str, list[str]] = {}
        province_types: dict[str, str] = {}  # Map province name to type: 'land', 'coastal', 'sea'
        province_prefixes: dict[str, str] = {}  # Track LAND/COAST/WATER prefix for each province
        
        for line in lines:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
                
            if line.startswith('LAND ') or line.startswith('COAST ') or line.startswith('WATER '):
                # Parse adjacency line like "COAST    CLY        ABUTS    EDI LVP NAO NWG"
                parts = line.split()
                if len(parts) >= 4 and parts[2] == 'ABUTS':
                    prefix = parts[0].upper()  # LAND, COAST, or WATER
                    province_raw = parts[1]  # Keep original case for multi-coast handling
                    province = province_raw.upper()  # Normalize to uppercase for key
                    
                    # Determine province type from prefix
                    if prefix == 'LAND':
                        province_types[province] = 'land'
                    elif prefix == 'COAST':
                        province_types[province] = 'coastal'
                    elif prefix == 'WATER':
                        province_types[province] = 'sea'
                    
                    province_prefixes[province] = prefix
                    
                    # Parse adjacent provinces (normalize to uppercase, handle case variations)
                    adjacent_provinces = []
                    for adj in parts[3:]:
                        adj_upper = adj.upper()
                        # Handle multi-coast provinces in adjacency list (e.g., "lvp", "edi")
                        adjacent_provinces.append(adj_upper)
                    
                    # Store adjacencies (handle both specific coast and base province entries)
                    if province not in adjacencies:
                        adjacencies[province] = []
                    adjacencies[province].extend(adjacent_provinces)

        # Create provinces with correct types
        for province, adj_list in adjacencies.items():
            # Determine if this is a supply center
            is_supply_center = province in supply_centers
            
            # Get province type (default to 'land' if not specified)
            prov_type = province_types.get(province, 'land')
            
            # Validate province type against mapping (for consistency check)
            if prov_type == 'sea' and province not in water_provinces:
                self.logger.warning(f"Province {province} marked as sea in map file but not in water_provinces mapping")
            elif prov_type == 'coastal' and province not in coastal_provinces:
                self.logger.warning(f"Province {province} marked as coastal in map file but not in coastal_provinces mapping")
            elif prov_type == 'land' and province not in land_provinces and province not in coastal_provinces:
                # Some provinces might be in both, which is fine
                pass
            
            # Create province with correct type
            self.provinces[province] = Province(province, is_supply_center=is_supply_center, type_=prov_type)
            if is_supply_center:
                self.supply_centers.add(province)
        
        # Create bidirectional adjacencies
        for province, adjacent_list in adjacencies.items():
            # Remove duplicates while preserving order
            seen = set()
            unique_adjacents = []
            for adj in adjacent_list:
                if adj not in seen and adj in self.provinces:
                    seen.add(adj)
                    unique_adjacents.append(adj)
            
            # Set adjacencies (bidirectional)
            for adj in unique_adjacents:
                if adj in self.provinces:
                    self.provinces[province].add_adjacent(adj)
                    self.provinces[adj].add_adjacent(province)
        
        # Validation: Check bidirectional consistency
        self._validate_adjacencies()

    def _validate_adjacencies(self) -> None:
        """Validate that adjacencies are bidirectional and complete."""
        issues = []
        
        # Check bidirectional consistency: if A borders B, B should border A
        for prov_name, province in self.provinces.items():
            for adj in province.adjacent:
                if adj in self.provinces:
                    adj_province = self.provinces[adj]
                    if prov_name not in adj_province.adjacent:
                        issues.append(f"Adjacency inconsistency: {prov_name} borders {adj}, but {adj} does not border {prov_name}")
        
        if issues:
            self.logger.warning(f"Found {len(issues)} adjacency inconsistencies:")
            for issue in issues[:10]:  # Limit to first 10
                self.logger.warning(f"  {issue}")
            if len(issues) > 10:
                self.logger.warning(f"  ... and {len(issues) - 10} more")
        
        # Check that all provinces have at least one adjacency (except possibly impassable)
        for prov_name, province in self.provinces.items():
            if len(province.adjacent) == 0:
                self.logger.warning(f"Province {prov_name} has no adjacencies")
    

    @staticmethod
    def _resolve_svg_path(map_name: str = 'standard') -> str:
        """
        Resolve SVG file path based on map name.
        
        Args:
            map_name: Name of the map variant ('standard' or 'standard-v2')
            
        Returns:
            Path to the SVG file
        """
        base_path = os.environ.get("DIPLOMACY_MAP_PATH", "maps/standard.svg")
        base_dir = os.path.dirname(base_path) if os.path.dirname(base_path) else "maps"
        
        if map_name == 'standard-v2':
            # Use v2.svg for standard-v2 map
            svg_path = os.path.join(base_dir, "v2.svg")
            # Fallback to standard if v2.svg doesn't exist
            if not os.path.exists(svg_path):
                svg_path = base_path
        elif map_name == 'standard':
            svg_path = base_path
        else:
            # For other variants, try {map_name}.svg
            svg_path = os.path.join(base_dir, f"{map_name}.svg")
            if not os.path.exists(svg_path):
                svg_path = base_path  # Fallback to standard
        
        return svg_path

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
            
            # Check if this is the standard-v2 map (doesn't have jdipNS structure)
            # standard-v2 uses text elements with transform attributes instead of jdipNS:PROVINCE
            if 'v2.svg' in svg_path or 'standard-v2' in svg_path.lower():
                coords = {}
                import re
                # Get viewBox to scale coordinates appropriately
                viewbox = root.get('viewBox', '0 0 7016 4960')
                viewbox_parts = viewbox.split()
                if len(viewbox_parts) >= 4:
                    svg_width = float(viewbox_parts[2])
                    svg_height = float(viewbox_parts[3])
                else:
                    svg_width = 7016.0
                    svg_height = 4960.0
                
                # Output dimensions for rendering (standard map size)
                output_width = 1835.0
                output_height = 1360.0
                
                # Scale factors
                scale_x = output_width / svg_width
                scale_y = output_height / svg_height
                
                # Parse text elements with transform="translate(x, y)" attributes
                # Text content format: "FullNameABBREV" (e.g., "LondonLON", "EdinburghEDI")
                for text_elem in root.findall('.//{http://www.w3.org/2000/svg}text'):
                    transform = text_elem.get('transform', '')
                    if 'translate' in transform:
                        # Extract coordinates from transform='translate(x y)'
                        match = re.search(r'translate\(([\d.]+)\s+([\d.]+)\)', transform)
                        if match:
                            x = float(match.group(1))
                            y = float(match.group(2))
                            # Scale coordinates to match output dimensions
                            x_scaled = x * scale_x
                            y_scaled = y * scale_y
                            # Get text content
                            content = ''.join(text_elem.itertext()).strip()
                            # Extract abbreviation (typically last 2-4 uppercase letters)
                            # Pattern: full name followed by abbreviation
                            abbrev_match = re.search(r'([A-Z]{2,4})$', content)
                            if abbrev_match:
                                abbrev = abbrev_match.group(1).upper()
                                coords[abbrev] = (x_scaled, y_scaled)
                
                if not coords:
                    logger.warning(f"Failed to extract coordinates from v2 SVG at {svg_path}, using empty dict")
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
        
        Note:
            This function processes SVG paths with IDs starting with '_' (preferred) and without '_' (fallback).
            Known limitation: MAO, NAO, NWG, and TYS do not have path elements in the SVG file and cannot be colored.
            These provinces will be logged as warnings but will not cause errors.
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
            # Some provinces have paths with underscore prefix (_province), some without (province)
            # We prioritize underscore paths but also include non-underscore paths as fallback
            province_paths = []
            province_paths_by_id = {}  # Map normalized ID to path element (to avoid duplicates)
            
            for path in all_paths:
                province_id = path.get('id')
                if province_id:
                    normalized_id = province_id.lstrip('_').upper()
                    # Prioritize paths with underscore prefix, but also track non-underscore paths
                    if province_id.startswith('_'):
                        # Path with underscore - preferred
                        if normalized_id not in province_paths_by_id:
                            province_paths_by_id[normalized_id] = path
                            province_paths.append(path)
                    else:
                        # Path without underscore - use as fallback if no underscore version exists
                        if normalized_id not in province_paths_by_id:
                            province_paths_by_id[normalized_id] = path
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
            
            # Track which provinces from province_power_map were found in SVG
            colored_provinces = set()
            
            # Color each province based on power control using SVG paths
            for path_elem in province_paths:
                province_id = path_elem.get('id')
                if province_id:
                    # Remove underscore prefix and convert to uppercase
                    normalized_id = province_id.lstrip('_').upper()
                    
                    if normalized_id in province_power_map:
                        colored_provinces.add(normalized_id)
                        
                        # If color_only_supply_centers is enabled, skip non-supply-center provinces
                        if color_only_supply_centers:
                            if supply_centers_set and normalized_id not in supply_centers_set:
                                continue
                        
                        # Get the power color for this province
                        power_color = province_power_map[normalized_id]
                        
                        # Convert color to RGB for proper transparency
                        rgb_color = Map._hex_to_rgb(power_color)
                        
                        # Parse the SVG path to extract polygon points
                        path_data = path_elem.get('d')
                        if path_data:
                            # Extract polygon points from path data
                            polygon_points = Map._extract_polygon_points_from_path(path_data, 195, 170)
                            
                            if normalized_id in Map.WATER_PROVINCES:
                                # Use hatched pattern for ocean provinces
                                # Pattern color: power color at 50% opacity for visibility
                                pattern_opacity = 120  # 120/255 ≈ 47% opacity
                                pattern_color = (*rgb_color, pattern_opacity)
                                
                                # Draw ocean pattern
                                if polygon_points and len(polygon_points) >= 3:
                                    Map._draw_ocean_pattern(overlay, polygon_points, pattern_color, spacing=10, angle=45, line_width=1)
                            else:
                                # Use solid fill for land provinces
                                base_opacity = 90  # 90/255 ≈ 0.35 (35% opacity)
                                transparent_color = (*rgb_color, base_opacity)
                                
                                # Apply correct transform to align SVG paths with jdipNS coordinates
                                Map._fill_svg_path_with_transform(overlay_draw, path_data, transparent_color, power_color, 195, 170)
            
            # Log warning for provinces in province_power_map but not found in SVG paths
            missing_provinces = set(province_power_map.keys()) - colored_provinces
            if missing_provinces:
                # Known missing provinces: MAO, NAO, NWG, TYS (these don't have path elements in the SVG file)
                known_missing = {"MAO", "NAO", "NWG", "TYS"}
                unknown_missing = missing_provinces - known_missing
                
                if unknown_missing:
                    logger.warning(f"Provinces in province_power_map but missing SVG paths (unexpected): {sorted(unknown_missing)}")
                
                if missing_provinces & known_missing:
                    logger.debug(f"Provinces missing SVG paths (known limitation): {sorted(missing_provinces & known_missing)}. "
                               f"These provinces (MAO, NAO, NWG, TYS) exist in the game but have no path elements in the SVG file.")
            
            # Composite the overlay onto the background image using proper alpha compositing
            bg_image.paste(overlay, (0, 0), overlay)
                    
        except Exception as e:
            logger.warning(f"Could not parse SVG for province coloring: {e}")
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
                            # SVG MapLayer has transform="translate(-195 -170)", so we compensate
                            Map._fill_svg_path_with_transform(draw, path_data, solid_color, power_color, 195, 170)
                            
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
            logger.warning(f"Could not parse SVG for province coloring: {e}")
            # Fallback: continue without province coloring
    
    @staticmethod
    def _extract_polygon_points_from_path(path_data, offset_x, offset_y):
        """Extract polygon points from SVG path data with coordinate transform.
        
        Handles M (moveto), L (lineto), C (cubic Bezier), and Z (close) commands.
        Bezier curves are sampled at multiple points for accurate boundary representation.
        
        Returns:
            List of (x, y) tuples, or None if parsing fails
        """
        def cubic_bezier_point(p0, p1, p2, p3, t):
            """Calculate point on cubic Bezier curve at parameter t (0 to 1)."""
            mt = 1 - t
            return (
                mt**3 * p0[0] + 3*mt**2*t * p1[0] + 3*mt*t**2 * p2[0] + t**3 * p3[0],
                mt**3 * p0[1] + 3*mt**2*t * p1[1] + 3*mt*t**2 * p2[1] + t**3 * p3[1]
            )
        
        try:
            import re
            points = []
            current_x, current_y = 0, 0
            start_x, start_y = 0, 0
            
            # Split path data into commands
            path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)
            
            for cmd, params in path_commands:
                coords = re.findall(r'(-?\d+\.?\d*)', params)
                coords = [float(c) for c in coords]
                
                if cmd == 'M':  # Absolute moveto
                    if len(coords) >= 2:
                        current_x, current_y = coords[0], coords[1]
                        start_x, start_y = current_x, current_y
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'm':  # Relative moveto
                    if len(coords) >= 2:
                        current_x += coords[0]
                        current_y += coords[1]
                        start_x, start_y = current_x, current_y
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'L':  # Absolute lineto
                    if len(coords) >= 2:
                        current_x, current_y = coords[0], coords[1]
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'l':  # Relative lineto
                    if len(coords) >= 2:
                        current_x += coords[0]
                        current_y += coords[1]
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'H':  # Absolute horizontal lineto
                    if len(coords) >= 1:
                        current_x = coords[0]
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'h':  # Relative horizontal lineto
                    if len(coords) >= 1:
                        current_x += coords[0]
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'V':  # Absolute vertical lineto
                    if len(coords) >= 1:
                        current_y = coords[0]
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'v':  # Relative vertical lineto
                    if len(coords) >= 1:
                        current_y += coords[0]
                        points.append((current_x - offset_x, current_y - offset_y))
                elif cmd == 'C':  # Absolute cubic Bezier
                    # Process all sets of 6 coordinates (multiple curves can be chained)
                    for i in range(0, len(coords) - 5, 6):
                        p0 = (current_x, current_y)
                        p1 = (coords[i], coords[i+1])
                        p2 = (coords[i+2], coords[i+3])
                        p3 = (coords[i+4], coords[i+5])
                        # Sample 8 points along the curve for smooth approximation
                        for t in [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]:
                            bx, by = cubic_bezier_point(p0, p1, p2, p3, t)
                            points.append((bx - offset_x, by - offset_y))
                        current_x, current_y = p3[0], p3[1]
                elif cmd == 'c':  # Relative cubic Bezier
                    for i in range(0, len(coords) - 5, 6):
                        p0 = (current_x, current_y)
                        p1 = (current_x + coords[i], current_y + coords[i+1])
                        p2 = (current_x + coords[i+2], current_y + coords[i+3])
                        p3 = (current_x + coords[i+4], current_y + coords[i+5])
                        for t in [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0]:
                            bx, by = cubic_bezier_point(p0, p1, p2, p3, t)
                            points.append((bx - offset_x, by - offset_y))
                        current_x, current_y = p3[0], p3[1]
                elif cmd in ['Z', 'z']:  # Close path
                    if start_x != current_x or start_y != current_y:
                        points.append((start_x - offset_x, start_y - offset_y))
            
            if len(points) > 2:
                return points
            return None
                    
        except Exception as e:
            logger.warning(f"Could not extract polygon points from path: {e}")
            return None

    @staticmethod
    def _fill_svg_path_with_transform(draw, path_data, fill_color, stroke_color, offset_x, offset_y):
        """Fill an SVG path with coordinate transform to compensate for SVG group transforms."""
        try:
            # Extract polygon points
            points = Map._extract_polygon_points_from_path(path_data, offset_x, offset_y)
            
            if points and len(points) > 2:
                # Draw the filled polygon with transformed coordinates
                draw.polygon(points, fill=fill_color, outline=stroke_color, width=2)
                    
        except Exception as e:
            logger.warning(f"Could not fill SVG path with transform: {e}")
            # Fallback: continue without path filling

    @staticmethod
    def _draw_ocean_pattern(overlay_image, polygon_points, pattern_color, spacing=10, angle=45, line_width=1):
        """Draw hatched/striped pattern for ocean provinces, clipped to polygon shape.
        
        Args:
            overlay_image: PIL Image object (RGBA mode) to draw on
            polygon_points: List of (x, y) tuples defining the polygon
            pattern_color: RGBA color tuple for the pattern lines
            spacing: Distance between pattern lines in pixels
            angle: Angle of pattern lines in degrees (45 = diagonal)
            line_width: Width of pattern lines in pixels
        """
        if len(polygon_points) < 3:
            return  # Need at least 3 points for a polygon
        
        try:
            # Calculate bounding box of the polygon
            x_coords = [p[0] for p in polygon_points]
            y_coords = [p[1] for p in polygon_points]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Create a mask from the polygon for clipping
            mask = Image.new('L', overlay_image.size, 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.polygon(polygon_points, fill=255)
            
            # Create a temporary image for the pattern (fully transparent)
            pattern_img = Image.new('RGBA', overlay_image.size, (0, 0, 0, 0))
            pattern_draw = ImageDraw.Draw(pattern_img)
            
            # Convert angle to radians
            angle_rad = math.radians(angle)
            cos_a = math.cos(angle_rad)
            sin_a = math.sin(angle_rad)
            
            # Calculate the diagonal length of the bounding box
            width = max_x - min_x
            height = max_y - min_y
            diagonal = math.sqrt(width * width + height * height)
            
            # Calculate number of lines needed
            num_lines = int(diagonal / spacing) + 2
            
            # Draw diagonal lines across the bounding box
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            for i in range(-num_lines, num_lines + 1):
                # Calculate line offset
                offset = i * spacing
                
                # Calculate line endpoints
                # For 45-degree diagonal, we move perpendicular to the line direction
                perp_x = -sin_a * offset
                perp_y = cos_a * offset
                
                # Line extends from one corner to the opposite corner
                # We extend it well beyond the bounding box
                line_length = diagonal * 1.5
                start_x = center_x + perp_x - cos_a * line_length / 2
                start_y = center_y + perp_y - sin_a * line_length / 2
                end_x = center_x + perp_x + cos_a * line_length / 2
                end_y = center_y + perp_y + sin_a * line_length / 2
                
                # Draw line on pattern image (lines have their own alpha from pattern_color)
                pattern_draw.line([(start_x, start_y), (end_x, end_y)], fill=pattern_color, width=line_width)
            
            # Apply mask to pattern image alpha channel to clip to polygon
            # This ensures only the polygon area shows the pattern, and transparent areas stay transparent
            pattern_alpha = pattern_img.split()[3]  # Get alpha channel
            # Multiply pattern alpha by mask: areas outside polygon become 0, areas inside keep pattern alpha
            masked_alpha = ImageChops.multiply(pattern_alpha, mask.convert('L'))
            pattern_img.putalpha(masked_alpha)
            
            # Composite pattern onto overlay - transparent areas remain transparent
            overlay_image.paste(pattern_img, (0, 0), pattern_img)
                
        except Exception as e:
            logger.warning(f"Could not draw ocean pattern: {e}")
            # Fallback: continue without pattern

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
            logger.warning(f"Could not fill SVG path with direct coordinates: {e}")
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
            logger.warning(f"Could not fill SVG path: {e}")
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
        # 3. Get power colors from config
        power_colors = _get_power_colors_dict()
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
                
                # Get unit specs from config
                unit_specs = _viz_config.get_unit_specs()
                unit_diameter = unit_specs["diameter"]
                r = unit_diameter // 2  # Radius from diameter
                
                # Convert color to RGB tuple
                rgb_color = Map._convert_color_to_rgb(color)
                if isinstance(rgb_color, str):
                    from PIL import ImageColor
                    try:
                        rgb_color = ImageColor.getrgb(rgb_color)
                    except ValueError:
                        rgb_color = (128, 128, 128)  # Fallback to gray
                
                outline_color = (0, 0, 0)  # Black outline
                failure_color = Map._convert_color_to_rgb(_viz_config.get_color("failure"))
                if isinstance(failure_color, str):
                    from PIL import ImageColor
                    try:
                        failure_color = ImageColor.getrgb(failure_color)
                    except ValueError:
                        failure_color = (255, 0, 0)  # Fallback to red
                
                if is_dislodged:
                    # Dislodged unit: offset position, red border, "D" marker
                    dislodged_offset = unit_specs["dislodged_offset"]
                    x += dislodged_offset[0]
                    y += dislodged_offset[1]
                    
                    # Draw icon with red outline for dislodged units
                    if unit_type == "A":
                        Map._draw_army_icon(draw, (x, y), rgb_color, failure_color, unit_diameter, bg)
                    else:  # F
                        Map._draw_fleet_icon(draw, (x, y), rgb_color, failure_color, unit_diameter, bg)
                    
                    # Add "D" marker in top-right corner
                    dislodged_indicator_size = unit_specs["dislodged_indicator_size"]
                    dislodged_indicator_offset = unit_specs["dislodged_indicator_offset"]
                    indicator_x = x + r - dislodged_indicator_offset[0]
                    indicator_y = y - r + dislodged_indicator_offset[1]
                    # Draw small circle/square for "D" marker
                    indicator_r = dislodged_indicator_size // 2
                    draw.ellipse((indicator_x - indicator_r, indicator_y - indicator_r,
                                indicator_x + indicator_r, indicator_y + indicator_r),
                               fill=failure_color, 
                               outline=failure_color)
                    # Draw "D" text
                    dislodged_font = Map._get_cached_font(dislodged_indicator_size)
                    draw.text((indicator_x - indicator_r//2, indicator_y - indicator_r//2), "D", 
                            fill="white", font=dislodged_font)
                else:
                    # Standard unit: black outline
                    if unit_type == "A":
                        Map._draw_army_icon(draw, (x, y), rgb_color, outline_color, unit_diameter, bg)
                    else:  # F
                        Map._draw_fleet_icon(draw, (x, y), rgb_color, outline_color, unit_diameter, bg)
        
        # 5. Add phase information to bottom right corner
        if phase_info:
            Map._draw_phase_info(draw, phase_info, bg.size)
        
        # 6. Add legend showing power colors
        active_powers = list(units.keys())
        Map._draw_legend(bg, "initial", active_powers)
        
        # 7. Save or return PNG
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
        Font size: from config (within 14-18 range)
        """
        font_specs = _viz_config.get_font_specs()
        font_size = font_specs["phase_overlay_size"]
        try:
            phase_font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
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
        
        # Get power colors from config
        power_colors = _get_power_colors_dict()
        
        # Draw order visualizations
        Map._draw_comprehensive_order_visualization(draw, orders, coords, power_colors, units)
        
        # Add orders legend
        active_powers = list(units.keys())
        Map._draw_legend(bg, "orders", active_powers)
        
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
        
        # Get power colors from config
        power_colors = _get_power_colors_dict()
        
        # Draw order visualizations with status indicators
        Map._draw_comprehensive_order_visualization(draw, orders, coords, power_colors, units)
        
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
        
        # Add resolution legend
        active_powers = list(units.keys())
        Map._draw_legend(bg, "resolution", active_powers)
        
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
        
        # Get power colors from config
        power_colors = _get_power_colors_dict()
        
        # Draw moves visualization
        Map._draw_moves_visualization(draw, moves, coords, power_colors)
        
        # Add orders legend (moves are a type of order)
        active_powers = list(units.keys())
        Map._draw_legend(bg, "orders", active_powers)
        
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
        
        # Get line width from config
        arrow_specs = _viz_config.get_arrow_specs()
        line_width = arrow_specs["line_width_primary"]
        arrowhead_size = arrow_specs["arrowhead_size"]
        outline_width = arrow_specs.get("outline_width", 2)
        
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        
        # Offset target by 4 pixels to prevent collisions
        collision_offset = 4
        actual_tip_x = to_x - collision_offset * math.cos(angle)
        actual_tip_y = to_y - collision_offset * math.sin(angle)
        
        arrow_length = arrowhead_size
        arrow_angle = math.pi / 6  # 30 degrees
        
        # Calculate arrowhead points
        head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)
        
        # Calculate arrowhead base center (where line should end)
        base_center_x = (head_x1 + head_x2) / 2
        base_center_y = (head_y1 + head_y2) / 2
        
        # Calculate outline arrowhead (slightly larger)
        outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
        outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
        outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
        outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)
        
        # Draw black outline first
        outline_color = (0, 0, 0)
        total_width = line_width + outline_width * 2
        draw.line([from_x, from_y, base_center_x, base_center_y], fill=outline_color, width=total_width)
        draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)
        
        # Draw colored arrow on top
        draw.line([from_x, from_y, base_center_x, base_center_y], fill=color, width=line_width)
        draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)

    @staticmethod
    def _draw_support_arrow(draw, supporter_coord, supported_from_coord, supported_to_coord, color):
        """Draw support for a move"""
        supp_x, supp_y = supporter_coord
        from_x, from_y = supported_from_coord
        to_x, to_y = supported_to_coord
        
        # Get line width from config
        arrow_specs = _viz_config.get_arrow_specs()
        line_width = arrow_specs["line_width_secondary"]
        
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
            
            draw.line([x1, y1, x2, y2], fill=color, width=line_width)
        
        # Draw "S" indicator
        draw.text((mid_x, mid_y), "S", fill=color, font=ImageFont.load_default())

    @staticmethod
    def _draw_support_hold(draw, supporter_coord, supported_coord, color):
        """Draw support for a hold"""
        supp_x, supp_y = supporter_coord
        supped_x, supped_y = supported_coord
        
        # Get line width from config
        arrow_specs = _viz_config.get_arrow_specs()
        line_width = arrow_specs["line_width_secondary"]
        
        # Draw straight support line
        draw.line([supp_x, supp_y, supped_x, supped_y], fill=color, width=line_width)
        
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
            self.logger.debug(f"get_adjacency({location}) -> {prov.adjacent}")
            return list(prov.adjacent)
        self.logger.debug(f"get_adjacency({location}) -> [] (not found)")
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
            logger.info("Preloaded empty map")
        except Exception as e:
            logger.warning(f"Could not preload empty map: {e}")
        
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
            logger.info("Preloaded starting positions map")
        except Exception as e:
            logger.warning(f"Could not preload starting positions map: {e}")
    
    @staticmethod
    def _draw_comprehensive_order_visualization(draw, orders: dict, coords: dict, power_colors: dict, units: dict = None):
        """
        Draw comprehensive order visualization based on orders dictionary format.
        
        Draws in proper visual layer order: hold → support → convoy → movement (primary actions on top)
        
        Args:
            draw: PIL ImageDraw object
            orders: Dictionary of power -> list of order dictionaries
            coords: Dictionary of province -> (x, y) coordinates
            power_colors: Dictionary of power -> color
            units: Dictionary of power -> list of units (for finding dislodged unit positions)
        """
        # Separate orders by type for proper layering
        hold_orders = []
        support_orders = []
        convoy_orders = []
        movement_orders = []
        other_orders = []
        
        for power, power_orders in orders.items():
            color = power_colors.get(power.upper(), "black")
            
            for order in power_orders:
                order_type = order.get("type", "")
                order_with_context = (order, power, color)
                
                if order_type == "hold":
                    hold_orders.append(order_with_context)
                elif order_type == "support":
                    support_orders.append(order_with_context)
                elif order_type == "convoy":
                    convoy_orders.append(order_with_context)
                elif order_type == "move":
                    movement_orders.append(order_with_context)
                else:
                    other_orders.append(order_with_context)
        
        # Draw in layer order per spec section 3.4.11:
        # 3. Hold indicators
        # 4. Support lines and circles
        # 5. Convoy routes
        # 6. Movement arrows
        # 7. Retreat arrows (in other_orders)
        # Note: Units, Build/Destroy, Conflict markers, Status indicators drawn separately
        for order_list in [hold_orders, support_orders, convoy_orders, movement_orders, other_orders]:
            for order, power, color in order_list:
                order_type = order.get("type", "")
                unit = order.get("unit", "")
                target = order.get("target", "")
                status = order.get("status", "success")
                
                # Extract province from unit (e.g., "A PAR" -> "PAR")
                unit_province = unit.split()[-1] if unit else ""
                
                if order_type == "move":
                    Map._draw_movement_order(draw, unit_province, target, color, status, coords)
                elif order_type == "hold":
                    Map._draw_hold_order(draw, unit_province, color, status, coords)
                elif order_type == "support":
                    # Extract support order parameters
                    supported_action = order.get("supported_action", "hold")
                    supported_unit_province = order.get("supported_unit_province", "")
                    if not supported_unit_province:
                        # Fallback: try to parse from "supporting" field
                        supporting = order.get("supporting", "")
                        if supporting:
                            supported_unit_province = supporting.split()[-1] if " " in supporting else supporting
                    supported_target = order.get("supported_target")
                    supporting_power_color = color
                    Map._draw_support_order(draw, unit_province, supported_unit_province, 
                                           supported_action, supported_target, 
                                           supporting_power_color, status, coords)
                elif order_type == "convoy":
                    # Extract convoy order parameters
                    convoyed_army_province = order.get("convoyed_army_province", "")
                    if not convoyed_army_province:
                        # Fallback: try to parse from "convoyed_unit" field
                        convoyed_unit = order.get("convoyed_unit", "")
                        if convoyed_unit:
                            convoyed_army_province = convoyed_unit.split()[-1] if " " in convoyed_unit else convoyed_unit
                    convoy_chain = order.get("convoy_chain", [])
                    if not convoy_chain:
                        # Fallback: try to use "via" field
                        convoy_chain = order.get("via", [])
                    convoy_color = _viz_config.get_color("convoy")
                    Map._draw_convoy_order(draw, convoyed_army_province, target, 
                                         convoy_chain, convoy_color, status, coords)
                elif order_type == "retreat":
                    # For retreat orders, ALWAYS use the dislodged unit's offset position
                    # Retreat orders are only for dislodged units, so they should always be offset
                    dislodged_unit_position = None
                    if unit_province in coords:
                        base_x, base_y = coords[unit_province]
                        unit_specs = _viz_config.get_unit_specs()
                        dislodged_offset = unit_specs.get("dislodged_offset", [20, 20])
                        # Always calculate offset position for retreat orders (dislodged units are always offset)
                        dislodged_unit_position = (base_x + dislodged_offset[0], base_y + dislodged_offset[1])
                    
                    Map._draw_retreat_order(draw, unit_province, target, color, status, coords, dislodged_unit_position)
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
                if not isinstance(move, dict):
                    continue
                unit = move.get("unit", "")
                target = move.get("target", "")
                if unit and target:
                    unit_parts = unit.split()
                    if len(unit_parts) >= 2:
                        from_province = unit_parts[1]
                        Map._draw_movement_order(draw, from_province, target, color, "success", coords)
            
            # Draw failed moves
            for move in power_moves.get("failed", []):
                if not isinstance(move, dict):
                    continue
                unit = move.get("unit", "")
                target = move.get("target", "")
                if unit and target:
                    unit_parts = unit.split()
                    if len(unit_parts) >= 2:
                        from_province = unit_parts[1]
                        Map._draw_movement_order(draw, from_province, target, color, "failed", coords)
            
            # Draw bounced moves
            for move in power_moves.get("bounced", []):
                if not isinstance(move, dict):
                    continue
                unit = move.get("unit", "")
                target = move.get("target", "")
                if unit and target:
                    unit_parts = unit.split()
                    if len(unit_parts) >= 2:
                        from_province = unit_parts[1]
                        Map._draw_movement_order(draw, from_province, target, color, "bounced", coords)
            
            # Draw holds
            for hold in power_moves.get("holds", []):
                if not isinstance(hold, dict):
                    continue
                unit = hold.get("unit", "")
                if unit:
                    unit_parts = unit.split()
                    if len(unit_parts) >= 2:
                        province = unit_parts[1]
                        Map._draw_hold_order(draw, province, color, "success", coords)
            
            # Draw supports
            for support in power_moves.get("supports", []):
                if not isinstance(support, dict):
                    continue
                unit = support.get("unit", "")
                supporting = support.get("supporting", "")
                target = support.get("target", "")
                if unit and supporting:
                    unit_parts = unit.split()
                    supporting_parts = supporting.split()
                    if len(unit_parts) >= 2 and len(supporting_parts) >= 2:
                        supporter = unit_parts[1]
                        supported_unit_province = supporting_parts[1]
                        # Determine support type: if target exists, it's offensive support
                        supported_action = "move" if target else "hold"
                        supported_target = target if target else None
                        Map._draw_support_order(draw, supporter, supported_unit_province, 
                                               supported_action, supported_target, 
                                               color, "success", coords)
            
            # Draw convoys
            for convoy in power_moves.get("convoys", []):
                if not isinstance(convoy, dict):
                    continue
                unit = convoy.get("unit", "")
                convoyed_unit = convoy.get("convoyed_unit", "")
                target = convoy.get("target", "")
                convoy_chain = convoy.get("convoy_chain", [])
                if unit and convoyed_unit and target:
                    unit_parts = unit.split()
                    convoyed_parts = convoyed_unit.split()
                    if len(unit_parts) >= 2 and len(convoyed_parts) >= 2:
                        convoyed_army_province = convoyed_parts[1]
                        # The convoying fleet is the unit, but we start from the convoyed army
                        # convoy_chain should include all convoying fleets (excluding the convoyed army)
                        if not convoy_chain:
                            # If no chain provided, add the convoying fleet
                            convoying_fleet = unit_parts[1]
                            convoy_chain = [convoying_fleet] if convoying_fleet != convoyed_army_province else []
                        Map._draw_convoy_order(draw, convoyed_army_province, target, 
                                              convoy_chain, _viz_config.get_color("convoy"), "success", coords)
            
            # Draw builds
            for build in power_moves.get("builds", []):
                if not isinstance(build, dict):
                    continue
                unit = build.get("unit", "")
                if unit:
                    unit_parts = unit.split()
                    if len(unit_parts) >= 2:
                        province = unit_parts[1]
                        Map._draw_build_order(draw, province, color, "success", coords)
            
            # Draw destroys
            for destroy in power_moves.get("destroys", []):
                if not isinstance(destroy, dict):
                    continue
                unit = destroy.get("unit", "")
                if unit:
                    unit_parts = unit.split()
                    if len(unit_parts) >= 2:
                        province = unit_parts[1]
                        Map._draw_destroy_order(draw, province, color, coords)

    @staticmethod
    def _draw_movement_order(draw, from_province: str, to_province: str, color: str, status: str, coords: dict):
        """Draw movement order arrow with status indicators"""
        if from_province not in coords or to_province not in coords:
            return
            
        from_coord = coords[from_province]
        to_coord = coords[to_province]
        
        # Get config values
        arrow_specs = _viz_config.get_arrow_specs()
        primary_width = arrow_specs["line_width_primary"]
        secondary_width = arrow_specs["line_width_secondary"]
        
        # Choose arrow style based on status
        if status == "success" or status == "pending":
            Map._draw_arrow(draw, from_coord, to_coord, color, width=primary_width, style="solid")
            # Add success checkmark at arrow tip
            if status == "success":
                Map._draw_checkmark(draw, to_coord, "green")
        elif status == "failed":
            Map._draw_arrow(draw, from_coord, to_coord, "red", width=secondary_width, style="dashed")
            # Add failure X at arrow tip
            Map._draw_status_x(draw, to_coord, "red")
        elif status == "bounced":
            # Draw curved return arrow for bounce
            Map._draw_bounce_arrow(draw, from_coord, to_coord, "orange", width=secondary_width)
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
    def _draw_support_order(draw, supporter_province: str, supported_unit_province: str, 
                           supported_action: str, supported_target: Optional[str], 
                           supporting_power_color: str, status: str, coords: dict):
        """
        Draw support order with distinct colors for defensive vs offensive support.
        
        Args:
            draw: PIL ImageDraw object
            supporter_province: Province of the unit providing support
            supported_unit_province: Province of the unit being supported
            supported_action: "hold" for defensive support, "move" for offensive support
            supported_target: Target province (for offensive support only)
            supporting_power_color: Power color of supporting unit (for defender circle)
            status: Order status ("success", "failed", etc.)
            coords: Dictionary mapping province names to (x, y) coordinates
        """
        if supporter_province not in coords or supported_unit_province not in coords:
            return
            
        supporter_coord = coords[supporter_province]
        supported_coord = coords[supported_unit_province]
        
        if supported_action == "hold":
            # Defensive Support (Hold Support) - spec section 3.4.4
            arrow_specs = _viz_config.get_arrow_specs()
            marker_specs = _viz_config.get_marker_specs()
            support_color = _viz_config.get_color("support_defensive") if status == "success" else _viz_config.get_color("failure")
            
            # Draw dashed line from supporter to defending unit (light green)
            Map._draw_arrow(draw, supporter_coord, supported_coord, support_color, 
                          width=arrow_specs["line_width_secondary"], style="dashed")
            
            # Draw circle around defending unit in supporting unit's power color
            if status == "success":
                circle_diameter = marker_specs["support_circle_diameter"]
                circle_border_width = marker_specs["support_circle_border_width"]
                Map._draw_circle_at_size(draw, supported_coord, supporting_power_color, 
                                       circle_diameter, circle_border_width, style="solid")
            
            # Add red X through support line if cut
            if status != "success":
                Map._draw_support_cut_indicator(draw, supporter_coord, supported_coord)
                
        elif supported_action == "move" and supported_target:
            # Offensive Support (Move Support) - spec section 3.4.4
            arrow_specs = _viz_config.get_arrow_specs()
            support_color = _viz_config.get_color("support_offensive") if status == "success" else _viz_config.get_color("failure")
            
            if supported_target in coords:
                target_coord = coords[supported_target]
                
                # Draw dashed arrow path: supporter → supported unit → attack target
                # First segment: supporter to supported unit
                Map._draw_arrow(draw, supporter_coord, supported_coord, support_color, 
                             width=arrow_specs["line_width_secondary"], style="dashed")
                # Second segment: supported unit to target
                Map._draw_arrow(draw, supported_coord, target_coord, support_color, 
                             width=arrow_specs["line_width_secondary"], style="dashed")
                
                # Add red X through support line if cut
                if status != "success":
                    Map._draw_support_cut_indicator(draw, supporter_coord, supported_coord)
                    if supported_target in coords:
                        Map._draw_support_cut_indicator(draw, supported_coord, target_coord)

    @staticmethod
    def _draw_convoy_order(draw, convoyed_army_province: str, convoyed_to: str, 
                          convoy_chain: List[str], convoy_color: str, status: str, coords: dict):
        """
        Draw convoy order per spec section 3.4.5.
        
        Curved path (bezier) from army through all fleets to destination.
        Gold/orange color, solid line, circles around convoying fleets, arrowhead at destination.
        """
        if convoyed_army_province not in coords or convoyed_to not in coords:
            return
        
        arrow_specs = _viz_config.get_arrow_specs()
        marker_specs = _viz_config.get_marker_specs()
        convoy_color_actual = convoy_color if status == "success" else _viz_config.get_color("failure")
        
        # Build complete path: army → fleet1 → fleet2 → ... → destination
        path = [convoyed_army_province]
        path.extend(convoy_chain)
        path.append(convoyed_to)
        
        # Draw curved arrows connecting each segment of the path
        for i in range(len(path) - 1):
            from_prov = path[i]
            to_prov = path[i + 1]
            
            if from_prov not in coords or to_prov not in coords:
                continue
                
            from_coord = coords[from_prov]
            to_coord = coords[to_prov]
            
            # Draw curved arrow segment using config line width
            Map._draw_curved_arrow(draw, from_coord, to_coord, convoy_color_actual, 
                                  width=arrow_specs["line_width_secondary"], 
                                  style="solid" if status == "success" else "dashed")
        
        # Draw circles/markers around convoying fleets in convoy color (per spec)
        fleet_marker_diameter = marker_specs["convoy_fleet_marker_diameter"]
        fleet_marker_border_width = marker_specs["convoy_fleet_marker_border_width"]
        for fleet_prov in convoy_chain:
            if fleet_prov in coords:
                fleet_coord = coords[fleet_prov]
                Map._draw_circle_at_size(draw, fleet_coord, convoy_color_actual, 
                                       fleet_marker_diameter, fleet_marker_border_width, style="solid")

    @staticmethod
    def _draw_build_order(draw, province: str, color: str, status: str, coords: dict):
        """
        Draw build marker per spec section 3.4.7.
        
        Green circle with plus sign or "A"/"F" label, power-colored border.
        """
        if province not in coords:
            return
        
        marker_specs = _viz_config.get_marker_specs()
        marker_diameter = marker_specs["build_marker_diameter"]
        border_width = marker_specs["build_marker_border_width"]
        r = marker_diameter // 2
        
        x, y = coords[province]
        build_color = _viz_config.get_color("success")
        rgb_build_color = Map._convert_color_to_rgb(build_color)
        rgb_border_color = Map._convert_color_to_rgb(color)
        
        # Draw green circle with power-colored border
        draw.ellipse((x - r, y - r, x + r, y + r), fill=rgb_build_color, 
                    outline=rgb_border_color, width=border_width)
        
        # Draw plus sign or unit type label (for now, use plus sign)
        plus_size = marker_diameter // 2
        # Horizontal line
        draw.line([x - plus_size//2, y, x + plus_size//2, y], 
                 fill="white", width=border_width)
        # Vertical line
        draw.line([x, y - plus_size//2, x, y + plus_size//2], 
                 fill="white", width=border_width)

    @staticmethod
    def _draw_destroy_order(draw, province: str, color: str, coords: dict):
        """
        Draw destroy marker per spec section 3.4.8.
        
        Red circle with X symbol, power-colored border.
        """
        if province not in coords:
            return
        
        marker_specs = _viz_config.get_marker_specs()
        marker_diameter = marker_specs["destroy_marker_diameter"]
        border_width = marker_specs["destroy_marker_border_width"]
        r = marker_diameter // 2
        
        x, y = coords[province]
        destroy_color = _viz_config.get_color("failure")
        rgb_destroy_color = Map._convert_color_to_rgb(destroy_color)
        rgb_border_color = Map._convert_color_to_rgb(color)
        
        # Draw red circle with power-colored border
        draw.ellipse((x - r, y - r, x + r, y + r), fill=rgb_destroy_color, 
                    outline=rgb_border_color, width=border_width)
        
        # Draw X symbol
        x_size = marker_diameter // 2
        x_line_width = border_width
        rgb_white = (255, 255, 255)
        draw.line([x - x_size, y - x_size, x + x_size, y + x_size], 
                 fill=rgb_white, width=x_line_width)
        draw.line([x - x_size, y + x_size, x + x_size, y - x_size], 
                 fill=rgb_white, width=x_line_width)
    
    @staticmethod
    def _draw_retreat_order(draw, from_province: str, to_province: str, color: str, status: str, coords: dict, dislodged_unit_position: tuple = None):
        """
        Draw retreat order per spec section 3.4.6.
        
        Dotted arrow, red if invalid retreat. Uses unified arrow function.
        Retreat orders ALWAYS start from dislodged unit position (offset from province center).
        """
        if to_province not in coords:
            return
        
        # Retreat orders are always for dislodged units, so always use offset position
        if dislodged_unit_position:
            from_coord = dislodged_unit_position
        elif from_province in coords:
            # Fallback: calculate offset position if not provided
            base_x, base_y = coords[from_province]
            unit_specs = _viz_config.get_unit_specs()
            dislodged_offset = unit_specs.get("dislodged_offset", [20, 20])
            from_coord = (base_x + dislodged_offset[0], base_y + dislodged_offset[1])
        else:
            return  # Can't draw without starting position
            
        to_coord = coords[to_province]
        
        # Use dotted line style for retreat, red if invalid
        arrow_specs = _viz_config.get_arrow_specs()
        retreat_color = _viz_config.get_color("failure") if status == "failed" else color
        arrow_status = "failure" if status == "failed" else None
        
        # Use unified arrow function with dotted style
        Map._draw_arrow(draw, from_coord, to_coord, retreat_color, 
                       width=arrow_specs["line_width_secondary"], 
                       style="dotted", status=arrow_status)
    
    @staticmethod
    def _draw_conflict_marker(draw, province: str, strengths: dict, result: str, coords: dict):
        """
        Draw battle indicator per spec section 3.4.9.
        
        Star/shield symbol, red/orange color, optional strength label.
        """
        if province not in coords:
            return
            
        coord = coords[province]
        x, y = coord
        
        marker_specs = _viz_config.get_marker_specs()
        marker_size = marker_specs["battle_indicator_size"]
        border_width = marker_specs["battle_indicator_border_width"]
        battle_color = _viz_config.get_color("failure")  # Red for battles
        
        # Draw conflict marker (star or special symbol)
        Map._draw_star(draw, (x, y), marker_size, battle_color, "yellow")
        
        # Add strength indicator if available
        if strengths:
            max_strength = max(strengths.values())
            font_specs = _viz_config.get_font_specs()
            font_size = font_specs["conflict_label_size"]
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            draw.text((x + marker_size + 5, y - 10), str(max_strength), fill="black", font=font)
    
    @staticmethod
    def _draw_standoff_indicator(draw, province: str, coords: dict):
        """
        Draw standoff indicator per spec section 3.4.9.
        
        Equal sign or balanced scales symbol, yellow/orange color.
        """
        if province not in coords:
            return
            
        coord = coords[province]
        x, y = coord
        
        marker_specs = _viz_config.get_marker_specs()
        marker_size = marker_specs["standoff_indicator_size"]
        border_width = marker_specs["standoff_indicator_border_width"]
        standoff_color = _viz_config.get_color("convoy")  # Use convoy color (gold/yellow) for standoff
        rgb_standoff_color = Map._convert_color_to_rgb(standoff_color)
        
        # Draw special standoff marker (circle with equal sign)
        radius = marker_size // 2
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], 
                    outline=rgb_standoff_color, width=border_width)
        # Draw equal sign
        line_length = radius - 2
        draw.line([x - line_length, y - 3, x + line_length, y - 3], 
                 fill=rgb_standoff_color, width=border_width)
        draw.line([x - line_length, y + 3, x + line_length, y + 3], 
                 fill=rgb_standoff_color, width=border_width)
    
    @staticmethod
    def _draw_bounce_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2):
        """Draw curved return arrow for bounced moves"""
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Get config for outline
        arrow_specs = _viz_config.get_arrow_specs()
        outline_width = arrow_specs.get("outline_width", 2)
        arrowhead_size = arrow_specs["arrowhead_size"]
        outline_color = (0, 0, 0)  # Black
        total_width = width + outline_width * 2
        
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
        
        # Offset target by 4 pixels to prevent collisions
        collision_offset = 4
        angle_to_dest = math.atan2(to_y - points[-2][1], to_x - points[-2][0])
        actual_tip_x = to_x - collision_offset * math.cos(angle_to_dest)
        actual_tip_y = to_y - collision_offset * math.sin(angle_to_dest)
        
        arrow_length = arrowhead_size
        arrow_angle = math.pi / 6
        head_x1 = actual_tip_x - arrow_length * math.cos(angle_to_dest - arrow_angle)
        head_y1 = actual_tip_y - arrow_length * math.sin(angle_to_dest - arrow_angle)
        head_x2 = actual_tip_x - arrow_length * math.cos(angle_to_dest + arrow_angle)
        head_y2 = actual_tip_y - arrow_length * math.sin(angle_to_dest + arrow_angle)
        
        # Calculate arrowhead base center (where curve should end)
        base_center_x = (head_x1 + head_x2) / 2
        base_center_y = (head_y1 + head_y2) / 2
        
        # Calculate outline arrowhead (slightly larger)
        outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle_to_dest - arrow_angle)
        outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle_to_dest - arrow_angle)
        outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle_to_dest + arrow_angle)
        outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle_to_dest + arrow_angle)
        
        # Adjust last point to end at arrowhead base
        points[-1] = (base_center_x, base_center_y)
        
        # Draw outline curve
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=outline_color, width=total_width)
        
        # Draw outline arrowhead (slightly larger)
        draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)
        
        # Draw colored curve on top
        for i in range(len(points) - 1):
            draw.line([points[i], points[i+1]], fill=color, width=width)
        
        # Draw colored arrowhead on top
        draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)
    
    @staticmethod
    def _draw_dotted_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: int = 2):
        """Draw dotted arrow for retreat orders"""
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Get config for outline
        arrow_specs = _viz_config.get_arrow_specs()
        outline_width = arrow_specs.get("outline_width", 2)
        arrowhead_size = arrow_specs["arrowhead_size"]
        outline_color = (0, 0, 0)  # Black
        total_width = width + outline_width * 2
        
        # Calculate arrowhead first
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        
        # Offset target by 4 pixels to prevent collisions
        collision_offset = 4
        actual_tip_x = to_x - collision_offset * math.cos(angle)
        actual_tip_y = to_y - collision_offset * math.sin(angle)
        
        arrow_length = arrowhead_size
        arrow_angle = math.pi / 6
        head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)
        
        # Calculate arrowhead base center (where line should end)
        base_center_x = (head_x1 + head_x2) / 2
        base_center_y = (head_y1 + head_y2) / 2
        
        # Calculate outline arrowhead (slightly larger)
        outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
        outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
        outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
        outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)
        
        # Draw dotted line ending at arrowhead base
        length = math.sqrt((base_center_x - from_x)**2 + (base_center_y - from_y)**2)
        if length == 0:
            return
        
        dot_spacing = 8
        num_dots = int(length / dot_spacing)
        dx = (base_center_x - from_x) / num_dots if num_dots > 0 else 0
        dy = (base_center_y - from_y) / num_dots if num_dots > 0 else 0
        
        # Draw outline dots
        for i in range(0, num_dots, 2):
            x1 = from_x + i * dx
            y1 = from_y + i * dy
            x2 = from_x + (i + 1) * dx if i + 1 < num_dots else base_center_x
            y2 = from_y + (i + 1) * dy if i + 1 < num_dots else base_center_y
            draw.line([x1, y1, x2, y2], fill=outline_color, width=total_width)
        
        # Draw outline arrowhead (slightly larger)
        draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)
        
        # Draw colored dots on top
        for i in range(0, num_dots, 2):
            x1 = from_x + i * dx
            y1 = from_y + i * dy
            x2 = from_x + (i + 1) * dx if i + 1 < num_dots else base_center_x
            y2 = from_y + (i + 1) * dy if i + 1 < num_dots else base_center_y
            draw.line([x1, y1, x2, y2], fill=color, width=width)
        
        # Draw colored arrowhead on top
        draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)
    
    @staticmethod
    def _draw_success_checkmark(draw, coord: tuple, color: Optional[str] = None):
        """Draw success checkmark at coordinate using config values."""
        if color is None:
            color = _viz_config.get_color("success")
        x, y = coord
        marker_specs = _viz_config.get_marker_specs()
        size = marker_specs["status_indicator_size"]
        line_width = marker_specs["status_indicator_line_width"]
        rgb_color = Map._convert_color_to_rgb(color)
        
        # Draw checkmark (check shape)
        check_points = [
            (x - size, y),
            (x - size // 3, y + size // 2),
            (x + size, y - size // 2)
        ]
        draw.line([check_points[0], check_points[1], check_points[2]], fill=rgb_color, width=line_width)
    
    @staticmethod
    def _draw_failure_x(draw, coord: tuple, color: Optional[str] = None):
        """Draw failure X marker at coordinate using config values."""
        if color is None:
            color = _viz_config.get_color("failure")
        x, y = coord
        marker_specs = _viz_config.get_marker_specs()
        size = marker_specs["status_indicator_size"]
        line_width = marker_specs["status_indicator_line_width"]
        rgb_color = Map._convert_color_to_rgb(color)
        
        # Draw X
        draw.line([x - size, y - size, x + size, y + size], fill=rgb_color, width=line_width)
        draw.line([x - size, y + size, x + size, y - size], fill=rgb_color, width=line_width)
    
    @staticmethod
    def _draw_checkmark(draw, coord: tuple, color: str = "green"):
        """Legacy method - use _draw_success_checkmark instead."""
        Map._draw_success_checkmark(draw, coord, color)
    
    @staticmethod
    def _draw_status_x(draw, coord: tuple, color: str = "red"):
        """Legacy method - use _draw_failure_x instead."""
        Map._draw_failure_x(draw, coord, color)
    
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
    def _draw_arrow(draw, from_coord: tuple, to_coord: tuple, color: str, width: Optional[int] = None, style: str = "solid", status: Optional[str] = None):
        """
        Unified arrow drawing function using config values.
        
        Args:
            draw: ImageDraw object
            from_coord: Start coordinate (x, y)
            to_coord: End coordinate (x, y)
            color: Arrow color (hex or named color)
            width: Line width (uses config if None)
            style: Line style ("solid", "dashed", "dotted")
            status: Optional status indicator ("success", "failure", "bounce")
        """
        # Get arrow specs from config
        arrow_specs = _viz_config.get_arrow_specs()
        line_width = width if width is not None else arrow_specs["line_width_primary"]
        arrowhead_size = arrow_specs["arrowhead_size"]
        arrowhead_base_width = arrow_specs["arrowhead_base_width"]
        outline_width = arrow_specs.get("outline_width", 2)  # Default 2px black outline
        
        # Convert color to RGB if needed
        rgb_color = Map._convert_color_to_rgb(color)
        
        from_x, from_y = from_coord
        to_x, to_y = to_coord
        
        # Offset target by 4 pixels to prevent collisions when multiple arrows point to same region
        collision_offset = 4
        import math
        angle = math.atan2(to_y - from_y, to_x - from_x)
        # Move target back by collision_offset pixels
        actual_tip_x = to_x - collision_offset * math.cos(angle)
        actual_tip_y = to_y - collision_offset * math.sin(angle)
        
        # Calculate arrowhead points first (needed for both outline and fill)
        arrow_length = arrowhead_size
        arrow_angle = math.pi / 6  # 30 degrees (triangular shape)
        
        # Arrowhead tip is at actual_tip (4px before destination)
        # Arrowhead base extends backwards from tip
        head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)
        
        # Calculate arrowhead base center (where line should end)
        base_center_x = (head_x1 + head_x2) / 2
        base_center_y = (head_y1 + head_y2) / 2
        
        # Draw black outline first (wider line + outlined arrowhead)
        outline_color = (0, 0, 0)  # Black
        total_width = line_width + outline_width * 2
        
        # Calculate outline arrowhead (slightly larger for outline effect)
        outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
        outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
        outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
        outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)
        
        if style == "solid":
            # Draw outline line ending at arrowhead base
            draw.line([from_x, from_y, base_center_x, base_center_y], fill=outline_color, width=total_width)
        elif style == "dashed":
            line_style = _viz_config.get_line_style("dashed")
            Map._draw_dashed_line(draw, from_x, from_y, base_center_x, base_center_y, outline_color, total_width, 
                                dash=line_style.get("dash", 4), gap=line_style.get("gap", 2))
        elif style == "dotted":
            line_style = _viz_config.get_line_style("dotted")
            Map._draw_dotted_line(draw, from_x, from_y, base_center_x, base_center_y, outline_color, total_width,
                                 dot=line_style.get("dot", 2), gap=line_style.get("gap", 2))
        
        # Draw outline arrowhead (slightly larger to create outline effect)
        draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)
        
        # Now draw the colored arrow on top
        if style == "dashed":
            line_style = _viz_config.get_line_style("dashed")
            Map._draw_dashed_line(draw, from_x, from_y, base_center_x, base_center_y, rgb_color, line_width, 
                                dash=line_style.get("dash", 4), gap=line_style.get("gap", 2))
        elif style == "dotted":
            line_style = _viz_config.get_line_style("dotted")
            Map._draw_dotted_line(draw, from_x, from_y, base_center_x, base_center_y, rgb_color, line_width,
                                 dot=line_style.get("dot", 2), gap=line_style.get("gap", 2))
        else:  # solid
            # Draw colored line ending at arrowhead base
            draw.line([from_x, from_y, base_center_x, base_center_y], fill=rgb_color, width=line_width)
        
        # Draw colored arrowhead on top
        draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=rgb_color)
        
        # Draw status indicators if provided (use actual tip position)
        actual_tip_coord = (actual_tip_x, actual_tip_y)
        if status == "success":
            Map._draw_success_checkmark(draw, actual_tip_coord)
        elif status == "failure":
            Map._draw_failure_x(draw, actual_tip_coord)
        elif status == "bounce":
            # Draw bounce indicator (curved return arrow)
            bounce_color = _viz_config.get_color("failure")  # Use failure color for bounce
            Map._draw_bounce_arrow(draw, actual_tip_coord, from_coord, bounce_color, arrow_specs["line_width_secondary"])

    @staticmethod
    def _draw_circle(draw, coord: tuple, color: str, width: int = 2, style: str = "solid"):
        """Draw circle around coordinate (legacy - use _draw_circle_at_size for config-based sizing)"""
        x, y = coord
        radius = 15
        
        if style == "dashed":
            Map._draw_dashed_circle(draw, x, y, radius, color, width)
        else:
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], outline=color, width=width)
    
    @staticmethod
    def _draw_circle_at_size(draw, coord: tuple, color: str, diameter: int, width: int, style: str = "solid"):
        """Draw circle at specified diameter using config values."""
        x, y = coord
        radius = diameter // 2
        rgb_color = Map._convert_color_to_rgb(color)
        
        if style == "dashed":
            Map._draw_dashed_circle(draw, x, y, radius, rgb_color, width)
        else:
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], 
                        outline=rgb_color, width=width)

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
        
        # Get config for outline
        arrow_specs = _viz_config.get_arrow_specs()
        outline_width = arrow_specs.get("outline_width", 2)
        arrowhead_size = arrow_specs["arrowhead_size"]
        outline_color = (0, 0, 0)  # Black
        total_width = width + outline_width * 2
        
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
        
        # Offset target by 4 pixels to prevent collisions
        collision_offset = 4
        actual_tip_x = to_x - collision_offset * math.cos(angle)
        actual_tip_y = to_y - collision_offset * math.sin(angle)
        
        # Calculate arrowhead position
        arrow_length = arrowhead_size
        arrow_angle = math.pi / 6
        head_x1 = actual_tip_x - arrow_length * math.cos(angle - arrow_angle)
        head_y1 = actual_tip_y - arrow_length * math.sin(angle - arrow_angle)
        head_x2 = actual_tip_x - arrow_length * math.cos(angle + arrow_angle)
        head_y2 = actual_tip_y - arrow_length * math.sin(angle + arrow_angle)
        
        # Calculate arrowhead base center (where curve should end)
        base_center_x = (head_x1 + head_x2) / 2
        base_center_y = (head_y1 + head_y2) / 2
        
        # Calculate outline arrowhead (slightly larger)
        outline_head_x1 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle - arrow_angle)
        outline_head_y1 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle - arrow_angle)
        outline_head_x2 = actual_tip_x - (arrow_length + outline_width) * math.cos(angle + arrow_angle)
        outline_head_y2 = actual_tip_y - (arrow_length + outline_width) * math.sin(angle + arrow_angle)
        
        # Draw outline curved line using quadratic bezier, ending at arrowhead base
        steps = 20
        for i in range(steps):
            t1 = i / steps
            t2 = (i + 1) / steps
            
            x1 = (1-t1)**2 * from_x + 2*(1-t1)*t1 * control_x + t1**2 * base_center_x
            y1 = (1-t1)**2 * from_y + 2*(1-t1)*t1 * control_y + t1**2 * base_center_y
            x2 = (1-t2)**2 * from_x + 2*(1-t2)*t2 * control_x + t2**2 * base_center_x
            y2 = (1-t2)**2 * from_y + 2*(1-t2)*t2 * control_y + t2**2 * base_center_y
            
            if style == "dashed" and i % 2 == 0:
                continue
            draw.line([x1, y1, x2, y2], fill=outline_color, width=total_width)
        
        # Draw outline arrowhead (slightly larger)
        draw.polygon([actual_tip_x, actual_tip_y, outline_head_x1, outline_head_y1, outline_head_x2, outline_head_y2], fill=outline_color)
        
        # Draw colored curved line on top
        for i in range(steps):
            t1 = i / steps
            t2 = (i + 1) / steps
            
            x1 = (1-t1)**2 * from_x + 2*(1-t1)*t1 * control_x + t1**2 * base_center_x
            y1 = (1-t1)**2 * from_y + 2*(1-t1)*t1 * control_y + t1**2 * base_center_y
            x2 = (1-t2)**2 * from_x + 2*(1-t2)*t2 * control_x + t2**2 * base_center_x
            y2 = (1-t2)**2 * from_y + 2*(1-t2)*t2 * control_y + t2**2 * base_center_y
            
            if style == "dashed" and i % 2 == 0:
                continue
            draw.line([x1, y1, x2, y2], fill=color, width=width)
        
        # Draw colored arrowhead on top
        draw.polygon([actual_tip_x, actual_tip_y, head_x1, head_y1, head_x2, head_y2], fill=color)

    @staticmethod
    def _draw_dashed_line(draw, x1: int, y1: int, x2: int, y2: int, color: str, width: int, dash: int = 4, gap: int = 2):
        """Draw dashed line with configurable dash and gap lengths."""
        import math
        length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
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
            end_length = min(current_length + dash, length)
            end_x = x1 + end_length * dx
            end_y = y1 + end_length * dy
            
            draw.line([start_x, start_y, end_x, end_y], fill=color, width=width)
            current_length += dash + gap
    
    @staticmethod
    def _draw_dotted_line(draw, x1: int, y1: int, x2: int, y2: int, color: str, width: int, dot: int = 2, gap: int = 2):
        """Draw dotted line with configurable dot and gap lengths."""
        import math
        length = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        if length == 0:
            return
        
        # Calculate unit vector
        dx = (x2 - x1) / length
        dy = (y2 - y1) / length
        
        # Draw dots
        current_length = 0
        while current_length < length:
            dot_x = x1 + current_length * dx
            dot_y = y1 + current_length * dy
            # Draw small circle for dot
            radius = width // 2
            draw.ellipse([dot_x - radius, dot_y - radius, dot_x + radius, dot_y + radius], 
                        fill=color, outline=color)
            current_length += dot + gap

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

    @staticmethod
    def _draw_legend(image: Image.Image, map_type: str, active_powers: List[str] = None) -> None:
        """
        Draw a context-aware legend on the map image.
        
        Args:
            image: PIL Image to draw on
            map_type: Type of map - "orders", "resolution", "initial", "final", "builds"
            active_powers: List of active power names to show in legend
        """
        if not _viz_config.is_legend_enabled():
            return
        
        legend_specs = _viz_config.get_legend_specs()
        arrow_specs = _viz_config.get_arrow_specs()
        marker_specs = _viz_config.get_marker_specs()
        
        padding = legend_specs["padding"]
        item_spacing = legend_specs["item_spacing"]
        symbol_size = legend_specs["symbol_size"]
        title_font_size = legend_specs["title_font_size"]
        item_font_size = legend_specs["item_font_size"]
        
        # Determine legend items based on map type
        legend_items = []
        
        if map_type == "orders":
            legend_items = [
                ("move", "Move"),
                ("hold", "Hold"),
                ("support", "Support"),
                ("convoy", "Convoy"),
            ]
        elif map_type == "resolution":
            legend_items = [
                ("success", "Success"),
                ("failed", "Failed"),
                ("bounce", "Bounced"),
                ("dislodged", "Dislodged"),
                ("cut", "Support Cut"),
            ]
        elif map_type == "builds":
            legend_items = [
                ("build", "Build"),
                ("destroy", "Destroy"),
            ]
        elif map_type in ["initial", "final"]:
            # Just show power colors for initial/final maps
            legend_items = []
        
        # Add power colors if active_powers provided (only use known power names; ignore unit strings like "A BUD" if wrong format was passed)
        power_items = []
        if active_powers:
            for power in sorted(active_powers):
                if power in KNOWN_POWER_NAMES:
                    power_items.append(("power", power))
        
        # Calculate legend dimensions
        total_items = len(legend_items) + len(power_items)
        if total_items == 0:
            return
        
        # Estimate text width (approximate)
        max_text_width = 100  # Default
        for _, label in legend_items + power_items:
            max_text_width = max(max_text_width, len(label) * 8)
        
        legend_width = padding * 2 + symbol_size + 10 + max_text_width
        item_height = max(symbol_size, 18) + item_spacing
        
        # Add title height if we have legend items
        title_height = title_font_size + 10 if legend_items else 0
        
        # Add separator height if we have both legend items and power items
        separator_height = 15 if legend_items and power_items else 0
        
        legend_height = padding * 2 + title_height + (len(legend_items) * item_height) + separator_height + (len(power_items) * item_height)
        
        # Position legend (bottom-left by default)
        position = legend_specs.get("position", "bottom-left")
        if position == "bottom-left":
            legend_x = 20
            legend_y = image.height - legend_height - 20
        elif position == "bottom-right":
            legend_x = image.width - legend_width - 20
            legend_y = image.height - legend_height - 20
        elif position == "top-left":
            legend_x = 20
            legend_y = 20
        else:  # top-right
            legend_x = image.width - legend_width - 20
            legend_y = 20
        
        # Create overlay for legend with transparency
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Draw legend background
        bg_color = tuple(legend_specs["background_color"])
        border_color = tuple(legend_specs["border_color"])
        border_width = legend_specs["border_width"]
        
        overlay_draw.rectangle(
            [legend_x, legend_y, legend_x + legend_width, legend_y + legend_height],
            fill=bg_color,
            outline=border_color[:3],
            width=border_width
        )
        
        # Draw legend title if we have legend items
        current_y = legend_y + padding
        if legend_items:
            title_text = {
                "orders": "Orders",
                "resolution": "Results",
                "builds": "Adjustments",
            }.get(map_type, "Legend")
            
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", title_font_size)
            except (IOError, OSError):
                font = ImageFont.load_default()
            
            overlay_draw.text(
                (legend_x + padding, current_y),
                title_text,
                fill=(0, 0, 0, 255),
                font=font
            )
            current_y += title_font_size + 10
        
        # Draw legend items
        try:
            item_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", item_font_size)
        except (IOError, OSError):
            item_font = ImageFont.load_default()
        
        symbol_x = legend_x + padding
        text_x = symbol_x + symbol_size + 10
        
        for item_type, label in legend_items:
            symbol_center_y = current_y + symbol_size // 2
            
            # Draw the symbol based on type
            if item_type == "move":
                # Draw a small arrow
                arrow_start = (symbol_x, symbol_center_y)
                arrow_end = (symbol_x + symbol_size, symbol_center_y)
                Map._draw_mini_arrow(overlay_draw, arrow_start, arrow_end, (0, 0, 0), "solid")
            elif item_type == "hold":
                # Draw a dashed circle
                r = symbol_size // 3
                overlay_draw.ellipse(
                    [symbol_x + symbol_size//2 - r, symbol_center_y - r, 
                     symbol_x + symbol_size//2 + r, symbol_center_y + r],
                    outline=(100, 100, 100, 255),
                    width=2
                )
            elif item_type == "support":
                # Draw a dashed line with green tint
                Map._draw_mini_arrow(overlay_draw, 
                    (symbol_x, symbol_center_y), 
                    (symbol_x + symbol_size, symbol_center_y), 
                    (144, 238, 144), "dashed")
            elif item_type == "convoy":
                # Draw golden curved line
                Map._draw_mini_arrow(overlay_draw,
                    (symbol_x, symbol_center_y),
                    (symbol_x + symbol_size, symbol_center_y),
                    (255, 215, 0), "solid")
            elif item_type == "success":
                # Draw checkmark
                Map._draw_mini_checkmark(overlay_draw, 
                    (symbol_x + symbol_size//2, symbol_center_y), (0, 200, 0))
            elif item_type == "failed":
                # Draw X
                Map._draw_mini_x(overlay_draw,
                    (symbol_x + symbol_size//2, symbol_center_y), (255, 0, 0))
            elif item_type == "bounce":
                # Draw orange X
                Map._draw_mini_x(overlay_draw,
                    (symbol_x + symbol_size//2, symbol_center_y), (255, 165, 0))
            elif item_type == "dislodged":
                # Draw red-bordered circle
                r = symbol_size // 3
                overlay_draw.ellipse(
                    [symbol_x + symbol_size//2 - r, symbol_center_y - r,
                     symbol_x + symbol_size//2 + r, symbol_center_y + r],
                    fill=(200, 200, 200, 255),
                    outline=(255, 0, 0, 255),
                    width=3
                )
            elif item_type == "cut":
                # Draw support line with X through it
                Map._draw_mini_arrow(overlay_draw,
                    (symbol_x, symbol_center_y),
                    (symbol_x + symbol_size, symbol_center_y),
                    (144, 238, 144), "dashed")
                Map._draw_mini_x(overlay_draw,
                    (symbol_x + symbol_size//2, symbol_center_y), (255, 0, 0), size=6)
            elif item_type == "build":
                # Draw green circle with plus
                r = symbol_size // 3
                cx, cy = symbol_x + symbol_size//2, symbol_center_y
                overlay_draw.ellipse(
                    [cx - r, cy - r, cx + r, cy + r],
                    fill=(0, 200, 0, 255),
                    outline=(0, 100, 0, 255),
                    width=2
                )
                overlay_draw.line([cx - r + 3, cy, cx + r - 3, cy], fill=(255, 255, 255), width=2)
                overlay_draw.line([cx, cy - r + 3, cx, cy + r - 3], fill=(255, 255, 255), width=2)
            elif item_type == "destroy":
                # Draw red circle with X
                r = symbol_size // 3
                cx, cy = symbol_x + symbol_size//2, symbol_center_y
                overlay_draw.ellipse(
                    [cx - r, cy - r, cx + r, cy + r],
                    fill=(200, 0, 0, 255),
                    outline=(100, 0, 0, 255),
                    width=2
                )
                Map._draw_mini_x(overlay_draw, (cx, cy), (255, 255, 255), size=r-2)
            
            # Draw label
            overlay_draw.text(
                (text_x, current_y + (symbol_size - item_font_size) // 2),
                label,
                fill=(0, 0, 0, 255),
                font=item_font
            )
            
            current_y += item_height
        
        # Draw separator line if we have both sections
        if legend_items and power_items:
            current_y += 5
            overlay_draw.line(
                [legend_x + padding, current_y, legend_x + legend_width - padding, current_y],
                fill=(150, 150, 150, 255),
                width=1
            )
            current_y += 10
        
        # Draw power color items
        for item_type, power in power_items:
            symbol_center_y = current_y + symbol_size // 2
            
            # Draw power color box
            power_color = _viz_config.get_power_color(power)
            rgb_color = Map._convert_color_to_rgb(power_color)
            # Ensure rgb_color is a tuple, not a string
            if isinstance(rgb_color, str):
                # Convert named color to RGB using PIL
                from PIL import ImageColor
                try:
                    rgb_color = ImageColor.getrgb(rgb_color)
                except ValueError:
                    rgb_color = (128, 128, 128)  # Fallback to gray
            r = symbol_size // 3
            cx, cy = symbol_x + symbol_size//2, symbol_center_y
            overlay_draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=rgb_color + (255,),
                outline=(0, 0, 0, 255),
                width=2
            )
            
            # Draw power name
            overlay_draw.text(
                (text_x, current_y + (symbol_size - item_font_size) // 2),
                power.title(),
                fill=(0, 0, 0, 255),
                font=item_font
            )
            
            current_y += item_height
        
        # Composite overlay onto image
        if image.mode == 'RGBA':
            image.alpha_composite(overlay)
        else:
            # Convert to RGBA, composite, convert back
            image_rgba = image.convert('RGBA')
            image_rgba.alpha_composite(overlay)
            # Paste back (for RGB images)
            image.paste(image_rgba.convert('RGB'))

    @staticmethod
    def _draw_mini_arrow(draw, start: tuple, end: tuple, color: tuple, style: str = "solid"):
        """Draw a small arrow for legend."""
        x1, y1 = start
        x2, y2 = end
        
        if style == "dashed":
            # Draw dashed line
            for i in range(0, int(x2 - x1), 6):
                draw.line([x1 + i, y1, x1 + i + 3, y2], fill=color + (255,), width=2)
        else:
            draw.line([x1, y1, x2, y2], fill=color + (255,), width=2)
        
        # Draw arrowhead
        arrow_size = 5
        draw.polygon([
            (x2, y2),
            (x2 - arrow_size, y2 - arrow_size//2),
            (x2 - arrow_size, y2 + arrow_size//2)
        ], fill=color + (255,))

    @staticmethod
    def _draw_mini_checkmark(draw, center: tuple, color: tuple):
        """Draw a small checkmark for legend."""
        x, y = center
        size = 8
        points = [
            (x - size, y),
            (x - size//3, y + size//2),
            (x + size, y - size//2)
        ]
        draw.line([points[0], points[1], points[2]], fill=color + (255,), width=3)

    @staticmethod
    def _draw_mini_x(draw, center: tuple, color: tuple, size: int = 8):
        """Draw a small X for legend."""
        x, y = center
        draw.line([x - size, y - size, x + size, y + size], fill=color + (255,), width=3)
        draw.line([x - size, y + size, x + size, y - size], fill=color + (255,), width=3)

    @staticmethod
    def _load_and_process_icon(icon_path: str, fill_color: tuple, outline_color: tuple, size: int) -> Optional[Image.Image]:
        """
        Load an icon PNG file, replace white pixels with fill_color, add outline, and scale to size.
        
        Args:
            icon_path: Path to the icon PNG file
            fill_color: RGB tuple for the icon color
            outline_color: RGB tuple for the outline
            size: Target size (diameter) for the icon
            
        Returns:
            Processed PIL Image, or None if file not found
        """
        if not os.path.exists(icon_path):
            logger.warning(f"Icon file not found: {icon_path}")
            return None
        
        try:
            # Load the icon image
            icon_img = Image.open(icon_path).convert("RGBA")
            original_size = icon_img.size
            
            # Create a new image with the same size for processing
            processed = Image.new("RGBA", original_size, (0, 0, 0, 0))
            pixels = icon_img.load()
            processed_pixels = processed.load()
            
            # Replace white/light pixels with fill_color, preserve transparency
            # White is approximately (255, 255, 255) or close to it
            white_threshold = 200  # Consider pixels brighter than this as "white"
            for y in range(original_size[1]):
                for x in range(original_size[0]):
                    r, g, b, a = pixels[x, y]
                    if a > 0:  # Not fully transparent
                        # Check if pixel is white/light
                        if r >= white_threshold and g >= white_threshold and b >= white_threshold:
                            # Replace with fill_color, preserve original alpha
                            processed_pixels[x, y] = (*fill_color, a)
                        else:
                            # Keep original pixel (for any non-white details)
                            processed_pixels[x, y] = (r, g, b, a)
            
            # Add outline using a simple expansion approach
            outline_width = 2
            # Create a slightly larger canvas
            canvas_size = (original_size[0] + outline_width * 2, original_size[1] + outline_width * 2)
            outlined = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            
            # Extract alpha channel as mask
            alpha_channel = processed.split()[3]
            
            # Create outline by drawing the icon slightly larger with outline_color
            # Simple approach: paste the icon multiple times at offsets to create outline
            outline_offsets = [(-outline_width, -outline_width), (-outline_width, 0), (-outline_width, outline_width),
                               (0, -outline_width), (0, outline_width),
                               (outline_width, -outline_width), (outline_width, 0), (outline_width, outline_width)]
            
            # Create outline version (colored with outline_color)
            outline_base = Image.new("RGBA", original_size, (0, 0, 0, 0))
            outline_pixels = outline_base.load()
            alpha_pixels = alpha_channel.load()
            for y in range(original_size[1]):
                for x in range(original_size[0]):
                    if alpha_pixels[x, y] > 0:
                        outline_pixels[x, y] = (*outline_color, alpha_pixels[x, y])
            
            # Paste outline versions at offsets
            for dx, dy in outline_offsets:
                outlined.paste(outline_base, (outline_width + dx, outline_width + dy), outline_base)
            
            # Paste the colored icon on top (centered)
            outlined.paste(processed, (outline_width, outline_width), processed)
            
            # Scale to target size (maintaining aspect ratio)
            # Scale to fit within the diameter
            scale_factor = size / max(canvas_size)
            new_size = (int(canvas_size[0] * scale_factor), int(canvas_size[1] * scale_factor))
            scaled = outlined.resize(new_size, Image.Resampling.LANCZOS)
            
            return scaled
            
        except Exception as e:
            logger.error(f"Error loading icon {icon_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    @staticmethod
    def _draw_army_icon(draw, center: tuple, fill_color: tuple, outline_color: tuple, size: int, base_image: Optional[Image.Image] = None):
        """
        Draw an army icon from PNG file with background circle for visibility.
        
        Args:
            draw: ImageDraw object
            center: (x, y) center coordinates
            fill_color: RGB tuple for fill
            outline_color: RGB tuple for outline
            size: Icon size (diameter)
            base_image: Optional PIL Image object to paste onto (if None, tries to get from draw.im)
        """
        x, y = center
        r = size // 2
        
        # Get config for background circle
        unit_specs = _viz_config.get_unit_specs()
        use_background = unit_specs.get("background_circle", True)
        bg_color = tuple(unit_specs.get("background_circle_color", [255, 255, 255, 230]))
        
        # Draw background circle for contrast
        if use_background:
            bg_r = r + 2  # Slightly larger than icon
            draw.ellipse([x - bg_r, y - bg_r, x + bg_r, y + bg_r], 
                        fill=bg_color, outline=outline_color, width=3)
        
        # Find icon file path (relative to project root)
        # map.py is at: new_implementation/src/engine/map.py
        # icons are at: new_implementation/icons/army.png
        current_file = os.path.abspath(__file__)
        # Go up from src/engine/map.py to src, then to new_implementation, then to icons
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        icon_path = os.path.join(project_root, "icons", "army.png")
        
        # Load and process the icon
        icon_img = Map._load_and_process_icon(icon_path, fill_color, outline_color, size)
        
        if icon_img:
            # Get the underlying image from the draw object or use provided base_image
            try:
                if base_image is None:
                    base_image = draw.im
                    # Try to convert ImagingCore to Image if needed
                    if not isinstance(base_image, Image.Image):
                        # For ImagingCore, we need to work with it differently
                        # Get the image from the draw's underlying object
                        try:
                            # Try accessing through the image that created the draw
                            base_image = getattr(draw, '_image', None) or draw.im
                        except:
                            pass
                
                # Ensure base_image is a proper PIL Image
                if not isinstance(base_image, Image.Image):
                    logger.warning(f"base_image is not a PIL Image: {type(base_image)}, falling back")
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
                    return
                
                icon_width, icon_height = icon_img.size
                paste_x = int(round(x - icon_width // 2))
                paste_y = int(round(y - icon_height // 2))
                
                # Ensure coordinates are within image bounds
                img_width, img_height = base_image.size
                paste_x = max(0, min(paste_x, img_width - icon_width))
                paste_y = max(0, min(paste_y, img_height - icon_height))
                
                # Paste the icon with alpha compositing
                if icon_img.mode == 'RGBA':
                    # Extract alpha channel for mask
                    alpha = icon_img.split()[3]
                    base_image.paste(icon_img, (paste_x, paste_y), alpha)
                else:
                    base_image.paste(icon_img, (paste_x, paste_y))
                    
            except (AttributeError, Exception) as e:
                logger.warning(f"Could not paste icon image: {e}, falling back to programmatic drawing")
                import traceback
                logger.debug(traceback.format_exc())
                # Fallback: draw a simple circle as placeholder
                draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
        else:
            # Fallback: draw a simple circle as placeholder
            logger.warning(f"Icon not loaded from {icon_path}")
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)

    @staticmethod
    def _draw_fleet_icon(draw, center: tuple, fill_color: tuple, outline_color: tuple, size: int, base_image: Optional[Image.Image] = None):
        """
        Draw a fleet icon from PNG file with background circle for visibility.
        
        Args:
            draw: ImageDraw object
            center: (x, y) center coordinates
            fill_color: RGB tuple for fill
            outline_color: RGB tuple for outline
            size: Icon size (diameter)
            base_image: Optional PIL Image object to paste onto (if None, tries to get from draw.im)
        """
        x, y = center
        r = size // 2
        
        # Get config for background circle
        unit_specs = _viz_config.get_unit_specs()
        use_background = unit_specs.get("background_circle", True)
        bg_color = tuple(unit_specs.get("background_circle_color", [255, 255, 255, 230]))
        
        # Draw background circle for contrast
        if use_background:
            bg_r = r + 2  # Slightly larger than icon
            draw.ellipse([x - bg_r, y - bg_r, x + bg_r, y + bg_r], 
                        fill=bg_color, outline=outline_color, width=3)
        
        # Find icon file path (relative to project root)
        # map.py is at: new_implementation/src/engine/map.py
        # icons are at: new_implementation/icons/ship.png
        current_file = os.path.abspath(__file__)
        # Go up from src/engine/map.py to src, then to new_implementation, then to icons
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        icon_path = os.path.join(project_root, "icons", "ship.png")
        
        # Load and process the icon
        icon_img = Map._load_and_process_icon(icon_path, fill_color, outline_color, size)
        
        if icon_img:
            # Get the underlying image from the draw object or use provided base_image
            try:
                if base_image is None:
                    base_image = draw.im
                    # Try to convert ImagingCore to Image if needed
                    if not isinstance(base_image, Image.Image):
                        # For ImagingCore, we need to work with it differently
                        # Get the image from the draw's underlying object
                        try:
                            # Try accessing through the image that created the draw
                            base_image = getattr(draw, '_image', None) or draw.im
                        except:
                            pass
                
                # Ensure base_image is a proper PIL Image
                if not isinstance(base_image, Image.Image):
                    logger.warning(f"base_image is not a PIL Image: {type(base_image)}, falling back")
                    draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
                    return
                
                icon_width, icon_height = icon_img.size
                paste_x = int(round(x - icon_width // 2))
                paste_y = int(round(y - icon_height // 2))
                
                # Ensure coordinates are within image bounds
                img_width, img_height = base_image.size
                paste_x = max(0, min(paste_x, img_width - icon_width))
                paste_y = max(0, min(paste_y, img_height - icon_height))
                
                # Paste the icon with alpha compositing
                if icon_img.mode == 'RGBA':
                    # Extract alpha channel for mask
                    alpha = icon_img.split()[3]
                    base_image.paste(icon_img, (paste_x, paste_y), alpha)
                else:
                    base_image.paste(icon_img, (paste_x, paste_y))
                    
            except (AttributeError, Exception) as e:
                logger.warning(f"Could not paste icon image: {e}, falling back to programmatic drawing")
                import traceback
                logger.debug(traceback.format_exc())
                # Fallback: draw a simple circle as placeholder
                draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
        else:
            # Fallback: draw a simple circle as placeholder
            logger.warning(f"Icon not loaded from {icon_path}")
            draw.ellipse([x - r, y - r, x + r, y + r], fill=fill_color, outline=outline_color, width=2)
