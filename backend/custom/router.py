from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
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
    UpdateRequestFieldsRequest,
)
from custom.schemas.response import (
    AdminCustomRequestDetailResponse,
    AdminCustomRequestListResponse,
    AdminMarkNegotiatingResponse,
    AdminSendQuoteResponse,
    CanvasSizeListResponse,
    ConfirmQuoteResponse,
    CreateCustomRequestResponse,
    CustomRequestDetailResponse,
    CustomRequestListResponse,
    CustomRequestMessageResponse,
    ExtendQuoteResponse,
    PhotoPriceListResponse,
    PhotoSignedUrlResponse,
    QuoteSummaryResponse,
    RejectQuoteResponse,
    RequestRevisionResponse,
    UpdatePhotoResponse,
)
from custom.sse import hub as sse_hub
from dependencies.auth import require_admin, require_auth

router = APIRouter(tags=["Custom"])


# ── Public reference data（無需登入；供 CustomPage 表單使用）──────────────────


@router.get("/canvas-sizes", response_model=CanvasSizeListResponse)
async def list_active_canvas_sizes(db: AsyncSession = Depends(get_db)):
    """公開：列出所有 is_active=true 的畫布尺寸（供客製表單下拉）。

    Response: { items: [{id, canvas_w_cm, canvas_h_cm, display_name}] }
    """
    from sqlalchemy import select

    from custom.models import CanvasSize
    result = await db.execute(
        select(CanvasSize)
        .where(CanvasSize.is_active.is_(True))
        .order_by(CanvasSize.sort_order, CanvasSize.canvas_w_cm)
    )
    rows = result.scalars().all()
    return {
        "items": [
            {
                "id": str(r.id),
                "canvas_w_cm": r.canvas_w_cm,
                "canvas_h_cm": r.canvas_h_cm,
                "display_name": r.display_name,
            }
            for r in rows
        ]
    }


@router.get("/custom-photo-prices", response_model=PhotoPriceListResponse)
async def list_public_photo_prices(db: AsyncSession = Depends(get_db)):
    """公開：客製照片基礎定價表（供 PriceRangeHint 顯示參考價）。

    Response: { items: [{canvas_w, canvas_h, difficulty, price}] }
    若管理員後台尚未填入價格 → items 可能為空陣列。
    """
    from sqlalchemy import select

    from custom.models import CustomPhotoPrice
    result = await db.execute(
        select(CustomPhotoPrice)
        .where(CustomPhotoPrice.price.is_not(None))
        .order_by(CustomPhotoPrice.canvas_w, CustomPhotoPrice.canvas_h)
    )
    rows = result.scalars().all()
    items = []
    for r in rows:
        diff = r.difficulty
        items.append({
            "id": str(r.id),
            "canvas_w": r.canvas_w,
            "canvas_h": r.canvas_h,
            "difficulty": diff.value if hasattr(diff, "value") else diff,
            "price": float(r.price) if r.price is not None else None,
        })
    return {"items": items}


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


@router.get(
    "/custom-requests/{request_id}/photo-signed-url",
    response_model=PhotoSignedUrlResponse,
    description=(
        "Customer 取自己客製申請照片的短期 read signed URL（15 分鐘）。"
        "DB 中 photo_url 為私密 firebase_path（custom_photos/...），不可直接給 <img>，"
        "需透過此端點重簽 GET URL。"
    ),
)
async def customer_get_photo_signed_url(
    request_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.customer_get_photo_signed_url(db, current_user.id, request_id)


@router.patch(
    "/custom-requests/{request_id}", response_model=CustomRequestDetailResponse
)
async def update_request_fields(
    request_id: UUID,
    body: UpdateRequestFieldsRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """quote_pending 狀態下客戶可改 canvas / difficulty / customer_notes（不含照片）。

    照片走 PATCH /photo。negotiating 後此 endpoint 回 409。
    """
    req = await service.update_request_fields(
        db, current_user.id, request_id, body.changes()
    )
    # 回傳完整 detail（前端可直接 hydrate query cache）
    detail = await service.get_customer_request(db, current_user.id, req.id)
    return detail


# ── SSE endpoints ────────────────────────────────────────────────────────────
# 規格：docs/api.md L1068, L1171
# 業務：custom_request 訊息／狀態變化即時推送，避免客戶／admin 重整頁


@router.get("/custom-requests/{request_id}/sse", response_model=None)
async def customer_sse(
    request_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """客戶端訂閱該 request 的訊息 / 狀態事件。

    驗證 owner — 不能訂閱別人的申請。連線維持直到客戶端斷開。
    """
    # 驗證該 request 屬於 current_user（service 內已 raise 404 if not owner）
    await service.get_customer_request(db, current_user.id, request_id)

    queue = sse_hub.subscribe_customer(request_id)

    async def event_stream():
        try:
            async for payload in sse_hub.stream(queue):
                yield payload
        finally:
            sse_hub.unsubscribe_customer(request_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/admin/custom-requests/sse", response_model=None)
async def admin_sse(_=Depends(require_admin)):
    """管理員全局訂閱客製訊息／新申請通知。"""
    queue = sse_hub.subscribe_admin()

    async def event_stream():
        try:
            async for payload in sse_hub.stream(queue):
                yield payload
        finally:
            sse_hub.unsubscribe_admin(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
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


@router.get(
    "/admin/custom-requests/{request_id}/preview-watermark",
    response_model=None,  # binary PNG stream
    response_class=Response,
)
async def admin_get_preview_watermark(
    request_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """送報價前 admin 預覽客戶會看到的浮水印圖。不消耗 view_count。"""
    png = await service.admin_get_preview_watermark(db, request_id)
    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


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
        production_job_id=body.production_job_id,
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
