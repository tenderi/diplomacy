import os
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw
import cairosvg
import io

class Map:
    """Represents a Diplomacy map with provinces, units, and rendering capabilities."""
    
    def __init__(self):
        """Initialize an empty map."""
        self.provinces = {}
        self.supply_centers = set()
        self._setup_provinces()
    
    def _setup_provinces(self):
        """Set up the standard Diplomacy provinces with their properties."""
        # Define province data: (name, is_supply_center, [adjacent_provinces])
        province_data = [
            # Supply centers
            ("LON", True, ["WAL", "YOR", "ENG", "NTH"]),
            ("EDI", True, ["YOR", "CLY", "NWG"]),
            ("LVP", True, ["CLY", "WAL", "IRI"]),
            ("PAR", True, ["PIC", "BUR", "GAS", "BRE"]),
            ("MAR", True, ["PIC", "BUR", "GAS", "SPA", "LYO", "PIE"]),
            ("BRE", True, ["ENG", "GAS", "PIC"]),
            ("BER", True, ["KIE", "PRU", "SIL", "MUN", "BAL"]),
            ("KIE", True, ["DEN", "SWE", "BAL", "BER", "MUN", "RUH"]),
            ("MUN", True, ["KIE", "BER", "SIL", "BOH", "TYR", "BUR", "RUH"]),
            ("WAR", True, ["PRU", "LIV", "MOS", "UKR", "GAL", "SIL"]),
            ("MOS", True, ["STP", "LIV", "WAR", "UKR", "SEV"]),
            ("STP", True, ["FIN", "LIV", "MOS", "BAR"]),
            ("SEV", True, ["MOS", "UKR", "RUM", "BLA", "ARM"]),
            ("CON", True, ["BUL", "SMY", "AEG", "BLA", "ARM", "ANK"]),
            ("SMY", True, ["CON", "ANK", "ARM", "SYR", "EAS"]),
            ("ANK", True, ["CON", "ARM", "BLA", "SEV"]),
            ("ROM", True, ["PIE", "TUS", "TYR", "VEN", "APU", "NAP", "ION"]),
            ("VEN", True, ["TYR", "TRI", "ADR", "APU", "ROM", "PIE"]),
            ("TRI", True, ["TYR", "BOH", "GAL", "UKR", "RUM", "SER", "ALB", "ADR", "VEN"]),
            ("VIE", True, ["BOH", "GAL", "TRI", "TYR", "BUD"]),
            ("BUD", True, ["GAL", "RUM", "SER", "TRI", "VIE"]),
            
            # Non-supply centers
            ("CLY", False, ["EDI", "LVP", "NAO", "NWG"]),
            ("WAL", False, ["LON", "LVP", "ENG", "IRI"]),
            ("YOR", False, ["LON", "EDI", "NTH"]),
            ("PIC", False, ["PAR", "BRE", "ENG", "BUR", "MAR"]),
            ("BUR", False, ["PAR", "PIC", "MAR", "MUN", "RUH", "BEL"]),
            ("GAS", False, ["PAR", "BRE", "MAR", "SPA", "MAO"]),
            ("SPA", False, ["GAS", "MAR", "LYO", "MAO", "POR"]),
            ("POR", False, ["SPA", "MAO"]),
            ("MAO", False, ["BRE", "GAS", "SPA", "POR", "ENG", "IRI", "NAO"]),
            ("IRI", False, ["LVP", "WAL", "ENG", "MAO", "NAO"]),
            ("NAO", False, ["CLY", "IRI", "MAO", "NWG", "BAR"]),
            ("NWG", False, ["CLY", "EDI", "BAR", "NAO"]),
            ("BAR", False, ["STP", "NWG", "NAO"]),
            ("NTH", False, ["LON", "YOR", "ENG", "BEL", "HOL", "DEN", "SKA", "NOR"]),
            ("ENG", False, ["LON", "WAL", "BRE", "PIC", "BEL", "NTH", "IRI", "MAO"]),
            ("BEL", False, ["PIC", "BUR", "RUH", "HOL", "NTH", "ENG"]),
            ("HOL", False, ["BEL", "RUH", "KIE", "DEN", "NTH"]),
            ("DEN", False, ["HOL", "KIE", "SWE", "SKA", "NTH", "BAL"]),
            ("SWE", False, ["DEN", "KIE", "BAL", "FIN", "NOR", "SKA"]),
            ("NOR", False, ["STP", "FIN", "SWE", "SKA", "NTH", "BAR"]),
            ("FIN", False, ["STP", "NOR", "SWE", "BAL", "LIV"]),
            ("BAL", False, ["KIE", "BER", "PRU", "LIV", "FIN", "SWE", "DEN"]),
            ("PRU", False, ["BER", "BAL", "LIV", "WAR", "SIL"]),
            ("LIV", False, ["STP", "FIN", "BAL", "PRU", "WAR", "MOS"]),
            ("SIL", False, ["BER", "PRU", "WAR", "GAL", "BOH", "MUN"]),
            ("BOH", False, ["MUN", "SIL", "GAL", "VIE", "TRI", "TYR"]),
            ("GAL", False, ["SIL", "WAR", "UKR", "RUM", "BUD", "VIE", "BOH"]),
            ("UKR", False, ["WAR", "MOS", "SEV", "RUM", "GAL"]),
            ("RUM", False, ["GAL", "UKR", "SEV", "BLA", "BUL", "SER", "TRI"]),
            ("BUL", False, ["RUM", "BLA", "CON", "AEG", "GRE", "SER"]),
            ("SER", False, ["TRI", "BUD", "RUM", "BUL", "GRE", "ALB"]),
            ("ALB", False, ["TRI", "SER", "GRE", "ION", "ADR"]),
            ("GRE", False, ["BUL", "AEG", "ION", "ALB", "SER"]),
            ("NAP", False, ["ROM", "ION", "TUS"]),
            ("APU", False, ["ROM", "VEN", "ADR", "ION", "NAP"]),
            ("TUS", False, ["PIE", "ROM", "NAP", "LYO"]),
            ("PIE", False, ["MAR", "LYO", "TUS", "ROM", "VEN"]),
            ("LYO", False, ["MAR", "PIE", "TUS", "NAP", "ION", "TYS", "WES"]),
            ("TYS", False, ["LYO", "ION", "NAP", "WES"]),
            ("ION", False, ["NAP", "APU", "ADR", "ALB", "GRE", "AEG", "TYS", "LYO"]),
            ("ADR", False, ["VEN", "TRI", "ALB", "ION", "APU"]),
            ("AEG", False, ["CON", "SMY", "EAS", "ION", "GRE", "BUL"]),
            ("EAS", False, ["SMY", "SYR", "ION", "AEG"]),
            ("SYR", False, ["SMY", "ARM", "EAS"]),
            ("ARM", False, ["SMY", "ANK", "BLA", "SEV", "SYR"]),
            ("BLA", False, ["CON", "ANK", "ARM", "SEV", "RUM", "BUL"]),
            ("RUH", False, ["BEL", "BUR", "MUN", "KIE", "HOL"]),
            ("SKAG", False, ["DEN", "SWE", "NOR", "NTH"]),
            ("BOT", False, ["STP", "FIN", "SWE", "BAL"]),
            ("WES", False, ["LYO", "TYS", "SPA", "MAO"]),
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
        
        # Original map parsing (jdipNS structure)
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
        
        # Original map parsing (jdipNS structure)
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
    def _color_provinces_by_power(draw, units, power_colors, svg_path):
        """Color provinces based on power control using jdipNS coordinates (same system as units)."""
        try:
            import xml.etree.ElementTree as ET
            
            # Parse the SVG file
            tree = ET.parse(svg_path)
            root = tree.getroot()
            
            # Use jdipNS:PROVINCE coordinates (same system as unit placement)
            ns = {'jdipNS': 'svg.dtd'}
            jdip_provinces = root.findall('.//jdipNS:PROVINCE', ns)
            
            if not jdip_provinces:
                print("Warning: No jdipNS:PROVINCE elements found, falling back to path-based coloring")
                return
            
            # Create a map of province names to power colors
            province_power_map = {}
            for power, unit_list in units.items():
                color = power_colors.get(power.upper(), "black")
                for unit in unit_list:
                    parts = unit.split()
                    if len(parts) == 2:
                        prov = parts[1].upper()
                        province_power_map[prov] = color
            
            # Color each province based on power control using jdipNS coordinates
            for jdip_prov in jdip_provinces:
                province_name = jdip_prov.attrib.get('name')
                if not province_name:
                    continue
                
                # Normalize province name (remove any prefixes)
                normalized_name = province_name.upper()
                if normalized_name.startswith('_'):
                    normalized_name = normalized_name[1:]
                
                if normalized_name in province_power_map:
                    # Get the power color for this province
                    power_color = province_power_map[normalized_name]
                    
                    # Convert color to RGB for transparency
                    rgb_color = Map._hex_to_rgb(power_color)
                    transparent_color = (*rgb_color, 38)  # 85% transparency (38/255 ≈ 0.149, so 85% transparent)
                    
                    # Get the jdipNS coordinates (same system as units)
                    unit_elem = jdip_prov.find('jdipNS:UNIT', ns)
                    if unit_elem is not None:
                        x = float(unit_elem.attrib.get('x', '0'))
                        y = float(unit_elem.attrib.get('y', '0'))
                        
                        # Draw a colored circle at the province center (same coordinates as units)
                        # Use a reasonable radius for province coloring
                        province_radius = 80  # Adjust this value to control province coloring size
                        
                        # Calculate circle bounds
                        left = x - province_radius
                        top = y - province_radius
                        right = x + province_radius
                        bottom = y + province_radius
                        
                        # Draw the colored province area
                        draw.ellipse((left, top, right, bottom), 
                                   fill=transparent_color, 
                                   outline=power_color, 
                                   width=2)
                    
        except Exception as e:
            print(f"Warning: Could not parse jdipNS for province coloring: {e}")
            # Fallback: continue without province coloring

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
    def render_board_png(units: dict, output_path: str, svg_path: str = "maps/standard.svg") -> bytes:
        """
        Render the game board as a PNG image.
        
        Args:
            units: Dict mapping power names to lists of unit strings (e.g., "F LON", "A PAR")
            output_path: Path to save the output PNG file
            svg_path: Path to the SVG map file
            
        Returns:
            PNG image data as bytes
        """
        try:
            # Convert SVG to PNG using cairosvg
            png_data = cairosvg.svg2png(url=svg_path, output_width=2202, output_height=1632)
            
            # Create PIL Image from PNG data
            image = Image.open(io.BytesIO(png_data))
            
            # Create a drawing object
            draw = ImageDraw.Draw(image)
            
            # Get province coordinates
            coords = Map.get_svg_province_coordinates(svg_path)
            
            # Define power colors
            power_colors = {
                "ENGLAND": "darkviolet",
                "FRANCE": "royalblue", 
                "GERMANY": "black",
                "RUSSIA": "forestgreen",
                "ITALY": "darkviolet",
                "AUSTRIA": "royalblue",
                "TURKEY": "forestgreen"
            }
            
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
                    
                    x, y = coords[prov]
                    
                    # Draw unit (simplified representation)
                    if unit_type == "F":  # Fleet
                        # Draw a triangle for fleet
                        points = [(x, y-15), (x-10, y+10), (x+10, y+10)]
                        draw.polygon(points, fill=color, outline="white", width=2)
                    else:  # Army
                        # Draw a circle for army
                        draw.ellipse((x-10, y-10, x+10, y+10), fill=color, outline="white", width=2)
            
            # Save the image
            image.save(output_path)
            
            return png_data
            
        except Exception as e:
            print(f"Error rendering board: {e}")
            raise

class Province:
    """Represents a province on the Diplomacy map."""
    
    def __init__(self, name: str, is_supply_center: bool = False, type_: str = 'land'):
        self.name = name
        self.is_supply_center = is_supply_center
        self.type = type_  # 'land', 'coast', or 'water'
        self.adjacent = set()
    
    def add_adjacent(self, province_name: str):
        """Add an adjacent province."""
        self.adjacent.add(province_name)
    
    def is_adjacent_to(self, province_name: str) -> bool:
        """Check if this province is adjacent to another."""
        return province_name in self.adjacent

# Define water and coastal provinces
water_provinces = {
    'ADR', 'AEG', 'BAL', 'BAR', 'BLA', 'BOT', 'EAS', 'ENG', 'ION', 'IRI', 'MAO', 'NAO', 'NTH', 'NWG', 'SKA', 'TYS', 'WES'
}

coastal_provinces = {
    'ALB', 'ANK', 'APU', 'ARM', 'BEL', 'BRE', 'BUL', 'CLY', 'CON', 'DEN', 'EDI', 'FIN', 'GAS', 'GRE', 'HOL', 'KIE', 'LON', 'LVP', 'MAR', 'NAP', 'NOR', 'PAR', 'PIC', 'PIE', 'POR', 'PRU', 'ROM', 'RUM', 'SEV', 'SMY', 'SPA', 'STP', 'SWE', 'SYR', 'TRI', 'TUN', 'TUS', 'UKR', 'VEN', 'VIE', 'WAL', 'WAR', 'YOR'
}
