import json

from minio import Minio
from minio.error import S3Error
from urllib.parse import urlsplit, urlunsplit
from datetime import timedelta

from app.core.config import settings

# MinIO client
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)

PUBLIC_READ_OBJECT_PREFIXES = (
    "actors/*.jpeg",
    "actors/*.jpg",
    "actors/*.png",
    "actors/*.webp",
    "events/*.jpeg",
    "events/*.jpg",
    "events/*.png",
    "events/*.webp",
    "movies/*.jpeg",
    "movies/*.jpg",
    "movies/*.png",
    "movies/*.webp",
    "movies/posters/*",
    "posters/*.jpeg",
    "posters/*.jpg",
    "posters/*.png",
    "posters/*.webp",
    "seed/posters/*.jpeg",
    "seed/posters/*.jpg",
    "seed/posters/*.png",
    "seed/posters/*.webp",
    "serials/posters/*.jpeg",
    "serials/posters/*.jpg",
    "serials/posters/*.png",
    "serials/posters/*.webp",
)


def _extract_netloc(endpoint: str) -> str:
    normalized = endpoint.strip().rstrip("/")
    if "://" not in normalized:
        normalized = f"http://{normalized}"
    return urlsplit(normalized).netloc


def get_minio_public_base_url() -> str:
    configured_base_url = settings.MINIO_PUBLIC_BASE_URL
    if configured_base_url:
        return configured_base_url.strip().rstrip("/")

    netloc = _extract_netloc(settings.MINIO_ENDPOINT)
    host, separator, port = netloc.partition(":")
    if host == "minio":
        host = "localhost"
    public_netloc = f"{host}{separator}{port}" if separator else host
    scheme = "https" if settings.MINIO_SECURE else "http"
    return f"{scheme}://{public_netloc}"


def build_public_object_url(bucket_name: str, object_name: str) -> str:
    normalized_object_name = object_name.lstrip("/")
    return f"{get_minio_public_base_url()}/{bucket_name}/{normalized_object_name}"


def _public_minio_client() -> Minio:
    public_base_url = urlsplit(get_minio_public_base_url())
    return Minio(
        public_base_url.netloc,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=public_base_url.scheme == "https",
    )


def _build_public_read_policy(bucket_name: str) -> str:
    resources = [
        f"arn:aws:s3:::{bucket_name}/{prefix.lstrip('/')}"
        for prefix in PUBLIC_READ_OBJECT_PREFIXES
    ]
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": resources,
                }
            ],
        },
        separators=(",", ":"),
    )


def ensure_media_bucket() -> None:
    bucket_name = settings.MINIO_BUCKET_NAME
    ensure_bucket(bucket_name)


def ensure_bucket(bucket_name: str) -> None:
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    if bucket_name == settings.MINIO_BUCKET_NAME:
        minio_client.set_bucket_policy(bucket_name, _build_public_read_policy(bucket_name))


def to_public_url(url: str | None) -> str | None:
    if not url:
        return url

    parsed_url = urlsplit(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        return url

    internal_netloc = _extract_netloc(settings.MINIO_ENDPOINT)
    public_base_url = urlsplit(get_minio_public_base_url())
    bucket_path = f"/{settings.MINIO_BUCKET_NAME}/"
    if parsed_url.netloc != internal_netloc and (
        parsed_url.netloc == public_base_url.netloc
        or not parsed_url.path.startswith(bucket_path)
    ):
        return url

    return urlunsplit(
        (
            public_base_url.scheme,
            public_base_url.netloc,
            parsed_url.path,
            parsed_url.query,
            parsed_url.fragment,
        )
    )


def normalize_media_fields(data: dict | None, fields: tuple[str, ...]) -> dict:
    if not data:
        return {}

    normalized = dict(data)
    for field in fields:
        if field in normalized:
            normalized[field] = to_public_url(normalized[field])
    return normalized


async def upload_file(bucket_name: str, object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    """
    Загрузить файл в MinIO
    """
    try:
        # Создаем бакет, если он не существует
        ensure_bucket(bucket_name)

        # Загружаем файл
        minio_client.fput_object(bucket_name, object_name, file_path, content_type=content_type)

        # Возвращаем URL файла
        return build_public_object_url(bucket_name, object_name)

    except S3Error as e:
        raise ValueError(f"Failed to upload file to MinIO: {str(e)}")


async def delete_file(bucket_name: str, object_name: str) -> bool:
    """
    Удалить файл из MinIO
    """
    try:
        minio_client.remove_object(bucket_name, object_name)
        return True
    except S3Error as e:
        raise ValueError(f"Failed to delete file from MinIO: {str(e)}")


async def get_presigned_url(bucket_name: str, object_name: str, expires: int = 3600) -> str:
    """
    Получить presigned URL для скачивания файла
    """
    return get_presigned_url_sync(bucket_name, object_name, expires)

def get_presigned_url_sync(bucket_name: str, object_name: str, expires: int = 3600) -> str:
    """
    Получить presigned URL для скачивания файла синхронно
    """
    try:
        url = _public_minio_client().presigned_get_object(
            bucket_name,
            object_name,
            expires=timedelta(seconds=expires),
        )
        return url
    except S3Error as e:
        raise ValueError(f"Failed to generate presigned URL: {str(e)}")


def file_exists(bucket_name: str, object_name: str) -> bool:
    """
    Проверить существование файла в MinIO
    """
    try:
        minio_client.stat_object(bucket_name, object_name)
        return True
    except S3Error:
        return False
