"""t08p0 data quality fix

Revision ID: d1e6f8a3b5c9
Revises: c9d5e3f7a2b8
Create Date: 2026-10-03 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd1e6f8a3b5c9'
down_revision: Union[str, None] = 'c9d5e3f7a2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # T08.0 P0-6：联系人角色区分（采购人/代理机构/项目联系人）与所属组织
    op.add_column('company_contacts', sa.Column('contact_type', sa.String(length=30), nullable=False, server_default='UNCLASSIFIED'))
    op.add_column('company_contacts', sa.Column('organization_name', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('company_contacts', 'organization_name')
    op.drop_column('company_contacts', 'contact_type')
