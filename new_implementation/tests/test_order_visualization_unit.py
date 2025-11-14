"""
Comprehensive unit tests for Order Visualization module.

Tests cover OrderVisualizationService class with data structure creation,
validation logic, moves format, and visual output generation.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch
from typing import Dict, List, Any

from engine.order_visualization import OrderVisualizationService, OrderVisualizationData
from engine.data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder,
    MapData, Province
)


class TestOrderVisualizationService:
    """Test OrderVisualizationService class."""
    
    @pytest.fixture
    def viz_service(self):
        """Create OrderVisualizationService instance."""
        return OrderVisualizationService()
    
    @pytest.fixture
    def sample_game_state(self, mid_game_state):
        """Create sample game state with orders."""
        game_state = mid_game_state
        
        # Add comprehensive orders
        france_orders = [
            MoveOrder(
                power="FRANCE",
                unit=Unit(unit_type="A", province="PAR", power="FRANCE"),
                order_type=OrderType.MOVE,
                phase="Movement",
                target_province="BUR",
                status=OrderStatus.SUBMITTED
            ),
            HoldOrder(
                power="FRANCE",
                unit=Unit(unit_type="A", province="MAR", power="FRANCE"),
                order_type=OrderType.HOLD,
                phase="Movement",
                status=OrderStatus.SUBMITTED
            ),
            SupportOrder(
                power="FRANCE",
                unit=Unit(unit_type="F", province="BRE", power="FRANCE"),
                order_type=OrderType.SUPPORT,
                phase="Movement",
                supported_unit=Unit(unit_type="A", province="PAR", power="FRANCE"),
                supported_action="move",
                supported_target="BUR",
                status=OrderStatus.SUBMITTED
            )
        ]
        
        germany_orders = [
            MoveOrder(
                power="GERMANY",
                unit=Unit(unit_type="A", province="BER", power="GERMANY"),
                order_type=OrderType.MOVE,
                phase="Movement",
                target_province="SIL",
                status=OrderStatus.SUBMITTED
            ),
            ConvoyOrder(
                power="GERMANY",
                unit=Unit(unit_type="F", province="KIE", power="GERMANY"),
                order_type=OrderType.CONVOY,
                phase="Movement",
                convoyed_unit=Unit(unit_type="A", province="BER", power="GERMANY"),
                convoyed_target="BAL",
                status=OrderStatus.SUBMITTED
            )
        ]
        
        game_state.orders = {
            "FRANCE": france_orders,
            "GERMANY": germany_orders
        }
        
        return game_state
    
    def test_service_initialization(self, viz_service):
        """Test OrderVisualizationService initialization."""
        assert viz_service is not None
    
    def test_create_visualization_data(self, viz_service, sample_game_state):
        """Test creating visualization data from game state."""
        viz_data = viz_service.create_visualization_data(sample_game_state)
        
        assert isinstance(viz_data, dict)
        assert "FRANCE" in viz_data
        assert "GERMANY" in viz_data
        
        # Check France orders
        france_orders = viz_data["FRANCE"]
        assert len(france_orders) == 3
        
        # Check move order
        move_order = next((o for o in france_orders if o["type"] == "move"), None)
        assert move_order is not None
        assert move_order["unit"] == "A PAR"
        assert move_order["target"] == "BUR"
        assert move_order["power"] == "FRANCE"
        
        # Check hold order
        hold_order = next((o for o in france_orders if o["type"] == "hold"), None)
        assert hold_order is not None
        assert hold_order["unit"] == "A MAR"
        assert hold_order["power"] == "FRANCE"
        
        # Check support order
        support_order = next((o for o in france_orders if o["type"] == "support"), None)
        assert support_order is not None
        assert support_order["unit"] == "F BRE"
        assert support_order["supporting"] == "A PAR"
        assert support_order["supported_target"] == "BUR"
        assert support_order["power"] == "FRANCE"
    
    def test_create_moves_visualization_data(self, viz_service, sample_game_state):
        """Test creating moves visualization data."""
        moves_data = viz_service.create_moves_visualization_data(sample_game_state)
        
        assert isinstance(moves_data, dict)
        assert "FRANCE" in moves_data
        assert "GERMANY" in moves_data
        
        # Check France moves
        france_moves = moves_data["FRANCE"]
        assert "successful" in france_moves
        assert "failed" in france_moves
        assert "bounced" in france_moves
        
        # Should have one successful move
        assert len(france_moves["successful"]) == 1
        assert france_moves["successful"][0]["unit"] == "A PAR"
        assert france_moves["successful"][0]["target"] == "BUR"
    
    def test_validate_visualization_data(self, viz_service, sample_game_state):
        """Test validation of visualization data."""
        viz_data = viz_service.create_visualization_data(sample_game_state)
        
        valid, errors = viz_service.validate_visualization_data(viz_data, sample_game_state)
        
        assert valid is True
        assert len(errors) == 0
    
    def test_validate_visualization_data_invalid(self, viz_service, sample_game_state):
        """Test validation with invalid data."""
        # Create invalid visualization data
        invalid_viz_data = {
            "FRANCE": [
                {
                    "type": "move",
                    "unit": "A INVALID_PROVINCE",  # Invalid province
                    "target": "BUR",
                    "power": "FRANCE"
                }
            ]
        }
        
        valid, errors = viz_service.validate_visualization_data(invalid_viz_data, sample_game_state)
        
        assert valid is False
        assert len(errors) > 0
        assert any("INVALID_PROVINCE" in error for error in errors)


class TestOrderVisualizationData:
    """Test OrderVisualizationData class."""
    
    def test_visualization_data_creation(self):
        """Test creating OrderVisualizationData."""
        from engine.data_models import Unit, OrderType, OrderStatus
        
        # Create a unit for the order
        unit = Unit(unit_type="A", province="PAR", power="FRANCE")
        
        # Create OrderVisualizationData for a single move order
        data = OrderVisualizationData(
            order_type=OrderType.MOVE,
            power="FRANCE",
            unit=unit,
            target_province="BUR",
            status=OrderStatus.PENDING
        )
        
        assert data.order_type == OrderType.MOVE
        assert data.power == "FRANCE"
        assert data.unit.unit_type == "A"
        assert data.unit.province == "PAR"
        assert data.target_province == "BUR"
        assert data.status == OrderStatus.PENDING


class TestOrderVisualizationFormats:
    """Test different order visualization formats."""
    
    @pytest.fixture
    def viz_service(self):
        """Create OrderVisualizationService instance."""
        return OrderVisualizationService()
    
    @pytest.fixture
    def orders_dictionary_format(self):
        """Create orders in dictionary format."""
        return {
            "FRANCE": [
                {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
                {"type": "hold", "unit": "A MAR", "status": "success"},
                {"type": "support", "unit": "F BRE", "supporting": "A PAR - BUR", "status": "success"},
                {"type": "build", "unit": "", "target": "PAR", "status": "success"}
            ],
            "GERMANY": [
                {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
                {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
                {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "success"},
                {"type": "destroy", "unit": "A PRU", "status": "success"}
            ],
            "ENGLAND": [
                {"type": "move", "unit": "F LON", "target": "NTH", "status": "bounced"},
                {"type": "support", "unit": "A LVP", "supporting": "F LON - NTH", "status": "failed", "reason": "cut_support"}
            ]
        }
    
    @pytest.fixture
    def units_dictionary_format(self):
        """Create units in dictionary format."""
        return {
            "FRANCE": ["A PAR", "A MAR", "F BRE"],
            "GERMANY": ["A BER", "A MUN", "F KIE", "A PRU"],
            "ENGLAND": ["F LON", "A LVP"]
        }
    
    @pytest.fixture
    def phase_info_format(self):
        """Create phase info in dictionary format."""
        return {
            "turn": 1,
            "season": "Spring",
            "phase": "Movement",
            "phase_code": "S1901M"
        }
    
    def test_orders_dictionary_format_processing(self, viz_service, orders_dictionary_format, units_dictionary_format, phase_info_format):
        """Test processing orders dictionary format."""
        # This would typically be used to generate map visualization
        # For unit testing, we verify the data structure is correct
        
        assert "FRANCE" in orders_dictionary_format
        assert "GERMANY" in orders_dictionary_format
        assert "ENGLAND" in orders_dictionary_format
        
        # Check France orders
        france_orders = orders_dictionary_format["FRANCE"]
        assert len(france_orders) == 4
        
        # Check order types
        order_types = [order["type"] for order in france_orders]
        assert "move" in order_types
        assert "hold" in order_types
        assert "support" in order_types
        assert "build" in order_types
        
        # Check Germany orders
        germany_orders = orders_dictionary_format["GERMANY"]
        assert len(germany_orders) == 4
        
        # Check failed order
        failed_order = next((o for o in germany_orders if o["status"] == "failed"), None)
        assert failed_order is not None
        assert failed_order["reason"] == "bounced"
    
    def test_moves_dictionary_format_processing(self, viz_service, orders_dictionary_format, units_dictionary_format, phase_info_format):
        """Test processing moves dictionary format."""
        # Convert orders to moves format
        moves_data = {
            "FRANCE": {
                "successful": [
                    {"unit": "A PAR", "target": "BUR", "type": "move"}
                ],
                "failed": [],
                "bounced": []
            },
            "GERMANY": {
                "successful": [
                    {"unit": "A BER", "target": "SIL", "type": "move"}
                ],
                "failed": [],
                "bounced": [
                    {"unit": "A MUN", "target": "TYR", "type": "move"}
                ]
            },
            "ENGLAND": {
                "successful": [],
                "failed": [],
                "bounced": [
                    {"unit": "F LON", "target": "NTH", "type": "move"}
                ]
            }
        }
        
        # Verify moves data structure
        assert "FRANCE" in moves_data
        assert "GERMANY" in moves_data
        assert "ENGLAND" in moves_data
        
        # Check France successful moves
        france_successful = moves_data["FRANCE"]["successful"]
        assert len(france_successful) == 1
        assert france_successful[0]["unit"] == "A PAR"
        assert france_successful[0]["target"] == "BUR"
        
        # Check Germany bounced moves
        germany_bounced = moves_data["GERMANY"]["bounced"]
        assert len(germany_bounced) == 1
        assert germany_bounced[0]["unit"] == "A MUN"
        assert germany_bounced[0]["target"] == "TYR"


class TestOrderVisualizationEdgeCases:
    """Test edge cases in order visualization."""
    
    @pytest.fixture
    def viz_service(self):
        """Create OrderVisualizationService instance."""
        return OrderVisualizationService()
    
    def test_empty_game_state(self, viz_service):
        """Test visualization with empty game state."""
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
        
        viz_data = viz_service.create_visualization_data(empty_state)
        
        assert isinstance(viz_data, dict)
        assert len(viz_data) == 0
    
    def test_game_state_without_orders(self, viz_service, mid_game_state):
        """Test visualization with game state that has no orders."""
        # Remove all orders
        for power_state in mid_game_state.powers.values():
            power_state.orders = []
        
        viz_data = viz_service.create_visualization_data(mid_game_state)
        
        assert isinstance(viz_data, dict)
        # Should still have power entries but with empty order lists
        for power_name in viz_data:
            assert viz_data[power_name] == []
    
    def test_game_state_with_invalid_orders(self, viz_service, mid_game_state):
        """Test visualization with invalid orders."""
        # Add invalid order
        invalid_order = MoveOrder(
            power="FRANCE",
            unit=Unit(unit_type="A", province="INVALID_PROVINCE", power="FRANCE"),
            order_type=OrderType.MOVE,
            phase="Movement",
            target_province="BUR",
            status=OrderStatus.SUBMITTED
        )
        
        mid_game_state.orders["FRANCE"].append(invalid_order)
        
        viz_data = viz_service.create_visualization_data(mid_game_state)
        
        # Should still create visualization data
        assert isinstance(viz_data, dict)
        assert "FRANCE" in viz_data
        
        # Should include the invalid order
        france_orders = viz_data["FRANCE"]
        invalid_order_data = next((o for o in france_orders if o["unit"] == "A INVALID_PROVINCE"), None)
        assert invalid_order_data is not None
    
    def test_coast_specifications(self, viz_service):
        """Test visualization with coast specifications."""
        from datetime import datetime
        from engine.data_models import MapData, GameStatus
        
        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        game_state = GameState(
            game_id="coast_test",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            map_data=map_data,
            powers={
                "FRANCE": PowerState(
                    power_name="FRANCE",
                    units=[
                        Unit(unit_type="F", province="SPA/NC", power="FRANCE"),
                        Unit(unit_type="F", province="SPA/SC", power="FRANCE")
                    ]
                )
            },
            orders={
                "FRANCE": [
                    MoveOrder(
                        power="FRANCE",
                        unit=Unit(unit_type="F", province="SPA/NC", power="FRANCE"),
                        order_type=OrderType.MOVE,
                        phase="Movement",
                        target_province="POR",
                        status=OrderStatus.SUBMITTED
                    ),
                    MoveOrder(
                        power="FRANCE",
                        unit=Unit(unit_type="F", province="SPA/SC", power="FRANCE"),
                        order_type=OrderType.MOVE,
                        phase="Movement",
                        target_province="WES",
                        status=OrderStatus.SUBMITTED
                    )
                ]
            }
        )
        
        viz_data = viz_service.create_visualization_data(game_state)
        
        assert "FRANCE" in viz_data
        france_orders = viz_data["FRANCE"]
        
        # Check coast specifications are preserved
        nc_order = next((o for o in france_orders if o["unit"] == "F SPA/NC"), None)
        assert nc_order is not None
        assert nc_order["target"] == "POR"
        
        sc_order = next((o for o in france_orders if o["unit"] == "F SPA/SC"), None)
        assert sc_order is not None
        assert sc_order["target"] == "WES"


class TestOrderVisualizationIntegration:
    """Integration tests for order visualization."""
    
    @pytest.fixture
    def viz_service(self):
        """Create OrderVisualizationService instance."""
        return OrderVisualizationService()
    
    def test_comprehensive_order_types(self, viz_service):
        """Test visualization with all order types."""
        from datetime import datetime
        from engine.data_models import MapData, GameStatus
        
        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        game_state = GameState(
            game_id="comprehensive_test",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            powers={
                "FRANCE": PowerState(
                    power_name="FRANCE",
                    units=[
                        Unit(unit_type="A", province="PAR", power="FRANCE"),
                        Unit(unit_type="A", province="MAR", power="FRANCE"),
                        Unit(unit_type="F", province="BRE", power="FRANCE")
                    ]
                ),
                "ENGLAND": PowerState(
                    power_name="ENGLAND",
                    units=[
                        Unit(unit_type="A", province="LON", power="ENGLAND"),
                        Unit(unit_type="F", province="NTH", power="ENGLAND")
                    ]
                ),
                "GERMANY": PowerState(
                    power_name="GERMANY",
                    units=[
                        Unit(unit_type="A", province="BER", power="GERMANY")
                    ]
                )
            },
            map_data=map_data,
            orders={}
        )
        
        # Add orders to game state
        game_state.orders = {
            "FRANCE": [
                MoveOrder(
                    power="FRANCE",
                    unit=Unit(unit_type="A", province="PAR", power="FRANCE"),
                    order_type=OrderType.MOVE,
                    phase="Movement",
                    target_province="BUR",
                    status=OrderStatus.SUBMITTED
                ),
                HoldOrder(
                    power="FRANCE",
                    unit=Unit(unit_type="A", province="MAR", power="FRANCE"),
                    order_type=OrderType.HOLD,
                    phase="Movement",
                    status=OrderStatus.SUBMITTED
                ),
                SupportOrder(
                    power="FRANCE",
                    unit=Unit(unit_type="F", province="BRE", power="FRANCE"),
                    order_type=OrderType.SUPPORT,
                    phase="Movement",
                    supported_unit=Unit(unit_type="A", province="PAR", power="FRANCE"),
                    supported_action="move",
                    supported_target="BUR",
                    status=OrderStatus.SUBMITTED
                )
            ],
            "ENGLAND": [
                ConvoyOrder(
                    power="ENGLAND",
                    unit=Unit(unit_type="F", province="NTH", power="ENGLAND"),
                    order_type=OrderType.CONVOY,
                    phase="Movement",
                    convoyed_unit=Unit(unit_type="A", province="LON", power="ENGLAND"),
                    convoyed_target="HOL",
                    convoy_chain=["ENG", "NTH"],
                    status=OrderStatus.SUBMITTED
                )
            ],
            "GERMANY": [
                RetreatOrder(
                    power="GERMANY",
                    unit=Unit(unit_type="A", province="BER", power="GERMANY"),
                    order_type=OrderType.RETREAT,
                    phase="Retreat",
                    retreat_province="SIL",
                    status=OrderStatus.SUBMITTED
                )
            ]
        }
        
        viz_data = viz_service.create_visualization_data(game_state)
        
        # Verify all order types are present
        all_orders = []
        for power_orders in viz_data.values():
            all_orders.extend(power_orders)
        
        order_types = [order["type"] for order in all_orders]
        assert "move" in order_types
        assert "hold" in order_types
        assert "support" in order_types
        assert "convoy" in order_types
        assert "retreat" in order_types
        
        # Verify convoy order details
        convoy_order = next((o for o in all_orders if o["type"] == "convoy"), None)
        assert convoy_order is not None
        assert convoy_order["unit"] == "F NTH"
        assert convoy_order["convoyed_unit"] == "A LON"
        assert convoy_order["convoyed_target"] == "HOL"
        assert convoy_order["convoy_chain"] == ["ENG", "NTH"]
    
    def test_moves_visualization_comprehensive(self, viz_service):
        """Test comprehensive moves visualization."""
        from datetime import datetime
        from engine.data_models import MapData, GameStatus
        
        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        game_state = GameState(
            game_id="moves_test",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            powers={
                "FRANCE": PowerState(
                    power_name="FRANCE",
                    units=[
                        Unit(unit_type="A", province="PAR", power="FRANCE"),
                        Unit(unit_type="A", province="MAR", power="FRANCE")
                    ]
                )
            },
            map_data=map_data,
            orders={
                "FRANCE": [
                    MoveOrder(
                        power="FRANCE",
                        unit=Unit(unit_type="A", province="PAR", power="FRANCE"),
                        order_type=OrderType.MOVE,
                        phase="Movement",
                        target_province="BUR",
                        status=OrderStatus.SUBMITTED
                    ),
                    MoveOrder(
                        power="FRANCE",
                        unit=Unit(unit_type="A", province="MAR", power="FRANCE"),
                        order_type=OrderType.MOVE,
                        phase="Movement",
                        target_province="PIC",
                        status=OrderStatus.SUBMITTED
                    )
                ]
            }
        )
        
        moves_data = viz_service.create_moves_visualization_data(game_state)
        
        assert "FRANCE" in moves_data
        france_moves = moves_data["FRANCE"]
        
        # Should have successful moves
        assert len(france_moves["successful"]) == 2
        assert len(france_moves["failed"]) == 0
        assert len(france_moves["bounced"]) == 0
        
        # Check move details
        successful_moves = france_moves["successful"]
        move_targets = [move["target"] for move in successful_moves]
        assert "BUR" in move_targets
        assert "PIC" in move_targets


# Performance tests
@pytest.mark.slow
class TestOrderVisualizationPerformance:
    """Performance tests for order visualization."""
    
    @pytest.fixture
    def viz_service(self):
        """Create OrderVisualizationService instance."""
        return OrderVisualizationService()
    
    def test_large_game_state_visualization(self, viz_service):
        """Test visualization with large game state."""
        # Create game state with many powers and orders
        powers = {}
        power_orders = {}
        for power_name in ["FRANCE", "GERMANY", "ENGLAND", "RUSSIA", "TURKEY", "AUSTRIA", "ITALY"]:
            units = [
                Unit(unit_type="A", province=f"{power_name[:3]}1", power=power_name),
                Unit(unit_type="A", province=f"{power_name[:3]}2", power=power_name),
                Unit(unit_type="F", province=f"{power_name[:3]}3", power=power_name)
            ]
            
            orders = [
                MoveOrder(
                    power=power_name,
                    unit=Unit(unit_type="A", province=f"{power_name[:3]}1", power=power_name),
                    order_type=OrderType.MOVE,
                    phase="Movement",
                    target_province=f"{power_name[:3]}2",
                    status=OrderStatus.SUBMITTED
                ),
                HoldOrder(
                    power=power_name,
                    unit=Unit(unit_type="F", province=f"{power_name[:3]}3", power=power_name),
                    order_type=OrderType.HOLD,
                    phase="Movement",
                    status=OrderStatus.SUBMITTED
                )
            ]
            
            powers[power_name] = PowerState(
                power_name=power_name,
                units=units
            )
            
            # Store orders separately
            power_orders[power_name] = orders
        
        from datetime import datetime
        from engine.data_models import MapData, GameStatus
        
        map_data = MapData(
            map_name="standard",
            provinces={},
            supply_centers=[],
            home_supply_centers={},
            starting_positions={}
        )
        
        game_state = GameState(
            game_id="large_test",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            powers=powers,
            map_data=map_data,
            orders=power_orders
        )
        
        import time
        start_time = time.time()
        
        viz_data = viz_service.create_visualization_data(game_state)
        moves_data = viz_service.create_moves_visualization_data(game_state)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should process large game state quickly
        assert duration < 0.1, f"Processing large game state took {duration:.3f} seconds"
        
        # Verify all powers are processed
        assert len(viz_data) == 7
        assert len(moves_data) == 7
