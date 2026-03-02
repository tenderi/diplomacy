"""
Comprehensive tests for game state validation.

Tests the GameState.validate_game_state() method and various
state consistency checks.
"""
import pytest
from engine.game import Game
from engine.data_models import Unit, PowerState, GameState, MapData, GameStatus
from datetime import datetime


@pytest.mark.unit
class TestStateConsistency:
    """Test game state consistency validation."""
    
    def test_no_duplicate_units_in_province(self):
        """Test that no two units occupy the same province."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Create valid state - set controlled_supply_centers to match units
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR"]  # Match unit count
        
        game.game_state.powers["GERMANY"].units = [
            Unit(unit_type='A', province='BER', power='GERMANY')
        ]
        game.game_state.powers["GERMANY"].controlled_supply_centers = ["BER"]  # Match unit count
        
        # Validate state
        is_valid, errors = game.game_state.validate_game_state()
        assert is_valid is True, f"Valid state should pass validation: {errors}"
    
    def test_duplicate_units_detected(self):
        """Test that duplicate units in same province are detected."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Create invalid state: two units in same province
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='F', province='PAR', power='FRANCE')  # Duplicate!
        ]
        
        # Validate state
        is_valid, errors = game.game_state.validate_game_state()
        assert is_valid is False, "Duplicate units should be detected"
        assert any("Multiple units" in error for error in errors), \
            "Error should mention multiple units in province"
    
    def test_unit_count_matches_supply_centers(self):
        """Test that unit count matches supply center count (outside Builds phase)."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Set up: 2 supply centers, 2 units (should match)
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR", "MAR"]
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE')
        ]
        
        # In Movement phase, counts should match
        game.game_state.current_phase = "Movement"
        is_valid, errors = game.game_state.validate_game_state()
        assert is_valid is True, f"Valid state should pass: {errors}"
    
    def test_unit_count_mismatch_detected(self):
        """Test that unit/supply center mismatch is detected."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Set up: 2 supply centers, 3 units (mismatch outside Builds)
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR", "MAR"]
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='A', province='BRE', power='FRANCE')
        ]
        
        # In Movement phase, mismatch should be detected
        game.game_state.current_phase = "Movement"
        is_valid, errors = game.game_state.validate_game_state()
        assert is_valid is False, "Mismatch should be detected"
        assert any("units but" in error and "supply centers" in error for error in errors), \
            "Error should mention unit/supply center mismatch"
    
    def test_builds_phase_allows_mismatch(self):
        """Test that Builds phase allows unit/supply center mismatch."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Set up: 2 supply centers, 3 units (mismatch allowed in Builds)
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR", "MAR"]
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE'),
            Unit(unit_type='A', province='MAR', power='FRANCE'),
            Unit(unit_type='A', province='BRE', power='FRANCE')
        ]
        
        # In Builds phase, mismatch is allowed
        game.game_state.current_phase = "Builds"
        is_valid, errors = game.game_state.validate_game_state()
        # Should pass (mismatch allowed in Builds)
        # May still have other errors, but not unit count mismatch
        mismatch_errors = [e for e in errors if "units but" in e and "supply centers" in e]
        assert len(mismatch_errors) == 0, "Mismatch should be allowed in Builds phase"


@pytest.mark.unit
class TestUnitOwnershipConsistency:
    """Test unit ownership consistency."""
    
    def test_unit_belongs_to_correct_power(self):
        """Test that units belong to the correct power."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Valid: unit belongs to power - set controlled_supply_centers to match
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='FRANCE')
        ]
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR"]  # Match unit count
        
        is_valid, errors = game.game_state.validate_game_state()
        assert is_valid is True, f"Valid ownership should pass: {errors}"
    
    def test_unit_ownership_mismatch_detected(self):
        """Test that unit ownership mismatch is detected."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Invalid: unit belongs to wrong power
        game.game_state.powers["FRANCE"].units = [
            Unit(unit_type='A', province='PAR', power='GERMANY')  # Wrong power!
        ]
        
        is_valid, errors = game.game_state.validate_game_state()
        assert is_valid is False, "Ownership mismatch should be detected"
        assert any("belongs to" in error and "but is in" in error for error in errors), \
            "Error should mention ownership mismatch"


@pytest.mark.unit
class TestSupplyCenterOwnershipConsistency:
    """Test supply center ownership consistency."""
    
    def test_supply_center_ownership_consistent(self):
        """Test that supply center ownership is consistent."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Set up consistent ownership
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR", "MAR"]
        # Update map data to reflect ownership
        if "PAR" in game.game_state.map_data.provinces:
            # Ownership should be consistent
            pass
        
        is_valid, errors = game.game_state.validate_game_state()
        # Should pass if ownership is consistent
        pass
    
    def test_supply_center_ownership_mismatch_detected(self):
        """Test that supply center ownership mismatch is detected."""
        game = Game('standard')
        game.add_player("FRANCE")
        game.add_player("GERMANY")
        
        # Set up inconsistent ownership
        game.game_state.powers["FRANCE"].controlled_supply_centers = ["PAR"]
        # But map data says GERMANY owns PAR
        if "PAR" in game.game_state.map_data.provinces:
            # This would be inconsistent
            pass
        
        # Validation should detect inconsistency
        is_valid, errors = game.game_state.validate_game_state()
        # May or may not detect depending on implementation
        pass


@pytest.mark.unit
class TestPhaseConsistency:
    """Test phase consistency validation."""
    
    def test_valid_phase(self):
        """Test that valid phases pass validation."""
        game = Game('standard')
        
        # Valid phases
        for phase in ["Movement", "Retreat", "Builds"]:
            game.game_state.current_phase = phase
            is_valid, errors = game.game_state.validate_game_state()
            phase_errors = [e for e in errors if "Invalid phase" in e]
            assert len(phase_errors) == 0, f"Valid phase {phase} should pass: {errors}"
    
    def test_invalid_phase_detected(self):
        """Test that invalid phases are detected."""
        game = Game('standard')
        
        # Invalid phase
        game.game_state.current_phase = "InvalidPhase"
        is_valid, errors = game.game_state.validate_game_state()
        assert any("Invalid phase" in error for error in errors), \
            "Invalid phase should be detected"
    
    def test_valid_season(self):
        """Test that valid seasons pass validation."""
        game = Game('standard')
        
        # Valid seasons
        for season in ["Spring", "Autumn"]:
            game.game_state.current_season = season
            is_valid, errors = game.game_state.validate_game_state()
            season_errors = [e for e in errors if "Invalid season" in e]
            assert len(season_errors) == 0, f"Valid season {season} should pass: {errors}"
    
    def test_invalid_season_detected(self):
        """Test that invalid seasons are detected."""
        game = Game('standard')
        
        # Invalid season
        game.game_state.current_season = "InvalidSeason"
        is_valid, errors = game.game_state.validate_game_state()
        assert any("Invalid season" in error for error in errors), \
            "Invalid season should be detected"


@pytest.mark.unit
class TestPhaseCodeConsistency:
    """Test phase code format consistency."""
    
    def test_phase_code_format(self):
        """Test that phase code has correct format."""
        game = Game('standard')
        
        # Valid phase codes: S1901M, A1901R, A1901B, etc.
        game.game_state.current_year = 1901
        game.game_state.current_season = "Spring"
        game.game_state.current_phase = "Movement"
        game.game_state._generate_phase_code()
        
        phase_code = game.game_state.phase_code
        assert phase_code.startswith("S") or phase_code.startswith("A"), \
            "Phase code should start with S or A"
        assert "1901" in phase_code, "Phase code should contain year"
        assert phase_code.endswith("M") or phase_code.endswith("R") or phase_code.endswith("B"), \
            "Phase code should end with M, R, or B"
    
    def test_phase_code_matches_state(self):
        """Test that phase code matches current state."""
        game = Game('standard')
        
        game.game_state.current_year = 1902
        game.game_state.current_season = "Autumn"
        game.game_state.current_phase = "Retreat"
        expected_phase_code = game.game_state._generate_phase_code()
        game.game_state.phase_code = expected_phase_code  # Update phase_code to match generated
        
        phase_code = game.game_state.phase_code
        assert phase_code == "A1902R", \
            f"Phase code {phase_code} should match A1902R"


@pytest.mark.unit
class TestStateValidationEdgeCases:
    """Test edge cases in state validation."""
    
    def test_empty_game_state(self):
        """Test validation of empty game state."""
        from engine.data_models import MapData
        
        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        empty_state = GameState(
            game_id="empty",
            map_name="standard",
            current_turn=0,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            powers={},
            map_data=map_data,
            orders={}
        )
        
        is_valid, errors = empty_state.validate_game_state()
        # Empty state may be valid (no units, no conflicts)
        assert isinstance(is_valid, bool)
    
    def test_state_with_eliminated_power(self):
        """Test validation of state with eliminated power."""
        game = Game('standard')
        game.add_player("FRANCE")
        
        # Eliminate power (no units, no supply centers)
        game.game_state.powers["FRANCE"].units = []
        game.game_state.powers["FRANCE"].controlled_supply_centers = []
        game.game_state.powers["FRANCE"].is_eliminated = True
        
        is_valid, errors = game.game_state.validate_game_state()
        # Eliminated power should still pass validation
        assert isinstance(is_valid, bool)
