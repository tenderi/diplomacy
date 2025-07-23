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
        coords = {}
        tree = ET.parse(svg_path)
        root = tree.getroot()
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
    def render_board_png(svg_path: str, units: dict, output_path: str = None) -> bytes:
        if svg_path is None:
            raise ValueError("svg_path must not be None")
        # 1. Convert SVG to PNG (background) with larger size for better readability
        # The SVG has viewBox="0 0 1835 1360" - scale up by 1.2x for better text readability
        # This gives us 2202x1632 pixels for a clearer map (reduced from 1.5x to save memory)
        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=2202, output_height=1632)  # type: ignore
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
        # 4. Draw units
        font = None
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)  # Increased font size for larger map
        except Exception:
            font = ImageFont.load_default()
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
                # Scale coordinates by 1.2x to match the larger map
                x, y = coords[prov]
                x = x * 1.2
                y = y * 1.2
                # Draw a colored circle for the unit (scaled up)
                r = 22  # Increased from 18 to 22 (1.2x)
                draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="black", width=3)  # Increased stroke width
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
