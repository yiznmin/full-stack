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


def copy_blob_to_public_prefix(source_url: str, prefix: str) -> dict:
    """把任意 Firebase blob server-side 複製到 public prefix，注入 download token。

    支援 source_url 格式：
    - gs://bucket/path
    - https://firebasestorage.googleapis.com/v0/b/<bucket>/o/<encoded_path>?alt=media
    - https://storage.googleapis.com/<bucket>/<path>?<query>（同 bucket 簽章 URL）

    用途：admin「從製作任務帶入」案例封面 — production_jobs/** 路徑 storage rules
    不公開讀（403），需要先 copy 到 case_images/** 公開區才能用作案例封面。
    """
    bucket = get_bucket()

    # 解析 source path
    src_path: str | None = None
    if source_url.startswith("gs://"):
        bucket_and_path = source_url[len("gs://"):]
        _, _, src_path = bucket_and_path.partition("/")
    elif "firebasestorage.googleapis.com/v0/b/" in source_url:
        # https://firebasestorage.googleapis.com/v0/b/<bucket>/o/<encoded_path>?alt=media...
        import re
        m = re.search(r"/o/([^?]+)", source_url)
        if m:
            src_path = urllib.parse.unquote(m.group(1))
    elif "storage.googleapis.com/" in source_url:
        # https://storage.googleapis.com/<bucket>/<path>?<query>
        m = source_url.split("storage.googleapis.com/", 1)[1]
        _, _, rest = m.partition("/")
        src_path = rest.split("?", 1)[0]

    if not src_path:
        raise ValueError(f"無法從 source_url 解出 blob 路徑：{source_url}")

    src_blob = bucket.blob(src_path)
    if not src_blob.exists():
        raise ValueError(f"來源 blob 不存在：{src_path}")

    # 目的 path：複用原檔名（取 basename），加 uuid 前綴避免衝突
    src_filename = src_path.rsplit("/", 1)[-1]
    safe = _safe_name(src_filename)
    dst_path = f"{prefix}/{uuid.uuid4().hex}_{safe}"

    # server-side copy（同 bucket 內，O(1) 不傳 bytes）
    new_blob = bucket.copy_blob(src_blob, bucket, dst_path)

    # 設 download token + 保留 source 的 content_type
    download_token = uuid.uuid4().hex
    new_blob.metadata = {"firebaseStorageDownloadTokens": download_token}
    new_blob.patch()

    return {
        "public_url": _firebase_download_url(bucket.name, dst_path, download_token),
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


def generate_private_read_signed_url(
    raw_path_or_url: str, ttl_minutes: int = _UPLOAD_TTL_MINUTES,
) -> dict:
    """私有檔案 → 短期讀取 signed URL。

    支援輸入：
    - 純 blob path（DB 儲存格式，如 ``custom_photos/abc.jpg``）
    - ``gs://bucket/path``
    - ``https://storage.googleapis.com/<bucket>/<path>?...`` 既有 signed URL（重簽）

    用途：customer 端 ``GET /custom-requests/{id}/photo-signed-url`` 用此函式
    回 ``<img>`` 可直接 src 的 URL。
    """
    bucket = get_bucket()
    blob_path: str
    if raw_path_or_url.startswith("gs://"):
        bucket_and_path = raw_path_or_url[len("gs://"):]
        _, _, blob_path = bucket_and_path.partition("/")
    elif "/" + bucket.name + "/" in raw_path_or_url:
        blob_path = raw_path_or_url.split(f"/{bucket.name}/", 1)[1].split("?", 1)[0]
    else:
        # 純 blob path
        blob_path = raw_path_or_url

    if not blob_path:
        raise ValueError(f"無法解析 blob 路徑：{raw_path_or_url}")

    blob = bucket.blob(blob_path)
    ttl = timedelta(minutes=ttl_minutes)
    url = blob.generate_signed_url(
        version="v4",
        expiration=ttl,
        method="GET",
    )
    return {
        "url": url,
        "expires_at": datetime.now(UTC) + ttl,
    }
