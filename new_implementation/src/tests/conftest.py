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
from server.db_models import Base
from server.db_session import SessionLocal


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp()
    
    # Create SQLAlchemy engine
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create session factory
    SessionLocal.configure(bind=engine)
    
    yield engine
    
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def db_session(temp_db):
    """Create a database session for testing."""
    session = SessionLocal()
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
    game_state = GameState(
        game_id="test_game_001",
        map_name="standard",
        current_turn=3,
        current_year=1901,
        current_season="Fall",
        current_phase="Movement",
        phase_code="F1901M",
        status="active"
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
