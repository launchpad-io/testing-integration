"""Add TikTok video tracking tables

Revision ID: add_tiktok_video_tracking
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_tiktok_video_tracking'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tiktok_videos table
    op.create_table('tiktok_videos',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('account_id', sa.String(), nullable=True),
        sa.Column('video_id', sa.String(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('view_count', sa.BigInteger(), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=True),
        sa.Column('comment_count', sa.Integer(), nullable=True),
        sa.Column('share_count', sa.Integer(), nullable=True),
        sa.Column('play_count', sa.BigInteger(), nullable=True),
        sa.Column('duration', sa.Integer(), nullable=True),
        sa.Column('video_url', sa.String(), nullable=True),
        sa.Column('share_url', sa.String(), nullable=True),
        sa.Column('cover_image_url', sa.String(), nullable=True),
        sa.Column('dynamic_cover_url', sa.String(), nullable=True),
        sa.Column('video_status', sa.String(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.Column('campaign_id', sa.String(), nullable=True),
        sa.Column('is_deliverable', sa.Boolean(), nullable=True),
        sa.Column('deliverable_id', sa.String(), nullable=True),
        sa.Column('deliverable_status', sa.String(), nullable=True),
        sa.Column('attributed_gmv', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('attributed_orders', sa.Integer(), nullable=True),
        sa.Column('last_attribution_update', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('discovered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['tiktok_accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tiktok_videos_video_id'), 'tiktok_videos', ['video_id'], unique=True)
    op.create_index(op.f('ix_tiktok_videos_campaign_id'), 'tiktok_videos', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_tiktok_videos_deliverable_id'), 'tiktok_videos', ['deliverable_id'], unique=False)

    # Create tiktok_video_metrics table
    op.create_table('tiktok_video_metrics',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('video_id', sa.String(), nullable=True),
        sa.Column('view_count', sa.BigInteger(), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=True),
        sa.Column('comment_count', sa.Integer(), nullable=True),
        sa.Column('share_count', sa.Integer(), nullable=True),
        sa.Column('play_count', sa.BigInteger(), nullable=True),
        sa.Column('engagement_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('view_velocity', sa.Integer(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['tiktok_videos.video_id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create campaign_video_deliverables table
    op.create_table('campaign_video_deliverables',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('campaign_id', sa.String(), nullable=True),
        sa.Column('deliverable_id', sa.String(), nullable=True),
        sa.Column('creator_id', sa.String(), nullable=True),
        sa.Column('video_id', sa.String(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('reviewer_id', sa.String(), nullable=True),
        sa.Column('target_views', sa.Integer(), nullable=True),
        sa.Column('target_engagement_rate', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('meets_requirements', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['video_id'], ['tiktok_videos.video_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_campaign_video_deliverables_campaign_id'), 'campaign_video_deliverables', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_campaign_video_deliverables_deliverable_id'), 'campaign_video_deliverables', ['deliverable_id'], unique=False)
    op.create_index(op.f('ix_campaign_video_deliverables_creator_id'), 'campaign_video_deliverables', ['creator_id'], unique=False)

    # Add new columns to tiktok_orders table for GMV attribution
    op.add_column('tiktok_orders', sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('tiktok_orders', sa.Column('currency', sa.String(), nullable=True))
    op.add_column('tiktok_orders', sa.Column('creator_id', sa.String(), nullable=True))
    op.add_column('tiktok_orders', sa.Column('attributed_video_id', sa.String(), nullable=True))
    op.add_column('tiktok_orders', sa.Column('attribution_method', sa.String(), nullable=True))
    op.add_column('tiktok_orders', sa.Column('attribution_confidence', sa.Numeric(precision=3, scale=2), nullable=True))
    
    # Create indexes for new columns
    op.create_index(op.f('ix_tiktok_orders_creator_id'), 'tiktok_orders', ['creator_id'], unique=False)
    op.create_index(op.f('ix_tiktok_orders_attributed_video_id'), 'tiktok_orders', ['attributed_video_id'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_tiktok_orders_attributed_video_id'), table_name='tiktok_orders')
    op.drop_index(op.f('ix_tiktok_orders_creator_id'), table_name='tiktok_orders')
    op.drop_index(op.f('ix_campaign_video_deliverables_creator_id'), table_name='campaign_video_deliverables')
    op.drop_index(op.f('ix_campaign_video_deliverables_deliverable_id'), table_name='campaign_video_deliverables')
    op.drop_index(op.f('ix_campaign_video_deliverables_campaign_id'), table_name='campaign_video_deliverables')
    op.drop_index(op.f('ix_tiktok_videos_deliverable_id'), table_name='tiktok_videos')
    op.drop_index(op.f('ix_tiktok_videos_campaign_id'), table_name='tiktok_videos')
    op.drop_index(op.f('ix_tiktok_videos_video_id'), table_name='tiktok_videos')

    # Drop columns from tiktok_orders
    op.drop_column('tiktok_orders', 'attribution_confidence')
    op.drop_column('tiktok_orders', 'attribution_method')
    op.drop_column('tiktok_orders', 'attributed_video_id')
    op.drop_column('tiktok_orders', 'creator_id')
    op.drop_column('tiktok_orders', 'currency')
    op.drop_column('tiktok_orders', 'total_amount')

    # Drop tables
    op.drop_table('campaign_video_deliverables')
    op.drop_table('tiktok_video_metrics')
    op.drop_table('tiktok_videos') 