from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orders.models import Order, OrderStatusEnum


async def sales_summary(
    db: AsyncSession, date_from: date | None, date_to: date | None
) -> dict:
    # Include completed (full) + partially_refunded (revenue = total - refund_amount).
    query = select(Order).where(
        Order.status.in_([OrderStatusEnum.completed, OrderStatusEnum.partially_refunded])
    )
    if date_from:
        query = query.where(
            Order.created_at >= datetime.combine(date_from, time.min, tzinfo=UTC)
        )
    if date_to:
        query = query.where(
            Order.created_at <= datetime.combine(date_to, time.max, tzinfo=UTC)
        )

    rows = (await db.execute(query)).scalars().all()

    total_orders = 0
    total_revenue = Decimal("0")
    for o in rows:
        # Skip fully refunded orders
        if o.refund_amount is not None and o.refund_amount >= o.total:
            continue
        total_orders += 1
        net = o.total
        if o.refund_amount is not None:
            net = o.total - o.refund_amount
        total_revenue += net

    return {
        "period": {
            "from": date_from.isoformat() if date_from else None,
            "to": date_to.isoformat() if date_to else None,
        },
        "total_orders": total_orders,
        "total_revenue": float(total_revenue),
        "note": (
            "僅計算 status=completed/partially_refunded 且未完全退款的訂單；"
            "部分退款以 total - refund_amount 計入"
        ),
    }
