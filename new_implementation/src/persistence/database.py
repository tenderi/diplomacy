"""
Database schema migration for Diplomacy game engine.

This migration implements the comprehensive database schema defined in data_spec.md
with proper foreign key relationships and data validation constraints.
"""

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, CheckConstraint, Index, text, inspect
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy import JSON
from datetime import datetime

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
    # New engine (M6): the whole GameState serialized via engine.serialization, plus the
    # submitted-but-not-yet-adjudicated orders keyed by power ({power: [order_str]}).
    # These supersede the legacy relational units/orders/supply_centers storage.
    state_json = Column(JSON, nullable=True)
    pending_orders = Column(JSON, nullable=True)
    # The most recent adjudication result (engine.serialization.resolution_to_dict),
    # kept only for rendering the resolution map after a turn is processed.
    last_resolution = Column(JSON, nullable=True)
    # Per-turn history of the orders players submitted, {turn: {power: [order_str]}},
    # appended each process_turn. Powers the /orders/history endpoint (state itself is
    # a single snapshot and does not retain past orders).
    order_history = Column(JSON, nullable=True)
    deadline = Column(DateTime, nullable=True)  # Optional deadline for turn processing
    channel_id = Column(String(255), nullable=True)  # Telegram channel ID for channel-linked games
    channel_settings = Column(JSON, nullable=True)  # Channel settings (auto_post_maps, etc.)
    observer_mode = Column(Boolean, default=False, nullable=True)  # If True, non-players can spectate
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
    spectators = relationship("SpectatorModel", back_populates="game", cascade="all, delete-orphan")


class UserModel(Base):
    """Users table (browser + Telegram). At least one of email or telegram_id must be set."""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=True)  # For browser login
    password_hash = Column(String(255), nullable=True)  # For browser login
    telegram_id = Column(String(255), unique=True, nullable=True)  # For Telegram; null until linked from web
    full_name = Column(String(255), nullable=False)
    username = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    players = relationship("PlayerModel", back_populates="user")
    messages_sent = relationship("MessageModel", foreign_keys="MessageModel.sender_user_id", back_populates="sender")
    # Note: messages_received removed - recipient_user_id doesn't exist in database schema
    link_codes = relationship("LinkCodeModel", back_populates="user", cascade="all, delete-orphan")


class LinkCodeModel(Base):
    """One-time codes for linking Telegram to a browser account."""
    __tablename__ = 'link_codes'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    code = Column(String(32), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("UserModel", back_populates="link_codes")


class PasswordResetTokenModel(Base):
    """One-time tokens for password reset (forgot password flow)."""
    __tablename__ = 'password_reset_tokens'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("UserModel", backref="password_reset_tokens")


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
    
    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint('game_id', 'power_name', name='uq_game_power'),
        Index('ix_players_game', 'game_id'),
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
    
    # Constraints and indexes
    __table_args__ = (
        CheckConstraint("unit_type IN ('A', 'F')", name='ck_order_unit_type'),
        CheckConstraint("order_type IN ('move', 'hold', 'support', 'convoy', 'retreat', 'build', 'destroy')", name='ck_order_type'),
        CheckConstraint("status IN ('pending', 'submitted', 'success', 'failed', 'bounced')", name='ck_order_status'),
        Index('ix_orders_game_turn', 'game_id', 'turn_number'),
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
    sender_user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    recipient_power = Column(String(20), nullable=True)
    text = Column(Text, nullable=False)  # Actual column name is 'text', not 'content'
    timestamp = Column(DateTime, nullable=False)  # Actual column name is 'timestamp', not 'created_at'
    
    # Constraints and indexes
    __table_args__ = (
        Index('ix_messages_game', 'game_id'),
    )
    
    # Relationships
    game = relationship("GameModel", back_populates="messages")
    sender = relationship("UserModel", foreign_keys=[sender_user_id], back_populates="messages_sent")
    # Note: recipient_user_id doesn't exist in database schema, only recipient_power


class ChannelMessageModel(Base):
    """Channel messages table (for Telegram channel integration)"""
    __tablename__ = 'channel_messages'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    channel_id = Column(String(255), nullable=False)
    message_id = Column(Integer, nullable=False)
    message_type = Column(String(50), nullable=False)  # 'map', 'broadcast', 'notification', 'battle_results', 'dashboard', 'timeline'
    content = Column(Text)
    thread_id = Column(Integer, nullable=True)  # For forum topics/threads
    parent_message_id = Column(Integer, nullable=True)  # For reply threading
    reaction_counts = Column(JSON, nullable=True)  # JSONB for reaction tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game = relationship("GameModel")


class ChannelProposalModel(Base):
    """Channel proposals table (for voting on proposals)"""
    __tablename__ = 'channel_proposals'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    channel_id = Column(String(255), nullable=False)
    message_id = Column(Integer, nullable=False)
    proposal_title = Column(String(255))
    proposal_text = Column(Text, nullable=False)
    power = Column(String(20), nullable=False)
    votes_support = Column(Integer, default=0)
    votes_oppose = Column(Integer, default=0)
    votes_undecided = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game = relationship("GameModel")


class ChannelTimelineEventModel(Base):
    """Channel timeline events table (for historical timeline)"""
    __tablename__ = 'channel_timeline_events'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    turn_number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    season = Column(String(10), nullable=False)
    phase = Column(String(20), nullable=False)
    event_type = Column(String(50), nullable=False)  # 'elimination', 'major_battle', 'supply_change', 'victory'
    event_description = Column(Text, nullable=False)
    power = Column(String(20), nullable=True)  # Power involved in event
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    game = relationship("GameModel")


class ChannelAnalyticsModel(Base):
    """Channel analytics table (for tracking engagement metrics)"""
    __tablename__ = 'channel_analytics'
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    channel_id = Column(String(255), nullable=False)
    event_type = Column(String(50), nullable=False)  # 'message_posted', 'player_activity', 'order_submitted', 'vote_cast', 'message_read'
    event_subtype = Column(String(50), nullable=True)  # 'map', 'broadcast', 'battle_results', 'dashboard', 'notification'
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # User who triggered the event
    power = Column(String(20), nullable=True)  # Power associated with the event
    event_data = Column(JSON, nullable=True)  # Additional event data (message_id, response_time, etc.)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('ix_channel_analytics_game_channel', 'game_id', 'channel_id'),
        Index('ix_channel_analytics_event_type', 'event_type'),
        Index('ix_channel_analytics_created_at', 'created_at'),
        Index('ix_channel_analytics_user', 'user_id'),
    )
    
    # Relationships
    game = relationship("GameModel")
    user = relationship("UserModel")


class TournamentModel(Base):
    """Tournaments table (for bracket/tournament organization)."""
    __tablename__ = 'tournaments'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default='pending')  # 'pending', 'active', 'completed', 'cancelled'
    bracket_type = Column(String(50), nullable=True)  # 'single_elimination', 'double_elimination', 'round_robin'
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    games = relationship("TournamentGameModel", back_populates="tournament", cascade="all, delete-orphan")
    players = relationship("TournamentPlayerModel", back_populates="tournament", cascade="all, delete-orphan")


class TournamentGameModel(Base):
    """Tournament games (links games to tournaments and rounds)."""
    __tablename__ = 'tournament_games'

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id', ondelete='CASCADE'), nullable=False)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    round_number = Column(Integer, nullable=False, default=1)
    bracket_position = Column(String(50), nullable=True)  # e.g. '1', '2', 'semifinal_1'
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('tournament_id', 'game_id', name='uq_tournament_game'),
        Index('ix_tournament_games_tournament', 'tournament_id'),
    )

    tournament = relationship("TournamentModel", back_populates="games")
    game = relationship("GameModel")


class TournamentPlayerModel(Base):
    """Tournament players (participants with optional seed/rank)."""
    __tablename__ = 'tournament_players'

    id = Column(Integer, primary_key=True)
    tournament_id = Column(Integer, ForeignKey('tournaments.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    seed = Column(Integer, nullable=True)
    final_rank = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('tournament_id', 'user_id', name='uq_tournament_user'),
        Index('ix_tournament_players_tournament', 'tournament_id'),
    )

    tournament = relationship("TournamentModel", back_populates="players")
    user = relationship("UserModel")


class SpectatorModel(Base):
    """Spectators table: users who observe a game without playing."""
    __tablename__ = 'spectators'

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('game_id', 'user_id', name='uq_spectator_game_user'),
        Index('ix_spectators_game', 'game_id'),
    )

    game = relationship("GameModel")
    user = relationship("UserModel")


def create_database_schema(database_url: str):
    """Create the complete database schema"""
    engine = create_engine(database_url)
    # Create all tables - this auto-commits in SQLAlchemy
    Base.metadata.create_all(engine)
    
    # Ensure all columns exist (handle case where table exists but columns are missing)
    # This is a safety check for columns that might have been added to models after table creation
    inspector_instance = inspect(engine)
    table_names = inspector_instance.get_table_names()
    
    with engine.begin() as conn:
        if 'users' in table_names:
            users_columns = [col['name'] for col in inspector_instance.get_columns('users')]
            
            # Add missing columns if they don't exist
            if 'is_active' not in users_columns:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT true"))
                    conn.execute(text("UPDATE users SET is_active = true WHERE is_active IS NULL"))
                    conn.execute(text("ALTER TABLE users ALTER COLUMN is_active SET NOT NULL"))
                except Exception:
                    # If column already exists or other error, continue
                    pass
            
            if 'created_at' not in users_columns:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))
                    conn.execute(text("UPDATE users SET created_at = NOW() WHERE created_at IS NULL"))
                    conn.execute(text("ALTER TABLE users ALTER COLUMN created_at SET NOT NULL"))
                    conn.execute(text("ALTER TABLE users ALTER COLUMN created_at SET DEFAULT NOW()"))
                except Exception:
                    pass
            
            if 'updated_at' not in users_columns:
                try:
                    conn.execute(text("ALTER TABLE users ADD COLUMN updated_at TIMESTAMP"))
                    conn.execute(text("UPDATE users SET updated_at = NOW() WHERE updated_at IS NULL"))
                    conn.execute(text("ALTER TABLE users ALTER COLUMN updated_at SET NOT NULL"))
                    conn.execute(text("ALTER TABLE users ALTER COLUMN updated_at SET DEFAULT NOW()"))
                except Exception:
                    pass
        
        # Force a commit by executing a simple query
        conn.execute(text("SELECT 1"))
    
    # Dispose engine to ensure all connections are closed
    engine.dispose()
    # Return a new engine for the caller to use
    return create_engine(database_url)


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

