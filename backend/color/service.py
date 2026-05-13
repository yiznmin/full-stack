import asyncio
import logging
import math
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from color.models import PhysicalColor, PhysicalColorRgbHistory
from core.config import settings
from core.exceptions import ConflictError, NotFoundError

logger = logging.getLogger(__name__)


async def _send_email(to: str, subject: str, html: str) -> None:
    try:
        import resend
        resend.api_key = settings.resend_api_key
        payload: dict = {
            "from": settings.resend_from_email,
            "to": to,
            "subject": subject,
            "html": html,
        }
        if settings.support_email:
            payload["reply_to"] = settings.support_email
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: resend.Emails.send(payload),
        )
    except Exception as e:
        logger.warning(f"Email send failed to {to}: {e}")


async def list_colors(
    db: AsyncSession,
    color_family: str | None,
    is_active: bool | None,
    search: str | None,
) -> list[PhysicalColor]:
    q = select(PhysicalColor)
    if color_family is not None:
        q = q.where(PhysicalColor.color_family == color_family)
    if is_active is not None:
        q = q.where(PhysicalColor.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            PhysicalColor.code.ilike(pattern) | PhysicalColor.name.ilike(pattern)
        )
    q = q.order_by(PhysicalColor.code)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_color(
    db: AsyncSession,
    data: dict,
    changed_by_user_id: UUID | None = None,
) -> PhysicalColor:
    existing = await db.execute(
        select(PhysicalColor).where(PhysicalColor.code == data["code"])
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"色號 {data['code']} 已存在")
    color = PhysicalColor(**data)
    db.add(color)
    await db.flush()
    db.add(PhysicalColorRgbHistory(
        physical_color_id=color.id,
        rgb=color.rgb,
        changed_by_user_id=changed_by_user_id,
        note="initial",
    ))
    await db.commit()
    await db.refresh(color)
    return color


async def update_color(db: AsyncSession, color_id: UUID, data: dict) -> PhysicalColor:
    """部分更新：data 來自 UpdateColorRequest.model_dump(exclude_unset=True)，
    只含使用者實際送來的欄位（PATCH 語義）。

    code 變動時才查重；其他欄位（color_family / brand / stock_ml / name）獨立更新。
    """
    color = await _get_or_404(db, color_id)
    if "code" in data and data["code"] != color.code:
        dup = await db.execute(
            select(PhysicalColor).where(
                PhysicalColor.code == data["code"],
                PhysicalColor.id != color_id,
            )
        )
        if dup.scalar_one_or_none():
            raise ConflictError(f"色號 {data['code']} 已被其他色條目使用")
    for k, v in data.items():
        setattr(color, k, v)
    await db.commit()
    await db.refresh(color)
    return color


async def toggle_active(db: AsyncSession, color_id: UUID) -> PhysicalColor:
    color = await _get_or_404(db, color_id)
    color.is_active = not color.is_active
    await db.commit()
    await db.refresh(color)
    return color


async def update_rgb(
    db: AsyncSession,
    color_id: UUID,
    rgb: list[int],
    changed_by_user_id: UUID | None = None,
    note: str = "manual",
) -> PhysicalColor:
    """校正實體色 RGB（palette workspace 彈跳視窗）。

    僅改 rgb 不動其他欄位。校正不影響：
    - 既有 palette_color_mappings（algorithm_rgb 是 mapping 建立時的快照）
    - 既有 required_ml（公式僅與面積 / 佔比 / 係數相關）

    校正後影響：未來新建 mapping 時的 LAB 距離自動配色結果。
    每次更新都產生 PhysicalColorRgbHistory 一筆 audit snapshot。
    """
    color = await _get_or_404(db, color_id)
    color.rgb = rgb
    db.add(PhysicalColorRgbHistory(
        physical_color_id=color.id,
        rgb=rgb,
        changed_by_user_id=changed_by_user_id,
        note=note,
    ))
    await db.commit()
    await db.refresh(color)
    return color


async def list_rgb_history(
    db: AsyncSession, color_id: UUID
) -> list[dict]:
    """列出實體色的 RGB 變動歷史（時間倒序）。"""
    from auth.models import User

    await _get_or_404(db, color_id)
    rows = (await db.execute(
        select(PhysicalColorRgbHistory, User)
        .outerjoin(User, PhysicalColorRgbHistory.changed_by_user_id == User.id)
        .where(PhysicalColorRgbHistory.physical_color_id == color_id)
        .order_by(PhysicalColorRgbHistory.created_at.desc())
    )).all()
    return [
        {
            "id": h.id,
            "rgb": h.rgb,
            "changed_by_user_id": h.changed_by_user_id,
            "changed_by_name": u.name if u else None,
            "note": h.note,
            "created_at": h.created_at,
        }
        for h, u in rows
    ]


async def revert_rgb(
    db: AsyncSession,
    color_id: UUID,
    history_id: UUID,
    changed_by_user_id: UUID | None = None,
) -> PhysicalColor:
    """還原實體色 RGB 到指定的歷史版本，並寫入新一筆 audit。"""
    color = await _get_or_404(db, color_id)

    history = (await db.execute(
        select(PhysicalColorRgbHistory).where(
            PhysicalColorRgbHistory.id == history_id,
            PhysicalColorRgbHistory.physical_color_id == color_id,
        )
    )).scalar_one_or_none()
    if history is None:
        raise NotFoundError("歷史版本不存在或不屬於此實體色")

    color.rgb = history.rgb
    db.add(PhysicalColorRgbHistory(
        physical_color_id=color.id,
        rgb=history.rgb,
        changed_by_user_id=changed_by_user_id,
        note=f"revert from {history.id}",
    ))
    await db.commit()
    await db.refresh(color)
    return color


async def add_stock(db: AsyncSession, color_id: UUID, add_ml: float) -> dict:
    """E33 + E34: 進貨 → 升單掃描 → 補缺貨通知。

    1. stock_ml += add_ml
    2. 掃所有 preorder_qty>0 的 order_items（依 created_at），整批升單或全跳
    3. 升單後扣 stock + 推進 production_progress + 管理員通知
    4. 掃完後檢查仍缺料的顏料，create_or_update_stock_shortage
    5. commit 後才寄客戶 email（避免 commit 失敗造成 DB 與通知不一致）
    """
    color = await _get_or_404(db, color_id)
    color.stock_ml = Decimal(str(color.stock_ml)) + Decimal(str(add_ml))
    await db.flush()

    upgraded_count, pending_emails = await _scan_preorders_and_upgrade(db)
    await _check_stock_shortages(db)

    await db.commit()
    await db.refresh(color)

    # commit 之後再寄 email：commit 失敗時客戶不會收到「已備齊」鬼魂訊息
    for em in pending_emails:
        await _send_email(em["to"], em["subject"], em["html"])

    return {
        "new_stock_ml": float(color.stock_ml),
        "fulfilled_orders": upgraded_count,
    }


async def _scan_preorders_and_upgrade(
    db: AsyncSession,
) -> tuple[int, list[dict]]:
    """E34: 掃所有 preorder_qty>0 的 order_items，整批升單或全跳。

    Email 客戶的內容收集到 list 回傳，由呼叫端在 commit 後才實際寄出。
    返回 (升單訂單數, [{"to", "subject", "html"}, ...])。
    """
    from sqlalchemy import update as sa_update

    from auth.models import User
    from notifications.service import create_notification
    from orders.models import (
        Order,
        OrderItem,
        OrderStatusEnum,
        ProductionProgress,
        ProductionProgressStatusEnum,
        ShippingPreferenceEnum,
    )
    from palette.models import PaletteColorMapping

    # Active orders that may have preorder items（排除已 cancelled/refunded/expired）
    active_statuses = [
        OrderStatusEnum.paid,
        OrderStatusEnum.processing,
        OrderStatusEnum.shipped,
    ]
    rows = (await db.execute(
        select(OrderItem, Order)
        .join(Order, OrderItem.order_id == Order.id)
        .where(
            OrderItem.preorder_qty > 0,
            OrderItem.production_job_id.isnot(None),
            Order.status.in_(active_statuses),
        )
        .order_by(Order.created_at.asc(), OrderItem.id.asc())
        .with_for_update(of=OrderItem)
    )).all()

    upgraded_order_ids: set[UUID] = set()
    pending_emails: list[dict] = []

    for item, order in rows:
        if item.preorder_qty <= 0:
            continue

        # 取此 item 的所有色料需求
        mappings = (await db.execute(
            select(PaletteColorMapping).where(
                PaletteColorMapping.production_job_id == item.production_job_id,
                PaletteColorMapping.required_ml.isnot(None),
            )
        )).scalars().all()

        # 累計每色 total need = required_ml × preorder_qty（可能多個 mapping 指到同色）
        needs: dict[UUID, Decimal] = {}
        for m in mappings:
            need = Decimal(str(m.required_ml)) * item.preorder_qty
            needs[m.physical_color_id] = needs.get(m.physical_color_id, Decimal("0")) + need

        # 鎖所有相關顏料；populate_existing 確保 ORM cache 同步前次扣減
        locked_stocks: dict[UUID, Decimal] = {}
        all_sufficient = True
        for cid in needs:
            cres = await db.execute(
                select(PhysicalColor)
                .where(PhysicalColor.id == cid)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            c = cres.scalar_one_or_none()
            if c is None:
                all_sufficient = False
                break
            locked_stocks[cid] = Decimal(str(c.stock_ml))

        if not all_sufficient:
            continue
        for cid, need in needs.items():
            if locked_stocks[cid] < need:
                all_sufficient = False
                break
        if not all_sufficient:
            continue  # 整批升或全跳

        # 升單：扣 stock + update item
        for cid, need in needs.items():
            await db.execute(
                sa_update(PhysicalColor)
                .where(PhysicalColor.id == cid)
                .values(stock_ml=PhysicalColor.stock_ml - need)
            )

        upgraded_qty = item.preorder_qty
        item.fulfilled_qty = item.fulfilled_qty + upgraded_qty
        item.preorder_qty = 0
        upgraded_order_ids.add(item.order_id)

        # 客戶 email — 留到 commit 後才寄
        user = (await db.execute(
            select(User).where(User.id == order.user_id)
        )).scalar_one_or_none()
        if user:
            pending_emails.append({
                "to": user.email,
                "subject": f"【易木 YIIMUI】您的預購商品已備齊 {order.order_number}",
                "html": (
                    f"<p>您的訂單 {order.order_number} 中的預購商品已備齊，"
                    f"即將進入出貨流程。</p>"
                    f"<p>升單數量：{upgraded_qty}</p>"
                ),
            })

        # 管理員通知（每筆訂單一條）
        await create_notification(
            db,
            type="preorder_upgraded",
            message=f"訂單 {order.order_number} 預購商品已自動升單（{upgraded_qty} 件）",
            reference_type="order",
            reference_id=order.id,
            requires_action=False,
        )

    # 升單後處理整張 order 連動（規格 admin_color.md §43）：
    # - 條件：整張 order 所有 items 的 preorder_qty 都歸零
    # - **且**：shipping_preference != 'together'（即 'separate' 或 None=無預購分批）
    #   → 'together' 表示客戶要求合併出貨，等所有 items（含尚未進貨那些）備齊
    #     才推進；本次只升一個顏料，不可自動帶整單進備貨
    # - 滿足時：order.status paid → processing；所有 production_progress pending → in_production
    for upgraded_order_id in upgraded_order_ids:
        remaining = (await db.execute(
            select(func.count(OrderItem.id)).where(
                OrderItem.order_id == upgraded_order_id,
                OrderItem.preorder_qty > 0,
            )
        )).scalar() or 0
        if remaining > 0:
            continue  # 訂單還有別的 item 等備齊，不推進
        order_obj = (await db.execute(
            select(Order).where(Order.id == upgraded_order_id).with_for_update()
        )).scalar_one()

        # 規格 §43 守衛：together 不自動推進
        if order_obj.shipping_preference == ShippingPreferenceEnum.together:
            continue

        if order_obj.status == OrderStatusEnum.paid:
            order_obj.status = OrderStatusEnum.processing

        # 推進該 order 所有 production_progress pending → in_production
        await db.execute(
            sa_update(ProductionProgress)
            .where(
                ProductionProgress.order_item_id.in_(
                    select(OrderItem.id).where(
                        OrderItem.order_id == upgraded_order_id
                    )
                ),
                ProductionProgress.status == ProductionProgressStatusEnum.pending,
            )
            .values(status=ProductionProgressStatusEnum.in_production)
        )

    return len(upgraded_order_ids), pending_emails


async def _check_stock_shortages(db: AsyncSession) -> None:
    """掃所有 active 顏料，計算「待備量 = Σ(required_ml × preorder_qty)」。
    若 shortage > 0 → create_or_update_stock_shortage（Module 11 race-safe helper）。
    """
    from notifications.service import create_or_update_stock_shortage
    from orders.models import Order, OrderItem, OrderStatusEnum
    from palette.models import PaletteColorMapping

    active_statuses = [
        OrderStatusEnum.paid,
        OrderStatusEnum.processing,
        OrderStatusEnum.shipped,
    ]

    # 計算每色總待備量：Σ(required_ml × preorder_qty)
    rows = (await db.execute(
        select(
            PaletteColorMapping.physical_color_id,
            func.sum(PaletteColorMapping.required_ml * OrderItem.preorder_qty)
            .label("total_need"),
        )
        .join(OrderItem, OrderItem.production_job_id == PaletteColorMapping.production_job_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.preorder_qty > 0,
            OrderItem.production_job_id.isnot(None),
            PaletteColorMapping.required_ml.isnot(None),
            Order.status.in_(active_statuses),
        )
        .group_by(PaletteColorMapping.physical_color_id)
    )).all()

    need_by_color: dict[UUID, Decimal] = {
        r.physical_color_id: Decimal(str(r.total_need or 0)) for r in rows
    }
    if not need_by_color:
        return

    color_rows = (await db.execute(
        select(PhysicalColor)
        .where(
            PhysicalColor.id.in_(need_by_color.keys()),
            PhysicalColor.is_active.is_(True),
        )
    )).scalars().all()

    for c in color_rows:
        need = need_by_color.get(c.id, Decimal("0"))
        stock = Decimal(str(c.stock_ml))
        shortage = need - stock
        if shortage > 0:
            shortage_rounded = math.ceil(float(shortage) * 100) / 100
            message = (
                f"色號 {c.code}（{c.name}）庫存不足，"
                f"待備 {float(need):.2f}ml / 現有 {float(stock):.2f}ml，"
                f"缺口 {shortage_rounded}ml"
            )
            await create_or_update_stock_shortage(db, c.id, message)


async def shortage_dashboard(db: AsyncSession) -> list[dict]:
    """缺貨儀表板。

    待備量 = Σ(palette_color_mappings.required_ml × order_items.preorder_qty)
        FROM palette_color_mappings
        JOIN order_items ON production_job_id
        JOIN orders WHERE status IN (paid/processing/shipped) AND preorder_qty > 0

    等待訂單數 = preorder_qty>0 且 active 訂單筆數（distinct order_id）。
    """
    from orders.models import Order, OrderItem, OrderStatusEnum
    from palette.models import PaletteColorMapping

    active_statuses = [
        OrderStatusEnum.paid,
        OrderStatusEnum.processing,
        OrderStatusEnum.shipped,
    ]

    need_rows = (await db.execute(
        select(
            PaletteColorMapping.physical_color_id,
            func.sum(PaletteColorMapping.required_ml * OrderItem.preorder_qty)
            .label("total_need"),
            func.count(func.distinct(OrderItem.order_id)).label("waiting_orders"),
        )
        .join(OrderItem, OrderItem.production_job_id == PaletteColorMapping.production_job_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            OrderItem.preorder_qty > 0,
            OrderItem.production_job_id.isnot(None),
            PaletteColorMapping.required_ml.isnot(None),
            Order.status.in_(active_statuses),
        )
        .group_by(PaletteColorMapping.physical_color_id)
    )).all()

    need_by_color: dict[UUID, dict] = {
        r.physical_color_id: {
            "need": float(r.total_need or 0),
            "waiting_orders": int(r.waiting_orders or 0),
        }
        for r in need_rows
    }

    colors = await list_colors(db, color_family=None, is_active=True, search=None)
    items = []
    for c in colors:
        agg = need_by_color.get(c.id, {"need": 0.0, "waiting_orders": 0})
        stock = float(c.stock_ml)
        required = agg["need"]
        shortage = required - stock
        if shortage > 0:
            items.append({
                "color_id": c.id,
                "code": c.code,
                "name": c.name,
                "stock_ml": stock,
                "required_ml": required,
                "shortage_ml": math.ceil(shortage * 100) / 100,
                "waiting_orders": agg["waiting_orders"],
            })
    return items


async def _get_or_404(db: AsyncSession, color_id: UUID) -> PhysicalColor:
    result = await db.execute(
        select(PhysicalColor).where(PhysicalColor.id == color_id)
    )
    color = result.scalar_one_or_none()
    if not color:
        raise NotFoundError("實體色不存在")
    return color


# ── LAB color utilities ───────────────────────────────────────────────────────

def _rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert sRGB (0-255) to CIE LAB using D65 illuminant."""
    def linearize(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = linearize(r), linearize(g), linearize(b)

    # sRGB → XYZ (D65)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041

    # XYZ → LAB (D65 white point)
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    xn, yn, zn = 0.95047, 1.00000, 1.08883
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    lab_l = 116 * fy - 16
    lab_a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return lab_l, lab_a, b_val


def lab_distance(rgb1: list[int], rgb2: list[int]) -> float:
    l1, a1, b1 = _rgb_to_lab(*rgb1)
    l2, a2, b2 = _rgb_to_lab(*rgb2)
    return math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)
