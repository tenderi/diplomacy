"""
Unit tests for order parser utilities.

Tests the order splitting functionality for parsing multiple orders in a single string.
"""
import pytest
from engine.order_parser_utils import split_orders


class TestSplitOrders:
    """Test split_orders function."""
    
    def test_empty_string(self):
        """Test splitting empty string."""
        assert split_orders("") == []
        assert split_orders("   ") == []
        assert split_orders("\n\t") == []
    
    def test_single_order(self):
        """Test splitting single order."""
        assert split_orders("A PAR - BUR") == ["A PAR - BUR"]
        assert split_orders("F BRE H") == ["F BRE H"]
        assert split_orders("A ROM - TUS") == ["A ROM - TUS"]
    
    def test_multiple_simple_orders(self):
        """Test splitting multiple simple orders."""
        result = split_orders("A PAR - BUR A VEN H")
        assert len(result) == 2
        assert "A PAR - BUR" in result
        assert "A VEN H" in result
    
    def test_support_orders(self):
        """Test splitting orders with support."""
        # Single support order should not be split
        assert split_orders("A ROM S A VEN H") == ["A ROM S A VEN H"]
        assert split_orders("F NAP S A ROM - TUS") == ["F NAP S A ROM - TUS"]
        
        # Multiple orders with support
        result = split_orders("A ROM S A VEN H A TUS - PIE")
        assert len(result) == 2
        assert "A ROM S A VEN H" in result
        assert "A TUS - PIE" in result
    
    def test_convoy_orders(self):
        """Test splitting orders with convoy."""
        # Single convoy order should not be split
        assert split_orders("F ION C A ROM - TUN") == ["F ION C A ROM - TUN"]
        
        # Multiple orders with convoy
        result = split_orders("F ION C A ROM - TUN A VEN H")
        assert len(result) == 2
        assert "F ION C A ROM - TUN" in result
        assert "A VEN H" in result
    
    def test_mixed_orders(self):
        """Test splitting mixed order types."""
        result = split_orders("A ROM - TUS F NAP - ROM A VEN S A ROM H")
        assert len(result) == 3
        assert "A ROM - TUS" in result
        assert "F NAP - ROM" in result
        assert "A VEN S A ROM H" in result
    
    def test_build_destroy_orders(self):
        """Test splitting build and destroy orders."""
        assert split_orders("BUILD A PAR") == ["BUILD A PAR"]
        assert split_orders("DESTROY A ROM") == ["DESTROY A ROM"]
        
        result = split_orders("BUILD A PAR DESTROY A ROM")
        assert len(result) == 2
        assert "BUILD A PAR" in result
        assert "DESTROY A ROM" in result
    
    def test_complex_support_orders(self):
        """Test splitting complex support order scenarios."""
        result = split_orders("A ROM S A VEN - TUS F NAP S A ROM H")
        assert len(result) == 2
        assert "A ROM S A VEN - TUS" in result
        assert "F NAP S A ROM H" in result
    
    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        result = split_orders("  A PAR - BUR  \n  A VEN H  ")
        assert len(result) == 2
        # Check that orders are trimmed
        assert result[0].strip() == "A PAR - BUR"
        assert result[1].strip() == "A VEN H"
    
    def test_incomplete_orders(self):
        """Test splitting incomplete orders."""
        # Incomplete order should still be returned
        result = split_orders("A ROM")
        assert len(result) == 1
        assert result[0] == "A ROM"
    
    def test_multiple_support_orders(self):
        """Test splitting multiple support orders."""
        result = split_orders("A ROM S A VEN H A TUS S A ROM - PIE")
        assert len(result) == 2
        assert "A ROM S A VEN H" in result
        assert "A TUS S A ROM - PIE" in result
    
    def test_fleet_and_army_orders(self):
        """Test splitting orders with both fleets and armies."""
        result = split_orders("A PAR - BUR F BRE - ENG")
        assert len(result) == 2
        assert "A PAR - BUR" in result
        assert "F BRE - ENG" in result
    
    def test_hold_orders(self):
        """Test splitting hold orders."""
        assert split_orders("A PAR H") == ["A PAR H"]
        result = split_orders("A PAR H A VEN H")
        assert len(result) == 2
        assert "A PAR H" in result
        assert "A VEN H" in result


@pytest.mark.unit
class TestSplitOrdersEdgeCases:
    """Test edge cases for order splitting."""
    
    def test_very_long_order_string(self):
        """Test splitting very long order strings."""
        long_orders = " ".join(["A PAR - BUR"] * 10)
        result = split_orders(long_orders)
        assert len(result) == 10
        assert all("A PAR - BUR" in order for order in result)
    
    def test_orders_with_special_characters(self):
        """Test splitting orders with special characters."""
        # Coast specifications
        result = split_orders("F SPA/NC - MAO F SPA/SC - WES")
        assert len(result) == 2
    
    def test_orders_with_numbers(self):
        """Test that orders with numbers are handled."""
        # Some provinces might have numbers in future variants
        result = split_orders("A PAR - BUR")
        assert len(result) == 1
    
    def test_nested_support_orders(self):
        """Test handling of complex nested support scenarios."""
        # This is a complex case that should not split incorrectly
        order_str = "A ROM S A VEN - TUS"
        result = split_orders(order_str)
        # Should remain as single order
        assert len(result) == 1
        assert "S A VEN" in result[0]


@pytest.mark.unit
class TestSplitOrdersIntegration:
    """Integration tests for order splitting."""
    
    def test_real_game_scenario(self):
        """Test splitting orders from a real game scenario."""
        # Typical orders a player might submit
        orders = "A PAR - BUR F BRE - ENG A MAR - GAS"
        result = split_orders(orders)
        assert len(result) == 3
        assert "A PAR - BUR" in result
        assert "F BRE - ENG" in result
        assert "A MAR - GAS" in result
    
    def test_italy_orders_scenario(self):
        """Test splitting Italy-specific orders."""
        orders = "A ROM - VEN F NAP S A ROM - VEN A VEN - TUS"
        result = split_orders(orders)
        assert len(result) == 3
        assert "A ROM - VEN" in result
        assert "F NAP S A ROM - VEN" in result
        assert "A VEN - TUS" in result
    
    def test_build_phase_orders(self):
        """Test splitting build phase orders."""
        orders = "BUILD A PAR BUILD F BRE"
        result = split_orders(orders)
        assert len(result) == 2
        assert "BUILD A PAR" in result
        assert "BUILD F BRE" in result
    
    def test_retreat_phase_orders(self):
        """Test splitting retreat phase orders."""
        orders = "A PAR R BUR F BRE R ENG"
        result = split_orders(orders)
        assert len(result) == 2
        assert "A PAR R BUR" in result
        assert "F BRE R ENG" in result

