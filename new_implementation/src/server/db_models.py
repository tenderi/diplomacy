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
    map_name = Column(String, nullable=False)
    state = Column(JSON, nullable=False)  # Serialized game state
    is_active = Column(Boolean, default=True)
    deadline = Column(DateTime, nullable=True)  # Deadline for current turn
    players = relationship("PlayerModel", back_populates="game")

class UserModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String, unique=True, nullable=False)
    full_name = Column(String, nullable=True)
    players = relationship("PlayerModel", back_populates="user")

class PlayerModel(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    power = Column(String, nullable=False, index=True)
    telegram_id = Column(String, nullable=True)  # Deprecated: use user_id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)  # New: track if player is active
    game = relationship("GameModel", back_populates="players")
    user = relationship("UserModel", back_populates="players")
    orders = relationship("OrderModel", back_populates="player")

Index('ix_players_game_id_power', PlayerModel.game_id, PlayerModel.power)
Index('ix_players_game_id_user_id', PlayerModel.game_id, PlayerModel.user_id)

class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, index=True)
    order_text = Column(String, nullable=False)
    turn = Column(Integer, nullable=False, default=0)  # New column for turn number
    player = relationship("PlayerModel", back_populates="orders")

Index('ix_orders_player_id_turn', OrderModel.player_id, OrderModel.turn)

class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_power = Column(String, nullable=True)  # Null for broadcast
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC), nullable=False)

class GameHistoryModel(Base):
    __tablename__ = "game_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    turn = Column(Integer, nullable=False)
    phase = Column(String, nullable=False)
    state = Column(JSON, nullable=False)  # Serialized game state snapshot
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
