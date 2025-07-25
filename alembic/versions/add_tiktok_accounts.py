"""Add TikTok accounts table for OAuth authentication

Revision ID: add_tiktok_accounts
Revises: add_tiktok_video_tracking
Create Date: 2024-12-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_tiktok_accounts'
down_revision = 'add_tiktok_video_tracking'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tiktok_accounts table
    op.create_table('tiktok_accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('access_token_expire_in', sa.Integer(), nullable=True),
        sa.Column('refresh_token_expire_in', sa.Integer(), nullable=True),
        sa.Column('tiktok_user_id', sa.String(255), nullable=True),
        sa.Column('username', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('follower_count', sa.Integer(), nullable=True, default=0),
        sa.Column('following_count', sa.Integer(), nullable=True, default=0),
        sa.Column('like_count', sa.Integer(), nullable=True, default=0),
        sa.Column('video_count', sa.Integer(), nullable=True, default=0),
        sa.Column('scopes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('connected_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for tiktok_accounts
    op.create_index('ix_tiktok_accounts_user_id', 'tiktok_accounts', ['user_id'])
    op.create_index('ix_tiktok_accounts_tiktok_user_id', 'tiktok_accounts', ['tiktok_user_id'])
    op.create_unique_constraint('uq_tiktok_accounts_user_id', 'tiktok_accounts', ['user_id'])
    op.create_unique_constraint('uq_tiktok_accounts_tiktok_user_id', 'tiktok_accounts', ['tiktok_user_id'])


def downgrade() -> None:
    # Drop the table and indexes
    op.drop_table('tiktok_accounts') 