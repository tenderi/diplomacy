#!/usr/bin/env python3
"""
Map Generation Testing Script

This script tests the map generation functionality with different scenarios:
- Empty map (no units)
- Starting positions
- Mid-game scenarios
- Custom unit placements
- Comparison between original and fixed SVG files
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.engine.map import Map

class MapTester:
    """Class for testing map generation with various scenarios."""
    
    def __init__(self, output_dir: str = "test_maps"):
        self.output_dir = output_dir
        self.ensure_output_dir()
        
    def ensure_output_dir(self):
        """Create output directory if it doesn't exist."""
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"📁 Created output directory: {self.output_dir}")
    
    def test_scenario(self, name: str, svg_path: str, units: Dict[str, List[str]], description: str = ""):
        """Test a specific scenario and save the result."""
        print(f"\n🧪 Testing scenario: {name}")
        if description:
            print(f"   Description: {description}")
        
        try:
            # Generate map
            img_bytes = Map.render_board_png(svg_path, units)
            
            # Save to file
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
            
            print(f"   ✅ Success! Saved as: {filename}")
            print(f"   📏 Size: {len(img_bytes):,} bytes")
            
            return True, filepath
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False, None
    
    def run_all_tests(self, svg_path: str):
        """Run all predefined test scenarios."""
        print(f"🚀 Running all map tests with SVG: {svg_path}")
        print(f"📁 Output directory: {self.output_dir}")
        
        results = []
        
        # Test 1: Empty map
        results.append(self.test_scenario(
            "empty_map",
            svg_path,
            {},
            "Clean Diplomacy board with no units"
        ))
        
        # Test 2: Starting positions (standard Diplomacy)
        starting_units = {
            'ENGLAND': ['F LON', 'F EDI', 'A LVP'],
            'FRANCE': ['A PAR', 'A MAR', 'F BRE'],
            'GERMANY': ['A BER', 'A MUN', 'F KIE'],
            'ITALY': ['A ROM', 'A VEN', 'F NAP'],
            'AUSTRIA': ['A VIE', 'A BUD', 'F TRI'],
            'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'F STP'],
            'TURKEY': ['A CON', 'A SMY', 'F ANK']
        }
        results.append(self.test_scenario(
            "starting_positions",
            svg_path,
            starting_units,
            "Standard Diplomacy 1901 starting positions"
        ))
        
        # Test 3: Single power (France only)
        results.append(self.test_scenario(
            "france_only",
            svg_path,
            {'FRANCE': ['A PAR', 'A MAR', 'F BRE', 'A BUR', 'A GAS']},
            "France with some expansion"
        ))
        
        # Test 4: Mid-game scenario
        midgame_units = {
            'ENGLAND': ['F NTH', 'F ENG', 'A YOR', 'A WAL'],
            'FRANCE': ['A PAR', 'A BUR', 'F MAO', 'A SPA'],
            'GERMANY': ['A BER', 'A MUN', 'A RUH', 'F BAL'],
            'RUSSIA': ['A MOS', 'A WAR', 'A UKR', 'F SEV'],
            'AUSTRIA': ['A VIE', 'A BUD', 'A TRI'],
            'ITALY': ['A ROM', 'F TYS', 'A VEN'],
            'TURKEY': ['A CON', 'A BUL', 'F BLA']
        }
        results.append(self.test_scenario(
            "midgame_scenario",
            svg_path,
            midgame_units,
            "Mid-game with expanded positions"
        ))
        
        # Test 5: Crowded scenario (many units)
        crowded_units = {
            'ENGLAND': ['F LON', 'F EDI', 'A LVP', 'F NTH', 'A YOR', 'F ENG'],
            'FRANCE': ['A PAR', 'A MAR', 'F BRE', 'A BUR', 'A GAS', 'A PIC'],
            'GERMANY': ['A BER', 'A MUN', 'F KIE', 'A RUH', 'A SIL', 'F BAL'],
            'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'A STP', 'A UKR', 'A LVN'],
            'AUSTRIA': ['A VIE', 'A BUD', 'F TRI', 'A BOH', 'A GAL'],
            'ITALY': ['A ROM', 'A VEN', 'F NAP', 'A TUS', 'F TYS'],
            'TURKEY': ['A CON', 'A SMY', 'F ANK', 'A BUL', 'F BLA']
        }
        results.append(self.test_scenario(
            "crowded_board",
            svg_path,
            crowded_units,
            "Crowded board with many units"
        ))
        
        # Test 6: Fleets only
        results.append(self.test_scenario(
            "fleets_only",
            svg_path,
            {
                'ENGLAND': ['F LON', 'F EDI', 'F NTH'],
                'FRANCE': ['F BRE', 'F MAO', 'F WES'],
                'ITALY': ['F NAP', 'F TYS', 'F ION'],
                'RUSSIA': ['F SEV', 'F BLA', 'F BOT'],
                'TURKEY': ['F ANK', 'F CON', 'F AEG']
            },
            "Naval scenario - fleets only"
        ))
        
        # Test 7: Armies only
        results.append(self.test_scenario(
            "armies_only",
            svg_path,
            {
                'FRANCE': ['A PAR', 'A MAR', 'A BUR'],
                'GERMANY': ['A BER', 'A MUN', 'A RUH'],
                'RUSSIA': ['A MOS', 'A WAR', 'A STP'],
                'AUSTRIA': ['A VIE', 'A BUD', 'A TRI'],
                'TURKEY': ['A CON', 'A SMY', 'A ANK']
            },
            "Land scenario - armies only"
        ))
        
        # Summary
        successful = sum(1 for success, _ in results if success)
        total = len(results)
        
        print(f"\n📊 Test Summary:")
        print(f"   ✅ Successful: {successful}/{total}")
        print(f"   ❌ Failed: {total - successful}/{total}")
        
        if successful == total:
            print(f"   🎉 All tests passed!")
        else:
            print(f"   ⚠️  Some tests failed")
        
        return results
    
    def compare_svg_files(self, original_svg: str, fixed_svg: str):
        """Compare map generation between original and fixed SVG files."""
        print(f"\n🔍 Comparing SVG files:")
        print(f"   Original: {original_svg}")
        print(f"   Fixed: {fixed_svg}")
        
        # Test with empty map
        test_units = {'FRANCE': ['A PAR', 'F BRE'], 'GERMANY': ['A BER', 'F KIE']}
        
        # Test original SVG
        print(f"\n📋 Testing original SVG...")
        if os.path.exists(original_svg):
            success_orig, path_orig = self.test_scenario(
                "original_svg_test",
                original_svg,
                test_units,
                "Test with original SVG file"
            )
        else:
            print(f"   ⚠️  Original SVG not found: {original_svg}")
            success_orig, path_orig = False, None
        
        # Test fixed SVG
        print(f"\n📋 Testing fixed SVG...")
        if os.path.exists(fixed_svg):
            success_fixed, path_fixed = self.test_scenario(
                "fixed_svg_test",
                fixed_svg,
                test_units,
                "Test with fixed SVG file"
            )
        else:
            print(f"   ⚠️  Fixed SVG not found: {fixed_svg}")
            success_fixed, path_fixed = False, None
        
        # Comparison results
        print(f"\n🔍 Comparison Results:")
        if success_orig and success_fixed:
            print(f"   ✅ Both SVG files generated maps successfully")
            print(f"   📊 You can now compare the visual results:")
            print(f"      Original: {path_orig}")
            print(f"      Fixed: {path_fixed}")
        elif success_fixed and not success_orig:
            print(f"   ✅ Fixed SVG works, original SVG failed")
            print(f"   🎯 This confirms the fix is working!")
        elif success_orig and not success_fixed:
            print(f"   ❌ Original SVG works, but fixed SVG failed")
            print(f"   🔧 The fix may have introduced issues")
        else:
            print(f"   ❌ Both SVG files failed to generate maps")
            print(f"   🚨 There may be a deeper issue")

def main():
    parser = argparse.ArgumentParser(description="Test Diplomacy map generation")
    parser.add_argument("--svg", default="maps/standard_fixed.svg", 
                       help="SVG file to test (default: maps/standard_fixed.svg)")
    parser.add_argument("--output", default="test_maps", 
                       help="Output directory for generated maps (default: test_maps)")
    parser.add_argument("--compare", action="store_true", 
                       help="Compare original vs fixed SVG files")
    parser.add_argument("--scenario", 
                       choices=["empty", "starting", "midgame", "crowded", "fleets", "armies"],
                       help="Run only a specific scenario")
    
    args = parser.parse_args()
    
    # Initialize tester
    tester = MapTester(args.output)
    
    # Check if SVG file exists
    if not os.path.exists(args.svg):
        print(f"❌ SVG file not found: {args.svg}")
        print(f"Available SVG files in maps/:")
        maps_dir = "maps"
        if os.path.exists(maps_dir):
            svg_files = [f for f in os.listdir(maps_dir) if f.endswith('.svg')]
            for svg_file in svg_files:
                print(f"   - {os.path.join(maps_dir, svg_file)}")
        sys.exit(1)
    
    print(f"🗺️  Diplomacy Map Generation Tester")
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if args.compare:
        # Compare mode
        original_svg = "maps/standard.svg"
        fixed_svg = args.svg
        tester.compare_svg_files(original_svg, fixed_svg)
    elif args.scenario:
        # Single scenario mode
        scenarios = {
            "empty": ("empty_map", {}, "Clean board with no units"),
            "starting": ("starting_positions", {
                'ENGLAND': ['F LON', 'F EDI', 'A LVP'],
                'FRANCE': ['A PAR', 'A MAR', 'F BRE'],
                'GERMANY': ['A BER', 'A MUN', 'F KIE'],
                'ITALY': ['A ROM', 'A VEN', 'F NAP'],
                'AUSTRIA': ['A VIE', 'A BUD', 'F TRI'],
                'RUSSIA': ['A MOS', 'A WAR', 'F SEV', 'F STP'],
                'TURKEY': ['A CON', 'A SMY', 'F ANK']
            }, "Standard 1901 starting positions"),
            "midgame": ("midgame", {
                'ENGLAND': ['F NTH', 'F ENG', 'A YOR'],
                'FRANCE': ['A PAR', 'A BUR', 'F MAO'],
                'GERMANY': ['A BER', 'A MUN', 'A RUH'],
                'RUSSIA': ['A MOS', 'A WAR', 'F SEV']
            }, "Mid-game scenario"),
            "crowded": ("crowded", {
                'ENGLAND': ['F LON', 'F EDI', 'A LVP', 'F NTH', 'A YOR'],
                'FRANCE': ['A PAR', 'A MAR', 'F BRE', 'A BUR', 'A GAS'],
                'GERMANY': ['A BER', 'A MUN', 'F KIE', 'A RUH', 'A SIL']
            }, "Crowded board"),
            "fleets": ("fleets_only", {
                'ENGLAND': ['F LON', 'F EDI', 'F NTH'],
                'FRANCE': ['F BRE', 'F MAO', 'F WES'],
                'ITALY': ['F NAP', 'F TYS', 'F ION']
            }, "Naval scenario - fleets only"),
            "armies": ("armies_only", {
                'FRANCE': ['A PAR', 'A MAR', 'A BUR'],
                'GERMANY': ['A BER', 'A MUN', 'A RUH'],
                'RUSSIA': ['A MOS', 'A WAR', 'A STP']
            }, "Land scenario - armies only")
        }
        
        name, units, description = scenarios[args.scenario]
        tester.test_scenario(name, args.svg, units, description)
    else:
        # Full test suite
        tester.run_all_tests(args.svg)
    
    print(f"\n🏁 Testing completed!")
    print(f"📁 Check the '{args.output}' directory for generated maps")

if __name__ == "__main__":
    main() 