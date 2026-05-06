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
    result = await db.execute(
        select(CartItem, ProductVariant, Product, ProductionJob)
        .join(ProductVariant, CartItem.product_variant_id == ProductVariant.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .outerjoin(ProductionJob, ProductVariant.production_job_id == ProductionJob.id)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at)
    )
    rows = result.all()

    items = []
    for cart_item, variant, product, job in rows:
        qty = cart_item.quantity
        if variant.production_job_id:
            fulfillable = await _compute_fulfillable_qty(db, variant.production_job_id, qty)
        else:
            fulfillable = qty
        fulfilled_units = fulfillable
        preorder_units = qty - fulfillable
        variant_spec = _job_spec(job) if job else {}
        # 縮圖：優先 variant filled_template、其次 product cover
        thumb = (job.filled_template_url if job and job.filled_template_url else product.cover_image_url)
        items.append({
            "id": cart_item.id,
            "variant_id": variant.id,
            "product_id": product.id,
            "product_title": product.title,
            "product_image_url": product.cover_image_url,
            "variant_image_url": job.filled_template_url if job else None,
            "thumb_url": thumb,
            "variant_spec": variant_spec,
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


def _compute_shipping_fee(subtotal: Decimal, total_qty: int, shipping_type: str) -> Decimal:
    if subtotal >= FREE_SHIPPING_MIN_AMOUNT or total_qty >= FREE_SHIPPING_MIN_QTY:
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

    discount_calc = await discount_svc.calculate_discount(
        db, user_id, float(subtotal), user_coupon_id, promo_code
    )
    discount_amount = Decimal(str(discount_calc["discount_amount"]))

    free_shipping_reason: str | None = None
    if subtotal >= FREE_SHIPPING_MIN_AMOUNT:
        free_shipping_reason = "amount"
    elif total_qty >= FREE_SHIPPING_MIN_QTY:
        free_shipping_reason = "quantity"

    shipping_fee = _compute_shipping_fee(subtotal, total_qty, shipping_type)
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
) -> Shipment:
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

    # ECpay stub
    ecpay_merchant_id = os.environ.get("ECPAY_MERCHANT_ID", "")
    if ecpay_merchant_id:
        # TODO: 呼叫真實 ECpay 物流 API
        tracking_number = f"REAL-{uuid.uuid4().hex[:12].upper()}"
        ecpay_logistics_id = f"EC-{uuid.uuid4().hex[:8].upper()}"
    else:
        logger.warning("ECPAY_MERCHANT_ID not set — using stub tracking number")
        tracking_number = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        ecpay_logistics_id = f"STUB-{uuid.uuid4().hex[:8].upper()}"

    now = datetime.now(UTC)
    shipment = Shipment(
        order_id=order_id,
        shipment_type=shipment_type,
        status=ShipmentStatusEnum.shipped,
        tracking_number=tracking_number,
        ecpay_logistics_id=ecpay_logistics_id,
        shipped_at=now,
    )
    db.add(shipment)
    await db.flush()

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

    # Email for manufacturing and ready_to_ship
    order_result = await db.execute(select(Order).where(Order.id == order_id))
    order = order_result.scalar_one()
    user_result = await db.execute(select(User).where(User.id == order.user_id))
    user = user_result.scalar_one()

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
