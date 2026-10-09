"""t06 validation feedback system

Revision ID: e7f3a91b2c4d
Revises: d15fe78e7edf
Create Date: 2026-10-02 16:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e7f3a91b2c4d'
down_revision: Union[str, None] = 'd15fe78e7edf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) experiments 扩展：完整实验定义（假设/价值主张/报价/目标/成功标准）
    op.add_column('experiments', sa.Column('value_proposition', sa.Text(), nullable=True))
    op.add_column('experiments', sa.Column('offer_description', sa.Text(), nullable=True))
    op.add_column('experiments', sa.Column('price_amount', sa.Numeric(14, 2), nullable=True))
    op.add_column('experiments', sa.Column('price_currency', sa.String(length=10), nullable=True))
    op.add_column('experiments', sa.Column('price_type', sa.String(length=30), nullable=True))
    op.add_column('experiments', sa.Column('start_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('experiments', sa.Column('end_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('experiments', sa.Column('target_contacts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('experiments', sa.Column('target_replies', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('experiments', sa.Column('target_meetings', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('experiments', sa.Column('target_quotes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('experiments', sa.Column('target_pilots', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('experiments', sa.Column('target_wins', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('experiments', sa.Column('success_criteria', sa.Text(), nullable=True))
    op.add_column('experiments', sa.Column('failure_criteria', sa.Text(), nullable=True))
    op.add_column('experiments', sa.Column('conclusion_notes', sa.Text(), nullable=True))

    # 2) experiment_targets（验证目标企业：漏斗按企业计数）
    op.create_table('experiment_targets',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('experiment_id', sa.String(length=32), nullable=False),
    sa.Column('company_id', sa.String(length=32), nullable=False),
    sa.Column('opportunity_id', sa.String(length=32), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('reached_stage', sa.String(length=30), nullable=False),
    sa.Column('assigned_to', sa.String(length=100), nullable=True),
    sa.Column('added_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_interaction_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_action', sa.String(length=300), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('experiment_id', 'company_id', name='uq_experiment_target')
    )
    op.create_index(op.f('ix_experiment_targets_company_id'), 'experiment_targets', ['company_id'], unique=False)
    op.create_index(op.f('ix_experiment_targets_experiment_id'), 'experiment_targets', ['experiment_id'], unique=False)
    op.create_index(op.f('ix_experiment_targets_last_interaction_at'), 'experiment_targets', ['last_interaction_at'], unique=False)
    op.create_index(op.f('ix_experiment_targets_opportunity_id'), 'experiment_targets', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_experiment_targets_status'), 'experiment_targets', ['status'], unique=False)

    # 3) interactions 扩展：结构化动作 + 目标/联系人关联（SQLite 需 batch 重建加 FK）
    with op.batch_alter_table('interactions') as batch_op:
        batch_op.add_column(sa.Column('target_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('contact_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('interaction_type', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('direction', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('subject', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('result', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('sentiment', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('next_action', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('evidence_attachment', sa.Text(), nullable=True))
        batch_op.create_foreign_key('fk_interactions_target_id', 'experiment_targets', ['target_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_interactions_contact_id', 'company_contacts', ['contact_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_interactions_target_id'), 'interactions', ['target_id'], unique=False)
    op.create_index(op.f('ix_interactions_contact_id'), 'interactions', ['contact_id'], unique=False)
    op.create_index(op.f('ix_interactions_interaction_type'), 'interactions', ['interaction_type'], unique=False)
    op.create_index(op.f('ix_interactions_direction'), 'interactions', ['direction'], unique=False)
    op.create_index(op.f('ix_interactions_occurred_at'), 'interactions', ['occurred_at'], unique=False)
    op.create_index(op.f('ix_interactions_result'), 'interactions', ['result'], unique=False)

    # 4) quotes（真实报价；报价金额永远不是收入）
    op.create_table('quotes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('experiment_id', sa.String(length=32), nullable=True),
    sa.Column('company_id', sa.String(length=32), nullable=False),
    sa.Column('opportunity_id', sa.String(length=32), nullable=True),
    sa.Column('target_id', sa.String(length=32), nullable=True),
    sa.Column('amount', sa.Numeric(14, 2), nullable=False),
    sa.Column('currency', sa.String(length=10), nullable=False),
    sa.Column('billing_type', sa.String(length=30), nullable=True),
    sa.Column('scope', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=30), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['target_id'], ['experiment_targets.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quotes_company_id'), 'quotes', ['company_id'], unique=False)
    op.create_index(op.f('ix_quotes_experiment_id'), 'quotes', ['experiment_id'], unique=False)
    op.create_index(op.f('ix_quotes_opportunity_id'), 'quotes', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_quotes_status'), 'quotes', ['status'], unique=False)
    op.create_index(op.f('ix_quotes_target_id'), 'quotes', ['target_id'], unique=False)

    # 5) experiment_outcomes（目标企业终态快照，驱动 Opportunity Feedback）
    op.create_table('experiment_outcomes',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('target_id', sa.String(length=32), nullable=False),
    sa.Column('experiment_id', sa.String(length=32), nullable=False),
    sa.Column('company_id', sa.String(length=32), nullable=False),
    sa.Column('opportunity_id', sa.String(length=32), nullable=True),
    sa.Column('final_status', sa.String(length=30), nullable=False),
    sa.Column('won', sa.Boolean(), nullable=False),
    sa.Column('contract_amount', sa.Numeric(14, 2), nullable=True),
    sa.Column('received_amount', sa.Numeric(14, 2), nullable=True),
    sa.Column('currency', sa.String(length=10), nullable=True),
    sa.Column('reject_reason', sa.String(length=50), nullable=True),
    sa.Column('pain_confirmed', sa.Boolean(), nullable=True),
    sa.Column('budget_confirmed', sa.Boolean(), nullable=True),
    sa.Column('intent_confirmed', sa.Boolean(), nullable=True),
    sa.Column('solution_fit_confirmed', sa.Boolean(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['target_id'], ['experiment_targets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_experiment_outcomes_company_id'), 'experiment_outcomes', ['company_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcomes_experiment_id'), 'experiment_outcomes', ['experiment_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcomes_final_status'), 'experiment_outcomes', ['final_status'], unique=False)
    op.create_index(op.f('ix_experiment_outcomes_opportunity_id'), 'experiment_outcomes', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_experiment_outcomes_reject_reason'), 'experiment_outcomes', ['reject_reason'], unique=False)
    op.create_index(op.f('ix_experiment_outcomes_target_id'), 'experiment_outcomes', ['target_id'], unique=False)

    # 6) opportunity_feedback（预测 vs 真实结果；只积累数据，不自动训练）
    op.create_table('opportunity_feedback',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('opportunity_id', sa.String(length=32), nullable=False),
    sa.Column('target_id', sa.String(length=32), nullable=True),
    sa.Column('predicted_score', sa.Float(), nullable=False),
    sa.Column('predicted_grade', sa.String(length=5), nullable=True),
    sa.Column('actual_reply', sa.Boolean(), nullable=True),
    sa.Column('actual_meeting', sa.Boolean(), nullable=True),
    sa.Column('actual_quote', sa.Boolean(), nullable=True),
    sa.Column('actual_pilot', sa.Boolean(), nullable=True),
    sa.Column('actual_win', sa.Boolean(), nullable=True),
    sa.Column('actual_revenue', sa.Float(), nullable=True),
    sa.Column('reject_reason', sa.String(length=50), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('feedback_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_opportunity_feedback_feedback_at'), 'opportunity_feedback', ['feedback_at'], unique=False)
    op.create_index(op.f('ix_opportunity_feedback_opportunity_id'), 'opportunity_feedback', ['opportunity_id'], unique=False)
    op.create_index(op.f('ix_opportunity_feedback_target_id'), 'opportunity_feedback', ['target_id'], unique=False)

    # 7) company_contacts 扩展：结构化联系方式 + 来源 + 验证状态
    op.add_column('company_contacts', sa.Column('email', sa.String(length=200), nullable=True))
    op.add_column('company_contacts', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('company_contacts', sa.Column('public_profile_url', sa.Text(), nullable=True))
    op.add_column('company_contacts', sa.Column('source_url', sa.Text(), nullable=True))
    op.add_column('company_contacts', sa.Column('source_type', sa.String(length=50), nullable=True))
    op.add_column('company_contacts', sa.Column('verification_status', sa.String(length=30), nullable=False, server_default='UNVERIFIED'))
    op.add_column('company_contacts', sa.Column('is_decision_maker', sa.Boolean(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_company_contacts_verification_status'), 'company_contacts', ['verification_status'], unique=False)

    # 8) pain_points 扩展：真实客户确认（CONFIRMED 的来源留痕）
    op.add_column('pain_points', sa.Column('confirmed_by_interaction_id', sa.String(length=32), nullable=True))
    op.add_column('pain_points', sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('pain_points', sa.Column('confirmed_by', sa.String(length=100), nullable=True))

    # 9) opportunities 扩展：observed_intent / 确认预算 / 联系聚合
    op.add_column('opportunities', sa.Column('observed_intent', sa.String(length=30), nullable=True))
    op.add_column('opportunities', sa.Column('confirmed_budget', sa.String(length=200), nullable=True))
    op.add_column('opportunities', sa.Column('last_contacted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('opportunities', sa.Column('contact_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_index(op.f('ix_opportunities_last_contacted_at'), 'opportunities', ['last_contacted_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_opportunities_last_contacted_at'), table_name='opportunities')
    op.drop_column('opportunities', 'contact_count')
    op.drop_column('opportunities', 'last_contacted_at')
    op.drop_column('opportunities', 'confirmed_budget')
    op.drop_column('opportunities', 'observed_intent')

    op.drop_column('pain_points', 'confirmed_by')
    op.drop_column('pain_points', 'confirmed_at')
    op.drop_column('pain_points', 'confirmed_by_interaction_id')

    op.drop_index(op.f('ix_company_contacts_verification_status'), table_name='company_contacts')
    op.drop_column('company_contacts', 'is_decision_maker')
    op.drop_column('company_contacts', 'verification_status')
    op.drop_column('company_contacts', 'source_type')
    op.drop_column('company_contacts', 'source_url')
    op.drop_column('company_contacts', 'public_profile_url')
    op.drop_column('company_contacts', 'phone')
    op.drop_column('company_contacts', 'email')

    op.drop_table('opportunity_feedback')

    op.drop_table('experiment_outcomes')
    op.drop_table('quotes')

    op.drop_index(op.f('ix_interactions_result'), table_name='interactions')
    op.drop_index(op.f('ix_interactions_occurred_at'), table_name='interactions')
    op.drop_index(op.f('ix_interactions_direction'), table_name='interactions')
    op.drop_index(op.f('ix_interactions_interaction_type'), table_name='interactions')
    op.drop_index(op.f('ix_interactions_contact_id'), table_name='interactions')
    op.drop_index(op.f('ix_interactions_target_id'), table_name='interactions')
    with op.batch_alter_table('interactions') as batch_op:
        batch_op.drop_column('evidence_attachment')
        batch_op.drop_column('created_by')
        batch_op.drop_column('next_action_at')
        batch_op.drop_column('next_action')
        batch_op.drop_column('sentiment')
        batch_op.drop_column('result')
        batch_op.drop_column('summary')
        batch_op.drop_column('subject')
        batch_op.drop_column('occurred_at')
        batch_op.drop_column('direction')
        batch_op.drop_column('interaction_type')
        batch_op.drop_column('contact_id')
        batch_op.drop_column('target_id')

    op.drop_table('experiment_targets')

    for col in ['conclusion_notes', 'failure_criteria', 'success_criteria', 'target_wins', 'target_pilots',
                'target_quotes', 'target_meetings', 'target_replies', 'target_contacts', 'end_at', 'start_at',
                'price_type', 'price_currency', 'price_amount', 'offer_description', 'value_proposition']:
        op.drop_column('experiments', col)
