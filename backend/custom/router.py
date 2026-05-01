from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from custom import service
from custom.schemas.request import (
    AdminSendQuoteRequest,
    ConfirmQuoteRequest,
    CreateCustomRequestRequest,
    PostMessageRequest,
    RejectQuoteRequest,
    RequestRevisionRequest,
    UpdatePhotoRequest,
)
from custom.schemas.response import (
    AdminCustomRequestDetailResponse,
    AdminCustomRequestListResponse,
    AdminMarkNegotiatingResponse,
    AdminSendQuoteResponse,
    ConfirmQuoteResponse,
    CreateCustomRequestResponse,
    CustomRequestDetailResponse,
    CustomRequestListResponse,
    CustomRequestMessageResponse,
    ExtendQuoteResponse,
    PhotoSignedUrlResponse,
    QuoteSummaryResponse,
    RejectQuoteResponse,
    RequestRevisionResponse,
    UpdatePhotoResponse,
)
from dependencies.auth import require_admin, require_auth

router = APIRouter(tags=["Custom"])


# ── Customer endpoints ────────────────────────────────────────────────────────


@router.post(
    "/custom-requests", status_code=201, response_model=CreateCustomRequestResponse
)
async def create_custom_request(
    body: CreateCustomRequestRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    req = await service.create_custom_request(
        db, current_user.id,
        body.request_type, body.photo_url, body.ref_product_id,
        body.canvas_w_cm, body.canvas_h_cm,
        body.difficulty, body.detail,
        body.customer_notes, body.parent_request_id,
    )
    return CreateCustomRequestResponse(
        id=req.id, request_type=req.request_type.value,
        status=req.status.value, created_at=req.created_at,
    )


@router.get("/custom-requests", response_model=CustomRequestListResponse)
async def list_custom_requests(
    current_user=Depends(require_auth),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_customer_requests(
        db, current_user.id, status, page, page_size
    )


@router.get(
    "/custom-requests/{request_id}", response_model=CustomRequestDetailResponse
)
async def get_custom_request(
    request_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_customer_request(db, current_user.id, request_id)


@router.post(
    "/custom-requests/{request_id}/messages",
    status_code=201,
    response_model=CustomRequestMessageResponse,
)
async def post_message(
    request_id: UUID,
    body: PostMessageRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    msg = await service.post_customer_message(
        db, current_user.id, request_id, body.message, body.image_url
    )
    return msg


@router.patch(
    "/custom-requests/{request_id}/photo", response_model=UpdatePhotoResponse
)
async def update_photo(
    request_id: UUID,
    body: UpdatePhotoRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    req = await service.update_photo(db, current_user.id, request_id, body.photo_url)
    return UpdatePhotoResponse(
        id=req.id, photo_url=req.photo_url, updated_at=datetime.now(UTC)
    )


# ── Quote token endpoints (auth + token verification done in service) ────────


@router.get("/custom/quote/{token}", response_model=QuoteSummaryResponse)
async def get_quote(
    token: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_quote_summary(db, current_user.id, token)


@router.get(
    "/custom/quote/{token}/preview",
    response_model=None,  # binary PNG stream — no Pydantic model
    response_class=Response,
)
async def get_quote_preview(
    token: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """客戶端浮水印降解析度預覽圖。token + owner + 狀態 + 過期 + 查看次數限制全部驗。

    回 PNG bytes，前端用 <img src="/.../preview"> 直接 inline 顯示。
    禁 cache（每次請求重算 + 計數）。
    """
    png = await service.get_quote_preview_image(db, current_user.id, token)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "no-store, max-age=0",
            # 客戶端工具想 download 也只拿到浮水印降解析度版
            "Content-Disposition": 'inline; filename="quote-preview.png"',
        },
    )


@router.post(
    "/custom/quote/{token}/confirm",
    status_code=201,
    response_model=ConfirmQuoteResponse,
)
async def confirm_quote(
    token: str,
    body: ConfirmQuoteRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.confirm_quote(
        db, current_user.id, token, body.shipping_profile_id
    )


@router.post("/custom/quote/{token}/reject", response_model=RejectQuoteResponse)
async def reject_quote(
    token: str,
    body: RejectQuoteRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    req = await service.reject_quote(db, current_user.id, token, body.reason)
    return RejectQuoteResponse(
        id=req.id, status=req.status.value, rejected_at=req.rejected_at
    )


@router.post("/custom/quote/{token}/extend", response_model=ExtendQuoteResponse)
async def extend_quote(
    token: str,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    req = await service.extend_quote(db, current_user.id, token)
    return ExtendQuoteResponse(
        id=req.id, quote_expires_at=req.quote_expires_at, is_extended=req.is_extended
    )


@router.post(
    "/custom/quote/{token}/request-revision", response_model=RequestRevisionResponse
)
async def request_revision(
    token: str,
    body: RequestRevisionRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    req = await service.request_revision(db, current_user.id, token, body.reason)
    return RequestRevisionResponse(
        id=req.id, status=req.status.value, revision_count=req.revision_count
    )


# ── Admin endpoints ───────────────────────────────────────────────────────────


@router.get(
    "/admin/custom-requests", response_model=AdminCustomRequestListResponse
)
async def admin_list_custom_requests(
    _=Depends(require_admin),
    status: str | None = Query(default=None),
    request_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_list_requests(db, status, request_type, page, page_size)


@router.get(
    "/admin/custom-requests/{request_id}",
    response_model=AdminCustomRequestDetailResponse,
)
async def admin_get_custom_request(
    request_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_get_request(db, request_id)


@router.post(
    "/admin/custom-requests/{request_id}/messages",
    status_code=201,
    response_model=CustomRequestMessageResponse,
)
async def admin_post_message(
    request_id: UUID,
    body: PostMessageRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_post_message(db, request_id, body.message, body.image_url)


@router.patch(
    "/admin/custom-requests/{request_id}/mark-negotiating",
    response_model=AdminMarkNegotiatingResponse,
)
async def admin_mark_negotiating(
    request_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    req = await service.admin_mark_negotiating(db, request_id)
    return AdminMarkNegotiatingResponse(id=req.id, status=req.status.value)


@router.post(
    "/admin/custom-requests/{request_id}/quote",
    response_model=AdminSendQuoteResponse,
)
async def admin_send_quote(
    request_id: UUID,
    body: AdminSendQuoteRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    req, _token = await service.admin_send_quote(
        db, request_id, body.quoted_price,
        body.detail, body.surcharge_ids, body.quote_note,
    )
    return AdminSendQuoteResponse(
        id=req.id, status=req.status.value,
        quote_expires_at=req.quote_expires_at,
        quoted_at=req.quoted_at,
        quoted_price=float(req.quoted_price),
    )


@router.get(
    "/admin/custom-requests/{request_id}/photo-signed-url",
    response_model=PhotoSignedUrlResponse,
)
async def admin_get_photo_signed_url(
    request_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_get_photo_signed_url(db, request_id)
