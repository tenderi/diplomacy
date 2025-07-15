"""
SQLAlchemy models for persistent Diplomacy game storage (PostgreSQL).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, relationship
import datetime

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
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    power = Column(String, nullable=False)
    telegram_id = Column(String, nullable=True)  # Deprecated: use user_id
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    game = relationship("GameModel", back_populates="players")
    user = relationship("UserModel", back_populates="players")
    orders = relationship("OrderModel", back_populates="player")

class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    order_text = Column(String, nullable=False)
    turn = Column(Integer, nullable=False, default=0)  # New column for turn number
    player = relationship("PlayerModel", back_populates="orders")

class MessageModel(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    sender_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recipient_power = Column(String, nullable=True)  # Null for broadcast
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
