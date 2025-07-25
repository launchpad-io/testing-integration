"""Add TikTok video tracking and enhanced order attribution

Revision ID: add_tiktok_video_tracking
Revises: 
Create Date: 2024-05-20 10:00:00.000000

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
    # Create enum types
    op.execute("CREATE TYPE videostatus AS ENUM ('active', 'inactive', 'deleted', 'pending')")
    op.execute("CREATE TYPE deliverablestatus AS ENUM ('pending', 'approved', 'rejected', 'completed')")
    op.execute("CREATE TYPE attributionmethod AS ENUM ('direct_link', 'promo_code', 'cookie_based', 'manual')")
    
    # Create tiktok_videos table
    op.create_table('tiktok_videos',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tiktok_video_id', sa.String(255), nullable=False),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('video_url', sa.String(1000), nullable=True),
        sa.Column('thumbnail_url', sa.String(1000), nullable=True),
        sa.Column('view_count', sa.Integer(), nullable=True, default=0),
        sa.Column('like_count', sa.Integer(), nullable=True, default=0),
        sa.Column('comment_count', sa.Integer(), nullable=True, default=0),
        sa.Column('share_count', sa.Integer(), nullable=True, default=0),
        sa.Column('promo_codes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('tracking_links', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'deleted', 'pending', name='videostatus'), nullable=True, default='active'),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for tiktok_videos
    op.create_index('ix_tiktok_videos_creator_id', 'tiktok_videos', ['creator_id'])
    op.create_index('ix_tiktok_videos_tiktok_video_id', 'tiktok_videos', ['tiktok_video_id'])
    op.create_unique_constraint('uq_tiktok_videos_tiktok_video_id', 'tiktok_videos', ['tiktok_video_id'])
    
    # Create tiktok_video_metrics table
    op.create_table('tiktok_video_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=True, default=0),
        sa.Column('like_count', sa.Integer(), nullable=True, default=0),
        sa.Column('comment_count', sa.Integer(), nullable=True, default=0),
        sa.Column('share_count', sa.Integer(), nullable=True, default=0),
        sa.Column('engagement_rate', sa.Float(), nullable=True, default=0.0),
        sa.Column('engagement_count', sa.Integer(), nullable=True, default=0),
        sa.Column('attributed_gmv', sa.Float(), nullable=True, default=0.0),
        sa.Column('attributed_orders', sa.Integer(), nullable=True, default=0),
        sa.Column('recorded_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['video_id'], ['tiktok_videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create campaign_video_deliverables table
    op.create_table('campaign_video_deliverables',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('video_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('deliverable_type', sa.String(100), nullable=True),
        sa.Column('requirements_met', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'approved', 'rejected', 'completed', name='deliverablestatus'), nullable=True, default='pending'),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('performance_score', sa.Float(), nullable=True),
        sa.Column('bonus_eligible', sa.Boolean(), nullable=True, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['video_id'], ['tiktok_videos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for campaign_video_deliverables
    op.create_index('ix_campaign_video_deliverables_campaign_id', 'campaign_video_deliverables', ['campaign_id'])
    op.create_index('ix_campaign_video_deliverables_creator_id', 'campaign_video_deliverables', ['creator_id'])
    
    # Create tiktok_creator_auth table
    op.create_table('tiktok_creator_auth',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('refresh_token', sa.Text(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('tiktok_user_id', sa.String(255), nullable=True),
        sa.Column('tiktok_username', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('scopes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes and constraints for tiktok_creator_auth
    op.create_index('ix_tiktok_creator_auth_creator_id', 'tiktok_creator_auth', ['creator_id'])
    op.create_index('ix_tiktok_creator_auth_tiktok_user_id', 'tiktok_creator_auth', ['tiktok_user_id'])
    op.create_unique_constraint('uq_tiktok_creator_auth_creator_id', 'tiktok_creator_auth', ['creator_id'])
    op.create_unique_constraint('uq_tiktok_creator_auth_tiktok_user_id', 'tiktok_creator_auth', ['tiktok_user_id'])
    
    # Create tiktok_orders table (if it doesn't exist) or add new columns
    # Assuming the table exists and we're adding new columns
    try:
        # Add new columns to existing tiktok_orders table
        op.add_column('tiktok_orders', sa.Column('total_amount', sa.Float(), nullable=True))
        op.add_column('tiktok_orders', sa.Column('currency', sa.String(3), nullable=True, default='USD'))
        op.add_column('tiktok_orders', sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column('tiktok_orders', sa.Column('attributed_video_id', postgresql.UUID(as_uuid=True), nullable=True))
        op.add_column('tiktok_orders', sa.Column('attribution_method', postgresql.ENUM('direct_link', 'promo_code', 'cookie_based', 'manual', name='attributionmethod'), nullable=True))
        op.add_column('tiktok_orders', sa.Column('attribution_confidence', sa.Float(), nullable=True, default=0.0))
        op.add_column('tiktok_orders', sa.Column('promo_code_used', sa.String(50), nullable=True))
        op.add_column('tiktok_orders', sa.Column('discount_amount', sa.Float(), nullable=True, default=0.0))
        op.add_column('tiktok_orders', sa.Column('customer_id', sa.String(255), nullable=True))
        op.add_column('tiktok_orders', sa.Column('customer_email', sa.String(255), nullable=True))
        op.add_column('tiktok_orders', sa.Column('order_date', sa.DateTime(), nullable=True))
        op.add_column('tiktok_orders', sa.Column('fulfilled_date', sa.DateTime(), nullable=True))
        
        # Add foreign key constraint
        op.create_foreign_key('fk_tiktok_orders_attributed_video', 'tiktok_orders', 'tiktok_videos', ['attributed_video_id'], ['id'])
        
        # Add indexes
        op.create_index('ix_tiktok_orders_creator_id', 'tiktok_orders', ['creator_id'])
        op.create_index('ix_tiktok_orders_attributed_video_id', 'tiktok_orders', ['attributed_video_id'])
        
    except Exception:
        # If table doesn't exist, create it
        op.create_table('tiktok_orders',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('tiktok_order_id', sa.String(255), nullable=False),
            sa.Column('total_amount', sa.Float(), nullable=False),
            sa.Column('currency', sa.String(3), nullable=True, default='USD'),
            sa.Column('order_status', sa.String(50), nullable=True),
            sa.Column('creator_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('attributed_video_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('attribution_method', postgresql.ENUM('direct_link', 'promo_code', 'cookie_based', 'manual', name='attributionmethod'), nullable=True),
            sa.Column('attribution_confidence', sa.Float(), nullable=True, default=0.0),
            sa.Column('promo_code_used', sa.String(50), nullable=True),
            sa.Column('discount_amount', sa.Float(), nullable=True, default=0.0),
            sa.Column('customer_id', sa.String(255), nullable=True),
            sa.Column('customer_email', sa.String(255), nullable=True),
            sa.Column('order_date', sa.DateTime(), nullable=True),
            sa.Column('fulfilled_date', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['attributed_video_id'], ['tiktok_videos.id']),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes
        op.create_index('ix_tiktok_orders_tiktok_order_id', 'tiktok_orders', ['tiktok_order_id'])
        op.create_index('ix_tiktok_orders_creator_id', 'tiktok_orders', ['creator_id'])
        op.create_index('ix_tiktok_orders_attributed_video_id', 'tiktok_orders', ['attributed_video_id'])
        op.create_unique_constraint('uq_tiktok_orders_tiktok_order_id', 'tiktok_orders', ['tiktok_order_id'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('campaign_video_deliverables')
    op.drop_table('tiktok_video_metrics')
    op.drop_table('tiktok_creator_auth')
    op.drop_table('tiktok_videos')
    
    # Remove columns from tiktok_orders if they exist
    try:
        op.drop_constraint('fk_tiktok_orders_attributed_video', 'tiktok_orders', type_='foreignkey')
        op.drop_index('ix_tiktok_orders_creator_id', 'tiktok_orders')
        op.drop_index('ix_tiktok_orders_attributed_video_id', 'tiktok_orders')
        
        op.drop_column('tiktok_orders', 'fulfilled_date')
        op.drop_column('tiktok_orders', 'order_date')
        op.drop_column('tiktok_orders', 'customer_email')
        op.drop_column('tiktok_orders', 'customer_id')
        op.drop_column('tiktok_orders', 'discount_amount')
        op.drop_column('tiktok_orders', 'promo_code_used')
        op.drop_column('tiktok_orders', 'attribution_confidence')
        op.drop_column('tiktok_orders', 'attribution_method')
        op.drop_column('tiktok_orders', 'attributed_video_id')
        op.drop_column('tiktok_orders', 'creator_id')
        op.drop_column('tiktok_orders', 'currency')
        op.drop_column('tiktok_orders', 'total_amount')
    except Exception:
        # If columns don't exist or table was created by this migration, drop the whole table
        op.drop_table('tiktok_orders')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS attributionmethod")
    op.execute("DROP TYPE IF EXISTS deliverablestatus")
    op.execute("DROP TYPE IF EXISTS videostatus") 