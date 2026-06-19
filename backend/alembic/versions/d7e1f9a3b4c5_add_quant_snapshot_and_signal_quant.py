"""add_quant_snapshot_and_signal_quant_fields

Revision ID: d7e1f9a3b4c5
Revises: bce95bc028dc
Create Date: 2026-06-17 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7e1f9a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'bce95bc028dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ── 1. 新建 quant_snapshots 表 ──
    op.create_table('quant_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('snapshot_date', sa.DateTime(), nullable=False),
        sa.Column('northbound_hgt', sa.Float(), nullable=True),
        sa.Column('northbound_sgt', sa.Float(), nullable=True),
        sa.Column('northbound_total', sa.Float(), nullable=True),
        sa.Column('industry_avg_change_pct', sa.Float(), nullable=True),
        sa.Column('industry_top_json', sa.JSON(), nullable=True),
        sa.Column('industry_bottom_json', sa.JSON(), nullable=True),
        sa.Column('fund_flow_000300', sa.Float(), nullable=True),
        sa.Column('fund_flow_399006', sa.Float(), nullable=True),
        sa.Column('fund_flow_000016', sa.Float(), nullable=True),
        sa.Column('fund_flow_detail', sa.JSON(), nullable=True),
        sa.Column('dragon_tiger_count', sa.Integer(), nullable=True),
        sa.Column('dragon_tiger_net_buy_wan', sa.Float(), nullable=True),
        sa.Column('dragon_tiger_top_json', sa.JSON(), nullable=True),
        sa.Column('pe_000300', sa.Float(), nullable=True),
        sa.Column('pb_000300', sa.Float(), nullable=True),
        sa.Column('fund_flow_score', sa.Float(), nullable=True),
        sa.Column('industry_momentum_score', sa.Float(), nullable=True),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quant_snapshots_id'), 'quant_snapshots', ['id'], unique=False)
    op.create_index(op.f('ix_quant_snapshots_snapshot_date'), 'quant_snapshots', ['snapshot_date'], unique=False)
    op.create_index('idx_quant_date', 'quant_snapshots', ['snapshot_date'], unique=True)

    # ── 2. daily_signals 加量化字段 ──
    op.add_column('daily_signals', sa.Column('fund_flow_score', sa.Float(), nullable=True))
    op.add_column('daily_signals', sa.Column('industry_momentum_score', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('daily_signals', 'industry_momentum_score')
    op.drop_column('daily_signals', 'fund_flow_score')
    op.drop_index('idx_quant_date', table_name='quant_snapshots')
    op.drop_index(op.f('ix_quant_snapshots_snapshot_date'), table_name='quant_snapshots')
    op.drop_index(op.f('ix_quant_snapshots_id'), table_name='quant_snapshots')
    op.drop_table('quant_snapshots')
