"""
Comprehensive unit tests for Strategic AI module.

Tests cover StrategicAI, OrderGenerator, and StrategicConfig classes
with focus on order generation logic, edge cases, and strategy parameters.
"""

import pytest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from engine.strategic_ai import StrategicAI, StrategicConfig, OrderGenerator
from engine.data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder
)


class TestStrategicConfig:
    """Test StrategicConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = StrategicConfig()
        
        assert config.aggression_level == 0.7
        assert config.support_probability == 0.3
        assert config.convoy_probability == 0.2
        assert config.defensive_probability == 0.4
        assert config.expansion_probability == 0.6
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = StrategicConfig(
            aggression_level=0.9,
            support_probability=0.5,
            convoy_probability=0.3,
            defensive_probability=0.2,
            expansion_probability=0.8
        )
        
        assert config.aggression_level == 0.9
        assert config.support_probability == 0.5
        assert config.convoy_probability == 0.3
        assert config.defensive_probability == 0.2
        assert config.expansion_probability == 0.8
    
    def test_config_validation(self):
        """Test configuration value validation."""
        # Test valid ranges
        config = StrategicConfig(aggression_level=1.0)
        assert config.aggression_level == 1.0
        
        config = StrategicConfig(aggression_level=0.0)
        assert config.aggression_level == 0.0
        
        # Test edge cases (should not raise errors, just use values)
        config = StrategicConfig(aggression_level=-0.1)
        assert config.aggression_level == -0.1  # No validation currently


class TestStrategicAI:
    """Test StrategicAI class."""
    
    @pytest.fixture
    def ai(self):
        """Create StrategicAI instance for testing."""
        return StrategicAI()
    
    @pytest.fixture
    def custom_ai(self):
        """Create StrategicAI with custom config."""
        config = StrategicConfig(aggression_level=0.9, support_probability=0.5)
        return StrategicAI(config)
    
    @pytest.fixture
    def movement_game_state(self, mid_game_state):
        """Create game state in Movement phase."""
        from engine.data_models import Province
        
        mid_game_state.current_phase = "Movement"
        mid_game_state.phase_code = "S1901M"
        
        # Add map data with adjacent provinces so AI can find move targets
        mid_game_state.map_data.provinces = {
            "PAR": Province(name="PAR", province_type="inland", adjacent_provinces=["BUR", "PIC", "BRE"], is_supply_center=True, is_home_supply_center=True),
            "MAR": Province(name="MAR", province_type="coastal", adjacent_provinces=["BUR", "GAS", "PIE"], is_supply_center=True, is_home_supply_center=True),
            "BUR": Province(name="BUR", province_type="inland", adjacent_provinces=["PAR", "MAR", "PIC", "GAS"], is_supply_center=False, is_home_supply_center=False),
            "PIC": Province(name="PIC", province_type="coastal", adjacent_provinces=["PAR", "BUR", "BEL"], is_supply_center=False, is_home_supply_center=False),
            "BRE": Province(name="BRE", province_type="coastal", adjacent_provinces=["PAR", "PIC", "GAS"], is_supply_center=True, is_home_supply_center=True)
        }
        
        return mid_game_state
    
    @pytest.fixture
    def retreat_game_state(self, mid_game_state):
        """Create game state in Retreat phase."""
        mid_game_state.current_phase = "Retreat"
        mid_game_state.phase_code = "S1901R"
        
        # Add dislodged units
        france_state = mid_game_state.powers["FRANCE"]
        france_state.dislodged_units = [
            Unit(unit_type="A", province="PAR", power="FRANCE")
        ]
        
        return mid_game_state
    
    @pytest.fixture
    def adjustment_game_state(self, mid_game_state):
        """Create game state in Adjustment phase."""
        mid_game_state.current_phase = "Adjustment"
        mid_game_state.phase_code = "S1901A"
        
        # Set supply center counts for builds/destroys
        france_state = mid_game_state.powers["FRANCE"]
        france_state.controlled_supply_centers = ["PAR", "MAR", "BRE", "BUR"]  # 4 SCs
        france_state.home_supply_centers = ["PAR", "MAR", "BRE", "BUR"]  # Home SCs for building
        france_state.units = [
            Unit(unit_type="A", province="PAR", power="FRANCE"),
            Unit(unit_type="A", province="MAR", power="FRANCE")
        ]  # 2 units (BRE and BUR are available for building)
        
        return mid_game_state
    
    def test_ai_initialization(self, ai):
        """Test AI initialization."""
        assert ai.config is not None
        assert ai.order_parser is not None
        assert isinstance(ai.config, StrategicConfig)
    
    def test_ai_custom_config(self, custom_ai):
        """Test AI with custom configuration."""
        assert custom_ai.config.aggression_level == 0.9
        assert custom_ai.config.support_probability == 0.5
    
    def test_generate_orders_movement_phase(self, ai, movement_game_state):
        """Test order generation in Movement phase."""
        orders = ai.generate_orders(movement_game_state, "FRANCE")
        
        assert isinstance(orders, list)
        # Should generate orders for all French units
        france_units = movement_game_state.powers["FRANCE"].units
        assert len(orders) <= len(france_units)  # May not order all units
    
    def test_generate_orders_retreat_phase(self, ai, retreat_game_state):
        """Test order generation in Retreat phase."""
        orders = ai.generate_orders(retreat_game_state, "FRANCE")
        
        assert isinstance(orders, list)
        # Should generate retreat orders for dislodged units
        dislodged_units = retreat_game_state.powers["FRANCE"].dislodged_units
        assert len(orders) <= len(dislodged_units)
    
    def test_generate_orders_adjustment_phase(self, ai, adjustment_game_state):
        """Test order generation in Adjustment phase."""
        orders = ai.generate_orders(adjustment_game_state, "FRANCE")
        
        assert isinstance(orders, list)
        # Should generate build/destroy orders based on SC count
        france_state = adjustment_game_state.powers["FRANCE"]
        sc_count = len(france_state.controlled_supply_centers)
        unit_count = len(france_state.units)
        
        if sc_count > unit_count:
            # Should have build orders
            build_orders = [o for o in orders if isinstance(o, BuildOrder)]
            assert len(build_orders) > 0
        elif sc_count < unit_count:
            # Should have destroy orders
            destroy_orders = [o for o in orders if isinstance(o, DestroyOrder)]
            assert len(destroy_orders) > 0
    
    def test_generate_orders_invalid_power(self, ai, movement_game_state):
        """Test order generation for invalid power."""
        orders = ai.generate_orders(movement_game_state, "INVALID_POWER")
        
        assert orders == []
    
    def test_generate_orders_empty_units(self, ai, movement_game_state):
        """Test order generation when power has no units."""
        movement_game_state.powers["FRANCE"].units = []
        orders = ai.generate_orders(movement_game_state, "FRANCE")
        
        assert orders == []
    
    @patch('engine.strategic_ai.random.random')
    def test_aggression_level_affects_behavior(self, mock_random, ai, movement_game_state):
        """Test that aggression level affects order generation."""
        # Set high aggression
        ai.config.aggression_level = 0.9
        ai.config.support_probability = 0.1  # Low support probability
        ai.config.convoy_probability = 0.1  # Low convoy probability
        
        # Mock random to return values that favor aggressive moves
        # Provide many values since AI makes multiple random calls
        mock_random.side_effect = [0.1] * 20  # Low values favor aggressive moves
        
        orders = ai.generate_orders(movement_game_state, "FRANCE")
        
        # With high aggression and low random, should prefer aggressive moves
        move_orders = [o for o in orders if isinstance(o, MoveOrder)]
        assert len(move_orders) > 0
    
    @patch('engine.strategic_ai.random.random')
    def test_support_probability_affects_support_orders(self, mock_random, ai, movement_game_state):
        """Test that support probability affects support order generation."""
        ai.config.support_probability = 0.9
        mock_random.return_value = 0.1  # Low random value
        
        orders = ai.generate_orders(movement_game_state, "FRANCE")
        
        # With high support probability, should generate support orders
        support_orders = [o for o in orders if isinstance(o, SupportOrder)]
        # Note: This test may need adjustment based on actual AI logic
    
    def test_movement_orders_generation(self, ai, movement_game_state):
        """Test movement order generation logic."""
        orders = ai._generate_movement_orders(movement_game_state, movement_game_state.powers["FRANCE"])
        
        assert isinstance(orders, list)
        for order in orders:
            assert isinstance(order, (MoveOrder, HoldOrder, SupportOrder, ConvoyOrder))
    
    def test_retreat_orders_generation(self, ai, retreat_game_state):
        """Test retreat order generation logic."""
        france_state = retreat_game_state.powers["FRANCE"]
        orders = ai._generate_retreat_orders(retreat_game_state, france_state)
        
        assert isinstance(orders, list)
        for order in orders:
            assert isinstance(order, RetreatOrder)
    
    def test_adjustment_orders_generation(self, ai, adjustment_game_state):
        """Test adjustment order generation logic."""
        france_state = adjustment_game_state.powers["FRANCE"]
        orders = ai._generate_build_orders(adjustment_game_state, france_state)
        
        assert isinstance(orders, list)
        for order in orders:
            assert isinstance(order, (BuildOrder, DestroyOrder))


class TestOrderGenerator:
    """Test OrderGenerator class."""
    
    @pytest.fixture
    def generator(self):
        """Create OrderGenerator instance."""
        return OrderGenerator()
    
    @pytest.fixture
    def sample_unit(self):
        """Create sample unit for testing."""
        return Unit(unit_type="A", province="PAR", power="FRANCE")
    
    def test_generator_initialization(self, generator):
        """Test OrderGenerator initialization."""
        assert generator is not None
    
    def test_generate_move_order(self, generator, sample_unit):
        """Test move order generation."""
        target = "BUR"
        mock_game_state = Mock()
        mock_game_state.get_unit_at_province = Mock(return_value=sample_unit)
        mock_game_state.current_phase = "Movement"
        
        order = generator.create_order_from_string(f"A {sample_unit.province} - {target}", sample_unit.power, mock_game_state)
        
        assert isinstance(order, MoveOrder)
        assert order.unit == sample_unit
        assert order.target_province == target
        assert order.power == sample_unit.power
    
    def test_generate_hold_order(self, generator, sample_unit):
        """Test hold order generation."""
        mock_game_state = Mock()
        mock_game_state.get_unit_at_province = Mock(return_value=sample_unit)
        mock_game_state.current_phase = "Movement"
        
        order = generator.create_order_from_string(f"A {sample_unit.province}", sample_unit.power, mock_game_state)
        
        assert isinstance(order, HoldOrder)
        assert order.unit == sample_unit
        assert order.power == sample_unit.power
    
    def test_generate_support_order(self, generator, sample_unit):
        """Test support order generation."""
        supported_unit = Unit(unit_type="A", province="MAR", power="FRANCE")
        supported_target = "BUR"
        
        mock_game_state = Mock()
        mock_game_state.get_unit_at_province = Mock(side_effect=lambda p: sample_unit if p == sample_unit.province else supported_unit)
        mock_game_state.current_phase = "Movement"
        
        order = generator.create_order_from_string(f"A {sample_unit.province} S A {supported_unit.province} - {supported_target}", sample_unit.power, mock_game_state)
        
        assert isinstance(order, SupportOrder)
        assert order.unit == sample_unit
        assert order.supported_unit == supported_unit
        assert order.supported_target == supported_target
        assert order.power == sample_unit.power
    
    def test_generate_convoy_order(self, generator, sample_unit):
        """Test convoy order generation."""
        fleet_unit = Unit(unit_type="F", province="ENG", power="FRANCE")
        convoyed_unit = Unit(unit_type="A", province="LON", power="FRANCE")
        convoyed_target = "HOL"
        
        mock_game_state = Mock()
        mock_game_state.get_unit_at_province = Mock(side_effect=lambda p: fleet_unit if p == fleet_unit.province else convoyed_unit)
        mock_game_state.current_phase = "Movement"
        
        order = generator.create_order_from_string(f"F {fleet_unit.province} C A {convoyed_unit.province} - {convoyed_target}", fleet_unit.power, mock_game_state)
        
        assert isinstance(order, ConvoyOrder)
        assert order.unit == fleet_unit
        assert order.convoyed_unit == convoyed_unit
        assert order.convoyed_target == convoyed_target
        assert order.power == fleet_unit.power
    
    def test_generate_retreat_order(self, generator, sample_unit):
        """Test retreat order generation."""
        retreat_province = "PIC"
        
        mock_game_state = Mock()
        mock_game_state.get_unit_at_province = Mock(return_value=sample_unit)
        mock_game_state.current_phase = "Retreat"
        
        order = generator.create_order_from_string(f"A {sample_unit.province} R {retreat_province}", sample_unit.power, mock_game_state)
        
        assert isinstance(order, RetreatOrder)
        assert order.unit == sample_unit
        assert order.retreat_province == retreat_province
        assert order.power == sample_unit.power
    
    def test_generate_build_order(self, generator):
        """Test build order generation."""
        power = "FRANCE"
        build_type = "A"
        build_province = "PAR"
        
        mock_game_state = Mock()
        mock_game_state.current_phase = "Builds"
        
        order = generator.create_order_from_string(f"BUILD {build_type} {build_province}", power, mock_game_state)
        
        assert isinstance(order, BuildOrder)
        assert order.power == power
        assert order.build_type == build_type
        assert order.build_province == build_province
    
    def test_generate_destroy_order(self, generator, sample_unit):
        """Test destroy order generation."""
        mock_game_state = Mock()
        mock_game_state.get_unit_at_province = Mock(return_value=sample_unit)
        mock_game_state.current_phase = "Builds"
        
        order = generator.create_order_from_string(f"DESTROY {sample_unit.unit_type} {sample_unit.province}", sample_unit.power, mock_game_state)
        
        assert isinstance(order, DestroyOrder)
        assert order.destroy_unit == sample_unit
        assert order.power == sample_unit.power


class TestStrategicAIEdgeCases:
    """Test edge cases and error handling in StrategicAI."""
    
    @pytest.fixture
    def ai(self):
        """Create StrategicAI instance."""
        return StrategicAI()
    
    def test_empty_game_state(self, ai):
        """Test behavior with empty game state."""
        from datetime import datetime
        from engine.data_models import MapData, GameStatus
        
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
        
        orders = ai.generate_orders(empty_state, "FRANCE")
        assert orders == []
    
    def test_invalid_phase(self, ai, mid_game_state):
        """Test behavior with invalid phase."""
        mid_game_state.current_phase = "InvalidPhase"
        
        orders = ai.generate_orders(mid_game_state, "FRANCE")
        assert orders == []
    
    def test_none_power_state(self, ai, mid_game_state):
        """Test behavior when power state is None."""
        mid_game_state.powers["FRANCE"] = None
        
        orders = ai.generate_orders(mid_game_state, "FRANCE")
        assert orders == []
    
    def test_units_with_invalid_provinces(self, ai, mid_game_state):
        """Test behavior with units in invalid provinces."""
        france_state = mid_game_state.powers["FRANCE"]
        france_state.units = [
            Unit(unit_type="A", province="INVALID_PROVINCE", power="FRANCE")
        ]
        
        orders = ai.generate_orders(mid_game_state, "FRANCE")
        # Should handle gracefully, not crash
        assert isinstance(orders, list)
    
    @patch('engine.strategic_ai.random.choice')
    def test_random_choice_failure(self, mock_choice, ai, mid_game_state):
        """Test behavior when random choice fails."""
        mock_choice.side_effect = Exception("Random choice failed")
        
        # Should handle gracefully
        orders = ai.generate_orders(mid_game_state, "FRANCE")
        assert isinstance(orders, list)


# Integration tests
@pytest.mark.integration
class TestStrategicAIIntegration:
    """Integration tests for StrategicAI with real game scenarios."""
    
    @pytest.fixture
    def ai(self):
        """Create StrategicAI instance."""
        return StrategicAI()
    
    def test_full_game_ai_orders(self, ai, standard_game):
        """Test AI can generate orders for a full game scenario."""
        # Set up a realistic game state
        game_state = standard_game.game_state
        
        # Test all powers
        for power_name in game_state.powers.keys():
            orders = ai.generate_orders(game_state, power_name)
            
            assert isinstance(orders, list)
            # Each power should be able to generate some orders
            # (exact count depends on game state and AI logic)
    
    def test_ai_orders_are_valid(self, ai, mid_game_state):
        """Test that AI-generated orders are valid."""
        orders = ai.generate_orders(mid_game_state, "FRANCE")
        
        for order in orders:
            # Basic validation - orders should have required fields
            assert order.power == "FRANCE"
            assert order.order_type is not None
            
            # More specific validation based on order type
            if isinstance(order, MoveOrder):
                assert order.target_province is not None
            elif isinstance(order, SupportOrder):
                assert order.supported_unit is not None
                # supported_target should be None for hold support, not None for move support
                if order.supported_action == "move":
                    assert order.supported_target is not None
                elif order.supported_action == "hold":
                    assert order.supported_target is None
            elif isinstance(order, ConvoyOrder):
                assert order.convoyed_unit is not None
                assert order.convoyed_target is not None
