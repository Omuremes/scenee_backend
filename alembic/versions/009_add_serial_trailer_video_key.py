"""Add serial trailer video key

Revision ID: 009
Revises: 008
Create Date: 2026-05-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("serials", sa.Column("trailer_video_key", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("serials", "trailer_video_key")