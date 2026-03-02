"""
Comprehensive tests for Power class.

Tests all methods and edge cases for the Power class.
"""
import pytest
from engine.power import Power
from engine.data_models import Unit, PowerState


@pytest.mark.unit
class TestPowerInitialization:
    """Test Power class initialization."""
    
    def test_power_init_with_home_centers(self):
        """Test Power initialization with home centers."""
        power = Power("FRANCE", ["PAR", "MAR", "BRE"])
        assert power.name == "FRANCE"
        assert "PAR" in power.home_centers
        assert "MAR" in power.home_centers
        assert "BRE" in power.home_centers
        assert len(power.home_centers) == 3
        assert power.controlled_centers == power.home_centers
        assert power.is_alive is True
        assert len(power.units) == 0
    
    def test_power_init_without_home_centers(self):
        """Test Power initialization without home centers."""
        power = Power("FRANCE")
        assert power.name == "FRANCE"
        assert len(power.home_centers) == 0
        assert len(power.controlled_centers) == 0
        assert power.is_alive is True
        assert len(power.units) == 0
    
    def test_power_init_with_empty_list(self):
        """Test Power initialization with empty list."""
        power = Power("FRANCE", [])
        assert power.name == "FRANCE"
        assert len(power.home_centers) == 0
        assert len(power.controlled_centers) == 0


@pytest.mark.unit
class TestPowerUnitManagement:
    """Test unit management methods."""
    
    def test_add_unit(self):
        """Test adding a unit to a power."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        
        assert len(power.units) == 1
        assert power.units[0].province == "PAR"
        assert power.units[0].unit_type == "A"
        assert power.units[0].power == "FRANCE"
    
    def test_add_multiple_units(self):
        """Test adding multiple units."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        power.add_unit("BRE", "F")
        
        assert len(power.units) == 3
        assert any(u.province == "PAR" for u in power.units)
        assert any(u.province == "MAR" for u in power.units)
        assert any(u.province == "BRE" for u in power.units)
        assert any(u.unit_type == "F" for u in power.units)
    
    def test_add_fleet_unit(self):
        """Test adding a fleet unit."""
        power = Power("FRANCE")
        power.add_unit("BRE", "F")
        
        assert len(power.units) == 1
        assert power.units[0].unit_type == "F"
    
    def test_remove_unit(self):
        """Test removing a unit from a power."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        
        power.remove_unit("PAR")
        
        assert len(power.units) == 1
        assert power.units[0].province == "MAR"
        assert not any(u.province == "PAR" for u in power.units)
    
    def test_remove_nonexistent_unit(self):
        """Test removing a unit that doesn't exist."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        
        # Should not raise error
        power.remove_unit("MAR")
        
        assert len(power.units) == 1
        assert power.units[0].province == "PAR"
    
    def test_get_unit_at_province(self):
        """Test getting unit at specific province."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        
        unit = power.get_unit_at_province("PAR")
        assert unit is not None
        assert unit.province == "PAR"
        assert unit.unit_type == "A"
        
        unit = power.get_unit_at_province("MAR")
        assert unit is not None
        assert unit.province == "MAR"
    
    def test_get_unit_at_nonexistent_province(self):
        """Test getting unit at province that doesn't have a unit."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        
        unit = power.get_unit_at_province("MAR")
        assert unit is None
    
    def test_get_unit_count(self):
        """Test getting unit count."""
        power = Power("FRANCE")
        assert power.get_unit_count() == 0
        
        power.add_unit("PAR", "A")
        assert power.get_unit_count() == 1
        
        power.add_unit("MAR", "A")
        assert power.get_unit_count() == 2
        
        power.remove_unit("PAR")
        assert power.get_unit_count() == 1


@pytest.mark.unit
class TestPowerSupplyCenters:
    """Test supply center management."""
    
    def test_gain_center(self):
        """Test gaining a supply center."""
        power = Power("FRANCE", ["PAR"])
        assert len(power.controlled_centers) == 1
        
        power.gain_center("MAR")
        assert "MAR" in power.controlled_centers
        assert len(power.controlled_centers) == 2
        assert power.is_alive is True
    
    def test_gain_existing_center(self):
        """Test gaining a center that's already controlled."""
        power = Power("FRANCE", ["PAR"])
        assert len(power.controlled_centers) == 1
        
        power.gain_center("PAR")  # Already controlled
        assert len(power.controlled_centers) == 1  # Should not duplicate
        assert "PAR" in power.controlled_centers
    
    def test_lose_center(self):
        """Test losing a supply center."""
        power = Power("FRANCE", ["PAR", "MAR"])
        assert len(power.controlled_centers) == 2
        
        power.lose_center("MAR")
        assert "MAR" not in power.controlled_centers
        assert len(power.controlled_centers) == 1
        assert power.is_alive is True  # Still has PAR
    
    def test_lose_all_centers(self):
        """Test losing all supply centers (power eliminated)."""
        power = Power("FRANCE", ["PAR"])
        assert power.is_alive is True
        
        power.lose_center("PAR")
        assert len(power.controlled_centers) == 0
        assert power.is_alive is False
    
    def test_lose_nonexistent_center(self):
        """Test losing a center that's not controlled."""
        power = Power("FRANCE", ["PAR"])
        assert len(power.controlled_centers) == 1
        
        power.lose_center("MAR")  # Not controlled
        assert len(power.controlled_centers) == 1  # Should not change
        assert power.is_alive is True
    
    def test_gain_center_after_elimination(self):
        """Test that gaining a center revives eliminated power."""
        power = Power("FRANCE", ["PAR"])
        power.lose_center("PAR")
        assert power.is_alive is False
        
        power.gain_center("MAR")
        assert power.is_alive is True
        assert "MAR" in power.controlled_centers
    
    def test_get_supply_center_count(self):
        """Test getting supply center count."""
        power = Power("FRANCE", ["PAR", "MAR"])
        assert power.get_supply_center_count() == 2
        
        power.gain_center("BRE")
        assert power.get_supply_center_count() == 3
        
        power.lose_center("MAR")
        assert power.get_supply_center_count() == 2


@pytest.mark.unit
class TestPowerBuildDestroyLogic:
    """Test build/destroy logic methods."""
    
    def test_needs_builds(self):
        """Test needs_builds method."""
        power = Power("FRANCE", ["PAR", "MAR", "BRE"])
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        # 3 centers, 2 units - needs build
        assert power.needs_builds() is True
        
        power.add_unit("BRE", "A")
        # 3 centers, 3 units - no build needed
        assert power.needs_builds() is False
    
    def test_needs_builds_no_units(self):
        """Test needs_builds with no units."""
        power = Power("FRANCE", ["PAR", "MAR"])
        # 2 centers, 0 units - needs builds
        assert power.needs_builds() is True
    
    def test_needs_builds_more_units_than_centers(self):
        """Test needs_builds when units exceed centers."""
        power = Power("FRANCE", ["PAR"])
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")  # Unit in non-center province
        # 1 center, 2 units - no build needed (but needs destroy)
        assert power.needs_builds() is False
    
    def test_needs_destroys(self):
        """Test needs_destroys method."""
        power = Power("FRANCE", ["PAR"])
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        # 1 center, 2 units - needs destroy
        assert power.needs_destroys() is True
        
        power.remove_unit("MAR")
        # 1 center, 1 unit - no destroy needed
        assert power.needs_destroys() is False
    
    def test_needs_destroys_no_centers(self):
        """Test needs_destroys with no centers."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        # 0 centers, 1 unit - needs destroy
        assert power.needs_destroys() is True
    
    def test_needs_destroys_equal_counts(self):
        """Test needs_destroys when counts are equal."""
        power = Power("FRANCE", ["PAR", "MAR"])
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        # 2 centers, 2 units - no destroy needed
        assert power.needs_destroys() is False


@pytest.mark.unit
class TestPowerStateConversion:
    """Test conversion to PowerState data model."""
    
    def test_to_power_state(self):
        """Test converting Power to PowerState."""
        power = Power("FRANCE", ["PAR", "MAR"])
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        power.gain_center("BRE")
        
        power_state = power.to_power_state()
        
        assert isinstance(power_state, PowerState)
        assert power_state.power_name == "FRANCE"
        assert set(power_state.home_supply_centers) == {"PAR", "MAR"}
        assert set(power_state.controlled_supply_centers) == {"PAR", "MAR", "BRE"}
        assert len(power_state.units) == 2
        assert power_state.is_eliminated is False
    
    def test_to_power_state_eliminated(self):
        """Test converting eliminated Power to PowerState."""
        power = Power("FRANCE", ["PAR"])
        power.lose_center("PAR")
        
        power_state = power.to_power_state()
        
        assert power_state.is_eliminated is True
        assert len(power_state.controlled_supply_centers) == 0
    
    def test_to_power_state_no_units(self):
        """Test converting Power with no units to PowerState."""
        power = Power("FRANCE", ["PAR", "MAR"])
        
        power_state = power.to_power_state()
        
        assert len(power_state.units) == 0
        assert power_state.is_eliminated is False


@pytest.mark.unit
class TestPowerEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_multiple_units_same_province(self):
        """Test handling multiple units in same province (should be prevented by game logic)."""
        power = Power("FRANCE")
        power.add_unit("PAR", "A")
        power.add_unit("PAR", "A")  # Duplicate province
        
        # Power class allows this, but game logic should prevent it
        assert len(power.units) == 2
        assert all(u.province == "PAR" for u in power.units)
    
    def test_remove_all_units(self):
        """Test removing all units."""
        power = Power("FRANCE", ["PAR", "MAR"])
        power.add_unit("PAR", "A")
        power.add_unit("MAR", "A")
        
        power.remove_unit("PAR")
        power.remove_unit("MAR")
        
        assert len(power.units) == 0
        assert power.get_unit_count() == 0
        # Power still alive if it has centers
        assert power.is_alive is True
    
    def test_gain_lose_multiple_centers(self):
        """Test gaining and losing multiple centers."""
        power = Power("FRANCE", ["PAR"])
        
        power.gain_center("MAR")
        power.gain_center("BRE")
        assert len(power.controlled_centers) == 3
        
        power.lose_center("MAR")
        power.lose_center("BRE")
        assert len(power.controlled_centers) == 1
        assert power.is_alive is True
        
        power.lose_center("PAR")
        assert power.is_alive is False
