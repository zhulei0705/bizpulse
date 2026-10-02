"""t05 opportunity candidates bundles and lifecycle

Revision ID: d15fe78e7edf
Revises: a0ae25d999ed
Create Date: 2026-10-02 11:23:37.600233
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd15fe78e7edf'
down_revision: Union[str, None] = 'a0ae25d999ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) signal_bundles（先建，供 opportunity_candidates.bundle_id 外键引用）
    op.create_table('signal_bundles',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('company_id', sa.String(length=32), nullable=False),
    sa.Column('bundle_type', sa.String(length=50), nullable=False),
    sa.Column('signal_ids_json', sa.JSON(), nullable=False),
    sa.Column('signal_types_json', sa.JSON(), nullable=False),
    sa.Column('pain_categories', sa.JSON(), nullable=False),
    sa.Column('confidence', sa.Integer(), nullable=False),
    sa.Column('time_window_days', sa.Integer(), nullable=False),
    sa.Column('signal_count_7d', sa.Integer(), nullable=False),
    sa.Column('signal_count_30d', sa.Integer(), nullable=False),
    sa.Column('signal_count_90d', sa.Integer(), nullable=False),
    sa.Column('explanation_json', sa.JSON(), nullable=False),
    sa.Column('first_signal_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_signal_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_signal_bundles_bundle_type'), 'signal_bundles', ['bundle_type'], unique=False)
    op.create_index(op.f('ix_signal_bundles_company_id'), 'signal_bundles', ['company_id'], unique=False)

    # 2) opportunity_candidates（候选机会；candidate→opportunity 单向 FK，避免与 opportunities.candidate_id 成环）
    op.create_table('opportunity_candidates',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('company_id', sa.String(length=32), nullable=False),
    sa.Column('market_id', sa.String(length=32), nullable=True),
    sa.Column('bundle_id', sa.String(length=32), nullable=True),
    sa.Column('pain_point_id', sa.String(length=32), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=False),
    sa.Column('problem_hypothesis', sa.Text(), nullable=False),
    sa.Column('solution_hypothesis', sa.Text(), nullable=False),
    sa.Column('value_hypothesis', sa.Text(), nullable=True),
    sa.Column('trigger_summary', sa.Text(), nullable=True),
    sa.Column('why_now', sa.Text(), nullable=True),
    sa.Column('evidence_summary', sa.Text(), nullable=True),
    sa.Column('recommended_next_action', sa.String(length=50), nullable=True),
    sa.Column('signal_ids_json', sa.JSON(), nullable=False),
    sa.Column('pain_category', sa.String(length=100), nullable=True),
    sa.Column('solution_category', sa.String(length=100), nullable=True),
    sa.Column('pain_score', sa.Integer(), nullable=False),
    sa.Column('budget_score', sa.Integer(), nullable=False),
    sa.Column('intent_score', sa.Integer(), nullable=False),
    sa.Column('urgency_score', sa.Integer(), nullable=False),
    sa.Column('agent_fit_score', sa.Integer(), nullable=False),
    sa.Column('reachability_score', sa.Integer(), nullable=False),
    sa.Column('evidence_score', sa.Integer(), nullable=False),
    sa.Column('total_score', sa.Float(), nullable=False),
    sa.Column('grade', sa.String(length=5), nullable=False),
    sa.Column('grade_cap_reason', sa.String(length=50), nullable=True),
    sa.Column('confidence', sa.Integer(), nullable=False),
    sa.Column('score_breakdown_json', sa.JSON(), nullable=False),
    sa.Column('risk_notes', sa.JSON(), nullable=False),
    sa.Column('validation_questions', sa.JSON(), nullable=False),
    sa.Column('evidence_refs_json', sa.JSON(), nullable=False),
    sa.Column('contradicting_evidence_json', sa.JSON(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('generated_by', sa.String(length=20), nullable=False),
    sa.Column('prompt_version', sa.String(length=50), nullable=True),
    sa.Column('analysis_input_hash', sa.String(length=64), nullable=True),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('last_signal_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_evidence_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.String(length=100), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('reject_reason', sa.String(length=50), nullable=True),
    sa.Column('opportunity_id', sa.String(length=32), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['bundle_id'], ['signal_bundles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['market_id'], ['markets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['pain_point_id'], ['pain_points.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('fingerprint', name='uq_opportunity_candidate_fingerprint')
    )
    op.create_index(op.f('ix_opportunity_candidates_analysis_input_hash'), 'opportunity_candidates', ['analysis_input_hash'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_bundle_id'), 'opportunity_candidates', ['bundle_id'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_company_id'), 'opportunity_candidates', ['company_id'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_fingerprint'), 'opportunity_candidates', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_market_id'), 'opportunity_candidates', ['market_id'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_opportunity_id'), 'opportunity_candidates', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_pain_category'), 'opportunity_candidates', ['pain_category'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_pain_point_id'), 'opportunity_candidates', ['pain_point_id'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_status'), 'opportunity_candidates', ['status'], unique=False)
    op.create_index(op.f('ix_opportunity_candidates_total_score'), 'opportunity_candidates', ['total_score'], unique=False)

    # 3) opportunities 扩展（candidate_id 为普通索引列，无 DB 级 FK —— 由应用层维护引用）
    op.add_column('opportunities', sa.Column('candidate_id', sa.String(length=32), nullable=True))
    op.add_column('opportunities', sa.Column('why_now', sa.Text(), nullable=True))
    op.add_column('opportunities', sa.Column('risk_notes', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('opportunities', sa.Column('validation_questions', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('opportunities', sa.Column('score_breakdown_json', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('opportunities', sa.Column('grade_cap_reason', sa.String(length=50), nullable=True))
    op.add_column('opportunities', sa.Column('recommended_next_action', sa.String(length=50), nullable=True))
    op.add_column('opportunities', sa.Column('fingerprint', sa.String(length=64), nullable=True))
    op.add_column('opportunities', sa.Column('analysis_input_hash', sa.String(length=64), nullable=True))
    op.add_column('opportunities', sa.Column('last_signal_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('opportunities', sa.Column('last_evidence_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('opportunities', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('opportunities', sa.Column('stale_reason', sa.String(length=200), nullable=True))
    op.add_column('opportunities', sa.Column('reject_reason', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_opportunities_candidate_id'), 'opportunities', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_opportunities_fingerprint'), 'opportunities', ['fingerprint'], unique=False)
    op.create_index(op.f('ix_opportunities_last_signal_at'), 'opportunities', ['last_signal_at'], unique=False)

    # 4) opportunity_evidences 扩展（极性 + 来源等级快照）
    op.add_column('opportunity_evidences', sa.Column('polarity', sa.String(length=20), nullable=False, server_default='SUPPORTING'))
    op.add_column('opportunity_evidences', sa.Column('source_grade', sa.String(length=1), nullable=True))
    op.create_index(op.f('ix_opportunity_evidences_polarity'), 'opportunity_evidences', ['polarity'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_opportunity_evidences_polarity'), table_name='opportunity_evidences')
    op.drop_column('opportunity_evidences', 'source_grade')
    op.drop_column('opportunity_evidences', 'polarity')

    op.drop_index(op.f('ix_opportunities_last_signal_at'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_fingerprint'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_candidate_id'), table_name='opportunities')
    op.drop_column('opportunities', 'reject_reason')
    op.drop_column('opportunities', 'stale_reason')
    op.drop_column('opportunities', 'expires_at')
    op.drop_column('opportunities', 'last_evidence_at')
    op.drop_column('opportunities', 'last_signal_at')
    op.drop_column('opportunities', 'analysis_input_hash')
    op.drop_column('opportunities', 'fingerprint')
    op.drop_column('opportunities', 'recommended_next_action')
    op.drop_column('opportunities', 'grade_cap_reason')
    op.drop_column('opportunities', 'score_breakdown_json')
    op.drop_column('opportunities', 'validation_questions')
    op.drop_column('opportunities', 'risk_notes')
    op.drop_column('opportunities', 'why_now')
    op.drop_column('opportunities', 'candidate_id')

    op.drop_table('opportunity_candidates')
    op.drop_table('signal_bundles')
