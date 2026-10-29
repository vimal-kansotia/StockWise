"""initial schema

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-18 23:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Products
    op.create_table(
        'products',
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('dept_id', sa.String(length=64), nullable=False),
        sa.Column('cat_id', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('item_id')
    )
    op.create_index(op.f('ix_products_dept_id'), 'products', ['dept_id'], unique=False)
    op.create_index(op.f('ix_products_cat_id'), 'products', ['cat_id'], unique=False)

    # Stores
    op.create_table(
        'stores',
        sa.Column('store_id', sa.String(length=64), nullable=False),
        sa.Column('state_id', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('store_id')
    )
    op.create_index(op.f('ix_stores_state_id'), 'stores', ['state_id'], unique=False)

    # Daily Sales
    op.create_table(
        'daily_sales',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.String(length=64), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('units_sold', sa.Integer(), nullable=False),
        sa.Column('sell_price', sa.Float(), nullable=False),
        sa.Column('has_event', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['products.item_id'], ),
        sa.ForeignKeyConstraint(['store_id'], ['stores.store_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sales_store_item_date', 'daily_sales', ['store_id', 'item_id', 'date'], unique=True)

    # Inventory Snapshots
    op.create_table(
        'inventory_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.String(length=64), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('stock_on_hand', sa.Integer(), nullable=False),
        sa.Column('incoming_stock', sa.Integer(), nullable=False),
        sa.Column('committed_stock', sa.Integer(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('supplier_lead_time_days', sa.Integer(), nullable=False),
        sa.Column('min_order_qty', sa.Integer(), nullable=False),
        sa.Column('order_multiple', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['products.item_id'], ),
        sa.ForeignKeyConstraint(['store_id'], ['stores.store_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_inv_store_item_date', 'inventory_snapshots', ['store_id', 'item_id', 'snapshot_date'], unique=True)

    # Forecast Runs
    op.create_table(
        'forecast_runs',
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('model_name', sa.String(length=64), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('run_id')
    )

    # Demand Forecasts
    op.create_table(
        'demand_forecasts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('store_id', sa.String(length=64), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('predicted_demand', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['products.item_id'], ),
        sa.ForeignKeyConstraint(['run_id'], ['forecast_runs.run_id'], ),
        sa.ForeignKeyConstraint(['store_id'], ['stores.store_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_forecast_run_store_item_date', 'demand_forecasts', ['run_id', 'store_id', 'item_id', 'forecast_date'], unique=True)

    # Inventory Recommendations
    op.create_table(
        'inventory_recommendations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('store_id', sa.String(length=64), nullable=False),
        sa.Column('item_id', sa.String(length=64), nullable=False),
        sa.Column('recommendation_date', sa.Date(), nullable=False),
        sa.Column('current_stock', sa.Integer(), nullable=False),
        sa.Column('incoming_stock', sa.Integer(), nullable=False),
        sa.Column('committed_stock', sa.Integer(), nullable=False),
        sa.Column('inventory_position', sa.Integer(), nullable=False),
        sa.Column('lead_time_demand', sa.Float(), nullable=False),
        sa.Column('safety_stock', sa.Float(), nullable=False),
        sa.Column('reorder_point', sa.Float(), nullable=False),
        sa.Column('recommended_order_qty', sa.Integer(), nullable=False),
        sa.Column('classification', sa.String(length=32), nullable=False),
        sa.Column('alert_triggered', sa.Boolean(), nullable=True),
        sa.Column('policy_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['products.item_id'], ),
        sa.ForeignKeyConstraint(['store_id'], ['stores.store_id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_rec_store_item_date', 'inventory_recommendations', ['store_id', 'item_id', 'recommendation_date'], unique=True)

    # Model Evaluations
    op.create_table(
        'model_evaluations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_name', sa.String(length=64), nullable=False),
        sa.Column('evaluation_date', sa.DateTime(), nullable=True),
        sa.Column('mae', sa.Float(), nullable=False),
        sa.Column('rmse', sa.Float(), nullable=False),
        sa.Column('wape', sa.Float(), nullable=False),
        sa.Column('bias', sa.Float(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('validation_split', sa.String(length=64), nullable=False),
        sa.Column('feature_count', sa.Integer(), nullable=True),
        sa.Column('is_champion', sa.Boolean(), nullable=True),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Pipeline Executions
    op.create_table(
        'pipeline_executions',
        sa.Column('run_id', sa.String(length=64), nullable=False),
        sa.Column('pipeline_type', sa.String(length=64), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('records_processed', sa.Integer(), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('run_id')
    )


def downgrade() -> None:
    op.drop_table('pipeline_executions')
    op.drop_table('model_evaluations')
    op.drop_index('idx_rec_store_item_date', table_name='inventory_recommendations')
    op.drop_table('inventory_recommendations')
    op.drop_index('idx_forecast_run_store_item_date', table_name='demand_forecasts')
    op.drop_table('demand_forecasts')
    op.drop_table('forecast_runs')
    op.drop_index('idx_inv_store_item_date', table_name='inventory_snapshots')
    op.drop_table('inventory_snapshots')
    op.drop_index('idx_sales_store_item_date', table_name='daily_sales')
    op.drop_table('daily_sales')
    op.drop_index(op.f('ix_stores_state_id'), table_name='stores')
    op.drop_table('stores')
    op.drop_index(op.f('ix_products_dept_id'), table_name='products')
    op.drop_index(op.f('ix_products_cat_id'), table_name='products')
    op.drop_table('products')
