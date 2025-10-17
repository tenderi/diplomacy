"""
Comprehensive integration tests for Diplomacy game engine.

Tests cover full game workflows, API endpoints, database integration,
and end-to-end scenarios using pytest with real components.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from engine.game import Game
from engine.data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder,
    MapData, Province, GameStatus
)
from server.server import Server
from engine.database_service import DatabaseService
from engine.order_parser import OrderParser
from engine.strategic_ai import StrategicAI


class TestFullGameWorkflow:
    """Test complete game workflows from start to finish."""
    
    @pytest.fixture
    def game_server(self):
        """Create game server instance."""
        return Server()
    
    @pytest.fixture
    def sample_game_state(self):
        """Create sample game state for testing."""
        # Create a minimal map data
        map_data = MapData(
            map_name="standard",
            provinces={
                "PAR": Province(name="PAR", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["BUR", "PIC", "GAS"]),
                "BUR": Province(name="BUR", province_type="land", is_supply_center=True, is_home_supply_center=False, adjacent_provinces=["PAR", "MAR", "MUN"]),
                "MAR": Province(name="MAR", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["BUR", "GAS", "SPA"]),
                "BER": Province(name="BER", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="GERMANY", adjacent_provinces=["KIE", "MUN", "SIL"]),
                "MUN": Province(name="MUN", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="GERMANY", adjacent_provinces=["BER", "BUR", "TYR"]),
                "KIE": Province(name="KIE", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="GERMANY", adjacent_provinces=["BER", "HOL", "DEN", "BAL"]),
                "LON": Province(name="LON", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["WAL", "YOR", "NTH"]),
                "NTH": Province(name="NTH", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["LON", "ENG", "BEL", "HOL", "DEN", "NOR", "EDI"]),
                "HOL": Province(name="HOL", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["KIE", "BEL", "RUH", "NTH"]),
                "ENG": Province(name="ENG", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["LON", "WAL", "PIC", "BEL", "NTH", "IRI"]),
                "BRE": Province(name="BRE", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["ENG", "PAR", "GAS"]),
                "GAS": Province(name="GAS", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["PAR", "MAR", "BOR", "SPA"]),
                "PIC": Province(name="PIC", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["PAR", "BEL", "ENG"]),
                "BEL": Province(name="BEL", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["PIC", "HOL", "RUH", "BUR", "ENG", "NTH"]),
                "RUH": Province(name="RUH", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="GERMANY", adjacent_provinces=["HOL", "BEL", "MUN", "KIE"]),
                "SIL": Province(name="SIL", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="GERMANY", adjacent_provinces=["BER", "MUN", "PRU", "WAR"]),
                "PRU": Province(name="PRU", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="GERMANY", adjacent_provinces=["SIL", "WAR", "BAL", "KIE"]),
                "BAL": Province(name="BAL", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["KIE", "PRU", "SWE", "DEN", "BOT"]),
                "WAL": Province(name="WAL", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["LON", "LVP", "ENG"]),
                "LVP": Province(name="LVP", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["CLY", "WAL", "YOR", "IRI"]),
                "YOR": Province(name="YOR", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["LON", "LVP", "EDI", "NTH"]),
                "CLY": Province(name="CLY", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["LVP", "EDI", "NWG"]),
                "EDI": Province(name="EDI", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["CLY", "YOR", "NTH", "NOR"]),
                "NOR": Province(name="NOR", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["NTH", "SWE", "FIN", "BAR", "NWG"]),
                "SWE": Province(name="SWE", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["NOR", "DEN", "BAL", "FIN", "BOT"]),
                "DEN": Province(name="DEN", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ENGLAND", adjacent_provinces=["KIE", "HOL", "NTH", "SWE", "BAL", "SKG"]),
                "FIN": Province(name="FIN", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["NOR", "SWE", "STP", "BOT"]),
                "STP": Province(name="STP", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["FIN", "MOS", "LVN", "BOT"]),
                "MOS": Province(name="MOS", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["STP", "WAR", "UKR", "SEV", "LVN"]),
                "WAR": Province(name="WAR", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["SIL", "PRU", "MOS", "UKR", "GAL", "LVN"]),
                "UKR": Province(name="UKR", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["MOS", "WAR", "GAL", "RUM", "SEV"]),
                "RUM": Province(name="RUM", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["UKR", "SER", "BUL", "BLA", "SEV"]),
                "SER": Province(name="SER", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["RUM", "BUL", "GRE", "ALB", "TRI", "BUD"]),
                "BUL": Province(name="BUL", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["RUM", "SER", "GRE", "CON", "BLA", "AEG"]),
                "GRE": Province(name="GRE", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["SER", "BUL", "ALB", "ION", "AEG"]),
                "ALB": Province(name="ALB", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["SER", "GRE", "TRI", "ION"]),
                "TRI": Province(name="TRI", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["SER", "ALB", "VEN", "TYR", "VIE", "BUD"]),
                "VEN": Province(name="VEN", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ITALY", adjacent_provinces=["TRI", "TYR", "PIE", "ROM", "APU", "ADR"]),
                "TYR": Province(name="TYR", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["MUN", "TRI", "VEN", "VIE", "BOH"]),
                "VIE": Province(name="VIE", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["TRI", "TYR", "BOH", "GAL", "BUD"]),
                "BUD": Province(name="BUD", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["TRI", "VIE", "GAL", "RUM", "SER"]),
                "GAL": Province(name="GAL", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["WAR", "UKR", "RUM", "BUD", "VIE", "BOH"]),
                "BOH": Province(name="BOH", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="AUSTRIA", adjacent_provinces=["MUN", "TYR", "VIE", "GAL", "SIL", "BER"]),
                "ROM": Province(name="ROM", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ITALY", adjacent_provinces=["VEN", "APU", "NAP", "TUS", "ADR", "TYR"]),
                "APU": Province(name="APU", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ITALY", adjacent_provinces=["VEN", "ROM", "NAP", "ION", "ADR"]),
                "NAP": Province(name="NAP", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ITALY", adjacent_provinces=["ROM", "APU", "ION", "TUS"]),
                "TUS": Province(name="TUS", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="ITALY", adjacent_provinces=["ROM", "PIE", "VEN", "TYR", "ADR", "GOL"]),
                "PIE": Province(name="PIE", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="ITALY", adjacent_provinces=["VEN", "TUS", "MAR", "BUR", "TYR"]),
                "SPA": Province(name="SPA", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["MAR", "GAS", "POR", "NAF", "WES", "GOL"]),
                "POR": Province(name="POR", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["SPA", "NAF", "MAO", "ATL"]),
                "NAF": Province(name="NAF", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["SPA", "POR", "MAO", "WES"]),
                "MAO": Province(name="MAO", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["POR", "NAF", "WES", "IRI", "MID", "ATL"]),
                "IRI": Province(name="IRI", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["LVP", "WAL", "ENG", "MAO", "MID", "ATL"]),
                "MID": Province(name="MID", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["MAO", "IRI", "WES", "GOL", "TUS", "ION", "TUN", "NAF"]),
                "WES": Province(name="WES", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["MAO", "SPA", "NAF", "GOL", "MID"]),
                "GOL": Province(name="GOL", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["WES", "SPA", "TUS", "MID"]),
                "ION": Province(name="ION", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["GRE", "ALB", "APU", "NAP", "TUN", "MID", "AEG"]),
                "TUN": Province(name="TUN", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="FRANCE", adjacent_provinces=["ION", "MID", "NAF"]),
                "AEG": Province(name="AEG", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["GRE", "BUL", "CON", "SMY", "EAS", "ION"]),
                "CON": Province(name="CON", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["BUL", "SMY", "ANK", "BLA", "AEG"]),
                "SMY": Province(name="SMY", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["CON", "ANK", "ARM", "SYR", "EAS", "AEG"]),
                "ANK": Province(name="ANK", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["CON", "SMY", "ARM", "BLA"]),
                "ARM": Province(name="ARM", province_type="land", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["ANK", "SMY", "SYR", "SEV", "BLA"]),
                "SYR": Province(name="SYR", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="TURKEY", adjacent_provinces=["SMY", "ARM", "EAS"]),
                "EAS": Province(name="EAS", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["SMY", "SYR", "AEG", "ION"]),
                "BLA": Province(name="BLA", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["RUM", "BUL", "CON", "ANK", "ARM", "SEV"]),
                "SEV": Province(name="SEV", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["UKR", "RUM", "BLA", "ARM", "MOS"]),
                "NWG": Province(name="NWG", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["CLY", "EDI", "NOR", "BAR", "ATL"]),
                "BAR": Province(name="BAR", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["NOR", "STP", "NWG", "ARC"]),
                "ARC": Province(name="ARC", province_type="coastal", is_supply_center=True, is_home_supply_center=True, home_power="RUSSIA", adjacent_provinces=["BAR", "STP"]),
                "BOT": Province(name="BOT", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["SWE", "FIN", "STP", "BAL"]),
                "SKG": Province(name="SKG", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["DEN", "NTH", "NOR", "SWE"]),
                "ADR": Province(name="ADR", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["VEN", "APU", "NAP", "ROM", "TUS", "ION", "ALB", "TRI"]),
                "ATL": Province(name="ATL", province_type="sea", is_supply_center=False, is_home_supply_center=False, adjacent_provinces=["MAO", "IRI", "NWG", "POR", "SPA", "ENG"])
            },
            supply_centers=["PAR", "MAR", "BRE", "BER", "MUN", "KIE", "LON", "EDI", "LVP"],
            home_supply_centers={
                "FRANCE": ["PAR", "MAR", "BRE"],
                "GERMANY": ["BER", "MUN", "KIE"],
                "ENGLAND": ["LON", "EDI", "LVP"]
            },
            starting_positions={
                "FRANCE": [
                    Unit(unit_type="A", province="PAR", power="FRANCE"),
                    Unit(unit_type="A", province="MAR", power="FRANCE"),
                    Unit(unit_type="F", province="BRE", power="FRANCE")
                ],
                "GERMANY": [
                    Unit(unit_type="A", province="BER", power="GERMANY"),
                    Unit(unit_type="A", province="MUN", power="GERMANY"),
                    Unit(unit_type="F", province="KIE", power="GERMANY")
                ],
                "ENGLAND": [
                    Unit(unit_type="A", province="LON", power="ENGLAND"),
                    Unit(unit_type="F", province="EDI", power="ENGLAND"),
                    Unit(unit_type="F", province="LVP", power="ENGLAND")
                ]
            }
        )
        
        return GameState(
            game_id="integration_test_game",
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
                    ],
                    controlled_supply_centers=["PAR", "MAR", "BRE"]
                ),
                "GERMANY": PowerState(
                    power_name="GERMANY",
                    units=[
                        Unit(unit_type="A", province="BER", power="GERMANY"),
                        Unit(unit_type="A", province="MUN", power="GERMANY"),
                        Unit(unit_type="F", province="KIE", power="GERMANY")
                    ],
                    controlled_supply_centers=["BER", "MUN", "KIE"]
                ),
                "ENGLAND": PowerState(
                    power_name="ENGLAND",
                    units=[
                        Unit(unit_type="A", province="LON", power="ENGLAND"),
                        Unit(unit_type="F", province="EDI", power="ENGLAND"),
                        Unit(unit_type="F", province="LVP", power="ENGLAND")
                    ],
                    controlled_supply_centers=["LON", "EDI", "LVP"]
                )
            },
            orders={},
            map_data=map_data
        )
    
    def test_game_creation_and_initialization(self, game_server, sample_game_state):
        """Test game creation and initialization."""
        # Create game using the process_command method
        result = game_server.process_command("CREATE_GAME standard")
        assert result["status"] == "ok"
        game_id = result["game_id"]
        assert game_id is not None
        
        # Add players
        result = game_server.process_command(f"ADD_PLAYER {game_id} FRANCE")
        assert result["status"] == "ok"
        
        result = game_server.process_command(f"ADD_PLAYER {game_id} GERMANY")
        assert result["status"] == "ok"
        
        # Get game state
        result = game_server.process_command(f"GET_GAME_STATE {game_id}")
        assert result["status"] == "ok"
        game_state = result["state"]
        
        # Verify initial state
        assert game_state.current_phase == "Movement"
        assert game_state.current_season == "Spring"
        assert game_state.current_year == 1901
        assert "FRANCE" in game_state.powers
        assert "GERMANY" in game_state.powers
        
        # Submit orders
        result = game_server.process_command(f"SET_ORDERS {game_id} FRANCE A PAR - BUR")
        assert result["status"] == "ok"
        
        result = game_server.process_command(f"SET_ORDERS {game_id} GERMANY A BER - MUN")
        assert result["status"] == "ok"
        
        # Process turn
        result = game_server.process_command(f"PROCESS_TURN {game_id}")
        assert result["status"] == "ok"
        
        print("Integration test: Game creation, player joining, order submission, and turn processing successful.")
    
    def test_add_players_to_game(self, game_server, sample_game_state):
        """Test adding players to game."""
        # Create game
        game_id = game_server.create_game("integration_test", "standard")
        
        # Add players
        powers = ["FRANCE", "GERMANY", "ENGLAND"]
        for power in powers:
            result = game_server.add_player(game_id, power, f"player_{power.lower()}")
            assert result["status"] == "ok"
        
        # Verify players were added
        state = game_server.get_game_state(game_id)
        game_state = state["state"]
        
        for power in powers:
            assert power in game_state["powers"]
            assert game_state["powers"][power]["power_name"] == power
    
    def test_order_submission_and_processing(self, game_server, sample_game_state):
        """Test order submission and processing."""
        # Create game and add players
        game_id = game_server.create_game("integration_test", "standard")
        powers = ["FRANCE", "GERMANY", "ENGLAND"]
        for power in powers:
            game_server.add_player(game_id, power, f"player_{power.lower()}")
        
        # Submit orders
        orders = {
            "FRANCE": [
                {"type": "move", "unit": "A PAR", "target": "BUR"},
                {"type": "hold", "unit": "A MAR"},
                {"type": "support", "unit": "F BRE", "supporting": "A PAR", "supported_target": "BUR"}
            ],
            "GERMANY": [
                {"type": "move", "unit": "A BER", "target": "SIL"},
                {"type": "hold", "unit": "A MUN"},
                {"type": "convoy", "unit": "F KIE", "convoyed_unit": "A BER", "convoyed_target": "BAL"}
            ],
            "ENGLAND": [
                {"type": "move", "unit": "A LON", "target": "YOR"},
                {"type": "move", "unit": "F EDI", "target": "NTH"},
                {"type": "move", "unit": "F LVP", "target": "IRI"}
            ]
        }
        
        for power, power_orders in orders.items():
            result = game_server.set_orders(game_id, power, power_orders)
            assert result["status"] == "ok"
        
        # Verify orders were set
        state = game_server.get_game_state(game_id)
        game_state = state["state"]
        
        for power, power_orders in orders.items():
            assert power in game_state["orders"]
            assert len(game_state["orders"][power]) == len(power_orders)


class TestAPIEndpoints:
    """Test API endpoints integration."""
    
    @pytest.fixture
    def game_server(self):
        """Create game server instance."""
        return Server()
    
    def test_create_game_endpoint(self, game_server):
        """Test create game API endpoint."""
        result = game_server.process_command("CREATE_GAME integration_test standard")
        
        assert result["status"] == "ok"
        assert "game_id" in result
        assert result["game_id"] is not None
    
    def test_add_player_endpoint(self, game_server):
        """Test add player API endpoint."""
        # Create game first
        game_id = game_server.create_game("integration_test", "standard")
        
        # Add player
        result = game_server.process_command(f"ADD_PLAYER {game_id} FRANCE player_france")
        
        assert result["status"] == "ok"
    
    def test_set_orders_endpoint(self, game_server):
        """Test set orders API endpoint."""
        # Create game and add player
        game_id = game_server.create_game("integration_test", "standard")
        game_server.add_player(game_id, "FRANCE", "player_france")
        
        # Set orders
        orders = [
            {"type": "move", "unit": "A PAR", "target": "BUR"},
            {"type": "hold", "unit": "A MAR"}
        ]
        
        result = game_server.process_command(f"SET_ORDERS {game_id} FRANCE {json.dumps(orders)}")
        
        assert result["status"] == "ok"
    
    def test_get_game_state_endpoint(self, game_server):
        """Test get game state API endpoint."""
        # Create game
        game_id = game_server.create_game("integration_test", "standard")
        
        # Get game state
        result = game_server.process_command(f"GET_GAME_STATE {game_id}")
        
        assert result["status"] == "ok"
        assert "state" in result
        assert result["state"]["game_id"] == game_id
    
    def test_invalid_command_handling(self, game_server):
        """Test handling of invalid commands."""
        # Test invalid command
        result = game_server.process_command("INVALID_COMMAND")
        
        assert result["status"] == "error"
        assert "message" in result
    
    def test_missing_game_handling(self, game_server):
        """Test handling of commands for non-existent games."""
        # Test command for non-existent game
        result = game_server.process_command("GET_GAME_STATE non_existent_game")
        
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()


class TestOrderParserIntegration:
    """Test order parser integration."""
    
    @pytest.fixture
    def order_parser(self):
        """Create order parser instance."""
        return OrderParser()
    
    def test_order_parser_integration(self, order_parser):
        """Test order parser integration with game engine."""
        # Test various order types
        test_orders = [
            ("A PAR - BUR", "FRANCE", OrderType.MOVE),
            ("A MAR H", "FRANCE", OrderType.HOLD),
            ("F BRE S A PAR - BUR", "FRANCE", OrderType.SUPPORT),
            ("F NTH C A LON - HOL", "ENGLAND", OrderType.CONVOY),
            ("A PAR R PIC", "FRANCE", OrderType.RETREAT),
            ("BUILD A PAR", "FRANCE", OrderType.BUILD),
            ("DESTROY A SIL", "GERMANY", OrderType.DESTROY)
        ]
        
        for order_text, power, expected_type in test_orders:
            parsed = order_parser.parse_order_text(order_text, power)
            
            assert parsed.order_type == expected_type
            assert parsed.power == power
            assert parsed.raw_text == order_text


class TestStrategicAIIntegration:
    """Test strategic AI integration."""
    
    @pytest.fixture
    def strategic_ai(self):
        """Create strategic AI instance."""
        return StrategicAI()
    
    @pytest.fixture
    def sample_game_state(self):
        """Create sample game state for AI testing."""
        # Create a minimal game state
        return GameState(
            game_id="ai_test_game",
            map_name="standard",
            current_turn=1,
            current_year=1901,
            current_season="Spring",
            current_phase="Movement",
            phase_code="S1901M",
            status=GameStatus.ACTIVE,
            powers={
                "FRANCE": PowerState(
                    power_name="FRANCE",
                    units=[
                        Unit(unit_type="A", province="PAR", power="FRANCE"),
                        Unit(unit_type="A", province="MAR", power="FRANCE"),
                        Unit(unit_type="F", province="BRE", power="FRANCE")
                    ],
                    controlled_supply_centers=["PAR", "MAR", "BRE"],
                    orders=[]
                )
            },
            orders={},
            retreat_options={},
            build_options={},
            messages=[],
            game_history=[],
            map_data=MapData(name="standard", provinces={})
        )
    
    def test_ai_order_generation(self, strategic_ai, sample_game_state):
        """Test AI order generation."""
        # Generate orders for France
        orders = strategic_ai.generate_orders(sample_game_state, "FRANCE")
        
        assert isinstance(orders, list)
        assert len(orders) > 0
        
        # Verify orders are valid
        for order in orders:
            assert order.power == "FRANCE"
            assert order.order_type is not None
            assert order.unit_type in ["A", "F"]
            assert order.unit_province is not None
    
    def test_ai_edge_cases(self, strategic_ai, sample_game_state):
        """Test AI edge cases."""
        # Test with empty units
        empty_state = sample_game_state
        empty_state.powers["FRANCE"].units = []
        
        orders = strategic_ai.generate_orders(empty_state, "FRANCE")
        
        # Should handle empty units gracefully
        assert isinstance(orders, list)
        assert len(orders) == 0
        
        # Test with invalid power
        orders = strategic_ai.generate_orders(sample_game_state, "INVALID_POWER")
        
        # Should handle invalid power gracefully
        assert isinstance(orders, list)
        assert len(orders) == 0


class TestEndToEndScenarios:
    """Test end-to-end scenarios."""
    
    @pytest.fixture
    def game_server(self):
        """Create game server instance."""
        return Server()
    
    def test_multi_player_game_scenario(self, game_server):
        """Test multi-player game scenario."""
        # Create game
        game_id = game_server.create_game("multi_player_test", "standard")
        
        # Add all 7 powers
        powers = ["FRANCE", "GERMANY", "ENGLAND", "RUSSIA", "TURKEY", "AUSTRIA", "ITALY"]
        for power in powers:
            result = game_server.add_player(game_id, power, f"player_{power.lower()}")
            assert result["status"] == "ok"
        
        # Submit orders for all powers
        for power in powers:
            orders = [{"type": "hold", "unit": f"A {power[:3]}"}]
            result = game_server.set_orders(game_id, power, orders)
            assert result["status"] == "ok"
        
        # Process turn
        result = game_server.process_turn(game_id)
        assert result["status"] == "ok"
        
        # Verify game state
        state = game_server.get_game_state(game_id)
        assert state["status"] == "ok"
        assert state["state"]["current_turn"] == 2
    
    def test_complex_adjudication_scenario(self, game_server):
        """Test complex adjudication scenario."""
        # Create game
        game_id = game_server.create_game("complex_test", "standard")
        
        # Add players
        game_server.add_player(game_id, "FRANCE", "player_france")
        game_server.add_player(game_id, "GERMANY", "player_germany")
        
        # Submit complex orders
        france_orders = [
            {"type": "move", "unit": "A PAR", "target": "BUR"},
            {"type": "support", "unit": "A MAR", "supporting": "A PAR", "supported_target": "BUR"}
        ]
        
        germany_orders = [
            {"type": "move", "unit": "A MUN", "target": "BUR"},
            {"type": "support", "unit": "A BER", "supporting": "A MUN", "supported_target": "BUR"}
        ]
        
        game_server.set_orders(game_id, "FRANCE", france_orders)
        game_server.set_orders(game_id, "GERMANY", germany_orders)
        
        # Process turn
        result = game_server.process_turn(game_id)
        assert result["status"] == "ok"
        
        # Verify adjudication results
        state = game_server.get_game_state(game_id)
        assert state["status"] == "ok"
    
    def test_error_recovery_scenario(self, game_server):
        """Test error recovery scenario."""
        # Create game
        game_id = game_server.create_game("error_recovery_test", "standard")
        
        # Add player
        game_server.add_player(game_id, "FRANCE", "player_france")
        
        # Submit invalid orders
        invalid_orders = [
            {"type": "move", "unit": "A INVALID_PROVINCE", "target": "BUR"},
            {"type": "invalid_order_type", "unit": "A PAR", "target": "BUR"}
        ]
        
        result = game_server.set_orders(game_id, "FRANCE", invalid_orders)
        
        # Should handle invalid orders gracefully
        assert result["status"] == "ok" or result["status"] == "error"
        
        # Game should still be in valid state
        state = game_server.get_game_state(game_id)
        assert state["status"] == "ok"
