"""一次性：建 demo 客製申請到本機 DB，覆蓋 admin 客製訂單頁所有 happy path。

用法：
    cd backend && venv/Scripts/python scripts/seed_demo_custom_requests.py

冪等：先清掉之前 seed 進去的 demo（admin_notes 以 '[DEMO]' 開頭），再重建。
"""
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import auth.models  # noqa: F401, E402
import color.models  # noqa: F401, E402
import discount.models  # noqa: F401, E402
import orders.models  # noqa: F401, E402
import product.models  # noqa: F401, E402
import production.models  # noqa: F401, E402

from sqlalchemy import delete, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from auth.models import User  # noqa: E402
from core.config import settings  # noqa: E402
from custom.models import (  # noqa: E402
    CustomPhotoPrice,
    CustomPhotoSurcharge,
    CustomRequest,
    CustomRequestMessage,
)


async def seed_prices(db: AsyncSession) -> None:
    """確保 custom_photo_prices 與 surcharges 有種子資料供報價試算。"""
    existing_prices = (await db.execute(select(CustomPhotoPrice).limit(1))).scalar_one_or_none()
    if existing_prices is None:
        # 種幾個常用尺寸
        for (w, h) in [(20, 20), (30, 30), (30, 40), (40, 50), (50, 70), (60, 60)]:
            for diff, base in [
                ("beginner", 480),
                ("elementary", 580),
                ("intermediate", 680),
                ("advanced", 880),
            ]:
                # 大尺寸略加錢
                if w * h > 1500:
                    base += 200
                db.add(CustomPhotoPrice(
                    canvas_w=w, canvas_h=h, difficulty=diff, price=Decimal(str(base)),
                ))

    existing_surcharges = (await db.execute(select(CustomPhotoSurcharge).limit(1))).scalar_one_or_none()
    if existing_surcharges is None:
        for cat, label, amount in [
            ("人物數量", "2 人", 200),
            ("人物數量", "3 人", 400),
            ("背景複雜度", "細節豐富", 300),
            ("毛髮 / 質感", "寵物毛髮細節", 250),
            ("特殊處理", "限時加急", 500),
        ]:
            db.add(CustomPhotoSurcharge(
                category=cat, label=label, amount=Decimal(str(amount)), is_active=True,
            ))

    await db.commit()


async def seed_requests(db: AsyncSession, admin_user: User) -> None:
    # 清掉舊 demo
    olds = (
        await db.execute(
            select(CustomRequest).where(CustomRequest.admin_notes.like("[DEMO]%"))
        )
    ).scalars().all()
    for r in olds:
        await db.execute(delete(CustomRequestMessage).where(CustomRequestMessage.request_id == r.id))
        await db.execute(delete(CustomRequest).where(CustomRequest.id == r.id))
    await db.commit()

    now = datetime.now(UTC)

    # ── Demo 1：quote_pending（剛申請）───────────────────────────────────
    r1 = CustomRequest(
        user_id=admin_user.id,
        request_type="custom_photo",
        status="quote_pending",
        photo_url="https://firebasestorage.googleapis.com/v0/b/paint-by-number-d9fa3.firebasestorage.app/o/demo%2Fpending.jpg?alt=media",
        canvas_w_cm=30,
        canvas_h_cm=40,
        difficulty="intermediate",
        detail="standard",
        customer_notes="想把家裡貓咪做成畫，希望保留毛色細節。希望 30×40 中等難度。",
        admin_notes="[DEMO] 等待管理員開始評估",
    )
    db.add(r1)
    await db.flush()
    db.add(CustomRequestMessage(
        request_id=r1.id,
        sender_type="admin",
        message="您好，您的客製申請已收到，我們會在 3 個工作天內回覆報價。",
    ))

    # ── Demo 2：negotiating（已帶入製作系統）────────────────────────────
    r2 = CustomRequest(
        user_id=admin_user.id,
        request_type="custom_photo",
        status="negotiating",
        photo_url="https://firebasestorage.googleapis.com/v0/b/paint-by-number-d9fa3.firebasestorage.app/o/demo%2Fnego.jpg?alt=media",
        canvas_w_cm=40,
        canvas_h_cm=50,
        difficulty="advanced",
        detail="detailed",
        customer_notes="女兒生日禮物，希望寫真品質，預算可以拉高。",
        admin_notes="[DEMO] production_job 跑中",
    )
    db.add(r2)
    await db.flush()
    db.add_all([
        CustomRequestMessage(
            request_id=r2.id,
            sender_type="admin",
            message="您好，您的客製申請已收到，我們會在 3 個工作天內回覆報價。",
            created_at=now - timedelta(hours=8),
        ),
        CustomRequestMessage(
            request_id=r2.id,
            sender_type="customer",
            message="如果可以希望畫面以人物為主，背景可以簡化一些。",
            created_at=now - timedelta(hours=6),
        ),
        CustomRequestMessage(
            request_id=r2.id,
            sender_type="admin",
            message="收到！我這邊試做幾個版本給您挑，預計明天送出報價＋初稿。",
            created_at=now - timedelta(hours=5),
        ),
    ])

    # ── Demo 3：quote_sent（已送報價，等客戶確認）───────────────────────
    r3 = CustomRequest(
        user_id=admin_user.id,
        request_type="custom_photo",
        status="quote_sent",
        photo_url="https://firebasestorage.googleapis.com/v0/b/paint-by-number-d9fa3.firebasestorage.app/o/demo%2Fsent.jpg?alt=media",
        canvas_w_cm=50,
        canvas_h_cm=70,
        difficulty="advanced",
        detail="premium",
        customer_notes="希望畫質精細，會做為客廳主視覺。",
        admin_notes="[DEMO] 等客戶於 /custom/quote/:token 確認",
        quoted_price=Decimal("3800"),
        quoted_at=now - timedelta(hours=2),
        quote_expires_at=now + timedelta(hours=22),
        quote_token="demo-token-xyz",
    )
    db.add(r3)
    await db.flush()
    db.add_all([
        CustomRequestMessage(
            request_id=r3.id,
            sender_type="admin",
            message="您好，您的客製申請已收到，我們會在 3 個工作天內回覆報價。",
            created_at=now - timedelta(days=1),
        ),
        CustomRequestMessage(
            request_id=r3.id,
            sender_type="admin",
            message="報價：NT$3,800 元 | 細緻度：premium | 含寵物毛髮細節加費，附上初稿預覽供確認，連結請見 email。",
            created_at=now - timedelta(hours=2),
        ),
    ])

    # ── Demo 4：draft_revision（客戶要求修改）──────────────────────────
    r4 = CustomRequest(
        user_id=admin_user.id,
        request_type="custom_photo",
        status="draft_revision",
        photo_url="https://firebasestorage.googleapis.com/v0/b/paint-by-number-d9fa3.firebasestorage.app/o/demo%2Frev.jpg?alt=media",
        canvas_w_cm=30,
        canvas_h_cm=40,
        difficulty="intermediate",
        detail="standard",
        customer_notes="原本要求拍夫妻合影，希望可以再簡化背景。",
        admin_notes="[DEMO] 客戶第 1 次要求修改",
        quoted_price=Decimal("1800"),
        quoted_at=now - timedelta(hours=12),
        quote_expires_at=now + timedelta(hours=12),
        quote_token="demo-token-abc",
        revision_count=1,
    )
    db.add(r4)
    await db.flush()
    db.add_all([
        CustomRequestMessage(
            request_id=r4.id,
            sender_type="admin",
            message="您好，您的客製申請已收到。",
            created_at=now - timedelta(days=2),
        ),
        CustomRequestMessage(
            request_id=r4.id,
            sender_type="admin",
            message="報價：NT$1,800 元 | 細緻度：standard",
            created_at=now - timedelta(hours=12),
        ),
        CustomRequestMessage(
            request_id=r4.id,
            sender_type="customer",
            message="背景太雜了，可以簡化一些嗎？人物的部分維持不變就好。",
            created_at=now - timedelta(hours=2),
        ),
    ])

    await db.commit()
    print("Seeded 4 demo custom requests:")
    print("  quote_pending      (剛申請)")
    print("  negotiating        (已帶入製作系統)")
    print("  quote_sent         (已送報價)")
    print("  draft_revision     (客戶要求修改)")


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        u = (await db.execute(select(User).where(User.role == "admin"))).scalar_one_or_none()
        if not u:
            print("ERROR: 找不到 admin user，請先跑 scripts/create_admin.py")
            return
        await seed_prices(db)
        await seed_requests(db, u)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
