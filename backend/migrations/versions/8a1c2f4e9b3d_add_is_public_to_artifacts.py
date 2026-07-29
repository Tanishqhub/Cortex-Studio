"""add is_public to artifacts

Revision ID: 8a1c2f4e9b3d
Revises: 5735222756dd
Create Date: 2026-07-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a1c2f4e9b3d'
down_revision = '5735222756dd'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false())
        )
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.alter_column('is_public', server_default=None)


def downgrade():
    with op.batch_alter_table('artifacts', schema=None) as batch_op:
        batch_op.drop_column('is_public')
