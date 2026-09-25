"""Drop the unused tables (Track AR)

Nothing reads or writes them: game state lives in ``games.state_json`` and the per-turn
boards in ``map_snapshots``. ``units``, ``orders``, ``supply_centers`` and
``turn_history`` predate that; ``game_history`` and ``game_snapshots`` came with the
initial schema and had no model at all. ``channel_messages``, ``channel_proposals`` and
``channel_timeline_events`` were models only -- no migration created them, so they exist
only where the schema autoupdater's ``create_all`` ran. All six migrated tables were
checked empty in production on 2026-09-25 before this was written.

The downgrade recreates the six migrated tables, empty, exactly as production had them
(from ``pg_dump -s``); the three model-only tables were never part of the migrated schema.

Revision ID: o3c9d0e1f2a3
Revises: n2b8c9d0e1f2
Create Date: 2026-09-25
"""

from alembic import op

revision = "o3c9d0e1f2a3"
down_revision = "n2b8c9d0e1f2"
branch_labels = None
depends_on = None

_TABLES = (
    "units",
    "orders",
    "supply_centers",
    "turn_history",
    "game_history",
    "game_snapshots",
    "channel_messages",
    "channel_proposals",
    "channel_timeline_events",
)

_RECREATE = """
CREATE TABLE units (
    id SERIAL PRIMARY KEY,
    game_id integer NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    power_name varchar(20) NOT NULL,
    unit_type varchar(1) NOT NULL,
    province varchar(20) NOT NULL,
    is_dislodged boolean DEFAULT false,
    dislodged_by varchar(20),
    can_retreat boolean DEFAULT true,
    retreat_options json DEFAULT '[]'::json,
    created_at timestamp without time zone,
    CONSTRAINT ck_unit_type CHECK (unit_type IN ('A', 'F')),
    CONSTRAINT uq_game_province UNIQUE (game_id, province)
);
CREATE INDEX ix_units_game ON units (game_id);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    created_at timestamp without time zone NOT NULL,
    game_id integer NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    power_name varchar(20) NOT NULL,
    order_type varchar(20) NOT NULL,
    unit_type varchar(1) NOT NULL,
    unit_province varchar(20) NOT NULL,
    target_province varchar(20),
    supported_unit_type varchar(1),
    supported_unit_province varchar(20),
    supported_target varchar(20),
    convoyed_unit_type varchar(1),
    convoyed_unit_province varchar(20),
    convoyed_target varchar(20),
    convoy_chain json,
    build_type varchar(1),
    build_province varchar(20),
    build_coast varchar(10),
    destroy_unit_type varchar(1),
    destroy_unit_province varchar(20),
    status varchar(20) DEFAULT 'pending',
    failure_reason text,
    phase varchar(20) NOT NULL,
    turn_number integer NOT NULL,
    CONSTRAINT ck_order_status
        CHECK (status IN ('pending', 'submitted', 'success', 'failed', 'bounced')),
    CONSTRAINT ck_order_type
        CHECK (order_type IN ('move', 'hold', 'support', 'convoy', 'retreat', 'build', 'destroy')),
    CONSTRAINT ck_order_unit_type CHECK (unit_type IN ('A', 'F'))
);
CREATE INDEX ix_orders_created_at ON orders (created_at);
CREATE INDEX ix_orders_game_turn ON orders (game_id, turn_number);

CREATE TABLE supply_centers (
    id SERIAL PRIMARY KEY,
    game_id integer NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    province varchar(20) NOT NULL,
    controlling_power varchar(20),
    is_home_supply_center boolean DEFAULT false,
    home_power varchar(20),
    created_at timestamp without time zone,
    CONSTRAINT uq_game_supply_province UNIQUE (game_id, province)
);
CREATE INDEX ix_supply_centers_game ON supply_centers (game_id);

CREATE TABLE turn_history (
    id SERIAL PRIMARY KEY,
    game_id integer NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    turn_number integer NOT NULL,
    year integer NOT NULL,
    season varchar(10) NOT NULL,
    phase varchar(20) NOT NULL,
    phase_code varchar(10) NOT NULL,
    units_before json,
    units_after json,
    supply_centers_before json,
    supply_centers_after json,
    created_at timestamp without time zone DEFAULT now()
);
CREATE INDEX ix_turn_history_game_id ON turn_history (game_id);

CREATE TABLE game_history (
    id SERIAL PRIMARY KEY,
    game_id integer NOT NULL REFERENCES games(id),
    turn integer NOT NULL,
    phase varchar NOT NULL,
    state json NOT NULL,
    "timestamp" timestamp without time zone
);
CREATE INDEX ix_game_history_game_id ON game_history (game_id);
CREATE INDEX ix_game_history_phase ON game_history (phase);
CREATE INDEX ix_game_history_timestamp ON game_history ("timestamp");
CREATE INDEX ix_game_history_turn ON game_history (turn);
CREATE INDEX ix_history_game_phase ON game_history (game_id, phase);
CREATE INDEX ix_history_game_turn ON game_history (game_id, turn);
CREATE INDEX ix_history_timestamp_desc ON game_history ("timestamp" DESC);
CREATE INDEX ix_history_turn_timestamp ON game_history (turn, "timestamp");

CREATE TABLE game_snapshots (
    id SERIAL PRIMARY KEY,
    game_id integer NOT NULL REFERENCES games(id),
    turn integer NOT NULL,
    year integer NOT NULL,
    season varchar NOT NULL,
    phase varchar NOT NULL,
    phase_code varchar NOT NULL,
    game_state json NOT NULL,
    map_image_path varchar,
    created_at timestamp without time zone NOT NULL
);
CREATE INDEX ix_game_snapshots_game_id ON game_snapshots (game_id);
CREATE INDEX ix_snapshots_created_at ON game_snapshots (created_at);
CREATE INDEX ix_snapshots_game_phase ON game_snapshots (game_id, phase_code);
CREATE INDEX ix_snapshots_game_turn ON game_snapshots (game_id, turn);
"""


def upgrade() -> None:
    # IF EXISTS: the channel_* tables exist only where create_all ran, and a database
    # built by the autoupdater may lack game_history/game_snapshots.
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")


def downgrade() -> None:
    op.execute(_RECREATE)
