import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from auth.models import User
from color.models import PhysicalColor, SystemSetting
from core.config import settings
from core.exceptions import BadRequestError, ConflictError, NotFoundError
from discount import service as discount_svc
from notifications.service import create_notification
from orders.models import (
    CancelReasonCodeEnum,
    CartItem,
    Order,
    OrderItem,
    OrderStatusEnum,
    PaymentSubmission,
    ProductionProgress,
    ProductionProgressStatusEnum,
    Shipment,
    ShipmentStatusEnum,
)
from palette.models import PaletteColorMapping
from product.models import Product, ProductVariant
from production.models import ProductionJob
from users.models import ShippingProfile

logger = logging.getLogger(__name__)


async def _compute_fulfillable_qty(
    db: AsyncSession, job_id: UUID, quantity: int
) -> int:
    """Return how many units of a job can be fulfilled from current stock (no locking)."""
    rows = (await db.execute(
        select(PaletteColorMapping, PhysicalColor)
        .join(PhysicalColor, PaletteColorMapping.physical_color_id == PhysicalColor.id)
        .where(
            PaletteColorMapping.production_job_id == job_id,
            PaletteColorMapping.required_ml.isnot(None),
        )
    )).all()
    if not rows:
        return quantity
    max_units = quantity
    for mapping, color in rows:
        req = Decimal(str(mapping.required_ml))
        if req > 0:
            max_units = min(max_units, int(Decimal(str(color.stock_ml)) / req))
    return max(0, max_units)


def _enum_val(v: object) -> str:
    return v.value if hasattr(v, "value") else str(v)


def _job_spec(job: "ProductionJob") -> dict:
    return {
        "canvas_w_cm": float(job.canvas_w_cm) if job.canvas_w_cm is not None else None,
        "canvas_h_cm": float(job.canvas_h_cm) if job.canvas_h_cm is not None else None,
        "difficulty": _enum_val(job.difficulty),
        "detail": _enum_val(job.detail),
        "color_count": job.num_colors_used,
    }


SHIPPING_FEE_HOME = Decimal("120")
SHIPPING_FEE_CONVENIENCE = Decimal("70")
FREE_SHIPPING_MIN_AMOUNT = Decimal("800")
FREE_SHIPPING_MIN_QTY = 3


# ── system_settings helpers ────────────────────────────────────────────────────

async def get_system_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def _get_payment_info(db: AsyncSession) -> dict:
    keys = ["bank_account_number", "bank_name", "bank_account_name"]
    info = {}
    for key in keys:
        info[key] = await get_system_setting(db, key) or ""
    return info


# ── email helpers ─────────────────────────────────────────────────────────────

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


# ── cart service ──────────────────────────────────────────────────────────────

async def get_cart(db: AsyncSession, user_id: UUID) -> dict:
    """回 cart items（一般商品 + 客製 line 混合）。

    一般 line：via product_variant_id；含 fulfillable / preorder 計算
    客製 line：via custom_request_id；qty 可大於 1，unit_price = quoted_price
    """
    from custom.models import CustomRequest, CustomRequestStatusEnum  # noqa: PLC0415

    cart_rows = (await db.execute(
        select(CartItem)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at)
    )).scalars().all()

    items = []
    for ci in cart_rows:
        if ci.custom_request_id is not None:
            # 客製 line — 從 custom_request 拉資料
            cr_result = await db.execute(
                select(CustomRequest).where(CustomRequest.id == ci.custom_request_id)
            )
            cr = cr_result.scalar_one_or_none()
            if cr is None:
                # custom_request 已被刪除，跳過（cascade 應已清，這是防禦性）
                continue
            # 抓對應 production_job 拿縮圖（filled_template_url 是 production_jobs/
            # 私密路徑，<img> 直接 src=gs:// 或 https 都會 403，需用 _make_signed_url
            # 簽 short-lived signed GET URL 才能讀）
            job = None
            filled_signed_url: str | None = None
            if ci.production_job_id:
                job_result = await db.execute(
                    select(ProductionJob).where(ProductionJob.id == ci.production_job_id)
                )
                job = job_result.scalar_one_or_none()
                if job and job.filled_template_url:
                    try:
                        from production.service import _make_signed_url  # noqa: PLC0415
                        filled_signed_url = _make_signed_url(job.filled_template_url)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "cart custom thumb signed_url failed (job=%s): %s",
                            ci.production_job_id, e,
                        )
            # 客製 line 沒有「現貨/預購」概念 — 全部都是預購（admin 製作）
            qty = ci.quantity
            unit_price = float(cr.quoted_price) if cr.quoted_price else 0.0
            quote_expired = (
                cr.status not in (
                    CustomRequestStatusEnum.quote_sent,
                    CustomRequestStatusEnum.quote_confirmed,
                )
                or (cr.quote_expires_at is not None and cr.quote_expires_at < datetime.now(UTC))
            )
            items.append({
                "id": ci.id,
                "is_custom": True,
                "variant_id": None,
                "product_id": None,
                "product_title": "客製作品",
                "product_image_url": None,
                "variant_image_url": filled_signed_url,
                "thumb_url": filled_signed_url,
                "variant_spec": {
                    "canvas_w_cm": cr.canvas_w_cm,
                    "canvas_h_cm": cr.canvas_h_cm,
                    "difficulty": (
                        cr.difficulty.value if hasattr(cr.difficulty, "value") else cr.difficulty
                    ),
                },
                "custom_request_id": ci.custom_request_id,
                "production_job_id": ci.production_job_id,
                "quote_status": (
                    cr.status.value if hasattr(cr.status, "value") else str(cr.status)
                ),
                "quote_expires_at": cr.quote_expires_at,
                "quote_expired": quote_expired,
                "unit_price": unit_price,
                "quantity": qty,
                "fulfilled_units": 0,
                "preorder_units": qty,
                "is_active": True,
            })
            continue

        # 一般 line — 透過 variant join 拉資料
        if ci.product_variant_id is None:
            continue  # 異常資料：兩個 FK 都空，跳過
        row = (await db.execute(
            select(ProductVariant, Product, ProductionJob)
            .join(Product, ProductVariant.product_id == Product.id)
            .outerjoin(ProductionJob, ProductVariant.production_job_id == ProductionJob.id)
            .where(ProductVariant.id == ci.product_variant_id)
        )).one_or_none()
        if row is None:
            continue
        variant, product, job = row
        qty = ci.quantity
        if variant.production_job_id:
            fulfillable = await _compute_fulfillable_qty(db, variant.production_job_id, qty)
        else:
            fulfillable = qty
        fulfilled_units = fulfillable
        preorder_units = qty - fulfillable
        variant_spec = _job_spec(job) if job else {}
        items.append({
            "id": ci.id,
            "is_custom": False,
            "variant_id": variant.id,
            "product_id": product.id,
            "product_title": product.title,
            "product_image_url": product.cover_image_url,
            "variant_image_url": job.filled_template_url if job else None,
            "thumb_url": product.cover_image_url,
            "variant_spec": variant_spec,
            "custom_request_id": None,
            "production_job_id": None,
            "quote_status": None,
            "quote_expires_at": None,
            "quote_expired": False,
            "unit_price": float(variant.price),
            "quantity": qty,
            "fulfilled_units": fulfilled_units,
            "preorder_units": preorder_units,
            "is_active": variant.is_active,
        })

    subtotal = sum(i["unit_price"] * i["quantity"] for i in items)
    return {"items": items, "subtotal": subtotal}


async def add_cart_item(
    db: AsyncSession, user_id: UUID, product_variant_id: UUID, quantity: int
) -> CartItem:
    result = await db.execute(
        select(ProductVariant).where(ProductVariant.id == product_variant_id)
    )
    variant = result.scalar_one_or_none()
    if variant is None or not variant.is_active:
        raise ConflictError("商品已下架或不存在")

    existing = await db.execute(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_variant_id == product_variant_id,
        )
    )
    cart_item = existing.scalar_one_or_none()
    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            user_id=user_id,
            product_variant_id=product_variant_id,
            quantity=quantity,
        )
        db.add(cart_item)

    await db.commit()
    await db.refresh(cart_item)
    return cart_item


async def add_cart_custom_item(
    db: AsyncSession,
    user_id: UUID,
    custom_request_id: UUID,
    quantity: int = 1,
) -> CartItem:
    """把客戶確認的 quote 加進 cart。

    驗證：
    - custom_request 屬於該 user
    - status == quote_sent（其他狀態不能加）
    - quote_expires_at 未過期
    - production_job_id 必須有（admin 在 QuoteDialog 已選定）

    冪等：同一個 custom_request 只能在 cart 一筆（既有則 quantity += 不疊加，直接覆蓋；
    這個流程不該疊加，cart 加進去時會帶用戶這次選的 qty）。
    """
    from custom.models import CustomRequest, CustomRequestStatusEnum  # noqa: PLC0415

    cr_result = await db.execute(
        select(CustomRequest).where(
            CustomRequest.id == custom_request_id,
            CustomRequest.user_id == user_id,
        )
    )
    cr = cr_result.scalar_one_or_none()
    if cr is None:
        raise NotFoundError("客製申請不存在")
    if cr.status != CustomRequestStatusEnum.quote_sent:
        raise ConflictError("此申請的報價狀態不允許加入購物車", code="QUOTE_NOT_PENDING")
    if cr.quote_expires_at and cr.quote_expires_at < datetime.now(UTC):
        raise ConflictError("報價已逾期", code="QUOTE_EXPIRED")
    if cr.quoted_production_job_id is None:
        raise ConflictError(
            "報價未綁定製作版本，無法加入購物車", code="QUOTE_NO_PRODUCTION_JOB",
        )
    if quantity < 1:
        raise ConflictError("數量需大於 0", code="INVALID_QUANTITY")

    existing = (await db.execute(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.custom_request_id == custom_request_id,
        )
    )).scalar_one_or_none()
    if existing:
        # 同個 custom_request 已在 cart → 改數量（不疊加；user 重新加是重設）
        existing.quantity = quantity
        await db.commit()
        await db.refresh(existing)
        return existing

    cart_item = CartItem(
        user_id=user_id,
        product_variant_id=None,
        custom_request_id=custom_request_id,
        production_job_id=cr.quoted_production_job_id,
        quantity=quantity,
    )
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)
    return cart_item


async def update_cart_item(
    db: AsyncSession, user_id: UUID, item_id: UUID, quantity: int
) -> CartItem | None:
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
    )
    cart_item = result.scalar_one_or_none()
    if cart_item is None:
        raise NotFoundError("購物車項目不存在")

    if quantity <= 0:
        await db.delete(cart_item)
        await db.commit()
        return None

    cart_item.quantity = quantity
    await db.commit()
    await db.refresh(cart_item)
    return cart_item


async def delete_cart_item(db: AsyncSession, user_id: UUID, item_id: UUID) -> None:
    result = await db.execute(
        select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id)
    )
    cart_item = result.scalar_one_or_none()
    if cart_item is None:
        raise NotFoundError("購物車項目不存在")
    await db.delete(cart_item)
    await db.commit()


def _compute_shipping_fee(
    non_custom_subtotal: Decimal,
    non_custom_qty: int,
    shipping_type: str,
    free_shipping_coupon: bool = False,
) -> Decimal:
    """免運判定：

    - 免運券 → 直接免運（trumps everything）
    - 一般商品 subtotal ≥ 800 OR 一般商品 qty ≥ 3 → 免運
    - **客製商品不計入門檻**（客戶要求）
    """
    if free_shipping_coupon:
        return Decimal("0")
    if non_custom_subtotal >= FREE_SHIPPING_MIN_AMOUNT or non_custom_qty >= FREE_SHIPPING_MIN_QTY:
        return Decimal("0")
    if shipping_type == "home":
        return SHIPPING_FEE_HOME
    return SHIPPING_FEE_CONVENIENCE


async def checkout_preview(
    db: AsyncSession,
    user_id: UUID,
    shipping_type: str,
    user_coupon_id: UUID | None,
    promo_code: str | None,
) -> dict:
    cart = await get_cart(db, user_id)
    if not cart["items"]:
        raise BadRequestError("購物車為空")

    subtotal = Decimal(str(cart["subtotal"]))
    total_qty = sum(i["quantity"] for i in cart["items"])

    # 拆「一般商品」與「客製」 — 免運門檻只算一般商品
    non_custom_items = [i for i in cart["items"] if not i.get("is_custom")]
    custom_items = [i for i in cart["items"] if i.get("is_custom")]
    non_custom_subtotal = Decimal(str(sum(
        i["unit_price"] * i["quantity"] for i in non_custom_items
    )))
    non_custom_qty = sum(i["quantity"] for i in non_custom_items)

    # 結帳前驗證所有客製 line 的 quote 仍 active；過期 → 警告
    expired_custom = [i for i in custom_items if i.get("quote_expired")]

    discount_calc = await discount_svc.calculate_discount(
        db, user_id, float(subtotal), user_coupon_id, promo_code
    )
    discount_amount = Decimal(str(discount_calc["discount_amount"]))
    # discount calculator 若回 free_shipping flag 表示用了免運券
    free_shipping_coupon = bool(discount_calc.get("free_shipping"))

    free_shipping_reason: str | None = None
    if free_shipping_coupon:
        free_shipping_reason = "coupon"
    elif non_custom_subtotal >= FREE_SHIPPING_MIN_AMOUNT:
        free_shipping_reason = "amount"
    elif non_custom_qty >= FREE_SHIPPING_MIN_QTY:
        free_shipping_reason = "quantity"

    shipping_fee = _compute_shipping_fee(
        non_custom_subtotal, non_custom_qty, shipping_type, free_shipping_coupon,
    )
    total = subtotal - discount_amount + shipping_fee

    has_preorder = any(i["preorder_units"] > 0 for i in cart["items"])
    split_items = [
        {
            "variant_id": i["variant_id"],
            "quantity": i["quantity"],
            "fulfilled_qty": i["fulfilled_units"],
            "preorder_qty": i["preorder_units"],
        }
        for i in cart["items"]
        if i["preorder_units"] > 0
    ]

    return {
        "subtotal": float(subtotal),
        "non_custom_subtotal": float(non_custom_subtotal),
        "non_custom_qty": non_custom_qty,
        "expired_custom_count": len(expired_custom),
        "discount_amount": float(discount_amount),
        "discount_source": discount_calc["discount_source"],
        "shipping_fee": float(shipping_fee),
        "total": float(total),
        "free_shipping_reason": free_shipping_reason,
        "has_preorder": has_preorder,
        "split_items": split_items,
    }


# ── order creation ─────────────────────────────────────────────────────────────

async def _deduct_stock(
    db: AsyncSession, order_items: list[dict]
) -> list[int]:
    """Lock physical colors, recompute fulfillable qty from locked stock, deduct.

    Returns actual fulfilled_qty for each item in the same order as order_items.
    Combining read+lock+deduct in one pass eliminates the TOCTOU race between
    _compute_fulfillable_qty (unlocked read) and the subsequent UPDATE.
    """
    actual_fulfilled: list[int] = []
    for item in order_items:
        job_id = item["production_job_id"]
        quantity = item["quantity"]

        mappings_result = await db.execute(
            select(PaletteColorMapping).where(
                PaletteColorMapping.production_job_id == job_id,
                PaletteColorMapping.required_ml.isnot(None),
            )
        )
        mappings = mappings_result.scalars().all()

        if not mappings:
            actual_fulfilled.append(quantity)
            continue

        # Lock all relevant color rows and compute fulfillable qty atomically
        max_units = quantity
        locked_colors: dict[UUID, tuple[Decimal, Decimal]] = {}
        for mapping in mappings:
            color_result = await db.execute(
                select(PhysicalColor)
                .where(PhysicalColor.id == mapping.physical_color_id)
                .with_for_update()
            )
            color = color_result.scalar_one()
            req = Decimal(str(mapping.required_ml))
            if req > 0:
                max_units = min(max_units, int(Decimal(str(color.stock_ml)) / req))
            locked_colors[mapping.physical_color_id] = (
                Decimal(str(color.stock_ml)), req
            )

        fulfilled = max(0, max_units)
        actual_fulfilled.append(fulfilled)

        if fulfilled == 0:
            continue

        for mapping in mappings:
            req = Decimal(str(mapping.required_ml))
            deduct = req * fulfilled
            await db.execute(
                update(PhysicalColor)
                .where(PhysicalColor.id == mapping.physical_color_id)
                .values(stock_ml=func.greatest(PhysicalColor.stock_ml - deduct, 0))
            )

    return actual_fulfilled


async def _restore_stock(db: AsyncSession, order_id: UUID) -> None:
    """Restore stock_ml for non-returned fulfilled items when order is cancelled."""
    items_result = await db.execute(
        select(OrderItem).where(
            OrderItem.order_id == order_id,
            OrderItem.is_returned == False,  # noqa: E712
        )
    )
    items = items_result.scalars().all()

    for item in items:
        if item.fulfilled_qty == 0 or item.production_job_id is None:
            continue
        qty = item.fulfilled_qty
        mappings_result = await db.execute(
            select(PaletteColorMapping).where(
                PaletteColorMapping.production_job_id == item.production_job_id,
                PaletteColorMapping.required_ml.isnot(None),
            )
        )
        for mapping in mappings_result.scalars().all():
            restored = Decimal(str(mapping.required_ml)) * qty
            await db.execute(
                select(PhysicalColor)
                .where(PhysicalColor.id == mapping.physical_color_id)
                .with_for_update()
            )
            await db.execute(
                update(PhysicalColor)
                .where(PhysicalColor.id == mapping.physical_color_id)
                .values(stock_ml=PhysicalColor.stock_ml + restored)
            )


async def _restore_stock_for_items(
    db: AsyncSession, order_id: UUID, item_ids: list[UUID]
) -> None:
    """Restore stock for specific order items (partial refund). Items must belong to order_id."""
    for item_id in item_ids:
        item_result = await db.execute(
            select(OrderItem).where(
                OrderItem.id == item_id, OrderItem.order_id == order_id
            )
        )
        item = item_result.scalar_one_or_none()
        if item is None or item.fulfilled_qty == 0 or item.production_job_id is None:
            continue
        qty = item.fulfilled_qty
        mappings_result = await db.execute(
            select(PaletteColorMapping).where(
                PaletteColorMapping.production_job_id == item.production_job_id,
                PaletteColorMapping.required_ml.isnot(None),
            )
        )
        for mapping in mappings_result.scalars().all():
            restored = Decimal(str(mapping.required_ml)) * qty
            await db.execute(
                select(PhysicalColor)
                .where(PhysicalColor.id == mapping.physical_color_id)
                .with_for_update()
            )
            await db.execute(
                update(PhysicalColor)
                .where(PhysicalColor.id == mapping.physical_color_id)
                .values(stock_ml=PhysicalColor.stock_ml + restored)
            )


async def _revert_order_effects(db: AsyncSession, order: Order) -> None:
    await _restore_stock(db, order.id)
    await discount_svc.revert_coupon(db, order.id)
    await discount_svc.revoke_reward_coupons(
        db, order.id, refund_amount=float(order.total), order_total=float(order.total)
    )


async def complete_order(db: AsyncSession, order: Order) -> None:
    """E40: Issue reward coupon after order completion."""
    await discount_svc.issue_reward_coupon(
        db, order.user_id, order.id, float(order.total)
    )


async def create_order(
    db: AsyncSession,
    user_id: UUID,
    shipping_profile_id: UUID,
    shipping_preference: str | None,
    user_coupon_id: UUID | None,
    promo_code: str | None,
    customer_notes: str | None,
) -> dict:
    # 1. Load and validate cart
    cart_result = await db.execute(
        select(CartItem, ProductVariant, Product, ProductionJob)
        .join(ProductVariant, CartItem.product_variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(ProductionJob, ProductVariant.production_job_id == ProductionJob.id)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at)
    )
    cart_rows = cart_result.all()
    if not cart_rows:
        raise BadRequestError("購物車為空")

    for _, variant, _, _job in cart_rows:
        if not variant.is_active:
            raise ConflictError("購物車中有商品已下架，請更新購物車")

    # 2. Validate shipping profile belongs to user
    profile_result = await db.execute(
        select(ShippingProfile).where(
            ShippingProfile.id == shipping_profile_id,
            ShippingProfile.user_id == user_id,
        )
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError("找不到指定的配送資料")

    shipping_type = _enum_val(profile.shipping_type)

    # 3. Calculate totals (fulfilled_qty determined later via locked stock read)
    subtotal = Decimal("0")
    order_items_data = []
    for cart_item, variant, product, job in cart_rows:
        line_subtotal = Decimal(str(variant.price)) * cart_item.quantity
        subtotal += line_subtotal
        spec_snapshot = _job_spec(job) if job else {}
        qty = cart_item.quantity
        order_items_data.append({
            "product_variant_id": variant.id,
            "production_job_id": variant.production_job_id,
            "product_title_snapshot": product.title,
            "variant_spec_snapshot": spec_snapshot,
            "unit_price": variant.price,
            "quantity": qty,
            "fulfilled_qty": qty,  # placeholder; corrected by _deduct_stock below
            "preorder_qty": 0,
        })

    total_qty = sum(d["quantity"] for d in order_items_data)

    # 4. Pre-generate order ID so apply_discount can record it
    order_id = uuid.uuid4()

    discount_calc = await discount_svc.apply_discount(
        db, order_id, user_id, float(subtotal), user_coupon_id, promo_code
    )
    discount_amount = Decimal(str(discount_calc["discount_amount"]))
    shipping_fee = _compute_shipping_fee(subtotal, total_qty, shipping_type)
    total = subtotal - discount_amount + shipping_fee

    # 5. Generate order_number
    _seq_sql = (
        "SELECT TO_CHAR(now(), 'PL-YYYYMMDD-')"
        " || LPAD(nextval('order_number_seq')::text, 6, '0')"
    )
    order_number_result = await db.execute(text(_seq_sql))
    order_number = order_number_result.scalar()

    # 6. Build shipping snapshot from profile
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

    deadline_hours = int(await get_system_setting(db, "payment_absolute_deadline_hours") or "48")
    payment_deadline = datetime.now(UTC) + timedelta(hours=deadline_hours)

    # 7. Create order with pre-generated ID
    order = Order(
        id=order_id,
        order_number=order_number,
        user_id=user_id,
        status=OrderStatusEnum.pending_payment,
        subtotal=subtotal,
        discount_amount=discount_amount,
        discount_source=discount_calc["discount_source"],
        auto_checkout_config_id=discount_calc["auto_checkout_config_id"],
        shipping_fee=shipping_fee,
        total=total,
        user_coupon_id=discount_calc["user_coupon_id"],
        shipping_type=shipping_type,
        shipping_preference=shipping_preference,
        shipping_snapshot=shipping_snapshot,
        payment_deadline=payment_deadline,
        customer_notes=customer_notes,
    )
    db.add(order)
    await db.flush()

    # 7. Lock stock, compute actual fulfilled_qty, deduct — all in one atomic pass
    actual_fulfilled = await _deduct_stock(db, order_items_data)
    for item_data, fulfilled in zip(order_items_data, actual_fulfilled, strict=True):
        item_data["fulfilled_qty"] = fulfilled
        item_data["preorder_qty"] = item_data["quantity"] - fulfilled

    # 8. Insert order items with corrected fulfilled/preorder quantities
    inserted_items = []
    for item_data in order_items_data:
        oi = OrderItem(
            order_id=order.id,
            product_variant_id=item_data["product_variant_id"],
            production_job_id=item_data["production_job_id"],
            product_title_snapshot=item_data["product_title_snapshot"],
            variant_spec_snapshot=item_data["variant_spec_snapshot"],
            unit_price=item_data["unit_price"],
            quantity=item_data["quantity"],
            fulfilled_qty=item_data["fulfilled_qty"],
            preorder_qty=item_data["preorder_qty"],
        )
        db.add(oi)
        inserted_items.append(oi)

    await db.flush()

    # 9. Delete cart items
    await db.execute(delete(CartItem).where(CartItem.user_id == user_id))

    await db.commit()

    # 10. Send confirmation email
    payment_info = await _get_payment_info(db)
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one()
    await _send_email(
        to=user.email,
        subject=f"【PaintLearn】訂單確認 {order_number}",
        html=(
            f"<p>感謝您的訂單！訂單編號：{order_number}</p>"
            f"<p>應付金額：NT${float(total)}</p>"
            f"<p>付款期限：{payment_deadline.strftime('%Y-%m-%d %H:%M')}</p>"
            f"<p>匯款帳號：{payment_info.get('bank_name', '')} "
            f"{payment_info.get('bank_account_number', '')}</p>"
            f"<p>戶名：{payment_info.get('bank_account_name', '')}</p>"
        ),
    )

    return {
        "order_id": order.id,
        "order_number": order_number,
        "total": float(total),
        "payment_deadline": payment_deadline,
        "payment_info": payment_info,
    }


# ── customer order queries ────────────────────────────────────────────────────

async def list_orders(
    db: AsyncSession,
    user_id: UUID,
    status: str | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(Order).where(Order.user_id == user_id)
    if status:
        query = query.where(Order.status == status)

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    orders_result = await db.execute(
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orders = orders_result.scalars().all()

    items = []
    for order in orders:
        count_res = await db.execute(
            select(func.count()).where(OrderItem.order_id == order.id)
        )
        items.append({
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "total": float(order.total),
            "item_count": count_res.scalar() or 0,
            "created_at": order.created_at,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_order_detail(db: AsyncSession, user_id: UUID, order_id: UUID) -> dict:
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")

    return await _build_order_detail(db, order, is_admin=False)


async def _build_order_detail(db: AsyncSession, order: Order, is_admin: bool = False) -> dict:
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order.id)
    )
    items = items_result.scalars().all()

    item_dicts = []
    for item in items:
        prog_result = await db.execute(
            select(ProductionProgress).where(ProductionProgress.order_item_id == item.id)
        )
        prog = prog_result.scalar_one_or_none()
        item_dicts.append({
            "id": item.id,
            "product_variant_id": item.product_variant_id,
            "product_title_snapshot": item.product_title_snapshot,
            "variant_spec_snapshot": item.variant_spec_snapshot,
            "unit_price": float(item.unit_price),
            "quantity": item.quantity,
            "fulfilled_qty": item.fulfilled_qty,
            "preorder_qty": item.preorder_qty,
            "is_returned": item.is_returned,
            "production_progress": {
                "id": prog.id,
                "order_item_id": prog.order_item_id,
                "status": prog.status,
                "notes": prog.notes,
                "updated_at": prog.updated_at,
            } if prog else None,
        })

    shipments_result = await db.execute(
        select(Shipment).where(Shipment.order_id == order.id)
    )
    shipments = shipments_result.scalars().all()

    subs_result = await db.execute(
        select(PaymentSubmission).where(PaymentSubmission.order_id == order.id)
    )
    subs = subs_result.scalars().all()

    base = {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "subtotal": float(order.subtotal),
        "discount_amount": float(order.discount_amount),
        "discount_source": order.discount_source,
        "auto_checkout_config_id": order.auto_checkout_config_id,
        "shipping_fee": float(order.shipping_fee),
        "total": float(order.total),
        "shipping_type": order.shipping_type,
        "shipping_preference": order.shipping_preference,
        "shipping_snapshot": order.shipping_snapshot,
        "shipping_locked": bool(order.shipping_locked),
        "payment_deadline": order.payment_deadline,
        "paid_at": order.paid_at,
        "completed_at": order.completed_at,
        "cancel_reason_code": order.cancel_reason_code,
        "cancel_reason_note": order.cancel_reason_note,
        "refund_amount": float(order.refund_amount) if order.refund_amount else None,
        "refunded_at": order.refunded_at,
        "refund_confirmed_at": order.refund_confirmed_at,
        "customer_notes": order.customer_notes,
        "items": item_dicts,
        "shipments": [
            {
                "id": s.id,
                "shipment_type": s.shipment_type,
                "status": s.status,
                "tracking_number": s.tracking_number,
                "ecpay_logistics_id": s.ecpay_logistics_id,
                "cvs_payment_no": s.cvs_payment_no,
                "cvs_validation_no": s.cvs_validation_no,
                "last_rtn_code": s.last_rtn_code,
                "last_rtn_msg": s.last_rtn_msg,
                "last_status_at": s.last_status_at,
                "shipped_at": s.shipped_at,
                "delivered_at": s.delivered_at,
            }
            for s in shipments
        ],
        "payment_submissions": [
            {
                "id": sub.id,
                "transfer_amount": float(sub.transfer_amount),
                "transfer_date": sub.transfer_date,
                "transfer_time": sub.transfer_time,
                "account_last5": sub.account_last5,
                "is_flagged": sub.is_flagged,
                "notes": sub.notes,
                "created_at": sub.created_at,
            }
            for sub in subs
        ],
        "created_at": order.created_at,
    }

    if not is_admin:
        base["can_cancel"] = order.status == OrderStatusEnum.pending_payment
        base["can_confirm_received"] = order.status == OrderStatusEnum.shipped
        # 用戶端：只在 pending_payment 階段且未鎖定才能改地址
        base["can_modify_shipping"] = (
            order.status == OrderStatusEnum.pending_payment
            and not order.shipping_locked
        )
    else:
        user_result = await db.execute(select(User).where(User.id == order.user_id))
        user = user_result.scalar_one_or_none()
        base["user_id"] = order.user_id
        base["user_name"] = user.name if user else ""
        base["user_email"] = user.email if user else ""
        base["admin_notes"] = order.admin_notes

    return base


# ── customer order actions ────────────────────────────────────────────────────

async def submit_payment(
    db: AsyncSession,
    user_id: UUID,
    order_id: UUID,
    transfer_amount: float,
    transfer_date,
    transfer_time,
    account_last5: str,
    notes: str | None,
) -> PaymentSubmission:
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.status != OrderStatusEnum.pending_payment:
        raise BadRequestError("只有待付款訂單可提交付款資訊")

    sub = PaymentSubmission(
        order_id=order_id,
        transfer_amount=transfer_amount,
        transfer_date=transfer_date,
        transfer_time=transfer_time,
        account_last5=account_last5,
        notes=notes,
    )
    db.add(sub)
    await db.flush()

    await create_notification(
        db,
        type="payment_submitted",
        message=f"訂單 {order.order_number} 客戶提交付款資訊",
        reference_type="order",
        reference_id=order_id,
        requires_action=True,
    )
    await db.commit()
    await db.refresh(sub)
    return sub


async def confirm_received(db: AsyncSession, user_id: UUID, order_id: UUID) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.status != OrderStatusEnum.shipped:
        raise BadRequestError("只有已出貨的訂單可確認收貨")

    await db.execute(
        update(Shipment)
        .where(Shipment.order_id == order_id)
        .values(status=ShipmentStatusEnum.delivered, delivered_at=datetime.now(UTC))
    )
    order.status = OrderStatusEnum.completed
    order.completed_at = datetime.now(UTC)

    await complete_order(db, order)

    await create_notification(
        db,
        type="order_completed_by_customer",
        message=f"訂單 {order.order_number} 客戶確認收貨",
        reference_type="order",
        reference_id=order_id,
    )
    await db.commit()
    await db.refresh(order)
    return order


def _merge_shipping_snapshot(existing: dict, updates: dict) -> dict:
    """Merge updates into existing shipping_snapshot. None values 忽略，'' 視為清空。"""
    result = dict(existing) if existing else {}
    for key, value in updates.items():
        if value is None:
            continue
        result[key] = value
    return result


def _diff_shipping_for_audit(old: dict, new: dict) -> str:
    """產生人類可讀的 diff 字串（給 admin_notes audit trail）."""
    fields_zh = {
        "recipient_name": "收件人",
        "phone": "電話",
        "notify_email": "Email",
        "city": "縣市",
        "district": "行政區",
        "address_detail": "地址",
        "store_id": "門市代碼",
        "store_name": "門市名稱",
    }
    parts = []
    for key, label in fields_zh.items():
        old_val = old.get(key) or ""
        new_val = new.get(key) or ""
        if old_val != new_val:
            parts.append(f"{label}「{old_val}」→「{new_val}」")
    return "; ".join(parts) if parts else "(無實質變更)"


async def update_shipping(
    db: AsyncSession,
    *,
    order_id: UUID,
    user_id: UUID | None,
    is_admin: bool,
    updates: dict,
) -> Order:
    """修改訂單出貨資訊。

    user (is_admin=False, 帶 user_id)：
      - 訂單必須屬於該 user
      - 訂單狀態必須 == pending_payment
      - shipping_locked 必須 == False

    admin (is_admin=True, user_id 忽略)：
      - 訂單狀態必須在 pending_payment / paid / processing
      - shipping_locked 必須 == False（已 lock 不能改）
      - 改完寫 audit trail 到 admin_notes
    """
    query = select(Order).where(Order.id == order_id).with_for_update()
    if not is_admin:
        query = query.where(Order.user_id == user_id)
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")

    if order.shipping_locked:
        raise ConflictError("出貨資訊已鎖定，無法修改")

    if is_admin:
        if order.status not in (
            OrderStatusEnum.pending_payment,
            OrderStatusEnum.paid,
            OrderStatusEnum.processing,
        ):
            raise BadRequestError(f"訂單狀態 {order.status} 不允許修改出貨資訊")
    else:
        if order.status != OrderStatusEnum.pending_payment:
            raise BadRequestError(
                "付款已被管理員確認，無法自行修改地址。請來信 admin 修改。"
            )

    # 把 updates dict 對映到 shipping_snapshot 的 key（注意 email → notify_email）
    snapshot_updates: dict = {}
    for k, v in updates.items():
        if v is None:
            continue
        if k == "email":
            snapshot_updates["notify_email"] = v
        else:
            snapshot_updates[k] = v

    old_snapshot = dict(order.shipping_snapshot or {})
    new_snapshot = _merge_shipping_snapshot(old_snapshot, snapshot_updates)
    order.shipping_snapshot = new_snapshot

    if is_admin:
        # audit trail
        diff_text = _diff_shipping_for_audit(old_snapshot, new_snapshot)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
        audit_line = f"[{stamp}] [admin 改地址] {diff_text}"
        order.admin_notes = (audit_line + "\n" + (order.admin_notes or "")).strip()
    else:
        # 客戶自己改 → 通知 admin
        await create_notification(
            db,
            type="customer_modified_shipping",
            message=f"客戶修改訂單 {order.order_number} 的出貨資訊",
            reference_type="order",
            reference_id=order_id,
            requires_action=True,
        )

    await db.commit()
    await db.refresh(order)
    return order


async def lock_shipping(db: AsyncSession, order_id: UUID) -> Order:
    """admin 確認出貨資訊 → 鎖定。鎖定後 create_shipment 才會放行。"""
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.shipping_locked:
        return order  # 已鎖，直接回（idempotent）
    if order.status not in (
        OrderStatusEnum.paid,
        OrderStatusEnum.processing,
    ):
        raise BadRequestError("只有已付款或備貨中的訂單才能鎖定出貨資訊")
    order.shipping_locked = True
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    audit = f"[{stamp}] 出貨資訊已鎖定"
    order.admin_notes = (audit + "\n" + (order.admin_notes or "")).strip()
    await db.commit()
    await db.refresh(order)
    return order


async def cancel_order(
    db: AsyncSession, user_id: UUID, order_id: UUID, cancel_reason: str | None = None
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.status != OrderStatusEnum.pending_payment:
        raise BadRequestError("只有待付款的訂單可取消")

    order.status = OrderStatusEnum.cancelled
    order.cancel_reason_code = CancelReasonCodeEnum.customer_cancelled
    order.cancel_reason_note = cancel_reason

    await _revert_order_effects(db, order)

    await create_notification(
        db,
        type="order_cancelled",
        message=f"訂單 {order.order_number} 客戶取消",
        reference_type="order",
        reference_id=order_id,
    )
    await db.commit()
    await db.refresh(order)
    return order


async def confirm_refund(db: AsyncSession, user_id: UUID, order_id: UUID) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
        .with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.status not in (OrderStatusEnum.refunded, OrderStatusEnum.partially_refunded):
        raise BadRequestError("只有已退款的訂單可確認退款")
    if order.refund_confirmed_at is not None:
        raise BadRequestError("已確認退款，無法重複確認")

    order.refund_confirmed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(order)
    return order


# ── admin order queries ───────────────────────────────────────────────────────

async def admin_list_orders(
    db: AsyncSession,
    status: str | None,
    date_from: str | None,
    date_to: str | None,
    search: str | None,
    order_type: str | None,
    page: int,
    page_size: int,
) -> dict:
    query = select(Order, User).join(User, Order.user_id == User.id)

    if status:
        query = query.where(Order.status == status)
    if date_from:
        query = query.where(Order.created_at >= date_from)
    if date_to:
        query = query.where(Order.created_at <= date_to)
    if order_type == "custom":
        custom_order_ids = select(OrderItem.order_id).where(
            OrderItem.custom_request_id.isnot(None)
        )
        query = query.where(Order.id.in_(custom_order_ids))
    elif order_type == "regular":
        custom_order_ids = select(OrderItem.order_id).where(
            OrderItem.custom_request_id.isnot(None)
        )
        query = query.where(Order.id.not_in(custom_order_ids))
    if search:
        like = f"%{search}%"
        query = query.where(
            (Order.order_number.ilike(like))
            | (User.name.ilike(like))
            | (User.email.ilike(like))
        )

    count_result = await db.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    rows_result = await db.execute(
        query.order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = rows_result.all()

    items = []
    for order, user in rows:
        count_res = await db.execute(
            select(func.count()).where(OrderItem.order_id == order.id)
        )
        items.append({
            "id": order.id,
            "order_number": order.order_number,
            "user_id": order.user_id,
            "user_name": user.name,
            "user_email": user.email,
            "status": order.status,
            "total": float(order.total),
            "item_count": count_res.scalar() or 0,
            "created_at": order.created_at,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def admin_get_order(db: AsyncSession, order_id: UUID) -> dict:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    return await _build_order_detail(db, order, is_admin=True)


# ── admin order actions ───────────────────────────────────────────────────────

_VALID_STATUS_TRANSITIONS = {
    OrderStatusEnum.paid: {OrderStatusEnum.pending_payment},
    OrderStatusEnum.processing: {OrderStatusEnum.paid},
    OrderStatusEnum.shipped: {OrderStatusEnum.processing},
    OrderStatusEnum.completed: {OrderStatusEnum.shipped},
    OrderStatusEnum.refund_processing: {
        OrderStatusEnum.paid,
        OrderStatusEnum.processing,
        OrderStatusEnum.shipped,
        OrderStatusEnum.completed,
    },
    OrderStatusEnum.cancelled: {OrderStatusEnum.pending_payment},
}


async def admin_update_order_status(
    db: AsyncSession,
    order_id: UUID,
    new_status: str,
    admin_notes: str | None,
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")

    target = OrderStatusEnum(new_status)
    allowed_from = _VALID_STATUS_TRANSITIONS.get(target, set())
    if order.status not in allowed_from:
        raise BadRequestError(f"無法從 {order.status} 轉換至 {new_status}")

    order.status = target

    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one()

    if target == OrderStatusEnum.paid:
        order.paid_at = datetime.now(UTC)
        items_result = await db.execute(
            select(OrderItem).where(OrderItem.order_id == order_id)
        )
        items = list(items_result.scalars().all())
        for item in items:
            prog = ProductionProgress(order_item_id=item.id)
            db.add(prog)
        # E21 (custom branch): if any item is from a custom request, notify admin
        is_custom = any(item.custom_request_id is not None for item in items)
        if is_custom:
            await create_notification(
                db,
                type="custom_order_paid",
                message=f"客製訂單 {order.order_number} 已付款，請進入備貨流程",
                reference_type="order",
                reference_id=order.id,
                requires_action=True,
            )
        await _send_email(
            to=user.email,
            subject=f"【PaintLearn】付款確認 {order.order_number}",
            html=f"<p>您的訂單 {order.order_number} 已確認付款，開始準備生產。</p>",
        )

    elif target == OrderStatusEnum.completed:
        order.completed_at = datetime.now(UTC)
        await complete_order(db, order)

    elif target == OrderStatusEnum.refund_processing:
        await _send_email(
            to=user.email,
            subject=f"【PaintLearn】退款處理中 {order.order_number}",
            html=f"<p>您的訂單 {order.order_number} 退款申請已受理，請耐心等待。</p>",
        )

    if admin_notes:
        order.admin_notes = admin_notes

    if target == OrderStatusEnum.cancelled:
        order.cancel_reason_code = CancelReasonCodeEnum.admin_cancelled
        order.cancel_reason_note = admin_notes
        await _revert_order_effects(db, order)
        await _send_email(
            to=user.email,
            subject=f"【PaintLearn】訂單取消 {order.order_number}",
            html=f"<p>您的訂單 {order.order_number} 已由管理員取消。</p>",
        )

    await db.commit()
    await db.refresh(order)
    return order


async def create_shipment(
    db: AsyncSession,
    order_id: UUID,
    shipment_type: str,
    *,
    server_reply_url: str = "",
) -> Shipment:
    """建立物流訂單 — Day 2 真實 ECpay 整合（不再是 stub）。

    Args:
        server_reply_url: ECpay 推狀態通知 URL（Day 3 webhook）。空字串時用 settings 預設。
    """
    from logistics import service as logistics_service

    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.status not in (
        OrderStatusEnum.paid, OrderStatusEnum.processing, OrderStatusEnum.shipped
    ):
        raise BadRequestError("訂單狀態不允許出貨")

    # 出貨資訊鎖定檢查：必須先「確認出貨資訊」
    if not order.shipping_locked:
        raise BadRequestError("請先按「確認出貨資訊」鎖定後才能建立物流訂單")

    # 重複建單防呆：本訂單同 shipment_type 已有 Shipment → 拒絕
    existing_check = await db.execute(
        select(Shipment).where(
            Shipment.order_id == order_id,
            Shipment.shipment_type == shipment_type,
        )
    )
    if existing_check.scalar_one_or_none():
        raise ConflictError(
            f"本訂單{shipment_type}類型已建立物流單，不可重複建單"
        )

    # 取訂單商品名（concat 用）
    items_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    order_items = items_result.scalars().all()
    goods_titles = [oi.product_title_snapshot for oi in order_items]

    # 呼叫 ECpay 真實建單
    if not server_reply_url:
        # 預設 fallback；正式由 router 注入
        server_reply_url = (
            "https://paint-web-production.up.railway.app"
            "/api/v1/logistics/status-callback"
        )

    try:
        ecpay_result = await logistics_service.execute_create_shipment(
            db,
            order_number=order.order_number,
            order_created_at=order.created_at,
            total_amount=float(order.total),
            goods_titles=goods_titles,
            shipping_snapshot=order.shipping_snapshot,
            server_reply_url=server_reply_url,
        )
    except (ValueError, ConnectionError) as e:
        # 業務錯誤（金額超限 / 寄件人未設）或 ECpay 連線失敗
        raise BadRequestError(str(e)) from e

    if not ecpay_result["ok"]:
        raise BadRequestError(
            f"ECpay 建單失敗 (RtnCode={ecpay_result['rtn_code']})：{ecpay_result['rtn_msg']}"
        )

    tracking_number = ecpay_result["tracking_number"]
    ecpay_logistics_id = ecpay_result["ecpay_logistics_id"]

    now = datetime.now(UTC)
    shipment = Shipment(
        order_id=order_id,
        shipment_type=shipment_type,
        status=ShipmentStatusEnum.shipped,
        tracking_number=tracking_number,
        ecpay_logistics_id=ecpay_logistics_id,
        cvs_payment_no=ecpay_result.get("cvs_payment_no"),
        cvs_validation_no=ecpay_result.get("cvs_validation_no"),
        shipped_at=now,
    )
    db.add(shipment)
    await db.flush()

    # 出貨即確認 — 確保 shipping_locked=True（雖然前面已檢查過，這裡 idempotent 雙保險）
    if not order.shipping_locked:
        order.shipping_locked = True

    # Update production progress → shipped, scoped to items matching shipment_type
    if shipment_type == "fulfilled":
        item_filter = OrderItem.fulfilled_qty > 0
    else:
        item_filter = OrderItem.preorder_qty > 0
    await db.execute(
        update(ProductionProgress)
        .where(
            ProductionProgress.order_item_id.in_(
                select(OrderItem.id).where(
                    OrderItem.order_id == order_id, item_filter
                )
            )
        )
        .values(status=ProductionProgressStatusEnum.shipped)
    )

    # Update order status
    if order.status in (OrderStatusEnum.paid, OrderStatusEnum.processing):
        order.status = OrderStatusEnum.shipped

    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one()

    await _send_email(
        to=user.email,
        subject=f"【PaintLearn】出貨通知 {order.order_number}",
        html=(
            f"<p>您的訂單 {order.order_number} 已出貨。</p>"
            f"<p>追蹤號：{tracking_number}</p>"
        ),
    )

    await db.commit()
    await db.refresh(shipment)
    return shipment


async def refresh_shipment_status(db: AsyncSession, order_id: UUID) -> None:
    """對該 Order 的每筆 Shipment 主動查 ECpay /7418/，比對狀態並同步。

    用於 webhook 掉包補救（admin 點「重新查詢狀態」按鈕）。
    """
    from logistics import service as logistics_service

    result = await db.execute(
        select(Shipment).where(Shipment.order_id == order_id)
    )
    shipments = list(result.scalars().all())
    if not shipments:
        raise NotFoundError("該訂單沒有物流訂單可查詢")

    for ship in shipments:
        if not ship.ecpay_logistics_id:
            logger.info(f"[refresh-shipment] skip {ship.id} — no ecpay_logistics_id")
            continue
        try:
            raw = await logistics_service.query_logistics_trade(
                all_pay_logistics_id=ship.ecpay_logistics_id,
            )
        except Exception as e:
            logger.warning(f"[refresh-shipment] query failed for {ship.id}: {e}")
            continue

        # ECpay /7418/ 回的格式不同於 webhook，狀態欄位是 LogisticsStatus
        try:
            new_rtn_code = int(raw.get("LogisticsStatus") or raw.get("RtnCode") or "0")
        except ValueError:
            new_rtn_code = 0
        new_rtn_msg = raw.get("RtnMsg") or raw.get("LogisticsStatus") or ""
        new_status_at = logistics_service.parse_ecpay_datetime(
            raw.get("UpdateStatusDate") or ""
        )

        # 比對：last_status_at >= new_status_at 跳過（已是最新）
        if (
            new_status_at
            and ship.last_status_at
            and ship.last_status_at >= new_status_at
        ):
            continue

        ship.last_rtn_code = new_rtn_code
        ship.last_rtn_msg = new_rtn_msg
        if new_status_at:
            ship.last_status_at = new_status_at

        if logistics_service.is_delivered_status(new_rtn_code, new_rtn_msg):
            if ship.status != ShipmentStatusEnum.delivered:
                ship.status = ShipmentStatusEnum.delivered
                ship.delivered_at = new_status_at or datetime.now(UTC)

    # 完成後檢查 Order.status 是否要推進到 completed
    order_result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = order_result.scalar_one_or_none()
    if order is not None:
        all_ships_result = await db.execute(
            select(Shipment).where(Shipment.order_id == order_id)
        )
        all_ships = list(all_ships_result.scalars().all())
        if all_ships and all(
            s.status == ShipmentStatusEnum.delivered for s in all_ships
        ):
            if order.status != OrderStatusEnum.completed:
                order.status = OrderStatusEnum.completed
                order.completed_at = datetime.now(UTC)

    await db.commit()


async def batch_create_shipments(
    db: AsyncSession,
    order_ids: list[UUID],
    shipment_type: str,
    *,
    server_reply_url: str = "",
) -> dict:
    """批次建單 — 一次最多 50 筆。

    每筆獨立 try/except，失敗不影響其他成功；不用 asyncio.gather 因為會吃 ECpay rate limit。
    依序呼叫，每筆一個 transaction（create_shipment 內部會 commit）。

    Returns:
        {total, success, failed, results: [{order_id, ok, tracking_number?, error?}]}
    """
    results: list[dict] = []
    success_count = 0
    failed_count = 0

    for order_id in order_ids:
        try:
            shipment = await create_shipment(
                db, order_id, shipment_type, server_reply_url=server_reply_url
            )
            results.append({
                "order_id": order_id,
                "ok": True,
                "tracking_number": shipment.tracking_number,
                "ecpay_logistics_id": shipment.ecpay_logistics_id,
                "error": None,
            })
            success_count += 1
        except (NotFoundError, BadRequestError, ConflictError) as e:
            results.append({
                "order_id": order_id,
                "ok": False,
                "tracking_number": None,
                "ecpay_logistics_id": None,
                "error": str(e),
            })
            failed_count += 1
        except Exception as e:  # 不預期錯誤也不能整批 fail
            logger.exception(f"[batch-shipment] order={order_id} unexpected error")
            results.append({
                "order_id": order_id,
                "ok": False,
                "tracking_number": None,
                "ecpay_logistics_id": None,
                "error": f"未預期錯誤：{e!s}",
            })
            failed_count += 1

    return {
        "total": len(order_ids),
        "success": success_count,
        "failed": failed_count,
        "results": results,
    }


async def update_production_progress(
    db: AsyncSession,
    order_id: UUID,
    progress_id: UUID,
    new_status: str,
    notes: str | None,
) -> ProductionProgress:
    result = await db.execute(
        select(ProductionProgress, OrderItem)
        .join(OrderItem, ProductionProgress.order_item_id == OrderItem.id)
        .where(
            ProductionProgress.id == progress_id,
            OrderItem.order_id == order_id,
        )
    )
    row = result.first()
    if row is None:
        raise NotFoundError("生產進度記錄不存在")

    progress, order_item = row

    disallowed = {
        ProductionProgressStatusEnum.in_production,
        ProductionProgressStatusEnum.shipped,
    }
    if ProductionProgressStatusEnum(new_status) in disallowed:
        raise BadRequestError(f"不允許手動設定狀態為 {new_status}")

    progress.status = ProductionProgressStatusEnum(new_status)
    if notes is not None:
        progress.notes = notes

    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one()
    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one()

    # 自動推進 order.status: paid → processing
    # admin 點任何手動生產階段（manufacturing/packaging/ready_to_ship）都代表「已開工」，
    # Order.status 應從 'paid' 升到 'processing'，user 端才會看到「製作中」狀態。
    if (
        order.status == OrderStatusEnum.paid
        and new_status in ("manufacturing", "packaging", "ready_to_ship")
    ):
        order.status = OrderStatusEnum.processing

    # Email for manufacturing and ready_to_ship
    if new_status in ("manufacturing", "ready_to_ship"):
        label = "開始製作" if new_status == "manufacturing" else "準備出貨"
        await _send_email(
            to=user.email,
            subject=f"【PaintLearn】生產進度更新 {order.order_number}",
            html=(
                f"<p>您的訂單 {order.order_number} 中"
                f" {order_item.product_title_snapshot} {label}。</p>"
            ),
        )

    await db.commit()
    await db.refresh(progress)
    return progress


async def process_refund(
    db: AsyncSession,
    order_id: UUID,
    refund_amount: float,
    returned_item_ids: list[UUID],
    cancel_reason: str | None,
) -> Order:
    result = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    if order.status != OrderStatusEnum.refund_processing:
        raise BadRequestError("訂單不在退款處理中")
    if Decimal(str(refund_amount)) > order.total:
        raise BadRequestError("退款金額不可超過訂單總額")

    # Dedupe and validate items belong to this order; ignore already-returned ones
    requested_ids = set(returned_item_ids)
    valid_items_result = await db.execute(
        select(OrderItem).where(
            OrderItem.id.in_(requested_ids),
            OrderItem.order_id == order_id,
            OrderItem.is_returned == False,  # noqa: E712
        )
    )
    valid_items = list(valid_items_result.scalars().all())
    valid_ids = [item.id for item in valid_items]

    # Determine full vs partial refund based on items not yet returned
    all_items_result = await db.execute(
        select(OrderItem.id).where(OrderItem.order_id == order_id)
    )
    all_item_ids = {row[0] for row in all_items_result.all()}
    is_full_refund = requested_ids >= all_item_ids

    order.refund_amount = refund_amount
    order.refunded_at = datetime.now(UTC)
    order.cancel_reason_note = cancel_reason
    order.status = (
        OrderStatusEnum.refunded if is_full_refund else OrderStatusEnum.partially_refunded
    )

    # Mark returned items and restore stock (only for items still active)
    for item in valid_items:
        item.is_returned = True

    await _restore_stock_for_items(db, order_id, valid_ids)

    if is_full_refund:
        await discount_svc.revert_coupon(db, order_id)

    await discount_svc.revoke_reward_coupons(
        db, order_id,
        refund_amount=refund_amount,
        order_total=float(order.total),
    )

    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one()

    refund_type = "全額退款" if is_full_refund else "部分退款"
    await _send_email(
        to=user.email,
        subject=f"【PaintLearn】{refund_type}通知 {order.order_number}",
        html=(
            f"<p>您的訂單 {order.order_number} 已完成{refund_type}。</p>"
            f"<p>退款金額：NT${refund_amount}</p>"
            f"<p>請確認退款：{settings.frontend_url}/orders/{order_id}?action=confirm_refund</p>"
        ),
    )

    await db.commit()
    await db.refresh(order)
    order._returned_item_count = len(valid_ids)  # transient hint for router
    return order


async def flag_payment_submission(
    db: AsyncSession,
    order_id: UUID,
    submission_id: UUID,
    is_flagged: bool = True,
    admin_note: str | None = None,
) -> dict:
    result = await db.execute(
        select(PaymentSubmission)
        .where(
            PaymentSubmission.id == submission_id,
            PaymentSubmission.order_id == order_id,
        )
        .with_for_update()
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise NotFoundError("付款資訊不存在")
    if sub.is_flagged:
        raise BadRequestError("付款資訊已標記")

    sub.is_flagged = True

    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one()

    deadline_hours = int(await get_system_setting(db, "payment_absolute_deadline_hours") or "48")
    absolute_deadline = order.created_at + timedelta(hours=deadline_hours)
    new_deadline = min(datetime.now(UTC) + timedelta(hours=24), absolute_deadline)
    order.payment_deadline = new_deadline

    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one()

    remaining = new_deadline - datetime.now(UTC)
    urgent = remaining.total_seconds() < 6 * 3600
    subject_prefix = "【緊急】" if urgent else ""
    note_html = f"<p>備注：{admin_note}</p>" if admin_note else ""
    await _send_email(
        to=user.email,
        subject=f"【PaintLearn】{subject_prefix}付款資訊有誤 {order.order_number}",
        html=(
            f"<p>您的訂單 {order.order_number} 付款資訊有誤，請重新提交。</p>"
            f"{note_html}"
            f"<p>新付款期限：{new_deadline.strftime('%Y-%m-%d %H:%M')}</p>"
        ),
    )

    await db.commit()
    return {"payment_deadline": new_deadline}


async def update_admin_notes(
    db: AsyncSession, order_id: UUID, admin_notes: str
) -> Order:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if order is None:
        raise NotFoundError("訂單不存在")
    order.admin_notes = admin_notes
    await db.commit()
    await db.refresh(order)
    return order


# ── ECpay webhook ─────────────────────────────────────────────────────────────

async def handle_ecpay_webhook(db: AsyncSession, payload: dict) -> str:
    # TODO: 正式上線前補上 CheckMacValue 驗證（SHA256 HMAC）
    logger.warning("ECpay CheckMacValue validation is SKIPPED (stub mode)")

    logistics_id = payload.get("AllPayLogisticsID") or payload.get("MerchantTradeNo", "")
    rtn_code = payload.get("RtnCode", "")
    rtn_msg = payload.get("RtnMsg", "")

    shipment_result = await db.execute(
        select(Shipment).where(Shipment.ecpay_logistics_id == logistics_id)
    )
    shipment = shipment_result.scalar_one_or_none()

    if shipment is None:
        logger.warning(f"ECpay webhook: unknown logistics_id {logistics_id}")
        return "1|OK"

    if str(rtn_code) == "3":  # 已取貨/已投遞
        shipment.status = ShipmentStatusEnum.delivered
        shipment.delivered_at = datetime.now(UTC)
        await db.flush()

        # Check if all shipments delivered
        all_subs_result = await db.execute(
            select(Shipment).where(Shipment.order_id == shipment.order_id)
        )
        all_shipments = all_subs_result.scalars().all()
        all_delivered = all(s.status == ShipmentStatusEnum.delivered for s in all_shipments)

        if all_delivered:
            order_result = await db.execute(
                select(Order).where(Order.id == shipment.order_id).with_for_update()
            )
            order = order_result.scalar_one_or_none()
            if order and order.status == OrderStatusEnum.shipped:
                order.status = OrderStatusEnum.completed
                order.completed_at = datetime.now(UTC)
                await complete_order(db, order)
                user_result = await db.execute(
                    select(User).where(User.id == order.user_id)
                )
                user = user_result.scalar_one()
                await _send_email(
                    to=user.email,
                    subject=f"【PaintLearn】訂單完成 {order.order_number}",
                    html=(
                        f"<p>您的訂單 {order.order_number} 已完成投遞，謝謝您的購買！</p>"
                        f"<p>感謝您獲得回饋券，請至會員中心查看。</p>"
                    ),
                )
    else:
        order_result = await db.execute(
            select(Order).where(Order.id == shipment.order_id)
        )
        order = order_result.scalar_one_or_none()
        order_number = order.order_number if order else logistics_id
        await create_notification(
            db,
            type="ecpay_status",
            message=f"ECpay 狀態更新：{rtn_msg}（訂單 {order_number}）",
            reference_type="order",
            reference_id=shipment.order_id,
        )

    await db.commit()
    return "1|OK"
