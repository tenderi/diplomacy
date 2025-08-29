"""
Map representation for Diplomacy.
- Represents provinces, supply centers, adjacency, and coasts.
- Loads map data (for now, hardcoded for classic map; later, can load from file).
"""

from typing import Dict, List, Set, Optional
import os
import json
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont
import cairosvg  # type: ignore
from io import BytesIO

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

class Map:
    """Represents the Diplomacy map, including provinces and their adjacencies."""
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
        """Fallback hardcoded standard map data."""
        # List of water provinces (sea/ocean spaces)
        water_provinces = {
            "ADR", "AEG", "BAL", "BAR", "BLA", "BOT", "EAS", "ENG", "HEL", "ION", "IRI", "MAO", "NAO", "NTH", "NWG", "SKA", "TYS", "WES"
        }
        # List of coastal provinces (land provinces fleets can enter)
        coastal_provinces = {
            "BRE", "BUL", "CLY", "CON", "DEN", "EDI", "FIN", "GAS", "GRE", "HOL", "KIE", "LON", "LVP", "MAR", "NAP", "NWY", "PAR", "PIC", "PIE", "POR", "PRU", "ROM", "RUH", "SMY", "SPA", "STP", "SWE", "TRI", "TUN", "VEN", "YOR", "ALB", "APU", "BEL", "BLA", "BOT", "EAS", "ENG", "HEL", "ION", "IRI", "MAO", "NAO", "NTH", "NWG", "SKA", "TYS", "WES"
        }
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
                type_ = 'water'
            elif name in coastal_provinces:
                type_ = 'coast'
            else:
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
    def get_svg_province_coordinates(svg_path: str) -> dict:
        """
        Parse the SVG file and extract province coordinates for unit placement.
        Returns a dict: {province_name: (x, y)}
        """
        # Check if this is the V2 map (doesn't have jdipNS structure)
        if 'v2' in svg_path.lower():
            try:
                from v2_map_coordinates import get_all_v2_coordinates
                return get_all_v2_coordinates()
            except ImportError:
                print("⚠️  Warning: v2_map_coordinates module not found, using fallback coordinates")
                # Fallback coordinates for V2 map
                return {
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
        
        # NEW APPROACH: Use SVG path centers instead of wrong jdipNS coordinates
        # This fixes the coordinate system mismatch
        coords = {}
        tree = ET.parse(svg_path)
        root = tree.getroot()
        
        # Find all SVG paths for provinces
        for path_elem in root.findall('.//*[@id]'):
            province_id = path_elem.get('id')
            if province_id and 'd' in path_elem.attrib:
                # Skip paths with underscores (these are not the main province areas)
                if not province_id.startswith('_'):
                    path_data = path_elem.attrib['d']
                    
                    # Parse SVG path to find center
                    import re
                    path_commands = re.findall(r'([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)', path_data)
                    
                    x_coords = []
                    y_coords = []
                    current_x, current_y = 0, 0
                    
                    for cmd, params in path_commands:
                        cmd = cmd.upper()
                        
                        if cmd == 'M':  # Move to (absolute)
                            coords_list = re.findall(r'(-?\d+\.?\d*)', params)
                            if len(coords_list) >= 2:
                                current_x, current_y = float(coords_list[0]), float(coords_list[1])
                                x_coords.append(current_x)
                                y_coords.append(current_y)
                                
                        elif cmd == 'L':  # Line to (absolute)
                            coords_list = re.findall(r'(-?\d+\.?\d*)', params)
                            if len(coords_list) >= 2:
                                current_x, current_y = float(coords_list[0]), float(coords_list[1])
                                x_coords.append(current_x)
                                y_coords.append(current_y)
                                
                        elif cmd == 'C':  # Cubic Bezier curve (absolute)
                            coords_list = re.findall(r'(-?\d+\.?\d*)', params)
                            if len(coords_list) >= 6:
                                # C x1 y1 x2 y2 x y - we care about end point
                                current_x, current_y = float(coords_list[4]), float(coords_list[5])
                                x_coords.append(current_x)
                                y_coords.append(current_y)
                    
                    if x_coords and y_coords:
                        # Calculate center of the province
                        center_x = sum(x_coords) / len(x_coords)
                        center_y = sum(y_coords) / len(y_coords)
                        coords[province_id.upper()] = (center_x, center_y)
        
        # FALLBACK: If no SVG paths found, try jdipNS (but they're wrong)
        if not coords:
            print("⚠️  Warning: No SVG paths found, falling back to jdipNS coordinates (these are known to be wrong!)")
            ns = {'jdipNS': 'svg.dtd'}
            for prov in root.findall('.//jdipNS:PROVINCE', ns):
                name = prov.attrib.get('name')
                unit = prov.find('jdipNS:UNIT', ns)
                if name and unit is not None:
                    x = float(unit.attrib.get('x', '0'))
                    y = float(unit.attrib.get('y', '0'))
                    coords[name.upper()] = (x, y)
        
        return coords

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
            
            # Separate paths with and without underscores
            paths_with_underscores = []
            paths_without_underscores = []
            
            for path in all_paths:
                province_id = path.get('id')
                if province_id:
                    if province_id.startswith('_'):
                        paths_with_underscores.append(path)
                    else:
                        paths_without_underscores.append(path)
            
            # Prioritize paths without underscores (actual provinces)
            province_paths = paths_without_underscores + paths_with_underscores
            


            

            

            
            # Create a map of province names to power colors
            province_power_map = {}
            for power, unit_list in units.items():
                color = power_colors.get(power.upper(), "black")
                for unit in unit_list:
                    parts = unit.split()
                    if len(parts) == 2:
                        prov = parts[1].upper()
                        province_power_map[prov] = color
            
            # Color each province based on power control
            for path_elem in province_paths:
                province_id = path_elem.get('id')
                if province_id:
                    # Normalize the province ID (remove underscore prefix and convert to uppercase)
                    normalized_id = province_id.lstrip('_').upper()
                    
                    if normalized_id in province_power_map:
                        # Get the power color for this province
                        power_color = province_power_map[normalized_id]
                        
                        # Convert color to RGB for transparency
                        rgb_color = Map._hex_to_rgb(power_color)
                        # 80% transparency means 20% opacity - use alpha 51 (51/255 ≈ 0.2)
                        transparent_color = (*rgb_color, 51)
                        
                        # Parse and fill the SVG path with correct coordinate alignment
                        path_data = path_elem.get('d')
                        if path_data:
                            # Use SVG paths directly - no scaling, no transformation
                            Map._fill_svg_path_direct(draw, path_data, transparent_color, power_color)
                    
        except Exception as e:
            print(f"Warning: Could not parse SVG for province coloring: {e}")
            # Fallback: continue without province coloring
    
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
            # SVG coordinates need to be scaled to match the PNG output
            # The PNG is 2202x1632, so we need to scale accordingly
            
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
    def render_board_png(svg_path: str, units: dict, output_path: str = None) -> bytes:
        if svg_path is None:
            raise ValueError("svg_path must not be None")
        # 1. Convert SVG to PNG (background) with EXACT SVG size - NO SCALING
        # The SVG has viewBox="0 0 1835 1360" - use exact size to avoid coordinate scaling issues
        # This gives us 1835x1360 pixels - no scaling, coordinates match exactly
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=1835, output_height=1360)  # type: ignore
        if png_bytes is None:
            raise ValueError("cairosvg.svg2png returned None")
        bg = Image.open(BytesIO(png_bytes)).convert("RGBA")  # type: ignore
        draw = ImageDraw.Draw(bg)
        # 2. Get province coordinates
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
        font = None
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 60)  # Increased font size by 2 (48 + 2 = 50)
        except Exception:
            font = ImageFont.load_default()
        
        # First pass: Color provinces based on power control
        if units:  # Only color provinces if there are units
            Map._color_provinces_by_power(draw, units, power_colors, svg_path)
        
        # Second pass: Draw units on top
        for power, unit_list in units.items():
            color = power_colors.get(power.upper(), "black")
            for unit in unit_list:
                parts = unit.split()
                if len(parts) != 2:
                    continue
                unit_type, prov = parts
                prov = prov.upper()
                if prov not in coords:
                    continue
                # NO SCALING - use SVG coordinates directly
                x, y = coords[prov]
                # All coordinates are now in the same coordinate system (no scaling needed)
                
                # Draw unit circle
                r = 14  # Reduced by 30% from 28 to 20 (28 * 0.7 = 19.6, rounded to 20)
                draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="black", width=3)
                
                # Draw unit type letter
                text = unit_type
                bbox = draw.textbbox((0, 0), text, font=font)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((x - w/2, y - h/2), text, fill="white", font=font)
        # 5. Save or return PNG
        if isinstance(output_path, str) and output_path:
            bg.save(output_path, format="PNG")
        output = BytesIO()
        bg.save(output, format="PNG")
        return output.getvalue()

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
    

