"""一次性：建 4 筆 demo 訂單到本機 DB，覆蓋 admin 訂單頁所有 happy path。

用法：
    cd backend && venv/Scripts/python scripts/seed_demo_orders.py

冪等：每次跑會先清掉之前 seed 進去的 demo 訂單（order_number 以 'PL-DEMO-' 開頭），再重建。
"""
import asyncio
import os
import sys
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Import all models with FK targets used by orders / order_items
import auth.models  # noqa: F401, E402
import color.models  # noqa: F401, E402
import custom.models  # noqa: F401, E402
import discount.models  # noqa: F401, E402
import product.models  # noqa: F401, E402
import production.models  # noqa: F401, E402
from auth.models import User  # noqa: E402
from core.config import settings  # noqa: E402
from orders.models import (  # noqa: E402
    Order,
    OrderItem,
    PaymentSubmission,
    ProductionProgress,
    Shipment,
)


def _spec(detail: str, w: int, h: int, difficulty: str) -> dict:
    return {
        "detail": detail,
        "difficulty": difficulty,
        "canvas_w_cm": w,
        "canvas_h_cm": h,
    }


async def seed(db: AsyncSession, admin_user: User) -> None:
    # 清掉舊的 demo orders（含 cascade 子表會由 delete 顯式處理）
    old = (await db.execute(select(Order).where(Order.order_number.like("PL-DEMO-%")))).scalars().all()
    for o in old:
        # 子表沒設 cascade，逐一刪
        items = (await db.execute(select(OrderItem).where(OrderItem.order_id == o.id))).scalars().all()
        for it in items:
            await db.execute(delete(ProductionProgress).where(ProductionProgress.order_item_id == it.id))
        await db.execute(delete(OrderItem).where(OrderItem.order_id == o.id))
        await db.execute(delete(Shipment).where(Shipment.order_id == o.id))
        await db.execute(delete(PaymentSubmission).where(PaymentSubmission.order_id == o.id))
        await db.execute(delete(Order).where(Order.id == o.id))
    await db.commit()

    base_snapshot = {
        "recipient_name": "易木 Demo 收件",
        "phone": "0912345678",
        "notify_email": None,
        "city": "台北市",
        "district": "信義區",
        "address_detail": "信義路五段 7 號 101 樓",
    }

    now = datetime.now(UTC)

    # ── Order 1：pending_payment（含已 submit 但未 flag 的付款核對）───────────────
    o1 = Order(
        order_number="PL-DEMO-000001",
        user_id=admin_user.id,
        status="pending_payment",
        subtotal=Decimal("1500"),
        discount_amount=Decimal("100"),
        discount_source="coupon",
        shipping_fee=Decimal("0"),
        total=Decimal("1400"),
        shipping_type="home",
        shipping_preference="together",
        shipping_snapshot=base_snapshot,
        payment_deadline=now + timedelta(hours=22),
        customer_notes="希望盡快出貨",
    )
    db.add(o1)
    await db.flush()

    db.add(OrderItem(
        order_id=o1.id,
        product_title_snapshot="京都楓葉 Kyoto Maple",
        variant_spec_snapshot=_spec("細緻", 30, 40, "中級"),
        unit_price=Decimal("980"),
        quantity=1,
        fulfilled_qty=1,
        preorder_qty=0,
    ))
    db.add(OrderItem(
        order_id=o1.id,
        product_title_snapshot="嵐山雪景 Arashiyama Snow",
        variant_spec_snapshot=_spec("標準", 40, 50, "進階"),
        unit_price=Decimal("520"),
        quantity=1,
        fulfilled_qty=0,
        preorder_qty=1,
    ))
    db.add(PaymentSubmission(
        order_id=o1.id,
        transfer_amount=Decimal("1400"),
        transfer_date=date.today(),
        transfer_time=time(14, 30),
        account_last5="01234",
        is_flagged=False,
        notes="已用網銀轉帳",
    ))

    # ── Order 2：paid（可測「開始備貨」、「出貨」、「標記退款處理中」）─────────────
    o2 = Order(
        order_number="PL-DEMO-000002",
        user_id=admin_user.id,
        status="paid",
        subtotal=Decimal("2400"),
        discount_amount=Decimal("0"),
        shipping_fee=Decimal("70"),
        total=Decimal("2470"),
        shipping_type="seven_eleven",
        shipping_preference="together",
        shipping_snapshot={
            **base_snapshot,
            "store_id": "123456",
            "store_name": "信義 7-11 永吉店",
            "address_detail": None,
        },
        paid_at=now - timedelta(hours=3),
    )
    db.add(o2)
    await db.flush()

    item_a = OrderItem(
        order_id=o2.id,
        product_title_snapshot="貓咪日常 Cat Diary",
        variant_spec_snapshot=_spec("細緻", 30, 30, "入門"),
        unit_price=Decimal("680"),
        quantity=2,
        fulfilled_qty=2,
        preorder_qty=0,
    )
    item_b = OrderItem(
        order_id=o2.id,
        product_title_snapshot="海岸線 Coastline",
        variant_spec_snapshot=_spec("標準", 50, 70, "進階"),
        unit_price=Decimal("1040"),
        quantity=1,
        fulfilled_qty=1,
        preorder_qty=0,
    )
    db.add_all([item_a, item_b])
    await db.flush()
    db.add_all([
        ProductionProgress(order_item_id=item_a.id, status="manufacturing"),
        ProductionProgress(order_item_id=item_b.id, status="pending"),
    ])

    # ── Order 3：refund_processing（可測「完成退款」）──────────────────────────────
    o3 = Order(
        order_number="PL-DEMO-000003",
        user_id=admin_user.id,
        status="refund_processing",
        subtotal=Decimal("3200"),
        discount_amount=Decimal("0"),
        shipping_fee=Decimal("120"),
        total=Decimal("3320"),
        shipping_type="home",
        shipping_preference="together",
        shipping_snapshot=base_snapshot,
        paid_at=now - timedelta(days=2),
        admin_notes="[退款原因] 客戶反映商品有瑕疵",
    )
    db.add(o3)
    await db.flush()

    item_c = OrderItem(
        order_id=o3.id,
        product_title_snapshot="富士山櫻 Mount Fuji Sakura",
        variant_spec_snapshot=_spec("高級", 60, 80, "進階"),
        unit_price=Decimal("3200"),
        quantity=1,
        fulfilled_qty=1,
        preorder_qty=0,
    )
    db.add(item_c)
    await db.flush()
    db.add(ProductionProgress(order_item_id=item_c.id, status="shipped"))
    db.add(Shipment(
        order_id=o3.id,
        shipment_type="fulfilled",
        status="delivered",
        tracking_number="ECPAY-DEMO-887766",
        shipped_at=now - timedelta(days=1, hours=20),
        delivered_at=now - timedelta(days=1),
    ))

    # ── Order 4：completed（read-only 顯示）────────────────────────────────────────
    o4 = Order(
        order_number="PL-DEMO-000004",
        user_id=admin_user.id,
        status="completed",
        subtotal=Decimal("980"),
        discount_amount=Decimal("0"),
        shipping_fee=Decimal("0"),
        total=Decimal("980"),
        shipping_type="family_mart",
        shipping_preference="together",
        shipping_snapshot={
            **base_snapshot,
            "store_id": "654321",
            "store_name": "信義 全家 松德店",
            "address_detail": None,
        },
        paid_at=now - timedelta(days=10),
        completed_at=now - timedelta(days=2),
    )
    db.add(o4)
    await db.flush()

    item_d = OrderItem(
        order_id=o4.id,
        product_title_snapshot="北極熊 Polar Bear",
        variant_spec_snapshot=_spec("細緻", 40, 40, "入門"),
        unit_price=Decimal("980"),
        quantity=1,
        fulfilled_qty=1,
        preorder_qty=0,
    )
    db.add(item_d)
    await db.flush()
    db.add(ProductionProgress(order_item_id=item_d.id, status="shipped"))
    db.add(Shipment(
        order_id=o4.id,
        shipment_type="fulfilled",
        status="delivered",
        tracking_number="ECPAY-DEMO-554433",
        shipped_at=now - timedelta(days=4),
        delivered_at=now - timedelta(days=2),
    ))

    await db.commit()
    print("Seeded 4 demo orders:")
    print("  PL-DEMO-000001  pending_payment")
    print("  PL-DEMO-000002  paid")
    print("  PL-DEMO-000003  refund_processing")
    print("  PL-DEMO-000004  completed")


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        u = (await db.execute(select(User).where(User.role == "admin"))).scalar_one_or_none()
        if not u:
            print("ERROR: 找不到 admin user，請先跑 scripts/create_admin.py")
            return
        await seed(db, u)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
