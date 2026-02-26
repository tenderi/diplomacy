"""add user auth and link_codes

Revision ID: a1b2c3d4e5f6
Revises: 9ee373e5cc74
Create Date: 2026-02-26

Adds email, password_hash to users; makes telegram_id nullable; creates link_codes table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '9ee373e5cc74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns to users (nullable for existing Telegram-only users)
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('password_hash', sa.String(255), nullable=True))
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Make telegram_id nullable (browser-only users have no telegram_id until they link)
    op.alter_column(
        'users',
        'telegram_id',
        existing_type=sa.String(255),
        nullable=True,
    )

    # Create link_codes table for Telegram linking flow
    op.create_table(
        'link_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(32), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
    )
    op.create_index('ix_link_codes_code', 'link_codes', ['code'], unique=True)
    op.create_index('ix_link_codes_user_id', 'link_codes', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_link_codes_user_id', table_name='link_codes')
    op.drop_index('ix_link_codes_code', table_name='link_codes')
    op.drop_table('link_codes')

    op.alter_column(
        'users',
        'telegram_id',
        existing_type=sa.String(255),
        nullable=False,
    )

    op.drop_index('ix_users_email', table_name='users')
    op.drop_column('users', 'password_hash')
    op.drop_column('users', 'email')
