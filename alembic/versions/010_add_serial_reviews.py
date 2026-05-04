"""Add serial reviews

Revision ID: 010
Revises: 009
Create Date: 2026-05-04 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "serial_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("serial_id", UUID(as_uuid=True), sa.ForeignKey("serials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rating >= 1.0 AND rating <= 10.0", name="ck_serial_review_rating"),
        sa.UniqueConstraint("serial_id", "user_id", name="uq_serial_review_serial_user"),
    )


def downgrade() -> None:
    op.drop_table("serial_reviews")