"""Admin Dashboard Summary — 給 admin 後台首頁的儀表板用聚合資料。

回傳 4 大區塊：
1. 4 張 stats card：本月訂單 / 本月營收 / 待處理客製 / 製作中批次（含 vs 上月 trend）
2. 6 筆最近活動（混合 orders / custom_requests，按時間排序）
3. 製作流水線：production_jobs 各 status count
4. 通知區：未處理通知數（之後可擴）

設計：
- 一個 endpoint 一次回完，避免 admin 首頁打 5 個 API
- 全部用 SQL aggregate，無 ORM N+1
"""
from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from custom.models import CustomRequest, CustomRequestStatusEnum
from dependencies.auth import require_admin
from notifications.models import AdminNotification, NotificationStatusEnum
from orders.models import Order, OrderStatusEnum
from production.models import JobStatusEnum, ProductionJob

router = APIRouter(tags=["Admin - Dashboard"])


def _month_range(today: date) -> tuple[datetime, datetime, datetime, datetime]:
    """回 (本月起, 本月迄+1秒(現在), 上月起, 上月迄)。tz-aware UTC。"""
    this_month_start = datetime.combine(
        today.replace(day=1), time.min, tzinfo=UTC,
    )
    now = datetime.now(UTC)
    if today.month == 1:
        last_month_y, last_month_m = today.year - 1, 12
    else:
        last_month_y, last_month_m = today.year, today.month - 1
    last_month_start = datetime(last_month_y, last_month_m, 1, tzinfo=UTC)
    last_month_end_day = monthrange(last_month_y, last_month_m)[1]
    last_month_end = datetime.combine(
        date(last_month_y, last_month_m, last_month_end_day),
        time.max, tzinfo=UTC,
    )
    return this_month_start, now, last_month_start, last_month_end


def _trend(this_val: float, last_val: float) -> dict:
    """算 trend up/down/flat + delta 百分比文字。"""
    if last_val == 0 and this_val == 0:
        return {"direction": "flat", "delta": "—"}
    if last_val == 0:
        return {"direction": "up", "delta": "新增"}
    pct = ((this_val - last_val) / last_val) * 100
    if abs(pct) < 1:
        return {"direction": "flat", "delta": "持平"}
    if pct > 0:
        return {"direction": "up", "delta": f"+{int(round(pct))}%"}
    return {"direction": "down", "delta": f"{int(round(pct))}%"}


@router.get("/admin/dashboard/summary")
async def dashboard_summary(
    _operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    today = datetime.now(UTC).date()
    this_start, now, last_start, last_end = _month_range(today)

    # ── 1. Orders this month / last month ────────────────────────────
    orders_this = (await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= this_start)
    )).scalar() or 0
    orders_last = (await db.execute(
        select(func.count(Order.id)).where(
            Order.created_at >= last_start, Order.created_at <= last_end,
        )
    )).scalar() or 0

    # ── 2. Revenue this month / last month（completed + partially_refunded）──
    async def _revenue(start: datetime, end: datetime) -> Decimal:
        rows = (await db.execute(
            select(Order.total, Order.refund_amount).where(
                Order.created_at >= start,
                Order.created_at <= end,
                Order.status.in_([
                    OrderStatusEnum.completed,
                    OrderStatusEnum.partially_refunded,
                ]),
            )
        )).all()
        total = Decimal("0")
        for row in rows:
            o_total = row[0] or Decimal("0")
            o_refund = row[1] or Decimal("0")
            if o_refund >= o_total:
                continue  # 完全退款 skip
            total += o_total - o_refund
        return total

    rev_this = await _revenue(this_start, now)
    rev_last = await _revenue(last_start, last_end)

    # ── 3. 待處理客製（quote_pending + negotiating）────────────────────
    custom_pending_groups = (await db.execute(
        select(CustomRequest.status, func.count(CustomRequest.id))
        .where(CustomRequest.status.in_([
            CustomRequestStatusEnum.quote_pending,
            CustomRequestStatusEnum.negotiating,
            CustomRequestStatusEnum.quote_sent,
        ]))
        .group_by(CustomRequest.status)
    )).all()
    custom_status_count = {row[0].value: row[1] for row in custom_pending_groups}
    custom_total_pending = sum(custom_status_count.values())

    # ── 4. 製作流水線 — 各 production_job status count（this month 區間）──
    pipeline_groups = (await db.execute(
        select(ProductionJob.status, func.count(ProductionJob.id))
        .where(ProductionJob.created_at >= this_start)
        .group_by(ProductionJob.status)
    )).all()
    pipeline_count = {row[0].value: row[1] for row in pipeline_groups}
    in_progress_count = (
        pipeline_count.get(JobStatusEnum.processing.value, 0)
    )

    # ── 5. 最近活動（最多 6 筆混合 orders + custom_requests）─────────────
    recent_orders = (await db.execute(
        select(Order)
        .order_by(Order.created_at.desc())
        .limit(6)
    )).scalars().all()
    recent_customs = (await db.execute(
        select(CustomRequest)
        .order_by(CustomRequest.created_at.desc())
        .limit(6)
    )).scalars().all()

    activities = []
    for o in recent_orders:
        activities.append({
            "kind": "order",
            "id": str(o.id),
            "title": o.order_number or str(o.id)[:8],
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })
    for c in recent_customs:
        activities.append({
            "kind": "custom",
            "id": str(c.id),
            "title": f"#{str(c.id)[:8]}",
            "status": c.status.value if hasattr(c.status, "value") else str(c.status),
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    activities.sort(key=lambda x: x["created_at"] or "", reverse=True)
    activities = activities[:6]

    # ── 6. 通知（未處理）─────────────────────────────────────────────
    unhandled_notifications = (await db.execute(
        select(func.count(AdminNotification.id))
        .where(AdminNotification.status == NotificationStatusEnum.unhandled)
    )).scalar() or 0

    return {
        "stats": {
            "orders_this_month": {
                "value": orders_this,
                "trend": _trend(orders_this, orders_last),
                "meta": "較上月",
            },
            "revenue_this_month": {
                "value": float(rev_this),
                "trend": _trend(float(rev_this), float(rev_last)),
                "meta": "較上月",
            },
            "custom_pending": {
                "value": custom_total_pending,
                "breakdown": {
                    "quote_pending": custom_status_count.get(
                        CustomRequestStatusEnum.quote_pending.value, 0,
                    ),
                    "negotiating": custom_status_count.get(
                        CustomRequestStatusEnum.negotiating.value, 0,
                    ),
                    "quote_sent": custom_status_count.get(
                        CustomRequestStatusEnum.quote_sent.value, 0,
                    ),
                },
            },
            "production_in_progress": {
                "value": in_progress_count,
            },
            "unhandled_notifications": {
                "value": unhandled_notifications,
            },
        },
        "production_pipeline": {
            "pending": pipeline_count.get(JobStatusEnum.pending.value, 0),
            "processing": pipeline_count.get(JobStatusEnum.processing.value, 0),
            "completed": pipeline_count.get(JobStatusEnum.completed.value, 0),
            "failed": pipeline_count.get(JobStatusEnum.failed.value, 0),
        },
        "recent_activities": activities,
    }
