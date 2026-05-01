"""Drop legacy movie-series columns

Revision ID: 008
Revises: 007
Create Date: 2026-05-01 19:45:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("episodes")
    op.drop_column("movies", "seasons_count")
    op.drop_column("movies", "is_series")


def downgrade() -> None:
    op.add_column(
        "movies",
        sa.Column("is_series", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "movies",
        sa.Column("seasons_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("movies", "is_series", server_default=None)
    op.alter_column("movies", "seasons_count", server_default=None)

    op.create_table(
        "episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("video_url", sa.String(length=1000), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["movie_id"], ["movies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("movie_id", "season_number", "episode_number", name="uq_episode_movie_season_number"),
    )
