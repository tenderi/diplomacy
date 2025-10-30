"""
Shared pytest fixtures for Diplomacy tests.

This module provides common fixtures used across test modules to ensure
consistent test setup and reduce code duplication.
"""

import pytest
import tempfile
import os
from typing import Generator, Dict, Any
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from engine.game import Game
from engine.data_models import GameState, PowerState, Unit, OrderType, OrderStatus
# Legacy DB modules removed in spec-only implementation; keep tests resilient
Base = None  # type: ignore
SessionLocal = None  # type: ignore


@pytest.fixture
def temp_db():
    """Optional database engine for tests that need it; skips if DB URL missing."""
    db_url = os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")
    if not db_url:
        pytest.skip("Database URL not configured; skipping DB-dependent fixtures")
    engine = create_engine(db_url, echo=False)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(temp_db):
    """Create a database session for testing using sessionmaker; skips if not configured."""
    Session = sessionmaker(bind=temp_db)  # type: ignore
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def standard_game():
    """Create a standard Diplomacy game in 1901 Spring Movement phase."""
    game = Game('standard')
    
    # Add all 7 powers
    powers = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']
    for power in powers:
        game.add_player(power)
    
    return game


@pytest.fixture
def mid_game_state():
    """Create a mid-game state with units and orders."""
    from datetime import datetime
    from engine.data_models import MapData, GameStatus, Province
    
    map_data = MapData(
        map_name="standard",
        provinces={
            "PAR": Province(name="PAR", province_type="inland", adjacent_provinces=["BUR", "PIC", "BRE"], is_supply_center=True, is_home_supply_center=True),
            "MAR": Province(name="MAR", province_type="coastal", adjacent_provinces=["BUR", "GAS", "PIE"], is_supply_center=True, is_home_supply_center=True),
            "BRE": Province(name="BRE", province_type="coastal", adjacent_provinces=["PAR", "PIC", "GAS"], is_supply_center=True, is_home_supply_center=True),
            "BER": Province(name="BER", province_type="coastal", adjacent_provinces=["MUN", "SIL", "BAL"], is_supply_center=True, is_home_supply_center=True),
            "MUN": Province(name="MUN", province_type="inland", adjacent_provinces=["BER", "SIL", "BUR"], is_supply_center=True, is_home_supply_center=True),
            "KIE": Province(name="KIE", province_type="sea", adjacent_provinces=["BER", "BAL", "DEN"], is_supply_center=True, is_home_supply_center=True),
            "BUR": Province(name="BUR", province_type="inland", adjacent_provinces=["PAR", "MAR", "MUN"], is_supply_center=False, is_home_supply_center=False),
            "SIL": Province(name="SIL", province_type="inland", adjacent_provinces=["BER", "MUN", "WAR"], is_supply_center=False, is_home_supply_center=False),
            "BAL": Province(name="BAL", province_type="sea", adjacent_provinces=["BER", "KIE", "DEN"], is_supply_center=False, is_home_supply_center=False),
            "PIC": Province(name="PIC", province_type="coastal", adjacent_provinces=["PAR", "BUR", "BEL"], is_supply_center=False, is_home_supply_center=False),
            "GAS": Province(name="GAS", province_type="coastal", adjacent_provinces=["MAR", "BUR", "BRE"], is_supply_center=False, is_home_supply_center=False),
            "PIE": Province(name="PIE", province_type="coastal", adjacent_provinces=["MAR", "VEN"], is_supply_center=False, is_home_supply_center=False),
            "DEN": Province(name="DEN", province_type="coastal", adjacent_provinces=["KIE", "BAL", "SWE"], is_supply_center=True, is_home_supply_center=False),
            "BEL": Province(name="BEL", province_type="coastal", adjacent_provinces=["PIC", "HOL"], is_supply_center=True, is_home_supply_center=False),
            "HOL": Province(name="HOL", province_type="coastal", adjacent_provinces=["BEL", "RUH"], is_supply_center=True, is_home_supply_center=False),
            "RUH": Province(name="RUH", province_type="inland", adjacent_provinces=["HOL", "MUN"], is_supply_center=False, is_home_supply_center=False),
            "VEN": Province(name="VEN", province_type="coastal", adjacent_provinces=["PIE", "TRI"], is_supply_center=True, is_home_supply_center=False),
            "TRI": Province(name="TRI", province_type="coastal", adjacent_provinces=["VEN", "VIE"], is_supply_center=True, is_home_supply_center=False),
            "VIE": Province(name="VIE", province_type="inland", adjacent_provinces=["TRI", "BUD"], is_supply_center=True, is_home_supply_center=False),
            "BUD": Province(name="BUD", province_type="inland", adjacent_provinces=["VIE", "SER"], is_supply_center=True, is_home_supply_center=False),
            "SER": Province(name="SER", province_type="inland", adjacent_provinces=["BUD", "BUL"], is_supply_center=True, is_home_supply_center=False),
            "BUL": Province(name="BUL", province_type="coastal", adjacent_provinces=["SER", "CON"], is_supply_center=True, is_home_supply_center=False),
            "CON": Province(name="CON", province_type="coastal", adjacent_provinces=["BUL", "ANK"], is_supply_center=True, is_home_supply_center=False),
            "ANK": Province(name="ANK", province_type="coastal", adjacent_provinces=["CON", "SMI"], is_supply_center=True, is_home_supply_center=False),
            "SMI": Province(name="SMI", province_type="coastal", adjacent_provinces=["ANK", "ARM"], is_supply_center=True, is_home_supply_center=False),
            "ARM": Province(name="ARM", province_type="coastal", adjacent_provinces=["SMI", "SEV"], is_supply_center=True, is_home_supply_center=False),
            "SEV": Province(name="SEV", province_type="coastal", adjacent_provinces=["ARM", "MOS"], is_supply_center=True, is_home_supply_center=False),
            "MOS": Province(name="MOS", province_type="inland", adjacent_provinces=["SEV", "WAR"], is_supply_center=True, is_home_supply_center=False),
            "WAR": Province(name="WAR", province_type="inland", adjacent_provinces=["MOS", "SIL"], is_supply_center=True, is_home_supply_center=False),
            "SWE": Province(name="SWE", province_type="coastal", adjacent_provinces=["DEN", "NOR"], is_supply_center=True, is_home_supply_center=False),
            "NOR": Province(name="NOR", province_type="coastal", adjacent_provinces=["SWE", "STP"], is_supply_center=True, is_home_supply_center=False),
            "STP": Province(name="STP", province_type="coastal", adjacent_provinces=["NOR", "MOS"], is_supply_center=True, is_home_supply_center=False)
        },
        supply_centers=["PAR", "MAR", "BRE", "BER", "MUN", "KIE", "DEN", "BEL", "HOL", "VEN", "TRI", "VIE", "BUD", "SER", "BUL", "CON", "ANK", "SMI", "ARM", "SEV", "MOS", "WAR", "SWE", "NOR", "STP"],
        home_supply_centers={
            "FRANCE": ["PAR", "MAR", "BRE"],
            "GERMANY": ["BER", "MUN", "KIE"]
        },
        starting_positions={}
    )
    
    game_state = GameState(
        game_id="test_game_001",
        map_name="standard",
        current_turn=3,
        current_year=1901,
        current_season="Fall",
        current_phase="Movement",
        phase_code="F1901M",
        status=GameStatus.ACTIVE,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        powers={},
        map_data=map_data,
        orders={}
    )
    
    # Add power states with units
    france_units = [
        Unit(unit_type="A", province="PAR", power="FRANCE"),
        Unit(unit_type="A", province="MAR", power="FRANCE"),
        Unit(unit_type="F", province="BRE", power="FRANCE")
    ]
    
    germany_units = [
        Unit(unit_type="A", province="BER", power="GERMANY"),
        Unit(unit_type="A", province="MUN", power="GERMANY"),
        Unit(unit_type="F", province="KIE", power="GERMANY")
    ]
    
    game_state.powers = {
        "FRANCE": PowerState(
            power_name="FRANCE",
            units=france_units,
            controlled_supply_centers=["PAR", "MAR", "BRE"]
        ),
        "GERMANY": PowerState(
            power_name="GERMANY", 
            units=germany_units,
            controlled_supply_centers=["BER", "MUN", "KIE"]
        )
    }
    
    # Initialize empty orders
    game_state.orders = {
        "FRANCE": [],
        "GERMANY": []
    }
    
    return game_state


@pytest.fixture
def mock_telegram_context():
    """Create a mock Telegram bot context for testing."""
    context = Mock()
    context.bot = Mock()
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    
    # Mock common bot methods
    context.bot.send_message = Mock()
    context.bot.edit_message_text = Mock()
    context.bot.answer_callback_query = Mock()
    
    return context


@pytest.fixture
def mock_telegram_update():
    """Create a mock Telegram update for testing."""
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_chat = Mock()
    update.effective_chat.id = 67890
    update.callback_query = None
    update.message = Mock()
    update.message.text = "/test"
    update.message.reply_text = Mock()
    update.message.reply_markup = Mock()
    
    return update


@pytest.fixture
def sample_orders():
    """Sample orders for testing."""
    return {
        "FRANCE": [
            {"type": "move", "unit": "A PAR", "target": "BUR", "status": "success"},
            {"type": "hold", "unit": "A MAR", "status": "success"},
            {"type": "support", "unit": "F BRE", "supporting": "A PAR", "supported_target": "BUR", "status": "success"}
        ],
        "GERMANY": [
            {"type": "move", "unit": "A BER", "target": "SIL", "status": "success"},
            {"type": "move", "unit": "A MUN", "target": "TYR", "status": "failed", "reason": "bounced"},
            {"type": "convoy", "unit": "F KIE", "target": "BAL", "via": ["BAL"], "status": "success"}
        ]
    }


@pytest.fixture
def mock_map():
    """Create a mock map object for testing."""
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


@pytest.fixture(scope="session")
def test_data_dir():
    """Provide path to test data directory."""
    return os.path.join(os.path.dirname(__file__), "..", "..", "test_data")


@pytest.fixture
def cleanup_temp_files():
    """Fixture to clean up temporary files after tests."""
    temp_files = []
    
    def add_temp_file(filepath: str):
        temp_files.append(filepath)
    
    yield add_temp_file
    
    # Cleanup
    for filepath in temp_files:
        if os.path.exists(filepath):
            os.remove(filepath)


# Markers for test categorization
pytestmark = [
    pytest.mark.unit,  # Default to unit tests
]
