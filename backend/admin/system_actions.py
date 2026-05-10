"""Admin 系統層級的危險動作（destructive）。

目前提供：
- clear_test_data: 清除所有 orders / cart_items / custom_requests 資料，
  還原 stock + 釋放 coupons。給 admin 設定頁的「Danger Zone」按鈕用。

設計：
- 共用底層 logic 給 scripts/clear_test_data.py 與 admin endpoint 使用
- 必須帶 confirm_phrase = "CLEAR-ALL-TEST-DATA" 才執行
- 回傳被刪除的 row count summary

⚠️ 安全：endpoint 只接受 admin auth + confirm phrase 雙重驗證。
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession


CONFIRM_PHRASE = "CLEAR-ALL-TEST-DATA"


async def preview_clear_test_data(db: AsyncSession) -> dict:
    """回傳將被清除的資料 count（不實際刪除）。"""
    counts: dict[str, int] = {}
    for tbl in (
        "orders", "order_items", "cart_items",
        "custom_requests", "custom_request_messages",
        "payment_submissions", "shipments", "production_progress",
    ):
        r = await db.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
        counts[tbl] = r.scalar() or 0

    # 通知只算 order/custom 相關的
    r = await db.execute(text(
        "SELECT COUNT(*) FROM admin_notifications "
        "WHERE reference_type IN ('order', 'custom_request')"
    ))
    counts["notifications_to_clear"] = r.scalar() or 0

    r = await db.execute(text(
        "SELECT COUNT(*) FROM user_coupons "
        "WHERE used_in_order_id IS NOT NULL AND is_used = TRUE"
    ))
    coupons_to_release = r.scalar() or 0

    r = await db.execute(text(
        "SELECT COUNT(*) FROM order_items "
        "WHERE production_job_id IS NOT NULL AND fulfilled_qty > 0"
    ))
    order_items_to_restore = r.scalar() or 0

    return {
        "counts": counts,
        "coupons_to_release": coupons_to_release,
        "order_items_to_restore_stock": order_items_to_restore,
    }


async def execute_clear_test_data(
    db_or_engine: AsyncSession | AsyncEngine,
) -> dict:
    """實際清除測試資料。回傳 deleted summary。

    使用 engine.begin() 包成一個 transaction 確保 atomicity；
    ORM session 也接受（呼叫端 commit / rollback）。
    """
    # 統一抽 connection — engine 給 begin()，session 直接 execute
    if hasattr(db_or_engine, "begin"):
        # AsyncEngine
        async with db_or_engine.begin() as conn:
            return await _do_clear(conn)
    else:
        # AsyncSession — 已在 transaction 中
        result = await _do_clear(db_or_engine)
        await db_or_engine.commit()
        return result


async def _do_clear(conn) -> dict:
    """9 階段清除流程。"""
    summary: dict[str, int] = {}

    # 1. 還原 physical_colors.stock_ml
    r = await conn.execute(text("""
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
    summary["stock_restored_colors"] = r.rowcount or 0

    # 2. 釋放 user_coupons
    r = await conn.execute(text("""
        UPDATE user_coupons
        SET is_used = FALSE, used_at = NULL, used_in_order_id = NULL
        WHERE used_in_order_id IS NOT NULL
    """))
    summary["coupons_released"] = r.rowcount or 0

    # 3. 清 order/custom 相關 notifications
    r = await conn.execute(text("""
        DELETE FROM admin_notifications
        WHERE reference_type IN ('order', 'custom_request')
    """))
    summary["notifications_deleted"] = r.rowcount or 0

    # 4. custom_request_messages
    r = await conn.execute(text("DELETE FROM custom_request_messages"))
    summary["custom_messages_deleted"] = r.rowcount or 0

    # 5. custom_requests（先解 production_jobs 反向 FK）
    await conn.execute(text(
        "UPDATE production_jobs SET custom_request_id = NULL "
        "WHERE custom_request_id IS NOT NULL"
    ))
    r = await conn.execute(text("DELETE FROM custom_requests"))
    summary["custom_requests_deleted"] = r.rowcount or 0

    # 6. 訂單 children
    r = await conn.execute(text("DELETE FROM shipments"))
    summary["shipments_deleted"] = r.rowcount or 0
    r = await conn.execute(text("DELETE FROM payment_submissions"))
    summary["payment_submissions_deleted"] = r.rowcount or 0
    r = await conn.execute(text("DELETE FROM production_progress"))
    summary["production_progress_deleted"] = r.rowcount or 0

    # 7. order_items
    r = await conn.execute(text("DELETE FROM order_items"))
    summary["order_items_deleted"] = r.rowcount or 0

    # 8. cart_items
    r = await conn.execute(text("DELETE FROM cart_items"))
    summary["cart_items_deleted"] = r.rowcount or 0

    # 9. orders
    r = await conn.execute(text("DELETE FROM orders"))
    summary["orders_deleted"] = r.rowcount or 0

    return summary
