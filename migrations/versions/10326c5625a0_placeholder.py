"""Placeholder migration to bridge missing revision on Render."""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '10326c5625a0'
down_revision = 'fc5a4539a324'
branch_labels = None
depends_on = None


def upgrade():
    # No-op: historical placeholder to satisfy existing databases.
    pass


def downgrade():
    # No-op: historical placeholder.
    pass

