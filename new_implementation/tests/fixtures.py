"""
Shared test fixtures and utilities for Diplomacy tests.

This module provides reusable fixtures and utility functions
that can be used across multiple test modules.
"""

import pytest
import tempfile
import os
import json
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta

from engine.data_models import (
    GameState, PowerState, Unit, Order, OrderType, OrderStatus, GameStatus,
    MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder,
    MapData, Province, TurnState, MapSnapshot
)


# ============================================================================
# Game State Fixtures
# ============================================================================

@pytest.fixture
def empty_game_state():
    """Create empty game state for testing."""
    from datetime import datetime
    from engine.data_models import MapData, GameStatus
    
    map_data = MapData(
        map_name="standard",
        provinces={},
        supply_centers=[],
        home_supply_centers={},
        starting_positions={}
    )
    
    return GameState(
        game_id="empty_test",
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


@pytest.fixture
def standard_1901_game_state():
    """Create standard 1901 Spring Movement game state."""
    from datetime import datetime
    from engine.data_models import MapData, GameStatus
    
    map_data = MapData(
        map_name="standard",
        provinces={},
        supply_centers=[],
        home_supply_centers={},
        starting_positions={}
    )
    
    return GameState(
        game_id="standard_1901",
        map_name="standard",
        current_turn=0,
        current_year=1901,
        current_season="Spring",
        current_phase="Movement",
        phase_code="S1901M",
        status=GameStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        map_data=map_data,
        orders={},
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
                    Unit(unit_type="A", province="LVP", power="ENGLAND"),
                    Unit(unit_type="F", province="LON", power="ENGLAND"),
                    Unit(unit_type="F", province="EDI", power="ENGLAND")
                ],
                controlled_supply_centers=["LVP", "LON", "EDI"]
            )
        }
    )


@pytest.fixture
def mid_game_state():
    """Create mid-game state with various units and orders."""
    return GameState(
        game_id="mid_game_test",
        map_name="standard",
        current_turn=5,
        current_year=1902,
        current_season="Fall",
        current_phase="Movement",
        phase_code="F1902M",
        status="active",
        powers={
            "FRANCE": PowerState(
                power_name="FRANCE",
                units=[
                    Unit(unit_type="A", province="PAR", power="FRANCE"),
                    Unit(unit_type="A", province="BUR", power="FRANCE"),
                    Unit(unit_type="F", province="BRE", power="FRANCE"),
                    Unit(unit_type="F", province="ENG", power="FRANCE")
                ],
                controlled_supply_centers=["PAR", "BUR", "BRE", "ENG"],
                orders=[
                    MoveOrder(
                        power="FRANCE",
                        unit_type="A",
                        unit_province="PAR",
                        target_province="BUR",
                        status=OrderStatus.SUBMITTED
                    ),
                    HoldOrder(
                        power="FRANCE",
                        unit_type="F",
                        unit_province="BRE",
                        status=OrderStatus.SUBMITTED
                    )
                ]
            ),
            "GERMANY": PowerState(
                power_name="GERMANY",
                units=[
                    Unit(unit_type="A", province="BER", power="GERMANY"),
                    Unit(unit_type="A", province="MUN", power="GERMANY"),
                    Unit(unit_type="F", province="KIE", power="GERMANY"),
                    Unit(unit_type="A", province="SIL", power="GERMANY")
                ],
                controlled_supply_centers=["BER", "MUN", "KIE", "SIL"],
                orders=[
                    MoveOrder(
                        power="GERMANY",
                        unit_type="A",
                        unit_province="BER",
                        target_province="SIL",
                        status=OrderStatus.SUBMITTED
                    ),
                    SupportOrder(
                        power="GERMANY",
                        unit_type="A",
                        unit_province="MUN",
                        supported_unit_type="A",
                        supported_unit_province="BER",
                        supported_target="SIL",
                        status=OrderStatus.SUBMITTED
                    )
                ]
            )
        }
    )


@pytest.fixture
def retreat_game_state():
    """Create game state in Retreat phase with dislodged units."""
    return GameState(
        game_id="retreat_test",
        map_name="standard",
        current_turn=1,
        current_year=1901,
        current_season="Spring",
        current_phase="Retreat",
        phase_code="S1901R",
        status="active",
        powers={
            "FRANCE": PowerState(
                power_name="FRANCE",
                units=[
                    Unit(unit_type="A", province="MAR", power="FRANCE"),
                    Unit(unit_type="F", province="BRE", power="FRANCE")
                ],
                dislodged_units=[
                    Unit(unit_type="A", province="PAR", power="FRANCE")
                ],
                controlled_supply_centers=["MAR", "BRE"]
            ),
            "GERMANY": PowerState(
                power_name="GERMANY",
                units=[
                    Unit(unit_type="A", province="PAR", power="GERMANY"),
                    Unit(unit_type="A", province="BER", power="GERMANY"),
                    Unit(unit_type="F", province="KIE", power="GERMANY")
                ],
                controlled_supply_centers=["PAR", "BER", "KIE"]
            )
        }
    )


@pytest.fixture
def adjustment_game_state():
    """Create game state in Adjustment phase."""
    return GameState(
        game_id="adjustment_test",
        map_name="standard",
        current_turn=2,
        current_year=1901,
        current_season="Fall",
        current_phase="Adjustment",
        phase_code="F1901A",
        status="active",
        powers={
            "FRANCE": PowerState(
                power_name="FRANCE",
                units=[
                    Unit(unit_type="A", province="PAR", power="FRANCE"),
                    Unit(unit_type="A", province="MAR", power="FRANCE"),
                    Unit(unit_type="F", province="BRE", power="FRANCE")
                ],
                controlled_supply_centers=["PAR", "MAR", "BRE", "BUR"]  # 4 SCs, 3 units = build
            ),
            "GERMANY": PowerState(
                power_name="GERMANY",
                units=[
                    Unit(unit_type="A", province="BER", power="GERMANY"),
                    Unit(unit_type="A", province="MUN", power="GERMANY"),
                    Unit(unit_type="F", province="KIE", power="GERMANY"),
                    Unit(unit_type="A", province="SIL", power="GERMANY")
                ],
                controlled_supply_centers=["BER", "MUN", "KIE"]  # 3 SCs, 4 units = destroy
            )
        }
    )


# ============================================================================
# Order Fixtures
# ============================================================================

@pytest.fixture
def sample_move_order():
    """Create sample move order."""
    return MoveOrder(
        power="FRANCE",
        unit_type="A",
        unit_province="PAR",
        target_province="BUR",
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def sample_hold_order():
    """Create sample hold order."""
    return HoldOrder(
        power="FRANCE",
        unit_type="A",
        unit_province="MAR",
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def sample_support_order():
    """Create sample support order."""
    return SupportOrder(
        power="FRANCE",
        unit_type="F",
        unit_province="BRE",
        supported_unit_type="A",
        supported_unit_province="PAR",
        supported_target="BUR",
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def sample_convoy_order():
    """Create sample convoy order."""
    return ConvoyOrder(
        power="ENGLAND",
        unit_type="F",
        unit_province="NTH",
        convoyed_unit_type="A",
        convoyed_unit_province="LON",
        convoyed_target="HOL",
        convoy_chain=["ENG", "NTH"],
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def sample_retreat_order():
    """Create sample retreat order."""
    return RetreatOrder(
        power="FRANCE",
        unit_type="A",
        unit_province="PAR",
        retreat_province="PIC",
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def sample_build_order():
    """Create sample build order."""
    return BuildOrder(
        power="FRANCE",
        build_type="A",
        build_province="PAR",
        build_coast=None,
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def sample_destroy_order():
    """Create sample destroy order."""
    return DestroyOrder(
        power="GERMANY",
        unit_type="A",
        unit_province="SIL",
        status=OrderStatus.SUBMITTED
    )


@pytest.fixture
def order_set_comprehensive():
    """Create comprehensive set of all order types."""
    return [
        MoveOrder(
            power="FRANCE",
            unit_type="A",
            unit_province="PAR",
            target_province="BUR",
            status=OrderStatus.SUBMITTED
        ),
        HoldOrder(
            power="FRANCE",
            unit_type="A",
            unit_province="MAR",
            status=OrderStatus.SUBMITTED
        ),
        SupportOrder(
            power="FRANCE",
            unit_type="F",
            unit_province="BRE",
            supported_unit_type="A",
            supported_unit_province="PAR",
            supported_target="BUR",
            status=OrderStatus.SUBMITTED
        ),
        ConvoyOrder(
            power="ENGLAND",
            unit_type="F",
            unit_province="NTH",
            convoyed_unit_type="A",
            convoyed_unit_province="LON",
            convoyed_target="HOL",
            convoy_chain=["ENG", "NTH"],
            status=OrderStatus.SUBMITTED
        ),
        RetreatOrder(
            power="FRANCE",
            unit_type="A",
            unit_province="PAR",
            retreat_province="PIC",
            status=OrderStatus.SUBMITTED
        ),
        BuildOrder(
            power="FRANCE",
            build_type="A",
            build_province="PAR",
            build_coast=None,
            status=OrderStatus.SUBMITTED
        ),
        DestroyOrder(
            power="GERMANY",
            unit_type="A",
            unit_province="SIL",
            status=OrderStatus.SUBMITTED
        )
    ]


# ============================================================================
# Unit Fixtures
# ============================================================================

@pytest.fixture
def sample_army_unit():
    """Create sample army unit."""
    return Unit(unit_type="A", province="PAR", power="FRANCE")


@pytest.fixture
def sample_fleet_unit():
    """Create sample fleet unit."""
    return Unit(unit_type="F", province="BRE", power="FRANCE")


@pytest.fixture
def unit_set_france():
    """Create set of French units."""
    return [
        Unit(unit_type="A", province="PAR", power="FRANCE"),
        Unit(unit_type="A", province="MAR", power="FRANCE"),
        Unit(unit_type="F", province="BRE", power="FRANCE")
    ]


@pytest.fixture
def unit_set_germany():
    """Create set of German units."""
    return [
        Unit(unit_type="A", province="BER", power="GERMANY"),
        Unit(unit_type="A", province="MUN", power="GERMANY"),
        Unit(unit_type="F", province="KIE", power="GERMANY")
    ]


@pytest.fixture
def unit_set_england():
    """Create set of English units."""
    return [
        Unit(unit_type="A", province="LVP", power="ENGLAND"),
        Unit(unit_type="F", province="LON", power="ENGLAND"),
        Unit(unit_type="F", province="EDI", power="ENGLAND")
    ]


# ============================================================================
# Map and Province Fixtures
# ============================================================================

@pytest.fixture
def sample_province():
    """Create sample province."""
    return Province(
        name="PAR",
        type="land",
        is_supply_center=True,
        coast=None,
        adjacencies=["BUR", "PIC", "GAS"]
    )


@pytest.fixture
def sample_coastal_province():
    """Create sample coastal province."""
    return Province(
        name="SPA",
        type="coast",
        is_supply_center=True,
        coast="NC",
        adjacencies=["POR", "GAS", "MAR"]
    )


@pytest.fixture
def sample_map_data():
    """Create sample map data."""
    provinces = {
        "PAR": Province(
            name="PAR",
            type="land",
            is_supply_center=True,
            coast=None,
            adjacencies=["BUR", "PIC", "GAS"]
        ),
        "BUR": Province(
            name="BUR",
            type="land",
            is_supply_center=True,
            coast=None,
            adjacencies=["PAR", "BEL", "RUH"]
        ),
        "BRE": Province(
            name="BRE",
            type="coast",
            is_supply_center=True,
            coast="NC",
            adjacencies=["ENG", "PIC", "GAS"]
        )
    }
    
    return MapData(
        provinces=provinces,
        adjacencies={
            "PAR": ["BUR", "PIC", "GAS"],
            "BUR": ["PAR", "BEL", "RUH"],
            "BRE": ["ENG", "PIC", "GAS"]
        }
    )


# ============================================================================
# Turn and Phase Fixtures
# ============================================================================

@pytest.fixture
def sample_turn_state():
    """Create sample turn state."""
    return TurnState(
        turn=1,
        year=1901,
        season="Spring",
        phase="Movement",
        phase_code="S1901M"
    )


@pytest.fixture
def turn_history_sample():
    """Create sample turn history."""
    return [
        TurnState(turn=1, year=1901, season="Spring", phase="Movement", phase_code="S1901M"),
        TurnState(turn=2, year=1901, season="Spring", phase="Retreat", phase_code="S1901R"),
        TurnState(turn=3, year=1901, season="Spring", phase="Adjustment", phase_code="S1901A"),
        TurnState(turn=4, year=1901, season="Fall", phase="Movement", phase_code="F1901M"),
        TurnState(turn=5, year=1901, season="Fall", phase="Retreat", phase_code="F1901R"),
        TurnState(turn=6, year=1901, season="Fall", phase="Adjustment", phase_code="F1901A")
    ]


# ============================================================================
# Map Snapshot Fixtures
# ============================================================================

@pytest.fixture
def sample_map_snapshot():
    """Create sample map snapshot."""
    return MapSnapshot(
        game_id="test_game",
        turn=1,
        map_data=sample_map_data(),
        units={
            "FRANCE": [
                Unit(unit_type="A", province="PAR", power="FRANCE"),
                Unit(unit_type="F", province="BRE", power="FRANCE")
            ]
        },
        orders={
            "FRANCE": [
                MoveOrder(
                    power="FRANCE",
                    unit_type="A",
                    unit_province="PAR",
                    target_province="BUR",
                    status=OrderStatus.SUBMITTED
                )
            ]
        }
    )


# ============================================================================
# Utility Functions
# ============================================================================

def create_test_game_state(
    game_id: str = "test_game",
    map_name: str = "standard",
    turn: int = 0,
    year: int = 1901,
    season: str = "Spring",
    phase: str = "Movement",
    powers: Optional[Dict[str, PowerState]] = None
) -> GameState:
    """Create a test game state with specified parameters."""
    from datetime import datetime
    from engine.data_models import MapData, Province, GameStatus
    
    # Create minimal map data
    map_data = MapData(
        map_name=map_name,
        provinces={},
        supply_centers=[],
        home_supply_centers={},
        starting_positions={}
    )
    
    return GameState(
        game_id=game_id,
        map_name=map_name,
        current_turn=turn,
        current_year=year,
        current_season=season,
        current_phase=phase,
        phase_code=f"{season[0]}{year}{phase[0]}",
        status=GameStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        powers=powers or {},
        map_data=map_data,
        orders={}
    )


def create_test_power_state(
    power_name: str,
    units: Optional[List[Unit]] = None,
    orders: Optional[List[Order]] = None,
    supply_centers: Optional[List[str]] = None
) -> PowerState:
    """Create a test power state with specified parameters."""
    return PowerState(
        power_name=power_name,
        units=units or [],
        orders=orders or [],
        controlled_supply_centers=supply_centers or []
    )


def create_test_unit(
    unit_type: str,
    province: str,
    power: str
) -> Unit:
    """Create a test unit with specified parameters."""
    return Unit(unit_type=unit_type, province=province, power=power)


def create_test_move_order(
    power: str,
    unit_type: str,
    unit_province: str,
    target_province: str,
    status: OrderStatus = OrderStatus.SUBMITTED
) -> MoveOrder:
    """Create a test move order with specified parameters."""
    return MoveOrder(
        power=power,
        unit_type=unit_type,
        unit_province=unit_province,
        target_province=target_province,
        status=status
    )


def create_test_support_order(
    power: str,
    unit_type: str,
    unit_province: str,
    supported_unit_type: str,
    supported_unit_province: str,
    supported_target: str,
    status: OrderStatus = OrderStatus.SUBMITTED
) -> SupportOrder:
    """Create a test support order with specified parameters."""
    return SupportOrder(
        power=power,
        unit_type=unit_type,
        unit_province=unit_province,
        supported_unit_type=supported_unit_type,
        supported_unit_province=supported_unit_province,
        supported_target=supported_target,
        status=status
    )


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_map():
    """Create mock map object for testing."""
    mock_map = Mock()
    mock_map.provinces = {
        "PAR": Mock(type="land", is_supply_center=True),
        "MAR": Mock(type="land", is_supply_center=True),
        "BRE": Mock(type="coast", is_supply_center=True),
        "BER": Mock(type="land", is_supply_center=True),
        "MUN": Mock(type="land", is_supply_center=True),
        "KIE": Mock(type="coast", is_supply_center=True),
        "BUR": Mock(type="land", is_supply_center=True),
        "SIL": Mock(type="land", is_supply_center=True),
        "TYR": Mock(type="land", is_supply_center=True),
        "BAL": Mock(type="sea", is_supply_center=False)
    }
    
    # Mock adjacency data
    mock_map.get_adjacency = Mock(return_value=["BUR", "PIC"])
    mock_map.get_coast_adjacency = Mock(return_value=["ENG"])
    
    return mock_map


@pytest.fixture
def mock_order_parser():
    """Create mock order parser for testing."""
    mock_parser = Mock()
    mock_parser.parse = Mock(return_value=Mock(
        order_type=OrderType.MOVE,
        power="FRANCE",
        unit_type="A",
        unit_province="PAR",
        target_province="BUR"
    ))
    return mock_parser


# ============================================================================
# Test Data Constants
# ============================================================================

STANDARD_POWERS = [
    "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", 
    "ITALY", "RUSSIA", "TURKEY"
]

STANDARD_SUPPLY_CENTERS = {
    "AUSTRIA": ["BUD", "TRI", "VIE"],
    "ENGLAND": ["EDI", "LON", "LVP"],
    "FRANCE": ["BRE", "MAR", "PAR"],
    "GERMANY": ["BER", "KIE", "MUN"],
    "ITALY": ["NAP", "ROM", "VEN"],
    "RUSSIA": ["MOS", "SEV", "STP", "WAR"],
    "TURKEY": ["ANK", "CON", "SMY"]
}

STANDARD_STARTING_UNITS = {
    "AUSTRIA": [
        Unit(unit_type="A", province="BUD", power="AUSTRIA"),
        Unit(unit_type="A", province="VIE", power="AUSTRIA"),
        Unit(unit_type="F", province="TRI", power="AUSTRIA")
    ],
    "ENGLAND": [
        Unit(unit_type="A", province="LVP", power="ENGLAND"),
        Unit(unit_type="F", province="EDI", power="ENGLAND"),
        Unit(unit_type="F", province="LON", power="ENGLAND")
    ],
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
    "ITALY": [
        Unit(unit_type="A", province="VEN", power="ITALY"),
        Unit(unit_type="A", province="ROM", power="ITALY"),
        Unit(unit_type="F", province="NAP", power="ITALY")
    ],
    "RUSSIA": [
        Unit(unit_type="A", province="MOS", power="RUSSIA"),
        Unit(unit_type="A", province="WAR", power="RUSSIA"),
        Unit(unit_type="F", province="STP", power="RUSSIA"),
        Unit(unit_type="F", province="SEV", power="RUSSIA")
    ],
    "TURKEY": [
        Unit(unit_type="A", province="CON", power="TURKEY"),
        Unit(unit_type="A", province="SMY", power="TURKEY"),
        Unit(unit_type="F", province="ANK", power="TURKEY")
    ]
}
