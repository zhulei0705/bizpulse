"""t02 evidence verification fields

Revision ID: c7a41d92b608
Revises: b5eee8fe7e95
Create Date: 2026-09-30 13:05:00.000000

真实数据强制规范（第三十一节）新增验证字段：
- source_records.verification_status / source_reliability / last_verified_at
- signals.verification_status
（content_hash / fact_or_inference / opportunity.review_* 首版或上一迁移已存在；
  opportunities.evidence_count 由查询动态计算，避免冗余字段与数据不一致。）
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c7a41d92b608'
down_revision: Union[str, None] = 'b5eee8fe7e95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('source_records', sa.Column('verification_status', sa.String(length=30), server_default='UNVERIFIED', nullable=False))
    op.create_index(op.f('ix_source_records_verification_status'), 'source_records', ['verification_status'], unique=False)
    op.add_column('source_records', sa.Column('source_reliability', sa.String(length=1), nullable=True))
    op.add_column('source_records', sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('signals', sa.Column('verification_status', sa.String(length=30), server_default='UNVERIFIED', nullable=False))
    op.create_index(op.f('ix_signals_verification_status'), 'signals', ['verification_status'], unique=False)

    # 存量数据回填来源等级快照
    op.execute("""
        UPDATE source_records
        SET source_reliability = (SELECT reliability_grade FROM sources WHERE sources.id = source_records.source_id)
        WHERE source_reliability IS NULL
    """)


def downgrade() -> None:
    op.drop_index(op.f('ix_signals_verification_status'), table_name='signals')
    op.drop_column('signals', 'verification_status')
    op.drop_column('source_records', 'last_verified_at')
    op.drop_column('source_records', 'source_reliability')
    op.drop_index(op.f('ix_source_records_verification_status'), table_name='source_records')
    op.drop_column('source_records', 'verification_status')
