"""t07 market validation prep

Revision ID: b8c4d2e6f1a9
Revises: e7f3a91b2c4d
Create Date: 2026-10-02 23:50:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b8c4d2e6f1a9'
down_revision: Union[str, None] = 'e7f3a91b2c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T07：目标企业选择必须可解释（任务书五十九）
    op.add_column('experiment_targets', sa.Column('selection_reason', sa.JSON(), nullable=False, server_default='[]'))
    # T07：实验开始时冻结假设/模型版本/报价假设，避免事后无法解释结果（任务书五十四）
    op.add_column('experiments', sa.Column('snapshot_json', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    op.drop_column('experiments', 'snapshot_json')
    op.drop_column('experiment_targets', 'selection_reason')
