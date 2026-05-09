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


def _firebase_download_url(bucket_name: str, path: str, token: str | None = None) -> str:
    """走 Firebase download URL，公開讀由 storage.rules 控制。

    若帶 token：URL 一定可讀（只要 metadata 內 firebaseStorageDownloadTokens 含此 token）。
    無 token：依賴 storage rules `allow read: if true`。
    """
    encoded = urllib.parse.quote(path, safe="")
    base = f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/{encoded}?alt=media"
    if token:
        return f"{base}&token={token}"
    return base


def upload_public_file_server_side(
    prefix: str, file_bytes: bytes, filename: str, content_type: str,
) -> dict:
    """後端直接收檔案 → 上傳到 Firebase → 設 download token → 回永久 URL。

    用於 admin 端「客製案例圖」這種需要 100% 可讀的場景：
    - 不依賴 signed PUT 流程，沒有 PUT/GET race condition
    - URL 內含 firebaseStorageDownloadTokens，即使 storage rules 收緊也仍可讀
    """
    bucket = get_bucket()
    name = _safe_name(filename)
    path = f"{prefix}/{uuid.uuid4().hex}_{name}"
    blob = bucket.blob(path)

    # 先設 metadata（含 download token）再 upload，這樣 firebase 主控台
    # 也能透過 token 公開存取
    download_token = uuid.uuid4().hex
    blob.metadata = {"firebaseStorageDownloadTokens": download_token}
    blob.upload_from_string(file_bytes, content_type=content_type)
    # upload_from_string 不會帶上 metadata，需要 patch 一次
    blob.patch()

    return {
        "public_url": _firebase_download_url(bucket.name, path, download_token),
    }


def generate_public_signed_url(
    prefix: str, filename: str, content_type: str = "image/jpeg",
) -> dict:
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


def generate_private_signed_url(
    prefix: str, filename: str, content_type: str = "image/jpeg",
) -> dict:
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
