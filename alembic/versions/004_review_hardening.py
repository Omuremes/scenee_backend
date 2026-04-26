"""Harden review constraints and align event review schema

Revision ID: 004
Revises: 003
Create Date: 2026-04-27 12:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM reviews
        WHERE id NOT IN (
            SELECT id
            FROM (
                SELECT DISTINCT ON (movie_id, user_id) id
                FROM reviews
                ORDER BY movie_id, user_id, created_at DESC, id DESC
            ) kept
        )
        """
    )
    op.execute(
        """
        DELETE FROM event_reviews
        WHERE id NOT IN (
            SELECT id
            FROM (
                SELECT DISTINCT ON (event_id, user_id) id
                FROM event_reviews
                ORDER BY event_id, user_id, created_at DESC, id DESC
            ) kept
        )
        """
    )

    op.alter_column(
        "event_reviews",
        "rating",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="rating::double precision",
    )
    op.drop_constraint("ck_event_review_rating", "event_reviews", type_="check")
    op.create_check_constraint(
        "ck_event_review_rating",
        "event_reviews",
        "rating >= 1.0 AND rating <= 10.0",
    )
    op.create_unique_constraint("uq_review_movie_user", "reviews", ["movie_id", "user_id"])
    op.create_unique_constraint("uq_event_review_event_user", "event_reviews", ["event_id", "user_id"])


def downgrade() -> None:
    op.drop_constraint("uq_event_review_event_user", "event_reviews", type_="unique")
    op.drop_constraint("uq_review_movie_user", "reviews", type_="unique")
    op.drop_constraint("ck_event_review_rating", "event_reviews", type_="check")
    op.create_check_constraint(
        "ck_event_review_rating",
        "event_reviews",
        "rating >= 1 AND rating <= 10",
    )
    op.alter_column(
        "event_reviews",
        "rating",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="ROUND(rating)::integer",
    )
