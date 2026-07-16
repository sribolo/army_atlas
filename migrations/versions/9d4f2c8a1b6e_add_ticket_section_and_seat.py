"""add ticket section and seat

Revision ID: 9d4f2c8a1b6e
Revises: 40bc06dc2787
Create Date: 2026-07-02 18:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d4f2c8a1b6e'
down_revision = '40bc06dc2787'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('section', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('seat', sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table('attendance', schema=None) as batch_op:
        batch_op.drop_column('seat')
        batch_op.drop_column('section')
