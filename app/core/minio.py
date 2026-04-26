from minio import Minio
from minio.error import S3Error
from app.core.config import settings

# MinIO client
minio_client = Minio(
    settings.MINIO_ENDPOINT,
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=settings.MINIO_SECURE
)


async def upload_file(bucket_name: str, object_name: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    """
    Загрузить файл в MinIO
    """
    try:
        # Создаем бакет, если он не существует
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)

        # Загружаем файл
        minio_client.fput_object(bucket_name, object_name, file_path, content_type=content_type)

        # Возвращаем URL файла
        return f"http{'s' if settings.MINIO_SECURE else ''}://{settings.MINIO_ENDPOINT}/{bucket_name}/{object_name}"

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
    try:
        url = minio_client.presigned_get_object(bucket_name, object_name, expires=expires)
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