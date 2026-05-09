import logging

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from core.exceptions import BadRequestError
from dependencies.auth import require_admin, require_auth
from production import service as production_service
from production.schemas.request import UploadProductionImageRequest
from production.schemas.response import UploadUrlResponse
from upload import service as upload_service
from upload.schemas.request import UploadImageRequest
from upload.schemas.response import PrivateUploadResponse, PublicUploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Upload"])


@router.post("/upload/production-image", response_model=UploadUrlResponse)
async def upload_production_image(
    body: UploadProductionImageRequest,
    operator=Depends(require_admin),
):
    return production_service.generate_upload_signed_url(body.filename, body.content_type)


@router.post("/upload/product-image", response_model=PublicUploadResponse)
async def upload_product_image(
    body: UploadImageRequest,
    _=Depends(require_admin),
):
    return upload_service.generate_public_signed_url(
        "product_images", body.filename, body.content_type
    )


@router.post("/upload/case-image", response_model=PublicUploadResponse)
async def upload_case_image(
    body: UploadImageRequest,
    _=Depends(require_admin),
):
    """legacy signed-URL flow（保留向後相容；admin 新版用 /upload/case-image-direct）。"""
    return upload_service.generate_public_signed_url(
        "case_images", body.filename, body.content_type
    )


# ── 直接上傳（後端代收 → Firebase）— 案例圖專用 ─────────────────────────


_MAX_CASE_IMAGE_BYTES = 20 * 1024 * 1024
_ALLOWED_CASE_IMAGE_TYPES = ("image/jpeg", "image/png")


class CaseImageDirectResponse(PublicUploadResponse):
    """直接上傳完成後回 public_url（已含 download token，永久可讀）。

    upload_url / expires_at 為 compat，內容與 public_url 一致 / 100 年後。
    """


@router.post(
    "/upload/case-image-direct",
    response_model=CaseImageDirectResponse,
    description=(
        "Admin 直接上傳案例圖（multipart/form-data field name: file）。"
        "後端代收檔案後上傳 Firebase 並注入 download token → 回 100% 可讀的永久 URL。"
        "取代 /upload/case-image 的 signed-URL 流程，避開 PUT/GET race。"
    ),
)
async def upload_case_image_direct(
    file: UploadFile = File(...),  # noqa: B008
    _=Depends(require_admin),
):
    if file.content_type not in _ALLOWED_CASE_IMAGE_TYPES:
        raise BadRequestError(
            f"只接受 JPEG / PNG（收到 {file.content_type}）",
            code="UNSUPPORTED_CONTENT_TYPE",
        )
    contents = await file.read()
    if len(contents) > _MAX_CASE_IMAGE_BYTES:
        raise BadRequestError(
            f"檔案超過 {_MAX_CASE_IMAGE_BYTES // (1024 * 1024)}MB",
            code="FILE_TOO_LARGE",
        )
    if len(contents) == 0:
        raise BadRequestError("檔案為空", code="EMPTY_FILE")

    from datetime import UTC, datetime, timedelta

    result = upload_service.upload_public_file_server_side(
        "case_images",
        contents,
        file.filename or "untitled",
        file.content_type,
    )
    return {
        "upload_url": result["public_url"],
        "public_url": result["public_url"],
        "expires_at": datetime.now(UTC) + timedelta(days=36500),
    }


# ── 從 production_job 帶入封面：copy 到 case_images 公開區 ─────────────


class CopyJobImageRequest(BaseModel):
    source_url: str  # job 的 cover_url 或 preview_url 或 gs:// path 都接受


@router.post(
    "/upload/case-image-from-job",
    response_model=CaseImageDirectResponse,
    description=(
        "Admin「從製作任務帶入」案例封面：後端 server-side copy 該 production_job 的"
        "filled image 到 case_images/ 公開區，並注入 download token。"
        "原因：production_jobs/** 在 Firebase Storage rules 是非公開讀（403），"
        "直接拿 cover_url 給前端 <img> 會 403 破圖。"
    ),
)
async def case_image_from_job(
    body: CopyJobImageRequest,
    _=Depends(require_admin),
):
    from datetime import UTC, datetime, timedelta
    try:
        result = upload_service.copy_blob_to_public_prefix(
            body.source_url, "case_images"
        )
    except ValueError as e:
        raise BadRequestError(str(e), code="COPY_FAILED") from e

    return {
        "upload_url": result["public_url"],
        "public_url": result["public_url"],
        "expires_at": datetime.now(UTC) + timedelta(days=36500),
    }


@router.post("/upload/custom-photo", response_model=PrivateUploadResponse)
async def upload_custom_photo(
    body: UploadImageRequest,
    _=Depends(require_auth),
):
    return upload_service.generate_private_signed_url(
        "custom_photos", body.filename, body.content_type
    )


# ── Diagnostics（admin 用）─────────────────────────────────────────────


@router.post("/admin/system/migrate-product-images", tags=["System"])
async def migrate_product_images(
    _=Depends(require_admin),
    db=Depends(__import__('core.database', fromlist=['get_db']).get_db),
):
    """掃所有商品的 cover_image_url + product_images，把 production_jobs/ 路徑
    server-side 複製到 product_images/ 公開路徑，更新 DB record。

    用途：admin 之前「從變體模板匯入」時直接存 production_jobs URL（沒公開讀），
    customer 看商品時會 ORB 擋住。這個 endpoint 一次性把所有舊紀錄修好。
    """
    from sqlalchemy import select

    from product.models import Product, ProductImage
    from product.service import _maybe_repath_to_public

    fixed_covers = 0
    fixed_images = 0
    skipped = 0

    # Cover images
    result = await db.execute(
        select(Product).where(
            Product.cover_image_url.like("%production_jobs%")
        )
    )
    for prod in result.scalars():
        new_url = _maybe_repath_to_public(prod.cover_image_url)
        if new_url != prod.cover_image_url:
            prod.cover_image_url = new_url
            fixed_covers += 1
        else:
            skipped += 1

    # Product images
    result = await db.execute(
        select(ProductImage).where(
            ProductImage.image_url.like("%production_jobs%")
        )
    )
    for img in result.scalars():
        new_url = _maybe_repath_to_public(img.image_url)
        if new_url != img.image_url:
            img.image_url = new_url
            fixed_images += 1
        else:
            skipped += 1

    await db.commit()
    return {
        "ok": True,
        "fixed_covers": fixed_covers,
        "fixed_images": fixed_images,
        "skipped": skipped,
    }


@router.get("/admin/system/firebase-status", tags=["System"])
async def firebase_status(_=Depends(require_admin)):
    """檢查 Firebase Storage bucket + CORS 設定（每次 reload 確保不是 cached）。"""
    from core.firebase import get_bucket
    bucket = get_bucket()
    bucket.reload()  # 強制從 GCS 拉最新 metadata
    return {
        "bucket": bucket.name,
        "cors": bucket.cors or [],
    }


@router.post("/admin/system/firebase-cors-fix", tags=["System"])
async def firebase_cors_fix(_=Depends(require_admin)):
    """一鍵修正 Firebase Storage CORS（允許 localhost / vercel admin 直傳）。

    Firebase 新版 .firebasestorage.app bucket 的 CORS 透過 Admin SDK 設定可能不持久。
    這裡用 google-cloud-storage SDK 直接操作 GCS bucket，更可靠。
    """
    import base64
    import json as _json
    import os

    from google.cloud import storage
    from google.oauth2 import service_account

    from core.config import settings

    # 用 ['*'] 接受任何 origin — Firebase signed URL PUT 不帶 cookie/credentials，
    # 攻擊者沒有 signed URL token 就沒辦法 PUT，所以 origin 開放是安全的。
    # 這也避免 user 在 Vercel preview URL 上被擋住。
    rules = [
        {
            "origin": ["*"],
            "method": ["PUT", "GET", "HEAD", "OPTIONS", "POST"],
            "responseHeader": ["Content-Type", "Content-MD5", "x-goog-resumable"],
            "maxAgeSeconds": 3600,
        }
    ]

    # 取得 service account credentials（從 BASE64 env 解或從 FIREBASE_CREDENTIALS）
    b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64", "").strip()
    cred_json: dict | None = None
    if b64:
        cred_json = _json.loads(base64.b64decode(b64).decode("utf-8"))
    elif settings.firebase_credentials.strip():
        v = settings.firebase_credentials.strip()
        if v.startswith("{"):
            cred_json = _json.loads(v)
        else:
            with open(v) as f:
                cred_json = _json.load(f)

    if not cred_json:
        return {"ok": False, "error": "No firebase credentials available"}

    credentials = service_account.Credentials.from_service_account_info(cred_json)
    storage_client = storage.Client(
        credentials=credentials,
        project=cred_json.get("project_id"),
    )

    bucket_name = settings.firebase_storage_bucket
    bucket = storage_client.bucket(bucket_name)
    bucket.reload()  # 確保不是 cached
    before = list(bucket.cors or [])
    bucket.cors = rules
    bucket.update()  # 用 update 而不是 patch
    bucket.reload()  # re-read 真實 GCS 狀態
    after = list(bucket.cors or [])

    # 也試試 legacy .appspot.com bucket 以防萬一
    legacy_name = bucket_name.replace(".firebasestorage.app", ".appspot.com")
    legacy_result = {"name": legacy_name, "tried": False}
    if legacy_name != bucket_name:
        try:
            legacy = storage_client.bucket(legacy_name)
            legacy.reload()
            legacy.cors = rules
            legacy.update()
            legacy.reload()
            legacy_result = {
                "name": legacy_name,
                "tried": True,
                "cors": list(legacy.cors or []),
            }
        except Exception as e:
            legacy_result = {"name": legacy_name, "tried": True, "error": str(e)}

    return {
        "ok": len(after) > 0,
        "primary_bucket": bucket_name,
        "before": before,
        "after": after,
        "legacy_bucket": legacy_result,
        "message": "CORS rules updated" if len(after) > 0 else "CORS update did not persist",
    }
