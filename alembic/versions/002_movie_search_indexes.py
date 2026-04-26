"""Add movie search indexes

Revision ID: 002
Revises: 001
Create Date: 2026-04-26 23:15:00.000000

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_movies_category_id", "movies", ["category_id"], unique=False)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_movies_search_vector
        ON movies
        USING GIN (
            to_tsvector(
                'simple',
                coalesce(name, '') || ' ' || coalesce(description, '')
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_movies_search_vector")
    op.drop_index("ix_movies_category_id", table_name="movies")
