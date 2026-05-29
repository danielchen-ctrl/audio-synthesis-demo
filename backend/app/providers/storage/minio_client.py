"""MinIO 客户端封装。"""
from __future__ import annotations

import io
from datetime import timedelta
from functools import lru_cache

from loguru import logger
from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings


@lru_cache
def get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL,
    )


def ensure_bucket() -> None:
    """启动时确保 bucket 存在。"""
    settings = get_settings()
    client = get_minio_client()
    try:
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
            logger.info(f"Created MinIO bucket: {settings.MINIO_BUCKET}")
    except S3Error as e:
        logger.error(f"MinIO bucket check failed: {e}")
        raise


def upload_bytes(
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """上传字节流，返回 object key。"""
    settings = get_settings()
    client = get_minio_client()
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return key


def upload_file(key: str, file_path: str, content_type: str = "application/octet-stream") -> str:
    settings = get_settings()
    client = get_minio_client()
    client.fput_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        file_path=file_path,
        content_type=content_type,
    )
    return key


def get_presigned_download_url(
    key: str,
    expires_sec: int = 600,
    *,
    force_download_name: str | None = None,
) -> str:
    """生成预签名下载 URL（浏览器直接从 MinIO 取）。

    force_download_name: 若提供，附加 response-content-disposition 头
      让浏览器触发"另存为"对话框而不是直接打开。
    """
    settings = get_settings()
    # 使用公网 endpoint 重写 URL，让浏览器能访问
    client = Minio(
        endpoint=settings.MINIO_PUBLIC_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_PUBLIC_ENDPOINT.startswith("https"),
    )
    response_headers: dict[str, str] | None = None
    if force_download_name:
        # RFC 5987: 中文文件名用 UTF-8 编码
        from urllib.parse import quote
        encoded = quote(force_download_name)
        response_headers = {
            "response-content-disposition": (
                f"attachment; filename=\"{force_download_name}\"; "
                f"filename*=UTF-8''{encoded}"
            ),
        }
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=key,
        expires=timedelta(seconds=expires_sec),
        response_headers=response_headers,
    )


def delete_object(key: str) -> None:
    settings = get_settings()
    client = get_minio_client()
    client.remove_object(settings.MINIO_BUCKET, key)


def get_object_stream(key: str):
    """返回 MinIO 对象的流（用完必须 close + release_conn）。"""
    settings = get_settings()
    client = get_minio_client()
    return client.get_object(settings.MINIO_BUCKET, key)


def build_audio_key(file_id: str, file_name: str) -> str:
    """音频对象 key 格式: audio/<file_id 前2位>/<file_id>/<file_name>"""
    return f"audio/{file_id[:2]}/{file_id}/{file_name}"
