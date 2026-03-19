"""Add BYOK (Bring Your Own Key) fields to User model

Revision ID: byok_api_keys
Revises: fc5a4539a324
Create Date: 2026-03-18

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'byok_api_keys'
down_revision = 'fc5a4539a324'
branch_labels = None
depends_on = None


def upgrade():
    # Add gemini_api_key column
    op.add_column('user', sa.Column('gemini_api_key', sa.String(length=512), nullable=True))
    
    # Add use_own_api_key column
    op.add_column('user', sa.Column('use_own_api_key', sa.Boolean(), nullable=True, default=False))


def downgrade():
    # Remove columns
    op.drop_column('user', 'use_own_api_key')
    op.drop_column('user', 'gemini_api_key')
