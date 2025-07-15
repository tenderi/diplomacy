"""
SQLAlchemy models for persistent Diplomacy game storage (PostgreSQL).
"""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class GameModel(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, autoincrement=True)
    map_name = Column(String, nullable=False)
    state = Column(JSON, nullable=False)  # Serialized game state
    is_active = Column(Boolean, default=True)
    players = relationship("PlayerModel", back_populates="game")

class PlayerModel(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    power = Column(String, nullable=False)
    telegram_id = Column(String, nullable=True)
    game = relationship("GameModel", back_populates="players")
    orders = relationship("OrderModel", back_populates="player")

class OrderModel(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    order_text = Column(String, nullable=False)
    player = relationship("PlayerModel", back_populates="orders")
