"""Normalize stored MinIO URLs to the public base URL

Revision ID: 005
Revises: 004
Create Date: 2026-04-27 14:35:00.000000

"""

import os

from alembic import op


# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _normalized_public_base_url() -> str:
    return os.getenv("MINIO_PUBLIC_BASE_URL", "http://localhost:9000").strip().rstrip("/")


def upgrade() -> None:
    public_base_url = _normalized_public_base_url()

    op.execute(
        f"""
        UPDATE actors
        SET photo_url = REPLACE(photo_url, 'http://minio:9000', '{public_base_url}')
        WHERE photo_url LIKE 'http://minio:9000/%'
        """
    )
    op.execute(
        f"""
        UPDATE events
        SET image_url = REPLACE(image_url, 'http://minio:9000', '{public_base_url}')
        WHERE image_url LIKE 'http://minio:9000/%'
        """
    )
    op.execute(
        f"""
        UPDATE posters
        SET url = REPLACE(url, 'http://minio:9000', '{public_base_url}')
        WHERE url LIKE 'http://minio:9000/%'
        """
    )


def downgrade() -> None:
    public_base_url = _normalized_public_base_url()

    op.execute(
        f"""
        UPDATE actors
        SET photo_url = REPLACE(photo_url, '{public_base_url}', 'http://minio:9000')
        WHERE photo_url LIKE '{public_base_url}/%'
        """
    )
    op.execute(
        f"""
        UPDATE events
        SET image_url = REPLACE(image_url, '{public_base_url}', 'http://minio:9000')
        WHERE image_url LIKE '{public_base_url}/%'
        """
    )
    op.execute(
        f"""
        UPDATE posters
        SET url = REPLACE(url, '{public_base_url}', 'http://minio:9000')
        WHERE url LIKE '{public_base_url}/%'
        """
    )
