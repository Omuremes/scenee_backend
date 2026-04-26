"""Expand movie, actor, and review schema

Revision ID: 003
Revises: 002
Create Date: 2026-04-27 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movie_category_links",
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["movie_categories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("movie_id", "category_id"),
    )

    op.add_column("movies", sa.Column("duration_minutes", sa.Integer(), nullable=True))
    op.add_column("movies", sa.Column("seasons_count", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("episodes", sa.Column("duration_minutes", sa.Integer(), nullable=True))

    op.alter_column("posters", "storage_path", existing_type=sa.String(length=1000), nullable=True)
    op.alter_column(
        "reviews",
        "rating",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="rating::double precision",
    )

    op.execute(
        """
        INSERT INTO movie_category_links (movie_id, category_id)
        SELECT id, category_id
        FROM movies
        WHERE category_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE episodes
        SET duration_minutes = CASE
            WHEN duration_sec IS NULL THEN NULL
            ELSE GREATEST(duration_sec / 60, 1)
        END
        """
    )
    op.create_unique_constraint(
        "uq_episode_movie_season_number",
        "episodes",
        ["movie_id", "season_number", "episode_number"],
    )

    op.alter_column("movies", "seasons_count", server_default=None)


def downgrade() -> None:
    op.drop_constraint("uq_episode_movie_season_number", "episodes", type_="unique")
    op.execute("DELETE FROM movie_category_links")

    op.alter_column(
        "reviews",
        "rating",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="ROUND(rating)::integer",
    )
    op.alter_column("posters", "storage_path", existing_type=sa.String(length=1000), nullable=False)

    op.drop_column("episodes", "duration_minutes")
    op.drop_column("movies", "seasons_count")
    op.drop_column("movies", "duration_minutes")
    op.drop_table("movie_category_links")
