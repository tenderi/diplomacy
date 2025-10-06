"""
Database schema migration for Diplomacy game engine.

This migration implements the comprehensive database schema defined in data_spec.md
with proper foreign key relationships and data validation constraints.
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy import JSON
from datetime import datetime
import json

Base = declarative_base()


class GameModel(Base):
    """Games table"""
    __tablename__ = 'games'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(String(50), unique=True, nullable=False)
    map_name = Column(String(50), nullable=False, default='standard')
    current_turn = Column(Integer, nullable=False, default=0)
    current_year = Column(Integer, nullable=False, default=1901)
    current_season = Column(String(10), nullable=False, default='Spring')
    current_phase = Column(String(20), nullable=False, default='Movement')
    phase_code = Column(String(10), nullable=False, default='S1901M')
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    players = relationship("PlayerModel", back_populates="game", cascade="all, delete-orphan")
    units = relationship("UnitModel", back_populates="game", cascade="all, delete-orphan")
    orders = relationship("OrderModel", back_populates="game", cascade="all, delete-orphan")
    supply_centers = relationship("SupplyCenterModel", back_populates="game", cascade="all, delete-orphan")
    turn_history = relationship("TurnHistoryModel", back_populates="game", cascade="all, delete-orphan")
    map_snapshots = relationship("MapSnapshotModel", back_populates="game", cascade="all, delete-orphan")
    messages = relationship("MessageModel", back_populates="game", cascade="all, delete-orphan")


class UserModel(Base):
    """Users table (for Telegram integration)"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    username = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    players = relationship("PlayerModel", back_populates="user")
    messages_sent = relationship("MessageModel", foreign_keys="MessageModel.sender_user_id", back_populates="sender")
    messages_received = relationship("MessageModel", foreign_keys="MessageModel.recipient_user_id", back_populates="recipient")


class PlayerModel(Base):
    """Players/Powers table"""
    __tablename__ = 'players'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    power_name = Column(String(20), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    is_active = Column(Boolean, default=True)
    is_eliminated = Column(Boolean, default=False)
    home_supply_centers = Column(JSON, default=list)
    controlled_supply_centers = Column(JSON, default=list)
    orders_submitted = Column(Boolean, default=False)
    last_order_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('game_id', 'power_name', name='uq_game_power'),
    )
    
    # Relationships
    game = relationship("GameModel", back_populates="players")
    user = relationship("UserModel", back_populates="players")


class UnitModel(Base):
    """Units table"""
    __tablename__ = 'units'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    power_name = Column(String(20), nullable=False)
    unit_type = Column(String(1), nullable=False)
    province = Column(String(20), nullable=False)
    is_dislodged = Column(Boolean, default=False)
    dislodged_by = Column(String(20))
    can_retreat = Column(Boolean, default=True)
    retreat_options = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('game_id', 'province', name='uq_game_province'),
        CheckConstraint("unit_type IN ('A', 'F')", name='ck_unit_type'),
    )
    
    # Relationships
    game = relationship("GameModel", back_populates="units")


class OrderModel(Base):
    """Orders table"""
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    power_name = Column(String(20), nullable=False)
    order_type = Column(String(20), nullable=False)
    unit_type = Column(String(1), nullable=False)
    unit_province = Column(String(20), nullable=False)
    target_province = Column(String(20))
    supported_unit_type = Column(String(1))
    supported_unit_province = Column(String(20))
    supported_target = Column(String(20))
    convoyed_unit_type = Column(String(1))
    convoyed_unit_province = Column(String(20))
    convoyed_target = Column(String(20))
    convoy_chain = Column(JSON, default=list)
    build_type = Column(String(1))
    build_province = Column(String(20))
    build_coast = Column(String(10))
    destroy_unit_type = Column(String(1))
    destroy_unit_province = Column(String(20))
    status = Column(String(20), default='pending')
    failure_reason = Column(Text)
    phase = Column(String(20), nullable=False)
    turn_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("unit_type IN ('A', 'F')", name='ck_order_unit_type'),
        CheckConstraint("order_type IN ('move', 'hold', 'support', 'convoy', 'retreat', 'build', 'destroy')", name='ck_order_type'),
        CheckConstraint("status IN ('pending', 'success', 'failed', 'bounced')", name='ck_order_status'),
    )
    
    # Relationships
    game = relationship("GameModel", back_populates="orders")


class SupplyCenterModel(Base):
    """Supply centers table"""
    __tablename__ = 'supply_centers'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    province = Column(String(20), nullable=False)
    controlling_power = Column(String(20))
    is_home_supply_center = Column(Boolean, default=False)
    home_power = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('game_id', 'province', name='uq_game_supply_province'),
    )
    
    # Relationships
    game = relationship("GameModel", back_populates="supply_centers")


class TurnHistoryModel(Base):
    """Turn history table"""
    __tablename__ = 'turn_history'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    turn_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    season = Column(String(10), nullable=False)
    phase = Column(String(20), nullable=False)
    phase_code = Column(String(10), nullable=False)
    units_before = Column(JSON)
    units_after = Column(JSON)
    supply_centers_before = Column(JSON)
    supply_centers_after = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game = relationship("GameModel", back_populates="turn_history")


class MapSnapshotModel(Base):
    """Map snapshots table"""
    __tablename__ = 'map_snapshots'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    turn_number = Column(Integer, nullable=False)
    phase_code = Column(String(10), nullable=False)
    units = Column(JSON, nullable=False)
    supply_centers = Column(JSON, nullable=False)
    map_image_path = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game = relationship("GameModel", back_populates="map_snapshots")


class MessageModel(Base):
    """Messages table (for diplomatic communication)"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    sender_user_id = Column(Integer, ForeignKey('users.id'))
    sender_power = Column(String(20))
    recipient_user_id = Column(Integer, ForeignKey('users.id'))
    recipient_power = Column(String(20))
    message_type = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Constraints
    __table_args__ = (
        CheckConstraint("message_type IN ('private', 'broadcast', 'system')", name='ck_message_type'),
    )
    
    # Relationships
    game = relationship("GameModel", back_populates="messages")
    sender = relationship("UserModel", foreign_keys=[sender_user_id], back_populates="messages_sent")
    recipient = relationship("UserModel", foreign_keys=[recipient_user_id], back_populates="messages_received")


def create_database_schema(database_url: str):
    """Create the complete database schema"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def clear_database(database_url: str):
    """Clear all data from the database (for migration)"""
    engine = create_engine(database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(database_url: str):
    """Get a session factory for database operations"""
    engine = create_engine(database_url)
    return sessionmaker(bind=engine)


# Data conversion utilities
def unit_to_dict(unit) -> dict:
    """Convert Unit dataclass to dictionary for JSON storage"""
    return {
        "unit_type": unit.unit_type,
        "province": unit.province,
        "power": unit.power,
        "is_dislodged": unit.is_dislodged,
        "dislodged_by": unit.dislodged_by,
        "can_retreat": unit.can_retreat,
        "retreat_options": unit.retreat_options
    }


def dict_to_unit(data: dict):
    """Convert dictionary to Unit dataclass from JSON storage"""
    from .data_models import Unit
    return Unit(
        unit_type=data["unit_type"],
        province=data["province"],
        power=data["power"],
        is_dislodged=data.get("is_dislodged", False),
        dislodged_by=data.get("dislodged_by"),
        can_retreat=data.get("can_retreat", True),
        retreat_options=data.get("retreat_options", [])
    )


def order_to_dict(order) -> dict:
    """Convert Order dataclass to dictionary for JSON storage"""
    base_data = {
        "power": order.power,
        "unit": unit_to_dict(order.unit),
        "order_type": order.order_type.value if hasattr(order.order_type, 'value') else str(order.order_type),
        "phase": order.phase,
        "status": order.status.value if hasattr(order.status, 'value') else str(order.status),
        "failure_reason": order.failure_reason
    }
    
    # Add order-specific fields
    if hasattr(order, 'target_province'):
        base_data["target_province"] = order.target_province
    if hasattr(order, 'supported_unit'):
        base_data["supported_unit"] = unit_to_dict(order.supported_unit)
    if hasattr(order, 'supported_action'):
        base_data["supported_action"] = order.supported_action
    if hasattr(order, 'supported_target'):
        base_data["supported_target"] = order.supported_target
    if hasattr(order, 'convoyed_unit'):
        base_data["convoyed_unit"] = unit_to_dict(order.convoyed_unit)
    if hasattr(order, 'convoyed_target'):
        base_data["convoyed_target"] = order.convoyed_target
    if hasattr(order, 'convoy_chain'):
        base_data["convoy_chain"] = order.convoy_chain
    if hasattr(order, 'retreat_province'):
        base_data["retreat_province"] = order.retreat_province
    if hasattr(order, 'build_province'):
        base_data["build_province"] = order.build_province
    if hasattr(order, 'build_type'):
        base_data["build_type"] = order.build_type
    if hasattr(order, 'build_coast'):
        base_data["build_coast"] = order.build_coast
    if hasattr(order, 'destroy_unit'):
        base_data["destroy_unit"] = unit_to_dict(order.destroy_unit)
    
    return base_data


def dict_to_order(data: dict):
    """Convert dictionary to Order dataclass from JSON storage"""
    from .data_models import Order, MoveOrder, HoldOrder, SupportOrder, ConvoyOrder, RetreatOrder, BuildOrder, DestroyOrder, OrderType, OrderStatus, Unit
    
    # Convert unit data
    unit = dict_to_unit(data["unit"])
    
    # Determine order type and create appropriate order
    order_type = OrderType(data["order_type"])
    status = OrderStatus(data["status"])
    
    if order_type == OrderType.MOVE:
        return MoveOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason"),
            target_province=data["target_province"],
            is_convoyed=data.get("is_convoyed", False),
            convoy_route=data.get("convoy_route", [])
        )
    elif order_type == OrderType.HOLD:
        return HoldOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason")
        )
    elif order_type == OrderType.SUPPORT:
        supported_unit = dict_to_unit(data["supported_unit"])
        return SupportOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason"),
            supported_unit=supported_unit,
            supported_action=data["supported_action"],
            supported_target=data.get("supported_target")
        )
    elif order_type == OrderType.CONVOY:
        convoyed_unit = dict_to_unit(data["convoyed_unit"])
        return ConvoyOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason"),
            convoyed_unit=convoyed_unit,
            convoyed_target=data["convoyed_target"],
            convoy_chain=data.get("convoy_chain", [])
        )
    elif order_type == OrderType.RETREAT:
        return RetreatOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason"),
            retreat_province=data["retreat_province"]
        )
    elif order_type == OrderType.BUILD:
        return BuildOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason"),
            build_province=data["build_province"],
            build_type=data["build_type"],
            build_coast=data.get("build_coast")
        )
    elif order_type == OrderType.DESTROY:
        destroy_unit = dict_to_unit(data["destroy_unit"])
        return DestroyOrder(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason"),
            destroy_unit=destroy_unit
        )
    else:
        return Order(
            power=data["power"],
            unit=unit,
            order_type=order_type,
            phase=data["phase"],
            status=status,
            failure_reason=data.get("failure_reason")
        )
