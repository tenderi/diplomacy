"""rename_power_to_power_name_in_players

Revision ID: bd48b54f9c5f
Revises: d9ade8d1818f
Create Date: 2025-10-31 11:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bd48b54f9c5f'
down_revision: Union[str, Sequence[str], None] = 'd9ade8d1818f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename power column to power_name in players table to match model."""
    # Drop old indexes first (use raw SQL to avoid transaction issues)
    op.execute("""
        DROP INDEX IF EXISTS ix_players_power;
        DROP INDEX IF EXISTS ix_players_game_id_power;
        DROP INDEX IF EXISTS ix_players_power_active;
    """)
    
    # Drop unique constraint if it exists
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ix_players_game_id_power') THEN
                ALTER TABLE players DROP CONSTRAINT ix_players_game_id_power;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_game_power') THEN
                ALTER TABLE players DROP CONSTRAINT uq_game_power;
            END IF;
        END $$;
    """)
    
    # Rename the column using raw SQL
    op.execute("ALTER TABLE players RENAME COLUMN power TO power_name")
    
    # Recreate indexes with new column name
    op.create_index('ix_players_power_name', 'players', ['power_name'])
    op.create_index('ix_players_game_id_power_name', 'players', ['game_id', 'power_name'])
    op.create_index('ix_players_power_name_active', 'players', ['power_name', 'is_active'])
    
    # Create unique constraint with new column name
    op.create_unique_constraint('uq_game_power', 'players', ['game_id', 'power_name'])


def downgrade() -> None:
    """Revert power_name column back to power."""
    # Drop new indexes
    op.drop_constraint('uq_players_game_id_power_name', 'players', type_='unique')
    op.drop_index('ix_players_power_name_active', table_name='players')
    op.drop_index('ix_players_game_id_power_name', table_name='players')
    op.drop_index('ix_players_power_name', table_name='players')
    
    # Recreate old indexes
    op.create_index('ix_players_power', 'players', ['power'])
    op.create_index('ix_players_game_id_power', 'players', ['game_id', 'power'])
    op.create_index('ix_players_power_active', 'players', ['power', 'is_active'])
    op.create_unique_constraint('ix_players_game_id_power', 'players', ['game_id', 'power'])
    
    # Rename column back
    op.alter_column('players', 'power_name', new_column_name='power', existing_type=sa.String())
