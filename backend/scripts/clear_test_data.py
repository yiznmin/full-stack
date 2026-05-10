"""Clear all orders / cart_items / custom_requests for fresh start (測試資料清除).

USAGE:
    cd backend
    venv/Scripts/python scripts/clear_test_data.py            # dry-run（預覽）
    venv/Scripts/python scripts/clear_test_data.py --confirm  # 實際執行

DELETE 順序（避免 FK constraint 衝突）：
    1. 還原 physical_colors.stock_ml（補回 order_items 扣掉的 ml）
    2. 釋放 user_coupons.is_used = FALSE WHERE used_in_order_id IN (...)
    3. DELETE notifications WHERE reference_type IN ('order', 'custom_request')
    4. DELETE custom_request_messages
    5. DELETE custom_requests
    6. DELETE shipments / payment_submissions / production_progress
    7. DELETE order_items
    8. DELETE cart_items
    9. DELETE orders

不動的東西：
    users / products / variants / themes / series / tags / physical_colors（只還原 stock）
    coupon_configs / promo_codes / canvas_sizes / photo_prices / system_settings
    production_jobs（原圖製作紀錄獨立於訂單）

Production deploy：
    Railway → backend service → 右上 ⋯ → "Open Shell" →
    `python scripts/clear_test_data.py --confirm`
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from core.config import settings  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="實際執行（否則只 dry-run）")
    args = parser.parse_args()

    print(f"[clear] DB: {settings.database_url.split('@')[-1]}")
    engine = create_async_engine(settings.database_url, echo=False)

    try:
        async with engine.begin() as conn:
            # ── Phase 0: 預覽 ────────────────────────────────────────
            counts = {}
            for tbl in (
                "orders", "order_items", "cart_items",
                "custom_requests", "custom_request_messages",
                "payment_submissions", "shipments", "production_progress",
                "notifications",
            ):
                r = await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                counts[tbl] = r.scalar() or 0

            # 額外算 order_items 累計扣掉的 stock_ml（用於還原預覽）
            r = await conn.execute(text("""
                SELECT COUNT(*), COALESCE(SUM(fulfilled_qty), 0)
                FROM order_items
                WHERE production_job_id IS NOT NULL AND fulfilled_qty > 0
            """))
            row = r.one()
            order_items_with_stock = row[0]
            total_fulfilled_units = row[1]

            r = await conn.execute(text("""
                SELECT COUNT(*) FROM user_coupons
                WHERE used_in_order_id IS NOT NULL AND is_used = TRUE
            """))
            coupons_to_release = r.scalar() or 0

            print("")
            print("【將清除的資料】")
            for tbl, n in counts.items():
                print(f"  {tbl:30s} {n:>6} rows")
            print("")
            print("【附帶處理】")
            print(f"  user_coupons 釋放（is_used=false）{coupons_to_release} 筆")
            print(f"  physical_colors.stock_ml 補回 {order_items_with_stock} 個 order_item × 對應 mapping")
            print(f"  累計補回 stock 對應 order_item 件數: {total_fulfilled_units}")

            if not args.confirm:
                print("")
                print("[DRY RUN] 沒實際執行。加 --confirm 才會清除。")
                return

            # ── Phase 1: 還原 physical_colors.stock_ml ────────────────
            print("")
            print("[1/9] 還原 physical_colors.stock_ml ...")
            await conn.execute(text("""
                WITH refunds AS (
                    SELECT
                        pcm.physical_color_id AS color_id,
                        SUM(pcm.required_ml * oi.fulfilled_qty) AS ml_to_restore
                    FROM order_items oi
                    JOIN palette_color_mappings pcm
                      ON pcm.production_job_id = oi.production_job_id
                    WHERE oi.production_job_id IS NOT NULL
                      AND oi.fulfilled_qty > 0
                      AND pcm.required_ml IS NOT NULL
                    GROUP BY pcm.physical_color_id
                )
                UPDATE physical_colors pc
                SET stock_ml = pc.stock_ml + r.ml_to_restore
                FROM refunds r
                WHERE pc.id = r.color_id
            """))

            # ── Phase 2: 釋放 user_coupons ─────────────────────────────
            print("[2/9] 釋放 user_coupons ...")
            await conn.execute(text("""
                UPDATE user_coupons
                SET is_used = FALSE, used_at = NULL, used_in_order_id = NULL
                WHERE used_in_order_id IS NOT NULL
            """))

            # ── Phase 3: 清 notifications（只 order / custom_request 相關）──
            print("[3/9] 刪除 orders / customs 的 notifications ...")
            await conn.execute(text("""
                DELETE FROM notifications
                WHERE reference_type IN ('order', 'custom_request')
            """))

            # ── Phase 4: 清 custom_request_messages ─────────────────
            print("[4/9] 刪除 custom_request_messages ...")
            await conn.execute(text("DELETE FROM custom_request_messages"))

            # ── Phase 5: 清 custom_requests（含解開 production_jobs FK）──
            print("[5/9] 刪除 custom_requests ...")
            # production_jobs.custom_request_id 反向 FK，先 set null
            await conn.execute(text(
                "UPDATE production_jobs SET custom_request_id = NULL "
                "WHERE custom_request_id IS NOT NULL"
            ))
            await conn.execute(text("DELETE FROM custom_requests"))

            # ── Phase 6: 訂單 children（CASCADE 應該也會處理但顯式刪確保）──
            print("[6/9] 刪除 shipments / payment_submissions / production_progress ...")
            await conn.execute(text("DELETE FROM shipments"))
            await conn.execute(text("DELETE FROM payment_submissions"))
            await conn.execute(text("DELETE FROM production_progress"))

            # ── Phase 7: order_items ───────────────────────────────────
            print("[7/9] 刪除 order_items ...")
            await conn.execute(text("DELETE FROM order_items"))

            # ── Phase 8: cart_items ────────────────────────────────────
            print("[8/9] 刪除 cart_items ...")
            await conn.execute(text("DELETE FROM cart_items"))

            # ── Phase 9: orders ────────────────────────────────────────
            print("[9/9] 刪除 orders ...")
            await conn.execute(text("DELETE FROM orders"))

            print("")
            print("✅ 完成")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
