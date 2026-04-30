"""add_serial_metadata

Revision ID: ed63303825ce
Revises: 006
Create Date: 2026-04-29 02:58:57.516428

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ed63303825ce'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("serials", sa.Column("average_rating", sa.Float(), server_default="0.0", nullable=False))
    op.add_column("serials", sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False))
    op.add_column("serials", sa.Column("updated_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("serials", "updated_at")
    op.drop_column("serials", "created_at")
    op.drop_column("serials", "average_rating")