"""Set serial reviews to five-star rating scale

Revision ID: 011
Revises: 010
Create Date: 2026-05-04 00:00:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_serial_review_rating", "serial_reviews", type_="check")
    op.create_check_constraint(
        "ck_serial_review_rating",
        "serial_reviews",
        "rating >= 1.0 AND rating <= 5.0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_serial_review_rating", "serial_reviews", type_="check")
    op.create_check_constraint(
        "ck_serial_review_rating",
        "serial_reviews",
        "rating >= 1.0 AND rating <= 10.0",
    )