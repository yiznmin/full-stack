from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import require_admin, require_auth
from orders import service
from orders.schemas.request import (
    AddCartItemRequest,
    AdminNotesRequest,
    AdminUpdateOrderStatusRequest,
    BatchCreateShipmentRequest,
    CancelOrderRequest,
    CheckoutPreviewRequest,
    CreateOrderRequest,
    CreateShipmentRequest,
    FlagPaymentSubmissionRequest,
    PaymentSubmissionRequest,
    RefundRequest,
    UpdateCartItemRequest,
    UpdateProductionProgressRequest,
    UpdateShippingRequest,
)
from orders.schemas.response import (
    AdminNotesUpdateResponse,
    AdminOrderDetailResponse,
    AdminOrderListResponse,
    BatchCreateShipmentResponse,
    CancelOrderResponse,
    CartItemMutationResponse,
    CartResponse,
    CheckoutPreviewResponse,
    ConfirmReceivedResponse,
    CreateOrderResponse,
    CreateShipmentResponse,
    FlagPaymentSubmissionResponse,
    OrderDetailResponse,
    OrderListResponse,
    OrderStatusUpdateResponse,
    PaymentSubmissionResponse,
    ProductionProgressResponse,
    RefundResponse,
)

router = APIRouter(tags=["orders"])


# ── Cart ──────────────────────────────────────────────────────────────────────

@router.get("/cart", response_model=CartResponse)
async def get_cart(
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_cart(db, current_user.id)


@router.post("/cart/items", status_code=201, response_model=CartItemMutationResponse)
async def add_cart_item(
    body: AddCartItemRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    item = await service.add_cart_item(db, current_user.id, body.variant_id, body.quantity)
    return CartItemMutationResponse(
        id=item.id, variant_id=item.product_variant_id, quantity=item.quantity
    )


@router.patch("/cart/items/{item_id}", response_model=CartItemMutationResponse)
async def update_cart_item(
    item_id: UUID,
    body: UpdateCartItemRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    item = await service.update_cart_item(db, current_user.id, item_id, body.quantity)
    if item is None:
        return CartItemMutationResponse(id=item_id, deleted=True)
    return CartItemMutationResponse(id=item.id, quantity=item.quantity)


@router.delete("/cart/items/{item_id}", status_code=204, response_model=None)
async def delete_cart_item(
    item_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await service.delete_cart_item(db, current_user.id, item_id)


@router.post("/cart/checkout-preview", response_model=CheckoutPreviewResponse)
async def checkout_preview(
    body: CheckoutPreviewRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.checkout_preview(
        db, current_user.id, body.shipping_type, body.user_coupon_id, body.promo_code
    )


# ── Customer orders ───────────────────────────────────────────────────────────

@router.post("/orders", status_code=201, response_model=CreateOrderResponse)
async def create_order(
    body: CreateOrderRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_order(
        db,
        current_user.id,
        body.shipping_profile_id,
        body.shipping_preference,
        body.user_coupon_id,
        body.promo_code,
        body.customer_notes,
    )


@router.get("/orders", response_model=OrderListResponse)
async def list_orders(
    current_user=Depends(require_auth),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_orders(db, current_user.id, status, page, page_size)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order(
    order_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_order_detail(db, current_user.id, order_id)


@router.post(
    "/orders/{order_id}/payment-submission",
    status_code=201,
    response_model=PaymentSubmissionResponse,
)
async def submit_payment(
    order_id: UUID,
    body: PaymentSubmissionRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    sub = await service.submit_payment(
        db, current_user.id, order_id,
        body.transfer_amount, body.transfer_date, body.transfer_time,
        body.account_last5, body.notes,
    )
    return sub


@router.post(
    "/orders/{order_id}/confirm-received",
    status_code=200,
    response_model=ConfirmReceivedResponse,
)
async def confirm_received(
    order_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    order = await service.confirm_received(db, current_user.id, order_id)
    return ConfirmReceivedResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        completed_at=order.completed_at,
    )


@router.patch(
    "/orders/{order_id}/shipping",
    response_model=OrderDetailResponse,
)
async def user_update_shipping(
    order_id: UUID,
    body: UpdateShippingRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """客戶修改自己訂單的出貨資訊。

    僅在 status=pending_payment 階段允許；後端嚴格鎖死。
    """
    await service.update_shipping(
        db,
        order_id=order_id,
        user_id=current_user.id,
        is_admin=False,
        updates=body.model_dump(exclude_none=True),
    )
    return await service.get_order_detail(db, current_user.id, order_id)


@router.post(
    "/orders/{order_id}/cancel", status_code=200, response_model=CancelOrderResponse
)
async def cancel_order(
    order_id: UUID,
    body: CancelOrderRequest,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    order = await service.cancel_order(db, current_user.id, order_id, body.cancel_reason)
    return CancelOrderResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        cancel_reason_code=order.cancel_reason_code,
        cancel_reason_note=order.cancel_reason_note,
        refund_amount=float(order.refund_amount) if order.refund_amount else None,
        refunded_at=order.refunded_at,
    )


@router.post("/orders/{order_id}/confirm-refund", status_code=204, response_model=None)
async def confirm_refund(
    order_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    await service.confirm_refund(db, current_user.id, order_id)


# ── Customer SSE ──────────────────────────────────────────────────────────────


@router.get("/orders/{order_id}/sse", response_model=None)
async def customer_order_sse(
    order_id: UUID,
    current_user=Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """客戶訂閱訂單狀態變更（status_changed / shipment_created / shipment_status_changed）。

    驗證 owner — 不能訂閱別人的訂單。連線維持直到客戶端斷開。
    """
    from fastapi.responses import StreamingResponse  # noqa: PLC0415

    from orders.sse import hub as order_sse_hub  # noqa: PLC0415

    # 驗 owner（service 內 raise 404 if not owner）
    await service.get_order_detail(db, current_user.id, order_id)

    queue = order_sse_hub.subscribe_customer(order_id)

    async def event_generator():
        try:
            async for chunk in order_sse_hub.stream(queue):
                yield chunk
        finally:
            order_sse_hub.unsubscribe_customer(order_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ── Admin orders ──────────────────────────────────────────────────────────────

@router.get("/admin/orders", response_model=AdminOrderListResponse)
async def admin_list_orders(
    current_user=Depends(require_admin),
    status: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    search: str | None = Query(default=None),
    order_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_list_orders(
        db, status, date_from, date_to, search, order_type, page, page_size
    )


@router.get("/admin/orders/{order_id}", response_model=AdminOrderDetailResponse)
async def admin_get_order(
    order_id: UUID,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.admin_get_order(db, order_id)


@router.patch("/admin/orders/{order_id}/status", response_model=OrderStatusUpdateResponse)
async def admin_update_status(
    order_id: UUID,
    body: AdminUpdateOrderStatusRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    order = await service.admin_update_order_status(
        db, order_id, body.status, body.admin_notes
    )
    return OrderStatusUpdateResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        paid_at=order.paid_at,
        completed_at=order.completed_at,
        refunded_at=order.refunded_at,
        admin_notes=order.admin_notes,
        cancel_reason_code=order.cancel_reason_code,
        updated_at=datetime.now(UTC),
    )


@router.patch(
    "/admin/orders/{order_id}/shipping",
    response_model=AdminOrderDetailResponse,
)
async def admin_update_shipping(
    order_id: UUID,
    body: UpdateShippingRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """admin 修改訂單出貨資訊（status: pending_payment / paid / processing 都可）。

    shipping_locked=true 時拒絕。修改自動寫 audit 進 admin_notes。
    """
    await service.update_shipping(
        db,
        order_id=order_id,
        user_id=None,
        is_admin=True,
        updates=body.model_dump(exclude_none=True),
    )
    return await service.admin_get_order(db, order_id)


@router.post(
    "/admin/orders/{order_id}/lock-shipping",
    response_model=AdminOrderDetailResponse,
)
async def admin_lock_shipping(
    order_id: UUID,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """admin 確認出貨資訊 → 鎖定。鎖定後才允許建立物流訂單。"""
    await service.lock_shipping(db, order_id)
    return await service.admin_get_order(db, order_id)


def _resolve_status_callback_url(request: Request) -> str:
    """ECpay 物流狀態通知 callback URL（Day 3 webhook 落點）.

    對應 logistics router 的 /api/v1/logistics/status-callback。
    Railway 反向代理 + 強制 https。
    """
    base = str(request.base_url).rstrip("/")
    if base.startswith("http://") and "railway.app" in base:
        base = "https://" + base[len("http://"):]
    return f"{base}/api/v1/logistics/status-callback"


@router.post(
    "/admin/orders/{order_id}/shipments", status_code=201, response_model=CreateShipmentResponse
)
async def create_shipment(
    order_id: UUID,
    body: CreateShipmentRequest,
    request: Request,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """單筆建單 — 真實呼叫 ECpay。"""
    shipment = await service.create_shipment(
        db, order_id, body.shipment_type,
        server_reply_url=_resolve_status_callback_url(request),
    )
    return {
        "shipment_id": shipment.id,
        "tracking_number": shipment.tracking_number,
        "ecpay_logistics_id": shipment.ecpay_logistics_id,
    }


@router.post(
    "/admin/shipments/batch-create",
    response_model=BatchCreateShipmentResponse,
)
async def batch_create_shipments(
    body: BatchCreateShipmentRequest,
    request: Request,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """批次建單（一次最多 50 筆）— 失敗筆獨立、不影響成功筆。"""
    return await service.batch_create_shipments(
        db, body.order_ids, body.shipment_type,
        server_reply_url=_resolve_status_callback_url(request),
    )


@router.post(
    "/admin/orders/{order_id}/refresh-shipment-status",
    response_model=AdminOrderDetailResponse,
)
async def admin_refresh_shipment_status(
    order_id: UUID,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """admin 主動向 ECpay 拉所有 Shipment 的最新狀態（webhook 掉包補救）.

    對該 Order 的每筆 Shipment 各打一次 ECpay /7418/，比對 LogisticsStatus，
    若有更新就同步寫 DB。完成後回最新訂單詳情。
    """
    await service.refresh_shipment_status(db, order_id)
    return await service.admin_get_order(db, order_id)


@router.patch(
    "/admin/orders/{order_id}/production-progress/{progress_id}",
    response_model=ProductionProgressResponse,
)
async def update_production_progress(
    order_id: UUID,
    progress_id: UUID,
    body: UpdateProductionProgressRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    progress = await service.update_production_progress(
        db, order_id, progress_id, body.status, body.notes
    )
    return progress


@router.post("/admin/orders/{order_id}/refund", response_model=RefundResponse)
async def process_refund(
    order_id: UUID,
    body: RefundRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    order = await service.process_refund(
        db, order_id, body.refund_amount, body.returned_item_ids, body.cancel_reason
    )
    return RefundResponse(
        id=order.id,
        order_number=order.order_number,
        status=order.status,
        refund_amount=float(order.refund_amount) if order.refund_amount else 0.0,
        refunded_at=order.refunded_at,
        cancel_reason_note=order.cancel_reason_note,
        returned_item_count=getattr(order, "_returned_item_count", 0),
    )


@router.patch(
    "/admin/orders/{order_id}/payment-submissions/{submission_id}/flag",
    response_model=FlagPaymentSubmissionResponse,
)
async def flag_payment_submission(
    order_id: UUID,
    submission_id: UUID,
    body: FlagPaymentSubmissionRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.flag_payment_submission(
        db, order_id, submission_id, body.is_flagged, body.admin_note
    )


@router.patch("/admin/orders/{order_id}/admin-notes", response_model=AdminNotesUpdateResponse)
async def update_admin_notes(
    order_id: UUID,
    body: AdminNotesRequest,
    current_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    order = await service.update_admin_notes(db, order_id, body.admin_notes)
    return AdminNotesUpdateResponse(
        id=order.id,
        admin_notes=order.admin_notes,
        updated_at=datetime.now(UTC),
    )


# ── ECpay webhook ─────────────────────────────────────────────────────────────

@router.post("/webhooks/ecpay", response_class=PlainTextResponse, response_model=None)
async def ecpay_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    payload = dict(form)
    result = await service.handle_ecpay_webhook(db, payload)
    return PlainTextResponse(content=result)
