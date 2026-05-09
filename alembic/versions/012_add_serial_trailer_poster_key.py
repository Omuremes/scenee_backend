"""Add serial trailer poster key

Revision ID: 012
Revises: 011
Create Date: 2026-05-09 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("serials", sa.Column("trailer_poster_key", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("serials", "trailer_poster_key")
