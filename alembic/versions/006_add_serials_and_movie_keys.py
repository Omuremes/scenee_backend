"""Add serials and movie keys

Revision ID: 006
Revises: 005
Create Date: 2026-04-28 19:40:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Add keys to movies
    op.add_column("movies", sa.Column("poster_key", sa.String(length=1000), nullable=True))
    op.add_column("movies", sa.Column("video_file_key", sa.String(length=1000), nullable=True))

    # Create serials tables
    op.create_table(
        "serials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("poster_key", sa.String(length=1000), nullable=True),
    )
    op.create_index(op.f("ix_serials_name"), "serials", ["name"], unique=False)

    op.create_table(
        "serial_actors",
        sa.Column("serial_id", UUID(as_uuid=True), sa.ForeignKey("serials.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "serial_category_links",
        sa.Column("serial_id", UUID(as_uuid=True), sa.ForeignKey("serials.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("category_id", UUID(as_uuid=True), sa.ForeignKey("movie_categories.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "seasons",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("serial_id", UUID(as_uuid=True), sa.ForeignKey("serials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("season_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("release_year", sa.Integer(), nullable=True),
        sa.UniqueConstraint("serial_id", "season_number", name="uq_season_serial_number"),
    )

    op.create_table(
        "serial_episodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("season_id", UUID(as_uuid=True), sa.ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.UniqueConstraint("season_id", "episode_number", name="uq_serial_episode_season_number"),
    )

    op.create_table(
        "episode_files",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("episode_id", UUID(as_uuid=True), sa.ForeignKey("serial_episodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("minio_bucket", sa.String(length=255), nullable=False),
        sa.Column("minio_object_key", sa.String(length=1000), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.UniqueConstraint("episode_id", name="uq_episode_file_episode"),
    )


def downgrade() -> None:
    op.drop_table("episode_files")
    op.drop_table("serial_episodes")
    op.drop_table("seasons")
    op.drop_table("serial_category_links")
    op.drop_table("serial_actors")
    op.drop_index(op.f("ix_serials_name"), table_name="serials")
    op.drop_table("serials")
    op.drop_column("movies", "video_file_key")
    op.drop_column("movies", "poster_key")
