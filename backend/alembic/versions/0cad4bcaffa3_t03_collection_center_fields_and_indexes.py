"""t03 collection center fields and indexes

Revision ID: 0cad4bcaffa3
Revises: c7a41d92b608
Create Date: 2026-09-30 17:13:42.702523

T03 真实数据采集中心：
- sources: + config_json / last_success_at
- source_records: + canonical_url / content_type / company_resolve_status /
  parent_record_id / version_number / is_latest / checked_at / parse_status /
  error_message / expires_at / is_active（版本与过期设计）
- collection_jobs: + job_type / scheduled_at / items_found / items_created /
  items_updated / items_skipped / run_log_json（逐 URL 明细）
- 存量数据回填 canonical_url 与版本默认值
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0cad4bcaffa3'
down_revision: Union[str, None] = 'c7a41d92b608'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- sources ----
    op.add_column('sources', sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('sources', sa.Column('config_json', sa.JSON(), server_default='{}', nullable=False))
    op.create_index(op.f('ix_sources_enabled'), 'sources', ['enabled'], unique=False)

    # ---- source_records ----
    op.add_column('source_records', sa.Column('canonical_url', sa.Text(), nullable=True))
    op.add_column('source_records', sa.Column('content_type', sa.String(length=120), nullable=True))
    op.add_column('source_records', sa.Column('company_resolve_status', sa.String(length=30), server_default='UNRESOLVED', nullable=False))
    op.add_column('source_records', sa.Column('parent_record_id', sa.String(length=32), nullable=True))
    op.add_column('source_records', sa.Column('version_number', sa.Integer(), server_default='1', nullable=False))
    op.add_column('source_records', sa.Column('is_latest', sa.Boolean(), server_default=sa.text('1'), nullable=False))
    op.add_column('source_records', sa.Column('checked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('source_records', sa.Column('parse_status', sa.String(length=20), server_default='OK', nullable=False))
    op.add_column('source_records', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column('source_records', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('source_records', sa.Column('is_active', sa.Boolean(), server_default=sa.text('1'), nullable=False))
    op.create_index(op.f('ix_source_records_canonical_url'), 'source_records', ['canonical_url'], unique=False)
    op.create_index(op.f('ix_source_records_company_resolve_status'), 'source_records', ['company_resolve_status'], unique=False)
    op.create_index(op.f('ix_source_records_is_latest'), 'source_records', ['is_latest'], unique=False)
    op.create_index(op.f('ix_source_records_parent_record_id'), 'source_records', ['parent_record_id'], unique=False)
    with op.batch_alter_table('source_records') as batch_op:
        batch_op.create_foreign_key('fk_source_records_parent', 'source_records', ['parent_record_id'], ['id'], ondelete='SET NULL')
    # 存量回填：canonical_url 先取原 url（后续采集会规范化）
    op.execute("UPDATE source_records SET canonical_url = url WHERE canonical_url IS NULL")

    # ---- collection_jobs ----
    op.add_column('collection_jobs', sa.Column('job_type', sa.String(length=30), server_default='MANUAL', nullable=False))
    op.add_column('collection_jobs', sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('collection_jobs', sa.Column('items_found', sa.Integer(), server_default='0', nullable=False))
    op.add_column('collection_jobs', sa.Column('items_created', sa.Integer(), server_default='0', nullable=False))
    op.add_column('collection_jobs', sa.Column('items_updated', sa.Integer(), server_default='0', nullable=False))
    op.add_column('collection_jobs', sa.Column('items_skipped', sa.Integer(), server_default='0', nullable=False))
    op.add_column('collection_jobs', sa.Column('run_log_json', sa.JSON(), server_default='[]', nullable=False))
    op.create_index(op.f('ix_collection_jobs_job_type'), 'collection_jobs', ['job_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_collection_jobs_job_type'), table_name='collection_jobs')
    op.drop_column('collection_jobs', 'run_log_json')
    op.drop_column('collection_jobs', 'items_skipped')
    op.drop_column('collection_jobs', 'items_updated')
    op.drop_column('collection_jobs', 'items_created')
    op.drop_column('collection_jobs', 'items_found')
    op.drop_column('collection_jobs', 'scheduled_at')
    op.drop_column('collection_jobs', 'job_type')
    with op.batch_alter_table('source_records') as batch_op:
        batch_op.drop_constraint('fk_source_records_parent', type_='foreignkey')
    op.drop_index(op.f('ix_source_records_parent_record_id'), table_name='source_records')
    op.drop_index(op.f('ix_source_records_is_latest'), table_name='source_records')
    op.drop_index(op.f('ix_source_records_company_resolve_status'), table_name='source_records')
    op.drop_index(op.f('ix_source_records_canonical_url'), table_name='source_records')
    op.drop_column('source_records', 'is_active')
    op.drop_column('source_records', 'expires_at')
    op.drop_column('source_records', 'error_message')
    op.drop_column('source_records', 'parse_status')
    op.drop_column('source_records', 'checked_at')
    op.drop_column('source_records', 'is_latest')
    op.drop_column('source_records', 'version_number')
    op.drop_column('source_records', 'parent_record_id')
    op.drop_column('source_records', 'company_resolve_status')
    op.drop_column('source_records', 'content_type')
    op.drop_column('source_records', 'canonical_url')
    op.drop_index(op.f('ix_sources_enabled'), table_name='sources')
    op.drop_column('sources', 'config_json')
    op.drop_column('sources', 'last_success_at')
