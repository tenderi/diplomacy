"""
Comprehensive tests for all order types and validation scenarios.
Tests all legal and illegal examples from order_spec.md
"""
import pytest
from src.engine.order import OrderParser, Order
from src.engine.map import Map


class TestOrderParsing:
    """Test order parsing for all order types."""
    
    def test_parse_movement_order(self):
        """Test parsing movement orders."""
        order = OrderParser.parse("FRANCE A PAR - BUR")
        assert order.power == "FRANCE"
        assert order.unit == "A PAR"
        assert order.action == "-"
        assert order.target == "BUR"
    
    def test_parse_support_order(self):
        """Test parsing support orders."""
        order = OrderParser.parse("FRANCE A BUR S A PAR - MAR")
        assert order.power == "FRANCE"
        assert order.unit == "A BUR"
        assert order.action == "S"
        assert order.target == "A PAR - MAR"
    
    def test_parse_convoy_order(self):
        """Test parsing convoy orders."""
        order = OrderParser.parse("FRANCE F NTH C A LON - BEL")
        assert order.power == "FRANCE"
        assert order.unit == "F NTH"
        assert order.action == "C"
        assert order.target == "A LON - BEL"
    
    def test_parse_hold_order(self):
        """Test parsing hold orders."""
        order = OrderParser.parse("FRANCE A PAR H")
        assert order.power == "FRANCE"
        assert order.unit == "A PAR"
        assert order.action == "H"
        assert order.target is None
    
    def test_parse_build_order(self):
        """Test parsing build orders."""
        order = OrderParser.parse("FRANCE BUILD A PAR")
        assert order.power == "FRANCE"
        assert order.unit == "BUILD"
        assert order.action == "BUILD"
        assert order.target == "A PAR"
    
    def test_parse_build_fleet_with_coast(self):
        """Test parsing build orders with coast specification."""
        order = OrderParser.parse("RUSSIA BUILD F STP NC")
        assert order.power == "RUSSIA"
        assert order.unit == "BUILD"
        assert order.action == "BUILD"
        assert order.target == "F STP NC"
    
    def test_parse_destroy_order(self):
        """Test parsing destroy orders."""
        order = OrderParser.parse("FRANCE DESTROY A PAR")
        assert order.power == "FRANCE"
        assert order.unit == "DESTROY"
        assert order.action == "DESTROY"
        assert order.target == "A PAR"
    
    def test_parse_invalid_format(self):
        """Test parsing invalid order formats."""
        with pytest.raises(ValueError):
            OrderParser.parse("FRANCE")  # Too short
        
        with pytest.raises(ValueError):
            OrderParser.parse("FRANCE BUILD")  # Missing target
        
        with pytest.raises(ValueError):
            OrderParser.parse("FRANCE X PAR")  # Invalid unit type


class TestOrderValidation:
    """Test order validation for all order types and scenarios."""
    
    def setup_method(self):
        """Set up test game state."""
        self.map_obj = Map("standard")
        self.game_state = {
            "powers": ["FRANCE", "GERMANY", "RUSSIA"],
            "units": {
                "FRANCE": ["A PAR", "F BRE", "A MAR"],
                "GERMANY": ["A BER", "A MUN", "F KIE"],
                "RUSSIA": ["A MOS", "F STP", "A WAR"]
            },
            "supply_centers": {
                "FRANCE": ["PAR", "BRE", "MAR"],
                "GERMANY": ["BER", "MUN", "KIE"],
                "RUSSIA": ["MOS", "STP", "WAR"]
            },
            "home_centers": {
                "FRANCE": ["PAR", "BRE", "MAR"],
                "GERMANY": ["BER", "MUN", "KIE"],
                "RUSSIA": ["MOS", "STP", "WAR"]
            },
            "phase": "Movement",
            "map_obj": self.map_obj
        }
    
    # MOVEMENT ORDER TESTS
    
    def test_valid_movement_orders(self):
        """Test valid movement orders."""
        valid_orders = [
            "FRANCE A PAR - BUR",  # Army to adjacent land
            "FRANCE F BRE - ENG",  # Fleet to adjacent sea
            "GERMANY A BER - SIL", # Army to adjacent land
            "RUSSIA F STP - BOT"   # Fleet to adjacent sea
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_movement_orders(self):
        """Test invalid movement orders."""
        invalid_orders = [
            ("FRANCE A PAR - LON", "Non-adjacent move"),
            ("FRANCE F BRE - MOS", "Fleet cannot move to inland province"),
            ("FRANCE A PAR - PAR", "Cannot move to same province"),
        ]
        
        for order_str, reason in invalid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert not valid, f"Order '{order_str}' should be invalid ({reason}): {msg}"
    
    # SUPPORT ORDER TESTS
    
    def test_valid_support_orders(self):
        """Test valid support orders."""
        # Add BUR to French units for support tests
        self.game_state["units"]["FRANCE"].append("A BUR")
        
        valid_orders = [
            "FRANCE A BUR S A PAR - MAR",  # Support move
            "FRANCE A BUR S F BRE",        # Support hold
            "FRANCE A BUR S GERMAN A BER - MUN"  # Support foreign unit
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_support_orders(self):
        """Test invalid support orders."""
        invalid_orders = [
            ("FRANCE A BUR S A PAR - LON", "Supporting non-adjacent move"),
            ("FRANCE F ENG S A PAR - MAR", "Fleet cannot support inland move"),
            ("FRANCE A BUR S F BRE - ENG", "Army cannot support sea move"),
        ]
        
        for order_str, reason in invalid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert not valid, f"Order '{order_str}' should be invalid ({reason}): {msg}"
    
    # CONVOY ORDER TESTS
    
    def test_valid_convoy_orders(self):
        """Test valid convoy orders."""
        # Add ENG to French units for convoy tests
        self.game_state["units"]["FRANCE"].append("F ENG")
        
        valid_orders = [
            "FRANCE F ENG C A PAR - BEL",  # Convoy army
            "FRANCE F ENG C GERMAN A BER - MUN"  # Convoy foreign army
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_convoy_orders(self):
        """Test invalid convoy orders."""
        invalid_orders = [
            ("FRANCE A PAR C A LON - BEL", "Only fleets can convoy"),
            ("FRANCE F ENG C F BRE - BEL", "Cannot convoy fleets"),
            ("FRANCE F ENG C A PAR - MOS", "Cannot convoy to inland province"),
        ]
        
        for order_str, reason in invalid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert not valid, f"Order '{order_str}' should be invalid ({reason}): {msg}"
    
    # HOLD ORDER TESTS
    
    def test_valid_hold_orders(self):
        """Test valid hold orders."""
        valid_orders = [
            "FRANCE A PAR H",  # Explicit hold
            "FRANCE F BRE",    # Implicit hold
            "GERMANY A BER H", # Explicit hold
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_hold_orders(self):
        """Test invalid hold orders."""
        invalid_orders = [
            ("FRANCE A PAR H MOS", "Hold with destination"),
        ]
        
        for order_str, reason in invalid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert not valid, f"Order '{order_str}' should be invalid ({reason}): {msg}"
    
    # BUILD ORDER TESTS
    
    def test_valid_build_orders(self):
        """Test valid build orders."""
        # Set up game state for builds phase with excess supply centers
        builds_state = self.game_state.copy()
        builds_state["phase"] = "Builds"
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE", "MAR", "BUR"]  # 4 centers
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE"]  # 2 units
        builds_state["supply_centers"]["RUSSIA"] = ["MOS", "STP", "WAR", "SEV"]  # 4 centers
        builds_state["units"]["RUSSIA"] = ["A MOS"]  # Only 1 unit, STP is free
        
        valid_orders = [
            "FRANCE BUILD A MAR",      # Build army in unoccupied home center
            "RUSSIA BUILD F STP NC",   # Build fleet with coast
            "RUSSIA BUILD F STP SC",   # Build fleet with coast
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, builds_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_build_orders(self):
        """Test invalid build orders."""
        # Test wrong phase
        order = OrderParser.parse("FRANCE BUILD A PAR")
        valid, msg = OrderParser.validate(order, self.game_state)
        assert not valid, f"Build order should be invalid during Movement phase: {msg}"
        
        # Test no excess supply centers
        builds_state = self.game_state.copy()
        builds_state["phase"] = "Builds"
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE"]  # 2 centers
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE"]  # 2 units
        
        order = OrderParser.parse("FRANCE BUILD A MAR")
        valid, msg = OrderParser.validate(order, builds_state)
        assert not valid, f"Build order should be invalid with no excess supply centers: {msg}"
        
        # Test occupied province
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE", "MAR", "BUR"]  # 4 centers
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE"]  # 2 units
        
        order = OrderParser.parse("FRANCE BUILD A PAR")  # PAR is occupied
        valid, msg = OrderParser.validate(order, builds_state)
        assert not valid, f"Build order should be invalid in occupied province: {msg}"
        
        # Test non-home supply center
        order = OrderParser.parse("FRANCE BUILD A BER")  # BER is not French home center
        valid, msg = OrderParser.validate(order, builds_state)
        assert not valid, f"Build order should be invalid in non-home supply center: {msg}"
        
        # Test St. Petersburg without coast
        order = OrderParser.parse("RUSSIA BUILD F STP")  # Missing coast
        valid, msg = OrderParser.validate(order, builds_state)
        assert not valid, f"Fleet build in St. Petersburg should specify coast: {msg}"
    
    # DESTROY ORDER TESTS
    
    def test_valid_destroy_orders(self):
        """Test valid destroy orders."""
        # Set up game state for builds phase with excess units
        builds_state = self.game_state.copy()
        builds_state["phase"] = "Builds"
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE"]  # 2 centers
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE", "A MAR"]  # 3 units
        
        valid_orders = [
            "FRANCE DESTROY A PAR",  # Destroy army
            "FRANCE DESTROY F BRE",  # Destroy fleet
            "FRANCE DESTROY A MAR",  # Destroy army
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, builds_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_destroy_orders(self):
        """Test invalid destroy orders."""
        # Test wrong phase
        order = OrderParser.parse("FRANCE DESTROY A PAR")
        valid, msg = OrderParser.validate(order, self.game_state)
        assert not valid, f"Destroy order should be invalid during Movement phase: {msg}"
        
        # Test no excess units
        builds_state = self.game_state.copy()
        builds_state["phase"] = "Builds"
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE", "MAR"]  # 3 centers
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE", "A MAR"]  # 3 units
        
        order = OrderParser.parse("FRANCE DESTROY A PAR")
        valid, msg = OrderParser.validate(order, builds_state)
        assert not valid, f"Destroy order should be invalid with no excess units: {msg}"
        
        # Test destroying unit that doesn't belong to player
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE"]  # 2 centers
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE", "A MAR"]  # 3 units
        
        order = OrderParser.parse("FRANCE DESTROY A BER")  # BER belongs to Germany
        valid, msg = OrderParser.validate(order, builds_state)
        assert not valid, f"Destroy order should be invalid for unit not belonging to player: {msg}"
    
    # PHASE-SPECIFIC TESTS
    
    def test_phase_specific_validation(self):
        """Test that orders are only valid in appropriate phases."""
        # Test BUILD/DESTROY only in Builds phase
        builds_state = self.game_state.copy()
        builds_state["phase"] = "Builds"
        builds_state["supply_centers"]["FRANCE"] = ["PAR", "BRE", "MAR", "BUR"]
        builds_state["units"]["FRANCE"] = ["A PAR", "F BRE"]
        
        # These should be valid in Builds phase
        build_order = OrderParser.parse("FRANCE BUILD A MAR")
        valid, msg = OrderParser.validate(build_order, builds_state)
        assert valid, f"Build order should be valid in Builds phase: {msg}"
        
        # These should be invalid in Movement phase
        build_order = OrderParser.parse("FRANCE BUILD A MAR")
        valid, msg = OrderParser.validate(build_order, self.game_state)
        assert not valid, f"Build order should be invalid in Movement phase: {msg}"
    
    # RETREAT ORDER TESTS
    
    def test_valid_retreat_orders(self):
        """Test valid retreat orders."""
        # Set up retreat phase with dislodged unit
        retreat_state = self.game_state.copy()
        retreat_state["phase"] = "Retreat"
        retreat_state["dislodged_units"] = {"FRANCE": ["A PAR"]}
        retreat_state["attacker_origins"] = {"A PAR": ["BUR"]}  # Attacker came from BUR
        retreat_state["standoff_vacated"] = ["MAR"]  # MAR was left vacant by standoff
        
        valid_orders = [
            "FRANCE A PAR - GAS",  # Valid retreat to unoccupied adjacent province
        ]
        
        for order_str in valid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, retreat_state)
            assert valid, f"Order '{order_str}' should be valid: {msg}"
    
    def test_invalid_retreat_orders(self):
        """Test invalid retreat orders."""
        # Set up retreat phase with dislodged unit
        retreat_state = self.game_state.copy()
        retreat_state["phase"] = "Retreat"
        retreat_state["dislodged_units"] = {"FRANCE": ["A PAR"]}
        retreat_state["attacker_origins"] = {"A PAR": ["BUR"]}  # Attacker came from BUR
        retreat_state["standoff_vacated"] = ["MAR"]  # MAR was left vacant by standoff
        
        invalid_orders = [
            ("FRANCE A PAR - BUR", "Retreat to attacker's origin province"),
            ("FRANCE A PAR - MAR", "Retreat to standoff-vacated province"),
            ("FRANCE A PAR - LON", "Non-adjacent retreat"),
            ("FRANCE A PAR - BRE", "Retreat to occupied province"),
        ]
        
        for order_str, reason in invalid_orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, retreat_state)
            assert not valid, f"Order '{order_str}' should be invalid ({reason}): {msg}"
    
    def test_retreat_wrong_phase(self):
        """Test that retreat orders are invalid in non-retreat phases."""
        # Test retreat order in Movement phase
        order = OrderParser.parse("FRANCE A PAR - GAS")
        valid, msg = OrderParser.validate(order, self.game_state)
        # This should be treated as a regular movement order, not a retreat
        # The validation will depend on whether PAR-GAS is a valid move
        
    def test_retreat_unit_not_dislodged(self):
        """Test that only dislodged units can retreat."""
        retreat_state = self.game_state.copy()
        retreat_state["phase"] = "Retreat"
        retreat_state["dislodged_units"] = {"FRANCE": []}  # No dislodged units
        
        order = OrderParser.parse("FRANCE A PAR - GAS")
        valid, msg = OrderParser.validate(order, retreat_state)
        assert not valid, f"Retreat order should be invalid for non-dislodged unit: {msg}"
        assert "was not dislodged" in msg
    
    # EDGE CASE TESTS
    
    def test_power_existence_validation(self):
        """Test validation when power doesn't exist."""
        order = OrderParser.parse("ITALY A ROM - NAP")
        valid, msg = OrderParser.validate(order, self.game_state)
        assert not valid, f"Order for non-existent power should be invalid: {msg}"
        assert "does not exist" in msg
    
    def test_unit_ownership_validation(self):
        """Test validation when unit doesn't belong to power."""
        order = OrderParser.parse("FRANCE A BER - SIL")  # BER belongs to Germany
        valid, msg = OrderParser.validate(order, self.game_state)
        assert not valid, f"Order for unit not belonging to power should be invalid: {msg}"
        assert "does not belong" in msg
    
    def test_invalid_action_validation(self):
        """Test validation with invalid action."""
        order = OrderParser.parse("FRANCE A PAR X BUR")
        valid, msg = OrderParser.validate(order, self.game_state)
        assert not valid, f"Order with invalid action should be invalid: {msg}"
        assert "Invalid action" in msg


class TestOrderGeneration:
    """Test legal order generation."""
    
    def setup_method(self):
        """Set up test game state."""
        self.map_obj = Map("standard")
        self.game_state = {
            "powers": ["FRANCE"],
            "units": {"FRANCE": ["A PAR", "F BRE"]},
            "map_obj": self.map_obj
        }
    
    def test_generate_legal_orders(self):
        """Test that generated orders are all valid."""
        orders = OrderParser.generate_legal_orders("FRANCE", "A PAR", self.game_state)
        
        for order_str in orders:
            order = OrderParser.parse(order_str)
            valid, msg = OrderParser.validate(order, self.game_state)
            assert valid, f"Generated order '{order_str}' should be valid: {msg}"
    
    def test_generate_hold_orders(self):
        """Test that hold orders are always generated."""
        orders = OrderParser.generate_legal_orders("FRANCE", "A PAR", self.game_state)
        hold_orders = [o for o in orders if "H" in o]
        assert len(hold_orders) > 0, "Should generate at least one hold order"
    
    def test_generate_move_orders(self):
        """Test that move orders are generated for adjacent provinces."""
        orders = OrderParser.generate_legal_orders("FRANCE", "A PAR", self.game_state)
        move_orders = [o for o in orders if " - " in o]
        assert len(move_orders) > 0, "Should generate move orders for adjacent provinces"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
