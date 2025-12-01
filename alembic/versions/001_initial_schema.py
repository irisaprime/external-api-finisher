"""Initial schema - channels, api_keys, usage_logs, messages

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-11-19 07:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create channels table (formerly teams)
    op.create_table(
        'channels',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('channel_id', sa.String(length=255), nullable=False),
        sa.Column('access_type', sa.String(length=50), nullable=False, server_default='private'),
        sa.Column('monthly_quota', sa.Integer(), nullable=True),
        sa.Column('daily_quota', sa.Integer(), nullable=True),
        sa.Column('rate_limit', sa.Integer(), nullable=True),
        sa.Column('max_history', sa.Integer(), nullable=True),
        sa.Column('default_model', sa.String(length=255), nullable=True),
        sa.Column('available_models', sa.Text(), nullable=True),
        sa.Column('allow_model_switch', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_channels_id'), 'channels', ['id'], unique=False)
    op.create_index(op.f('ix_channels_title'), 'channels', ['title'], unique=True)
    op.create_index(op.f('ix_channels_channel_id'), 'channels', ['channel_id'], unique=True)
    op.create_index(op.f('ix_channels_access_type'), 'channels', ['access_type'], unique=False)

    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('key_prefix', sa.String(length=16), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('monthly_quota', sa.Integer(), nullable=True),
        sa.Column('daily_quota', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)
    op.create_index(op.f('ix_api_keys_channel_id'), 'api_keys', ['channel_id'], unique=False)

    # Create usage_logs table
    op.create_table(
        'usage_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('api_key_id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('channel_identifier', sa.String(length=50), nullable=False),
        sa.Column('model_used', sa.String(length=255), nullable=False),
        sa.Column('tokens_used', sa.Integer(), nullable=True),
        sa.Column('estimated_cost', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('response_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_logs_id'), 'usage_logs', ['id'], unique=False)
    op.create_index(op.f('ix_usage_logs_api_key_id'), 'usage_logs', ['api_key_id'], unique=False)
    op.create_index(op.f('ix_usage_logs_channel_id'), 'usage_logs', ['channel_id'], unique=False)
    op.create_index(op.f('ix_usage_logs_channel_identifier'), 'usage_logs', ['channel_identifier'], unique=False)
    op.create_index(op.f('ix_usage_logs_session_id'), 'usage_logs', ['session_id'], unique=False)
    op.create_index(op.f('ix_usage_logs_timestamp'), 'usage_logs', ['timestamp'], unique=False)

    # Create messages table
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=True),
        sa.Column('api_key_id', sa.Integer(), nullable=True),
        sa.Column('channel_identifier', sa.String(length=50), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('cleared_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_id'), 'messages', ['id'], unique=False)
    op.create_index(op.f('ix_messages_channel_id'), 'messages', ['channel_id'], unique=False)
    op.create_index(op.f('ix_messages_api_key_id'), 'messages', ['api_key_id'], unique=False)
    op.create_index(op.f('ix_messages_channel_identifier'), 'messages', ['channel_identifier'], unique=False)
    op.create_index(op.f('ix_messages_user_id'), 'messages', ['user_id'], unique=False)
    op.create_index(op.f('ix_messages_created_at'), 'messages', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_index(op.f('ix_messages_created_at'), table_name='messages')
    op.drop_index(op.f('ix_messages_user_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_channel_identifier'), table_name='messages')
    op.drop_index(op.f('ix_messages_api_key_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_channel_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_id'), table_name='messages')
    op.drop_table('messages')

    op.drop_index(op.f('ix_usage_logs_timestamp'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_session_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_channel_identifier'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_channel_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_api_key_id'), table_name='usage_logs')
    op.drop_index(op.f('ix_usage_logs_id'), table_name='usage_logs')
    op.drop_table('usage_logs')

    op.drop_index(op.f('ix_api_keys_channel_id'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_key_hash'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_id'), table_name='api_keys')
    op.drop_table('api_keys')

    op.drop_index(op.f('ix_channels_access_type'), table_name='channels')
    op.drop_index(op.f('ix_channels_channel_id'), table_name='channels')
    op.drop_index(op.f('ix_channels_title'), table_name='channels')
    op.drop_index(op.f('ix_channels_id'), table_name='channels')
    op.drop_table('channels')
