"""t08 company pool expansion

Revision ID: c9d5e3f7a2b8
Revises: b8c4d2e6f1a9
Create Date: 2026-10-03 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c9d5e3f7a2b8'
down_revision: Union[str, None] = 'b8c4d2e6f1a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T08：企业池扩充 —— 组织类型 / 验证状态 / 数据质量 / 发现来源
    op.add_column('companies', sa.Column('organization_type', sa.String(length=30), nullable=False, server_default='UNKNOWN'))
    op.add_column('companies', sa.Column('verification_status', sa.String(length=30), nullable=False, server_default='UNVERIFIED'))
    op.add_column('companies', sa.Column('company_data_quality', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('companies', sa.Column('discovery_source_url', sa.Text(), nullable=True))
    op.add_column('companies', sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_companies_organization_type'), 'companies', ['organization_type'], unique=False)
    op.create_index(op.f('ix_companies_verification_status'), 'companies', ['verification_status'], unique=False)

    # T08：采集战役（某个市场的数据扩充任务；只做采集计划，不直接创造企业）
    op.create_table('collection_campaigns',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=300), nullable=False),
    sa.Column('market', sa.String(length=200), nullable=True),
    sa.Column('keywords', sa.JSON(), nullable=False),
    sa.Column('source_types', sa.JSON(), nullable=False),
    sa.Column('seed_urls', sa.JSON(), nullable=False),
    sa.Column('target_company_count', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('progress_json', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('collection_campaigns')
    op.drop_index(op.f('ix_companies_verification_status'), table_name='companies')
    op.drop_index(op.f('ix_companies_organization_type'), table_name='companies')
    op.drop_column('companies', 'verified_at')
    op.drop_column('companies', 'discovery_source_url')
    op.drop_column('companies', 'company_data_quality')
    op.drop_column('companies', 'verification_status')
    op.drop_column('companies', 'organization_type')
