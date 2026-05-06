import logging

from fastapi import APIRouter, Depends

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
    return upload_service.generate_public_signed_url(
        "case_images", body.filename, body.content_type
    )


@router.post("/upload/custom-photo", response_model=PrivateUploadResponse)
async def upload_custom_photo(
    body: UploadImageRequest,
    _=Depends(require_auth),
):
    return upload_service.generate_private_signed_url(
        "custom_photos", body.filename, body.content_type
    )


# ── Diagnostics（admin 用）─────────────────────────────────────────────


@router.get("/admin/system/firebase-status", tags=["System"])
async def firebase_status(_=Depends(require_admin)):
    """檢查 Firebase Storage bucket + CORS 設定。"""
    from core.firebase import get_bucket
    bucket = get_bucket()
    return {
        "bucket": bucket.name,
        "cors": bucket.cors or [],
    }


@router.post("/admin/system/firebase-cors-fix", tags=["System"])
async def firebase_cors_fix(_=Depends(require_admin)):
    """一鍵修正 Firebase Storage CORS（允許 localhost / vercel admin 直傳）。"""
    from core.firebase import get_bucket

    ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "https://yiimui-admin.vercel.app",
        "https://paint-by-number-store.vercel.app",
    ]
    rules = [
        {
            "origin": ALLOWED_ORIGINS,
            "method": ["PUT", "GET", "HEAD", "OPTIONS"],
            "responseHeader": ["Content-Type"],
            "maxAgeSeconds": 3600,
        }
    ]

    bucket = get_bucket()
    before = bucket.cors or []
    bucket.cors = rules
    bucket.patch()
    return {
        "ok": True,
        "bucket": bucket.name,
        "before": before,
        "after": bucket.cors,
        "message": "CORS rules updated",
    }
