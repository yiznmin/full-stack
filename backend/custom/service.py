import asyncio
import hashlib
import io
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


# ── Quote viewer security ───────────────────────────────────────────────────
# 客戶看到的預覽圖防護：避免他把 token 連結轉給其他賣家/廠商拿圖去印
QUOTE_PREVIEW_MAX_WIDTH = 800   # 降解析度，不夠拿去印實品
QUOTE_VIEW_MAX_COUNT = 10        # 客戶看 quote 頁面的次數上限（10 次必須做決定）


def _watermark_text_for(req: CustomRequest, user_email: str) -> str:
    """產追溯浮水印字串：純拉丁字母 (品牌 + PREVIEW + 客戶 email 縮寫 + 申請 ID 前 8 碼)。

    刻意不用中文 — 部署 Linux 容器時無需額外安裝中文字型即可正確 render，
    PIL 內建字型可直接畫；流到競品時仍可從 ABCD-XXXXXXXX 反推來源。
    """
    local = user_email.split("@", 1)[0]
    abbrev = local[:4].upper() if local else "????"
    return f"YIIMUI PREVIEW  #{abbrev}-{str(req.id)[:8]}"


def render_watermarked_preview(
    image_bytes: bytes,
    watermark_text: str,
    *,
    max_width: int = QUOTE_PREVIEW_MAX_WIDTH,
) -> bytes:
    """把 filled_template PNG 降解析度 + 對角線浮水印 + 中間 banner 浮水印。

    回 PNG bytes，可直接由 endpoint 串流給客戶瀏覽器。
    """
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    # 1. 降解析度 — 寬度 > max_width 才縮
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 2. 字型 — watermark 用純拉丁字母，PIL 內建字型即可，不需安裝任何字型檔
    # 但 load_default() 大小固定太小，找一個常見系統英文字型放大；找不到才 fallback
    main_size = max(20, img.width // 20)
    diag_size = max(16, img.width // 30)
    font_main = font_diag = None
    for font_name in ("DejaVuSans-Bold.ttf", "Arial.ttf", "arial.ttf"):
        try:
            font_main = ImageFont.truetype(font_name, size=main_size)
            font_diag = ImageFont.truetype(font_name, size=diag_size)
            break
        except OSError:
            continue
    if font_main is None:
        # 真的找不到才走 PIL 內建（極小但純拉丁仍可讀）
        font_main = ImageFont.load_default()
        font_diag = ImageFont.load_default()

    # 3. 中央 banner 浮水印
    bbox = draw.textbbox((0, 0), watermark_text, font=font_main)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    cx = (img.width - text_w) // 2
    cy = (img.height - text_h) // 2
    # 半透明黑色 banner 底
    pad = 20
    draw.rectangle(
        [(cx - pad, cy - pad), (cx + text_w + pad, cy + text_h + pad)],
        fill=(0, 0, 0, 130),
    )
    draw.text((cx, cy), watermark_text, fill=(255, 255, 255, 220), font=font_main)

    # 4. 對角斜紋浮水印（防裁掉中間 banner）
    diag_text = f"  {watermark_text}  "
    diag_overlay = Image.new("RGBA", (img.width * 2, img.height * 2), (0, 0, 0, 0))
    diag_draw = ImageDraw.Draw(diag_overlay)
    diag_bbox = diag_draw.textbbox((0, 0), diag_text, font=font_diag)
    diag_w = diag_bbox[2] - diag_bbox[0]
    diag_h = diag_bbox[3] - diag_bbox[1]
    step_y = diag_h * 6
    step_x = diag_w + 60
    for y in range(-img.height, img.height * 2, step_y):
        for x in range(-img.width, img.width * 2, step_x):
            diag_draw.text((x, y), diag_text, fill=(255, 255, 255, 60), font=font_diag)
    # 旋轉 -30° 後貼回 overlay
    rotated = diag_overlay.rotate(-30, resample=Image.Resampling.BICUBIC)
    crop_x = (rotated.width - img.width) // 2
    crop_y = (rotated.height - img.height) // 2
    diag_clip = rotated.crop((crop_x, crop_y, crop_x + img.width, crop_y + img.height))
    overlay = Image.alpha_composite(overlay, diag_clip)

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    out = io.BytesIO()
    composed.save(out, format="PNG", optimize=True)
    return out.getvalue()


async def _resolve_quote_preview_job(
    db: AsyncSession, req: CustomRequest,
) -> ProductionJob | None:
    """決定客戶報價頁要看到的 production_job。

    優先順序：
    1. req.quoted_production_job_id（admin 在 QuoteDialog 選定的）
    2. fallback：最新一筆有 filled_template_url 的 job（向後相容舊 quote）
    """
    if req.quoted_production_job_id:
        result = await db.execute(
            select(ProductionJob).where(
                ProductionJob.id == req.quoted_production_job_id,
                ProductionJob.filled_template_url.isnot(None),
            )
        )
        job = result.scalar_one_or_none()
        if job is not None:
            return job
        # quoted job 被刪 / 缺 filled → fallback

    result = await db.execute(
        select(ProductionJob).where(
            ProductionJob.custom_request_id == req.id,
            ProductionJob.filled_template_url.isnot(None),
        ).order_by(ProductionJob.created_at.desc())
    )
    return result.scalars().first()


async def fetch_filled_template_bytes(filled_template_url: str | None) -> bytes | None:
    """抓 production_job.filled_template_url（gs:// 或 https）的原始 bytes。

    回 None 代表抓不到（URL 為 null 或下載失敗）— 上層應走「無預覽」狀態。
    """
    if not filled_template_url:
        return None
    import httpx  # noqa: PLC0415

    fetch_url = filled_template_url
    if fetch_url.startswith("gs://"):
        try:
            from production.service import _make_signed_url  # noqa: PLC0415

            fetch_url = _make_signed_url(fetch_url)
        except Exception as e:  # noqa: BLE001
            logger.warning("filled_template signed URL 失敗 %s: %s", filled_template_url, e)
            return None
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(fetch_url)
            r.raise_for_status()
            return r.content
    except Exception as e:  # noqa: BLE001
        logger.warning("抓 filled_template 失敗 %s: %s", fetch_url, e)
        return None


SHIPPING_FEE_HOME = Decimal("120")
SHIPPING_FEE_CONVENIENCE = Decimal("70")


def _enum_val(v: object) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _hash_token(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def _publish_to_admin(event_type: str, data: dict) -> None:
    """SSE publish helper — admin 全局訂閱者。"""
    from custom.sse import hub
    hub.publish_to_admin(event_type, data)


def _publish_to_customer(request_id: UUID, event_type: str, data: dict) -> None:
    """SSE publish helper — 該 request 的客戶訂閱者。"""
    from custom.sse import hub
    hub.publish_to_customer(request_id, event_type, data)


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

    # SSE: 通知 admin 有新申請
    _publish_to_admin("new_request", {
        "request_id": str(req.id),
        "request_type": _enum_val(req.request_type),
        "user_id": str(user_id),
        "created_at": req.created_at.isoformat() if req.created_at else None,
    })

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
    db: AsyncSession,
    user_id: UUID,
    request_id: UUID,
    message: str,
    image_url: str | None = None,
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
        image_url=image_url,
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

    # SSE: 通知 admin（全局）有新客戶訊息
    payload = {
        "request_id": str(request_id),
        "message_id": str(msg.id),
        "sender_type": "customer",
        "message": msg.message,
        "image_url": msg.image_url,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    }
    _publish_to_admin("new_message", payload)
    # SSE: 通知該 request 的訂閱者（同 user 多分頁）
    _publish_to_customer(request_id, "new_message", payload)
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

    # SSE: 通知 admin 客戶已更換照片
    _publish_to_admin("photo_updated", {
        "request_id": str(request_id),
        "photo_url": photo_url,
    })
    return req


async def update_request_fields(
    db: AsyncSession,
    user_id: UUID,
    request_id: UUID,
    changes: dict,
) -> CustomRequest:
    """quote_pending 狀態下客戶修改尺寸 / 難度 / 備註。

    照片用獨立 PATCH /photo endpoint。
    negotiating 後鎖定（409）— 跟 PATCH /photo 相同邏輯。
    """
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
            "申請已進入洽談階段，無法修改",
            code="REQUEST_LOCKED_AFTER_NEGOTIATING",
        )

    # 空 body → no-op：直接 return 不 commit（避免無意義的 onupdate timestamp 跳動）
    if not changes:
        return req

    # 應用變更（model_fields_set 過濾過：只動實際送出的欄位）
    if "difficulty" in changes:
        from production.models import DifficultyEnum
        v = changes["difficulty"]
        req.difficulty = DifficultyEnum(v) if v else None
    if "canvas_w_cm" in changes:
        req.canvas_w_cm = changes["canvas_w_cm"]
    if "canvas_h_cm" in changes:
        req.canvas_h_cm = changes["canvas_h_cm"]
    if "customer_notes" in changes:
        req.customer_notes = changes["customer_notes"]

    await db.commit()
    await db.refresh(req)

    # SSE: 通知 admin 客戶改了規格
    _publish_to_admin("request_updated", {
        "request_id": str(request_id),
        "changes": list(changes.keys()),
    })
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
    if (req.view_count or 0) >= QUOTE_VIEW_MAX_COUNT:
        raise GoneError(
            f"報價已超過 {QUOTE_VIEW_MAX_COUNT} 次查看上限",
            code="QUOTE_VIEW_LIMIT_REACHED",
        )

    # 客戶看的訊息：admin/customer 雙向訊息都列，依時間排序（admin_notes 仍只 admin 看）
    msgs_result = await db.execute(
        select(CustomRequestMessage)
        .where(CustomRequestMessage.request_id == req.id)
        .order_by(CustomRequestMessage.created_at.asc())
    )
    customer_messages = [
        {
            "id": m.id,
            "sender_type": m.sender_type.value,
            "message": m.message,
            "image_url": m.image_url,
            "created_at": m.created_at,
        }
        for m in msgs_result.scalars().all()
    ]

    # 是否有可預覽的 production_job（優先 quoted_production_job_id，
    # 否則 fallback 到最新一筆 filled）
    quote_job = await _resolve_quote_preview_job(db, req)
    preview_available = quote_job is not None

    # 原子 UPDATE 累加 view_count（avoid 多 client 同時 GET 漏算）
    from sqlalchemy import update  # noqa: PLC0415
    await db.execute(
        update(CustomRequest)
        .where(CustomRequest.id == req.id)
        .values(
            view_count=CustomRequest.view_count + 1,
            last_viewed_at=datetime.now(UTC),
        )
    )
    await db.commit()
    await db.refresh(req)

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
        "messages": customer_messages,
        "preview_available": preview_available,
        "view_count": req.view_count,
        "max_views": QUOTE_VIEW_MAX_COUNT,
    }


async def admin_get_preview_watermark(
    db: AsyncSession, request_id: UUID
) -> bytes:
    """Admin 端點：渲染與客戶 viewer 完全相同的浮水印預覽圖。

    用途：admin 在 QuoteDialog 確認送出前先看「客戶會收到的圖長什麼樣」。
    不消耗 view_count（admin 不算客戶查看）。
    """
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")

    quote_job = await _resolve_quote_preview_job(db, req)
    if quote_job is None:
        raise NotFoundError("尚無可預覽的製作圖")

    raw_bytes = await fetch_filled_template_bytes(quote_job.filled_template_url)
    if raw_bytes is None:
        raise NotFoundError("預覽圖無法載入")

    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar_one()
    watermark = _watermark_text_for(req, user.email)
    return await asyncio.to_thread(render_watermarked_preview, raw_bytes, watermark)


async def get_quote_preview_image(
    db: AsyncSession, user_id: UUID, token: str
) -> bytes:
    """客戶看到的浮水印降解析度預覽圖。

    驗 token + owner + 狀態 + expires + view_count，過了拿不到。
    回 PNG bytes 供 endpoint 直接 stream。
    """
    req = await _load_request_by_token(db, token)
    if req.user_id != user_id:
        raise NotFoundError("報價連結無效")
    if req.status != CustomRequestStatusEnum.quote_sent:
        raise GoneError("報價已失效", code="QUOTE_EXPIRED")
    if req.quote_expires_at and req.quote_expires_at < datetime.now(UTC):
        raise GoneError("報價已逾期", code="QUOTE_EXPIRED")
    # `>= MAX` 與 get_quote_summary 一致：summary 達上限後 preview 也鎖（攻擊者
    # 即使只打 preview 端點也不能繞過）
    if (req.view_count or 0) >= QUOTE_VIEW_MAX_COUNT:
        raise GoneError(
            f"報價已超過 {QUOTE_VIEW_MAX_COUNT} 次查看上限",
            code="QUOTE_VIEW_LIMIT_REACHED",
        )

    quote_job = await _resolve_quote_preview_job(db, req)
    if quote_job is None:
        raise NotFoundError("尚無可預覽的製作圖")

    # 拿原圖 bytes → 浮水印處理
    raw_bytes = await fetch_filled_template_bytes(quote_job.filled_template_url)
    if raw_bytes is None:
        raise NotFoundError("預覽圖無法載入")

    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar_one()
    watermark = _watermark_text_for(req, user.email)
    return await asyncio.to_thread(render_watermarked_preview, raw_bytes, watermark)


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

    # SSE: 通知 admin 客戶已確認報價
    _publish_to_admin("quote_confirmed", {
        "request_id": str(req.id),
        "order_id": str(order.id),
        "order_number": order_number,
        "status": _enum_val(req.status),
    })
    # SSE: 同時通知 customer SSE（自己的別分頁也需即時換 status badge）
    _publish_to_customer(req.id, "status_changed", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
        "order_id": str(order.id),
    })

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

    # SSE: 通知 admin 客戶已拒絕報價
    _publish_to_admin("quote_rejected", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
        "rejected_at": req.rejected_at.isoformat() if req.rejected_at else None,
    })
    _publish_to_customer(req.id, "status_changed", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
    })
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

    # SSE: 通知 admin 客戶要求修改
    _publish_to_admin("revision_requested", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
        "revision_count": req.revision_count,
        "reason": reason,
    })
    _publish_to_customer(req.id, "status_changed", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
        "revision_count": req.revision_count,
    })
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
    detail["view_count"] = req.view_count or 0
    detail["last_viewed_at"] = req.last_viewed_at
    return detail


async def admin_post_message(
    db: AsyncSession,
    request_id: UUID,
    message: str,
    image_url: str | None = None,
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
        image_url=image_url,
    )
    db.add(msg)
    await db.flush()

    user_result = await db.execute(select(User).where(User.id == req.user_id))
    user = user_result.scalar_one()
    # email 不附 image（避免直接外流），僅提示客戶上 viewer 頁查看
    body_text = message or "（圖片訊息）請至客製申請頁查看"
    await _send_email(
        to=user.email,
        subject="【PaintLearn】客製申請有新訊息",
        html=f"<p>{body_text}</p>",
    )

    await db.commit()
    await db.refresh(msg)

    # SSE: 通知 customer admin 已回覆
    _publish_to_customer(request_id, "new_message", {
        "request_id": str(request_id),
        "message_id": str(msg.id),
        "sender_type": "admin",
        "message": msg.message,
        "image_url": msg.image_url,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    })
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

    # SSE: 通知 customer 申請已進入洽談階段（會鎖照片更換 UI）
    _publish_to_customer(req.id, "status_changed", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
    })
    _publish_to_admin("status_changed", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
    })
    return req


async def admin_send_quote(
    db: AsyncSession,
    request_id: UUID,
    quoted_price: float,
    detail: str | None,
    surcharge_ids: list[UUID] | None,
    quote_note: str | None,
    production_job_id: UUID | None = None,
) -> tuple[CustomRequest, str]:
    """Returns (request, plain_token). Plain token is included in email link.

    production_job_id：admin 在 QuoteDialog 選定的 completed job。
    寫入 quoted_production_job_id 後，customer 看到的 preview / 規格都從該 job 拿，
    不再用「最新一筆 filled」的猜測。
    canvas / difficulty / detail 也同步從 job 帶到 custom_request（admin 製作出來的
    版本可能與客戶原申請不同 — admin 為準）。
    """
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

    # 驗證 production_job_id 並從中同步規格（若指定）
    if production_job_id is not None:
        job_result = await db.execute(
            select(ProductionJob).where(
                ProductionJob.id == production_job_id,
                ProductionJob.custom_request_id == request_id,
            )
        )
        job = job_result.scalar_one_or_none()
        if job is None:
            raise BadRequestError(
                "production_job_id 不屬於此申請",
                code="INVALID_PRODUCTION_JOB",
            )
        if str(job.status) != "completed":
            raise BadRequestError(
                f"job 必須為 completed 狀態才能用作報價（目前：{job.status}）",
                code="PRODUCTION_JOB_NOT_COMPLETED",
            )
        req.quoted_production_job_id = production_job_id
        # 以 admin 實際做出來的規格為準
        if job.canvas_w_cm:
            req.canvas_w_cm = int(job.canvas_w_cm)
        if job.canvas_h_cm:
            req.canvas_h_cm = int(job.canvas_h_cm)
        if job.difficulty:
            req.difficulty = job.difficulty
        if job.detail:
            req.detail = job.detail

    plain_token = secrets.token_urlsafe(32)
    req.quoted_price = Decimal(str(quoted_price))
    req.quote_token = _hash_token(plain_token)
    req.quote_expires_at = datetime.now(UTC) + timedelta(hours=24)
    req.quoted_at = datetime.now(UTC)
    req.status = CustomRequestStatusEnum.quote_sent
    # detail param 仍允許覆蓋（job 沒設或 admin 想用不同 detail）
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
    # 客戶 viewer 頁路徑：/customer-quote/{token}（admin app 內 no-AdminLayout 路由）
    quote_link = f"{settings.frontend_url}/customer-quote/{plain_token}"
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

    # SSE: 通知 customer 報價已送達（觸發前端 toast + 自動跳 QuotePage CTA）
    _publish_to_customer(req.id, "quote_sent", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
        "quoted_price": float(req.quoted_price),
        "quote_expires_at": req.quote_expires_at.isoformat() if req.quote_expires_at else None,
    })
    _publish_to_admin("quote_sent", {
        "request_id": str(req.id),
        "status": _enum_val(req.status),
        "quoted_price": float(req.quoted_price),
    })
    return req, plain_token


async def admin_get_photo_signed_url(
    db: AsyncSession, request_id: UUID
) -> dict:
    """Admin 取私密照片的短期讀取 signed URL（15 分鐘 TTL）。"""
    from upload.service import generate_private_read_signed_url  # noqa: PLC0415
    result = await db.execute(
        select(CustomRequest).where(CustomRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    if not req.photo_url:
        raise NotFoundError("此申請無照片")
    return generate_private_read_signed_url(req.photo_url)


async def customer_get_photo_signed_url(
    db: AsyncSession, user_id: UUID, request_id: UUID
) -> dict:
    """Customer 取自己客製申請照片的短期讀取 signed URL（15 分鐘 TTL）。

    驗證 owner 後再簽：避免他人猜測 request_id 拿到別人的照片。
    """
    from upload.service import generate_private_read_signed_url  # noqa: PLC0415
    result = await db.execute(
        select(CustomRequest).where(
            CustomRequest.id == request_id, CustomRequest.user_id == user_id
        )
    )
    req = result.scalar_one_or_none()
    if req is None:
        raise NotFoundError("客製申請不存在")
    if not req.photo_url:
        raise NotFoundError("此申請無照片")
    return generate_private_read_signed_url(req.photo_url)


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
            "image_url": m.image_url,
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
    from sqlalchemy import func as sa_func
    from sqlalchemy import update

    from notifications.models import AdminNotification, NotificationStatusEnum
    await db.execute(
        update(AdminNotification)
        .where(
            AdminNotification.type == "quote_pending",
            AdminNotification.reference_type == "custom_request",
            AdminNotification.reference_id == request_id,
        )
        .values(
            status=NotificationStatusEnum.completed,
            requires_action=False,
            updated_at=sa_func.now(),
        )
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

    # SSE: 通知 customer 報價已逾期（前端切到「重新申請」CTA）
    for req in expired:
        _publish_to_customer(req.id, "status_changed", {
            "request_id": str(req.id),
            "status": _enum_val(req.status),
        })
        _publish_to_admin("quote_expired", {
            "request_id": str(req.id),
            "status": _enum_val(req.status),
        })
    return len(expired)


# Suppress unused warning; ProductionJob status enum is used implicitly via Celery / approval
_ = JobStatusEnum
