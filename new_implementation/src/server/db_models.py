"""
SQLAlchemy models for persistent Diplomacy game storage (PostgreSQL).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, DateTime, Text, Index
from sqlalchemy.orm import declarative_base, relationship
import datetime

# Ensure UTC is available (Python 3.11+)
if not hasattr(datetime, "UTC"):
    from datetime import timezone
    datetime.UTC = timezone.utc

Base = declarative_base()

class GameModel(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, autoincrement=True)
    map_name = Column(String, nullable=False, index=True)  # Index for map-based queries
    state = Column(JSON, nullable=False)  # Serialized game state
    is_active = Column(Boolean, default=True, index=True)  # Index for active games filter
    deadline = Column(DateTime, nullable=True, index=True)  # Index for deadline-based queries
    players = relationship("PlayerModel", back_populates="game")
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('ix_games_active_deadline', is_active, deadline),  # For turn processing
        Index('ix_games_map_active', map_name, is_active),  # For map-based active games
    )

class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String, unique=True, nullable=False, index=True)  # Already unique, but explicit index
    full_name = Column(String, nullable=True, index=True)  # Index for name-based searches
    players = relationship("PlayerModel", back_populates="user")
    messages_sent = relationship("MessageModel", foreign_keys="MessageModel.sender_user_id", back_populates="sender")
    messages_received = relationship("MessageModel", foreign_keys="MessageModel.recipient_user_id", back_populates="recipient")

class PlayerModel(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    power = Column(String, nullable=False, index=True)
    telegram_id = Column(String, nullable=True, index=True)  # Deprecated: use user_id, but keep index for migration
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, index=True)  # Index for active players filter
    game = relationship("GameModel", back_populates="players")
    user = relationship("UserModel", back_populates="players")
    orders = relationship("OrderModel", back_populates="player")
    
    # Enhanced composite indexes for common query patterns
    __table_args__ = (
        Index('ix_players_game_id_power', game_id, power),  # Unique constraint replacement
        Index('ix_players_game_id_user_id', game_id, user_id),  # User's games
        Index('ix_players_game_active', game_id, is_active),  # Active players in game
        Index('ix_players_user_active', user_id, is_active),  # User's active games
        Index('ix_players_power_active', power, is_active),  # Power-based active players
    )

class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    order_text = Column(String, nullable=False, index=True)  # Index for order text searches
    turn = Column(Integer, nullable=False, default=0, index=True)  # Index for turn-based queries
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False, index=True)  # Index for chronological queries
    player = relationship("PlayerModel", back_populates="orders")
    
    # Enhanced composite indexes for order queries
    __table_args__ = (
        Index('ix_orders_player_id_turn', player_id, turn),  # Player's orders by turn
        Index('ix_orders_turn_created', turn, created_at),  # Orders by turn and creation time
        Index('ix_orders_player_created', player_id, created_at),  # Player's orders chronologically
    )

class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # For private messages
    recipient_power = Column(String, nullable=True, index=True)  # Null for broadcast, power name for private
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False, index=True)
    
    # Relationships
    sender = relationship("UserModel", foreign_keys=[sender_user_id], back_populates="messages_sent")
    recipient = relationship("UserModel", foreign_keys=[recipient_user_id], back_populates="messages_received")
    
    # Composite indexes for message queries
    __table_args__ = (
        Index('ix_messages_game_timestamp', game_id, timestamp),  # Game messages chronologically
        Index('ix_messages_sender_timestamp', sender_user_id, timestamp),  # User's sent messages
        Index('ix_messages_recipient_timestamp', recipient_user_id, timestamp),  # User's received messages
        Index('ix_messages_game_recipient', game_id, recipient_power),  # Game messages by recipient
        Index('ix_messages_timestamp_desc', timestamp.desc()),  # Recent messages (descending)
    )

class GameSnapshotModel(Base):
    __tablename__ = "game_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    turn = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)  # e.g., 1901, 1902, etc.
    season = Column(String, nullable=False)  # "Spring" or "Autumn"
    phase = Column(String, nullable=False)  # "Movement", "Retreat", "Builds"
    phase_code = Column(String, nullable=False)  # e.g., "S1901M", "S1901R", "A1901M", "A1901B"
    game_state = Column(JSON, nullable=False)  # Complete serialized game state
    map_image_path = Column(String, nullable=True)  # Path to generated map image
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)
    
    # Index for efficient queries
    __table_args__ = (
        Index('ix_snapshots_game_turn', game_id, turn),
        Index('ix_snapshots_game_phase', game_id, phase_code),
        Index('ix_snapshots_created_at', created_at),  # For cleanup
    )

class GameHistoryModel(Base):
    __tablename__ = "game_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    turn = Column(Integer, nullable=False, index=True)
    phase = Column(String, nullable=False, index=True)
    state = Column(JSON, nullable=False)  # Serialized game state snapshot
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), index=True)
    
    # Composite indexes for game history queries
    __table_args__ = (
        Index('ix_history_game_turn', game_id, turn),  # Game history by turn
        Index('ix_history_game_phase', game_id, phase),  # Game history by phase
        Index('ix_history_turn_timestamp', turn, timestamp),  # History by turn and time
        Index('ix_history_timestamp_desc', timestamp.desc()),  # Recent history (descending)
    )
