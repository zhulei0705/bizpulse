"""t02 review fields indexes and signal timestamps

Revision ID: b5eee8fe7e95
Revises: 98ea2807c623
Create Date: 2026-09-30 11:39:45.963792

T02 变更：
- opportunities 增加人工审核字段（review_status/reviewed_at/review_note/reviewed_by）
- signals 增加标准时间戳（created_at/updated_at）
- 按 T02 索引规范补齐：companies.website、source_records.url、
  opportunities.created_at、signals.created_at
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b5eee8fe7e95'
down_revision: Union[str, None] = '98ea2807c623'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 人工审核字段
    op.add_column('opportunities', sa.Column('review_status', sa.String(length=30), server_default='PENDING', nullable=False))
    op.add_column('opportunities', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('opportunities', sa.Column('review_note', sa.Text(), nullable=True))
    op.add_column('opportunities', sa.Column('reviewed_by', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_opportunities_review_status'), 'opportunities', ['review_status'], unique=False)

    # signals 标准时间戳
    op.add_column('signals', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))
    op.add_column('signals', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False))

    # T02 指定索引
    op.create_index(op.f('ix_companies_website'), 'companies', ['website'], unique=False)
    op.create_index(op.f('ix_source_records_url'), 'source_records', ['url'], unique=False)
    op.create_index(op.f('ix_opportunities_created_at'), 'opportunities', ['created_at'], unique=False)
    op.create_index(op.f('ix_signals_created_at'), 'signals', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_signals_created_at'), table_name='signals')
    op.drop_index(op.f('ix_opportunities_created_at'), table_name='opportunities')
    op.drop_index(op.f('ix_source_records_url'), table_name='source_records')
    op.drop_index(op.f('ix_companies_website'), table_name='companies')
    op.drop_column('signals', 'updated_at')
    op.drop_column('signals', 'created_at')
    op.drop_index(op.f('ix_opportunities_review_status'), table_name='opportunities')
    op.drop_column('opportunities', 'reviewed_by')
    op.drop_column('opportunities', 'review_note')
    op.drop_column('opportunities', 'reviewed_at')
    op.drop_column('opportunities', 'review_status')
