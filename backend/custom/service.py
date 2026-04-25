import asyncio
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User
from core.config import settings
from core.exceptions import (
    BadRequestError,
    ConflictError,
    GoneError,
    NotFoundError,
)
from custom.models import (
    CustomRequest,
    CustomRequestMessage,
    CustomRequestStatusEnum,
    CustomRequestTypeEnum,
    MessageSenderTypeEnum,
)
from notifications.service import create_notification
from orders.models import (
    CancelReasonCodeEnum,  # noqa: F401  (used by orders refund logic)
    Order,
    OrderItem,
    OrderStatusEnum,
)
from product.models import Product
from production.models import JobStatusEnum, ProductionJob
from users.models import ShippingProfile

logger = logging.getLogger(__name__)


SHIPPING_FEE_HOME = Decimal("120")
SHIPPING_FEE_CONVENIENCE = Decimal("70")


def _enum_val(v: object) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


async def _send_email(to: str, subject: str, html: str) -> None:
    try:
        import resend
        resend.api_key = settings.resend_api_key
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: resend.Emails.send({
                "from": settings.resend_from_email,
                "to": to,
                "subject": subject,
                "html": html,
            }),
        )
    except Exception as e:
        logger.warning(f"Email send failed to {to}: {e}")


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    from color.models import SystemSetting
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


# ── Customer endpoints ────────────────────────────────────────────────────────


async def create_custom_request(
    db: AsyncSession,
    user_id: UUID,
    request_type: str,
    photo_url: str | None,
    ref_product_id: UUID | None,
    canvas_w_cm: int | None,
    canvas_h_cm: int | None,
    difficulty: str | None,
    detail: str | None,
    customer_notes: str | None,
    parent_request_id: UUID | None,
) -> CustomRequest:
    if request_type == "custom_spec" and ref_product_id is not None:
        prod = await db.execute(select(Product).where(Product.id == ref_product_id))
        if prod.scalar_one_or_none() is None:
            raise NotFoundError("ref_product_id 對應的商品不存在")

    if parent_request_id is not None:
        parent = await db.execute(
            select(CustomRequest).where(CustomRequest.id == parent_request_id)
        )
        if parent.scalar_one_or_none() is None:
            raise NotFoundError("parent_request_id 對應的申請不存在")

    req = CustomRequest(
        user_id=user_id,
        request_type=CustomRequestTypeEnum(request_type),
        status=CustomRequestStatusEnum.quote_pending,
        photo_url=photo_url,
        ref_product_id=ref_product_id,
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
        difficulty=difficulty,
        detail=detail,
        customer_notes=customer_notes,
        parent_request_id=parent_request_id,
    )
    db.add(req)
    await db.flush()

    reply_days = int(await _get_setting(db, "quote_reply_days") or "3")
    welcome = CustomRequestMessage(
        request_id=req.id,
        sender_type=MessageSenderTypeEnum.admin,
        message=f"您的客製申請已收到，預計 {reply_days} 個工作天內回覆報價。",
    )
    db.add(welcome)

    await create_notification(
        db,
        type="quote_pending",
        message=f"新客製申請 {req.id}（{request_type}）",
        reference_type="custom_request",
        reference_id=req.id,
        requires_action=True,
    )

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    await _send_email(
        to=user.email,
        subject="【PaintLearn】客製申請已收到",
        html=(
            f"<p>您的客製申請已收到，預計 {reply_days} 個工作天內回覆報價。</p>"
            f"<p>申請編號：{req.id}</p>"
        ),
    )

    await db.commit()
    await db.refresh(req)
    return req


async def list_customer_requests(
    db: AsyncSession,
    user_id: UUID,
    status: str | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(CustomRequest).where(CustomRequest.user_id == user_id)
    if status:
        query = query.where(CustomRequest.status == status)
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    rows = (await db.execute(
        query.order_by(CustomRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    items = [_request_summary(r) for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_customer_request(
    db: AsyncSession, user_id: UUID, request_id: UUID
) -> dict:
    result = await db.execute(
        select(CustomRequest).where(
            CustomRequest.id == request_id, CustomRequest.user_id == user_id
        )
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    return await _request_detail(db, req)


async def post_customer_message(
    db: AsyncSession, user_id: UUID, request_id: UUID, message: str
) -> CustomRequestMessage:
    req_result = await db.execute(
        select(CustomRequest).where(
            CustomRequest.id == request_id, CustomRequest.user_id == user_id
        )
    )
    req = req_result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")

    msg = CustomRequestMessage(
        request_id=request_id,
        sender_type=MessageSenderTypeEnum.customer,
        message=message,
    )
    db.add(msg)
    await db.flush()

    await create_notification(
        db,
        type="new_message",
        message=f"客戶於申請 {request_id} 發送新訊息",
        reference_type="custom_request",
        reference_id=request_id,
        requires_action=False,
    )

    await db.commit()
    await db.refresh(msg)
    return msg


async def update_photo(
    db: AsyncSession, user_id: UUID, request_id: UUID, photo_url: str
) -> CustomRequest:
    result = await db.execute(
        select(CustomRequest).where(
            CustomRequest.id == request_id, CustomRequest.user_id == user_id
        ).with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    if req.status != CustomRequestStatusEnum.quote_pending:
        raise ConflictError(
            "申請已進入洽談階段，無法更換照片",
            code="PHOTO_LOCKED_AFTER_NEGOTIATING",
        )

    # TODO: 正式上線前以 Firebase Admin SDK 刪除舊照片
    logger.info(f"Photo replaced for request {request_id}; old: {req.photo_url}")
    req.photo_url = photo_url
    await db.commit()
    await db.refresh(req)
    return req


# ── Quote token endpoints ─────────────────────────────────────────────────────


async def _load_request_by_token(db: AsyncSession, token: str) -> CustomRequest:
    hashed = _hash_token(token)
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.quote_token == hashed)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("報價連結無效")
    return req


async def get_quote_summary(
    db: AsyncSession, user_id: UUID, token: str
) -> dict:
    req = await _load_request_by_token(db, token)
    if req.user_id != user_id:
        raise NotFoundError("報價連結無效")
    if req.status != CustomRequestStatusEnum.quote_sent:
        raise GoneError("報價已失效", code="QUOTE_EXPIRED")
    if req.quote_expires_at and req.quote_expires_at < datetime.now(UTC):
        raise GoneError("報價已逾期", code="QUOTE_EXPIRED")

    return {
        "custom_request_id": req.id,
        "spec_summary": {
            "canvas_w_cm": req.canvas_w_cm,
            "canvas_h_cm": req.canvas_h_cm,
            "difficulty": _enum_val(req.difficulty) if req.difficulty else None,
            "detail": _enum_val(req.detail) if req.detail else None,
            "photo_url": req.photo_url,
            "customer_notes": req.customer_notes,
        },
        "quoted_price": float(req.quoted_price) if req.quoted_price else 0.0,
        "quote_expires_at": req.quote_expires_at,
        "is_extended": req.is_extended,
        "revision_count": req.revision_count,
    }


async def confirm_quote(
    db: AsyncSession, user_id: UUID, token: str, shipping_profile_id: UUID
) -> dict:
    req = await _load_request_by_token(db, token)
    if req.user_id != user_id:
        raise NotFoundError("報價連結無效")
    if req.status != CustomRequestStatusEnum.quote_sent:
        raise BadRequestError("報價狀態不允許確認", code="QUOTE_NOT_PENDING")
    if req.quote_expires_at and req.quote_expires_at < datetime.now(UTC):
        raise GoneError("報價已逾期", code="QUOTE_EXPIRED")

    profile_result = await db.execute(
        select(ShippingProfile).where(
            ShippingProfile.id == shipping_profile_id,
            ShippingProfile.user_id == user_id,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError("找不到指定的配送資料")

    job_result = await db.execute(
        select(ProductionJob).where(
            ProductionJob.custom_request_id == req.id,
            ProductionJob.approved == True,  # noqa: E712
        ).order_by(ProductionJob.approved_at.desc())
    )
    job = job_result.scalars().first()
    if job is None:
        raise BadRequestError("尚未有對應的已核准製作記錄", code="PRODUCTION_NOT_READY")

    shipping_type = _enum_val(profile.shipping_type)
    shipping_fee = SHIPPING_FEE_HOME if shipping_type == "home" else SHIPPING_FEE_CONVENIENCE
    quoted_price = Decimal(str(req.quoted_price))
    total = quoted_price + shipping_fee

    shipping_snapshot = {
        "type": shipping_type,
        "recipient_name": profile.recipient_name,
        "phone": profile.phone,
        "notify_email": profile.email,
        "city": profile.city,
        "district": profile.district,
        "address_detail": profile.address_detail,
        "store_id": profile.store_id,
        "store_name": profile.store_name,
    }

    from sqlalchemy import text as sa_text
    seq_sql = (
        "SELECT TO_CHAR(now(), 'PL-YYYYMMDD-')"
        " || LPAD(nextval('order_number_seq')::text, 6, '0')"
    )
    order_number_result = await db.execute(sa_text(seq_sql))
    order_number = order_number_result.scalar()

    deadline_hours = int(
        await _get_setting(db, "payment_absolute_deadline_hours") or "48"
    )
    payment_deadline = datetime.now(UTC) + timedelta(hours=deadline_hours)

    order_id = uuid4()
    order = Order(
        id=order_id,
        order_number=order_number,
        user_id=user_id,
        status=OrderStatusEnum.pending_payment,
        subtotal=quoted_price,
        discount_amount=Decimal("0"),
        discount_source=None,
        auto_checkout_config_id=None,
        shipping_fee=shipping_fee,
        total=total,
        user_coupon_id=None,
        shipping_type=shipping_type,
        shipping_preference=None,
        shipping_snapshot=shipping_snapshot,
        payment_deadline=payment_deadline,
        customer_notes=None,
    )
    db.add(order)
    await db.flush()

    item = OrderItem(
        order_id=order.id,
        product_variant_id=None,
        custom_request_id=req.id,
        production_job_id=job.id,
        product_title_snapshot="客製作品",
        variant_spec_snapshot={
            "canvas_w_cm": float(job.canvas_w_cm) if job.canvas_w_cm else None,
            "canvas_h_cm": float(job.canvas_h_cm) if job.canvas_h_cm else None,
            "difficulty": _enum_val(job.difficulty),
            "detail": _enum_val(job.detail),
            "color_count": job.num_colors_used,
        },
        unit_price=quoted_price,
        quantity=1,
        fulfilled_qty=0,
        preorder_qty=1,
        is_returned=False,
    )
    db.add(item)

    req.status = CustomRequestStatusEnum.quote_confirmed
    req.order_id = order.id

    await create_notification(
        db,
        type="quote_confirmed",
        message=f"客戶已確認報價（申請 {req.id}）",
        reference_type="custom_request",
        reference_id=req.id,
        requires_action=False,
    )

    payment_info = {
        "bank_account_number": await _get_setting(db, "bank_account_number") or "",
        "bank_name": await _get_setting(db, "bank_name") or "",
        "bank_account_name": await _get_setting(db, "bank_account_name") or "",
    }

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    await _send_email(
        to=user.email,
        subject=f"【PaintLearn】訂單確認 {order_number}",
        html=(
            f"<p>感謝您的客製訂單！訂單編號：{order_number}</p>"
            f"<p>應付金額：NT${float(total):.0f}</p>"
            f"<p>付款期限：{payment_deadline.strftime('%Y-%m-%d %H:%M')}</p>"
        ),
    )

    await db.commit()
    return {
        "order_id": order.id,
        "order_number": order_number,
        "total": float(total),
        "payment_deadline": payment_deadline,
        "payment_info": payment_info,
    }


async def reject_quote(
    db: AsyncSession, user_id: UUID, token: str, reason: str | None
) -> CustomRequest:
    req = await _load_request_by_token(db, token)
    if req.user_id != user_id:
        raise NotFoundError("報價連結無效")
    if req.status != CustomRequestStatusEnum.quote_sent:
        raise BadRequestError("報價狀態不允許拒絕", code="QUOTE_NOT_PENDING")

    req.status = CustomRequestStatusEnum.quote_rejected
    req.rejected_at = datetime.now(UTC)

    db.add(CustomRequestMessage(
        request_id=req.id,
        sender_type=MessageSenderTypeEnum.customer,
        message=reason or "客戶拒絕報價",
    ))

    await create_notification(
        db,
        type="quote_rejected",
        message=f"客戶拒絕報價（申請 {req.id}）",
        reference_type="custom_request",
        reference_id=req.id,
        requires_action=False,
    )

    await db.commit()
    await db.refresh(req)
    return req


async def extend_quote(
    db: AsyncSession, user_id: UUID, token: str
) -> CustomRequest:
    req = await _load_request_by_token(db, token)
    if req.user_id != user_id:
        raise NotFoundError("報價連結無效")
    if req.status != CustomRequestStatusEnum.quote_sent:
        raise BadRequestError("報價狀態不允許延長", code="QUOTE_NOT_PENDING")
    if req.is_extended:
        raise BadRequestError("已使用過延長機會", code="QUOTE_ALREADY_EXTENDED")

    now = datetime.now(UTC)
    base = max(now, req.quote_expires_at) if req.quote_expires_at else now
    req.quote_expires_at = base + timedelta(hours=24)
    req.is_extended = True

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    await _send_email(
        to=user.email,
        subject="【PaintLearn】報價已延長",
        html=f"<p>您已延長報價有效期至 {req.quote_expires_at.strftime('%Y-%m-%d %H:%M')}。</p>",
    )

    await db.commit()
    await db.refresh(req)
    return req


async def request_revision(
    db: AsyncSession, user_id: UUID, token: str, reason: str
) -> CustomRequest:
    req = await _load_request_by_token(db, token)
    if req.user_id != user_id:
        raise NotFoundError("報價連結無效")
    if req.status != CustomRequestStatusEnum.quote_sent:
        raise BadRequestError("報價狀態不允許要求修改", code="QUOTE_NOT_PENDING")
    if req.revision_count >= 3:
        raise BadRequestError("已達修改次數上限", code="REVISION_LIMIT_EXCEEDED")

    req.status = CustomRequestStatusEnum.draft_revision
    req.revision_count += 1

    db.add(CustomRequestMessage(
        request_id=req.id,
        sender_type=MessageSenderTypeEnum.customer,
        message=reason,
    ))

    await create_notification(
        db,
        type="draft_revision_requested",
        message=f"客戶要求修改（申請 {req.id}）",
        reference_type="custom_request",
        reference_id=req.id,
        requires_action=True,
    )

    await db.commit()
    await db.refresh(req)
    return req


# ── Admin endpoints ───────────────────────────────────────────────────────────


async def admin_list_requests(
    db: AsyncSession,
    status: str | None,
    request_type: str | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(CustomRequest, User).join(User, CustomRequest.user_id == User.id)
    if status:
        query = query.where(CustomRequest.status == status)
    if request_type:
        query = query.where(CustomRequest.request_type == request_type)
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0
    rows = (await db.execute(
        query.order_by(CustomRequest.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all()

    items = [
        {
            "id": r.id,
            "request_type": _enum_val(r.request_type),
            "status": _enum_val(r.status),
            "user_id": u.id,
            "user_name": u.name,
            "user_email": u.email,
            "quoted_price": float(r.quoted_price) if r.quoted_price else None,
            "quote_expires_at": r.quote_expires_at,
            "revision_count": r.revision_count,
            "created_at": r.created_at,
        }
        for r, u in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def admin_get_request(db: AsyncSession, request_id: UUID) -> dict:
    result = await db.execute(
        select(CustomRequest, User)
        .join(User, CustomRequest.user_id == User.id)
        .where(CustomRequest.id == request_id)
    )
    row = result.first()
    if row is None:
        raise NotFoundError("客製申請不存在")
    req, user = row
    detail = await _request_detail(db, req)
    # Hide raw photo_url from admin response — force going through signed-URL endpoint
    detail["photo_url"] = None
    detail["user_name"] = user.name
    detail["user_email"] = user.email
    detail["admin_notes"] = req.admin_notes
    return detail


async def admin_post_message(
    db: AsyncSession, request_id: UUID, message: str
) -> CustomRequestMessage:
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")

    msg = CustomRequestMessage(
        request_id=request_id,
        sender_type=MessageSenderTypeEnum.admin,
        message=message,
    )
    db.add(msg)
    await db.flush()

    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar_one()
    await _send_email(
        to=user.email,
        subject="【PaintLearn】客製申請有新訊息",
        html=f"<p>{message}</p>",
    )

    await db.commit()
    await db.refresh(msg)
    return msg


async def admin_mark_negotiating(
    db: AsyncSession, request_id: UUID
) -> CustomRequest:
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.id == request_id).with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    if req.status != CustomRequestStatusEnum.quote_pending:
        raise BadRequestError("僅 quote_pending 狀態可標記為 negotiating")

    req.status = CustomRequestStatusEnum.negotiating
    await _mark_quote_pending_notifications_done(db, request_id)

    await db.commit()
    await db.refresh(req)
    return req


async def admin_send_quote(
    db: AsyncSession,
    request_id: UUID,
    quoted_price: float,
    detail: str | None,
    surcharge_ids: list[UUID] | None,
    quote_note: str | None,
) -> tuple[CustomRequest, str]:
    """Returns (request, plain_token). Plain token is included in email link."""
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.id == request_id).with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    if req.status not in (
        CustomRequestStatusEnum.quote_pending,
        CustomRequestStatusEnum.negotiating,
        CustomRequestStatusEnum.draft_revision,
    ):
        raise BadRequestError("此申請狀態不允許送出報價")

    plain_token = secrets.token_urlsafe(32)
    req.quoted_price = Decimal(str(quoted_price))
    req.quote_token = _hash_token(plain_token)
    req.quote_expires_at = datetime.now(UTC) + timedelta(hours=24)
    req.quoted_at = datetime.now(UTC)
    req.status = CustomRequestStatusEnum.quote_sent
    if detail:
        from production.models import DetailEnum
        req.detail = DetailEnum(detail)

    note_html = f"<p>備註：{quote_note}</p>" if quote_note else ""
    quote_msg = f"報價金額：NT${float(quoted_price):.0f}"
    if quote_note:
        quote_msg += f"\n備註：{quote_note}"
    db.add(CustomRequestMessage(
        request_id=request_id,
        sender_type=MessageSenderTypeEnum.admin,
        message=quote_msg,
    ))

    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar_one()
    quote_link = f"{settings.frontend_url}/custom/quote/{plain_token}"
    await _send_email(
        to=user.email,
        subject="【PaintLearn】客製報價已送出",
        html=(
            f"<p>您的客製申請 {request_id} 已完成報價。</p>"
            f"<p>報價金額：NT${float(quoted_price):.0f}</p>"
            f"{note_html}"
            f"<p>請於 24 小時內確認：<a href=\"{quote_link}\">查看報價</a></p>"
        ),
    )

    await db.commit()
    await db.refresh(req)
    return req, plain_token


async def admin_get_photo_signed_url(
    db: AsyncSession, request_id: UUID
) -> dict:
    """Stub: returns photo_url + faux 15-min expires_at; real Firebase SDK later."""
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    if not req.photo_url:
        raise NotFoundError("此申請無照片")
    logger.warning(
        "Photo signed URL is STUB (returning raw photo_url) — replace with Firebase SDK"
    )
    return {
        "url": req.photo_url,
        "expires_at": datetime.now(UTC) + timedelta(minutes=15),
    }


# ── helpers ───────────────────────────────────────────────────────────────────


def _request_summary(req: CustomRequest) -> dict:
    return {
        "id": req.id,
        "request_type": _enum_val(req.request_type),
        "status": _enum_val(req.status),
        "quoted_price": float(req.quoted_price) if req.quoted_price else None,
        "quote_expires_at": req.quote_expires_at,
        "is_extended": req.is_extended,
        "revision_count": req.revision_count,
        "order_id": req.order_id,
        "created_at": req.created_at,
    }


async def _request_detail(db: AsyncSession, req: CustomRequest) -> dict:
    msgs_result = await db.execute(
        select(CustomRequestMessage)
        .where(CustomRequestMessage.request_id == req.id)
        .order_by(CustomRequestMessage.created_at.asc())
    )
    messages = [
        {
            "id": m.id,
            "request_id": m.request_id,
            "sender_type": _enum_val(m.sender_type),
            "message": m.message,
            "created_at": m.created_at,
        }
        for m in msgs_result.scalars().all()
    ]
    return {
        "id": req.id,
        "user_id": req.user_id,
        "request_type": _enum_val(req.request_type),
        "status": _enum_val(req.status),
        "photo_url": req.photo_url,
        "ref_product_id": req.ref_product_id,
        "canvas_w_cm": req.canvas_w_cm,
        "canvas_h_cm": req.canvas_h_cm,
        "difficulty": _enum_val(req.difficulty) if req.difficulty else None,
        "detail": _enum_val(req.detail) if req.detail else None,
        "customer_notes": req.customer_notes,
        "quoted_price": float(req.quoted_price) if req.quoted_price else None,
        "quote_expires_at": req.quote_expires_at,
        "is_extended": req.is_extended,
        "revision_count": req.revision_count,
        "parent_request_id": req.parent_request_id,
        "order_id": req.order_id,
        "created_at": req.created_at,
        "quoted_at": req.quoted_at,
        "rejected_at": req.rejected_at,
        "messages": messages,
    }


async def _mark_quote_pending_notifications_done(
    db: AsyncSession, request_id: UUID
) -> None:
    """Mark admin_notifications(type=quote_pending, reference_id=request_id) as completed."""
    from sqlalchemy import update

    from notifications.models import AdminNotification
    await db.execute(
        update(AdminNotification)
        .where(
            AdminNotification.type == "quote_pending",
            AdminNotification.reference_type == "custom_request",
            AdminNotification.reference_id == request_id,
        )
        .values(is_completed=True, requires_action=False)
    )


# ── Cross-module hooks (used by orders / production) ──────────────────────────


async def auto_mark_negotiating_on_production_job(
    db: AsyncSession, custom_request_id: UUID
) -> None:
    """Called by production.create_jobs(): if request is quote_pending,
    transition to negotiating and mark notification done. (E26)
    """
    result = await db.execute(
        select(CustomRequest)
        .where(CustomRequest.id == custom_request_id)
        .with_for_update()
    )
    req = result.scalar_one_or_none()
    if req is None:
        return
    if req.status == CustomRequestStatusEnum.quote_pending:
        req.status = CustomRequestStatusEnum.negotiating
        await _mark_quote_pending_notifications_done(db, req.id)


# ── Celery: expire quotes (E12) ───────────────────────────────────────────────


async def expire_quotes_async(db: AsyncSession) -> int:
    """Scan quote_sent + expired → quote_expired. Returns count."""
    now = datetime.now(UTC)
    result = await db.execute(
        select(CustomRequest)
        .where(
            CustomRequest.status == CustomRequestStatusEnum.quote_sent,
            CustomRequest.quote_expires_at < now,
        )
        .with_for_update()
    )
    expired = list(result.scalars().all())

    for req in expired:
        req.status = CustomRequestStatusEnum.quote_expired
        user_result = await db.execute(select(User).where(User.id == req.user_id))
        user = user_result.scalar_one()
        await _send_email(
            to=user.email,
            subject="【PaintLearn】您的報價已逾期",
            html=f"<p>您的客製申請 {req.id} 報價已逾期，已自動取消。</p>",
        )

    await db.commit()
    return len(expired)


# Suppress unused warning; ProductionJob status enum is used implicitly via Celery / approval
_ = JobStatusEnum
