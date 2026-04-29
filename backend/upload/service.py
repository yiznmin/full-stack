"""Firebase Storage signed-URL helpers for upload endpoints."""
import logging
import urllib.parse
import uuid
from datetime import UTC, datetime, timedelta

from core.firebase import get_bucket

logger = logging.getLogger(__name__)

_UPLOAD_TTL_MINUTES = 15


def _safe_name(filename: str) -> str:
    return filename.replace(" ", "_").replace("/", "_")


def _firebase_download_url(bucket_name: str, path: str) -> str:
    """走 Firebase download URL，公開讀由 storage.rules 控制。"""
    encoded = urllib.parse.quote(path, safe="")
    return f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded}?alt=media"


def generate_public_signed_url(prefix: str, filename: str, content_type: str = "image/jpeg") -> dict:
    """前台會看到的公開圖片（商品圖、案例圖）— 回 Firebase download URL。"""
    bucket = get_bucket()
    name = _safe_name(filename)
    path = f"{prefix}/{uuid.uuid4().hex}_{name}"
    blob = bucket.blob(path)
    ttl = timedelta(minutes=_UPLOAD_TTL_MINUTES)
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=ttl,
        method="PUT",
        content_type=content_type,
    )
    return {
        "upload_url": upload_url,
        "public_url": _firebase_download_url(bucket.name, path),
        "expires_at": datetime.now(UTC) + ttl,
    }


def generate_private_signed_url(prefix: str, filename: str, content_type: str = "image/jpeg") -> dict:
    """私有檔案（用戶客製照片）— 不回公開 URL，只回 firebase_path。"""
    bucket = get_bucket()
    name = _safe_name(filename)
    path = f"{prefix}/{uuid.uuid4().hex}_{name}"
    blob = bucket.blob(path)
    ttl = timedelta(minutes=_UPLOAD_TTL_MINUTES)
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=ttl,
        method="PUT",
        content_type=content_type,
    )
    return {
        "upload_url": upload_url,
        "firebase_path": path,
        "expires_at": datetime.now(UTC) + ttl,
    }
