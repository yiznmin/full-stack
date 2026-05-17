"""首次部署用：用 Base.metadata.create_all 建 schema + alembic stamp head 記錄版本。

背景：alembic migrations 缺 `production_jobs` 表的 create_table（疑似遺漏），
但 ORM models 完整。本地 dev/test 都靠 create_all 建 schema，alembic 從未驗證過 from-scratch。
從乾淨 DB 跑 alembic upgrade head 會在 product_variants FK reference production_jobs 處炸掉。

短期解（本檔案）：
  1. import 所有 models 註冊 metadata
  2. Base.metadata.create_all → 一次建好所有 ORM-defined tables（idempotent，已存在不重建）
  3. alembic stamp head → 把 alembic_version 推到最新，未來增量 migration 才能正常
"""
from __future__ import annotations

import asyncio
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# 註冊所有 ORM models 的 metadata
import auth.models  # noqa: F401
import color.models  # noqa: F401
import content.models  # noqa: F401
import custom.models  # noqa: F401
import discount.models  # noqa: F401
import notifications.models  # noqa: F401
import orders.models  # noqa: F401
import palette.models  # noqa: F401
import print_batch.models  # noqa: F401
import product.models  # noqa: F401
import production.models  # noqa: F401
import users.models  # noqa: F401
from core.config import settings
from core.database import Base


async def init_schema() -> None:
    print("[init_db] connecting to DB ...", flush=True)
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            print("[init_db] running Base.metadata.create_all (idempotent) ...", flush=True)
            await conn.run_sync(Base.metadata.create_all)

            # PostgreSQL sequences 不在 ORM Base.metadata 裡，create_all 不會建。
            # 對應 alembic migration c3d4e5f6a7b8_create_order_tables；alembic stamp head
            # 不執行 migration body 所以這裡要主動補。idempotent.
            print("[init_db] ensuring sequences (order_number_seq) ...", flush=True)
            await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS order_number_seq START 1"))

            # 新增 column：create_all 不會在已存在的 table 加新欄位，
            # 需要顯式 ALTER TABLE。 IF NOT EXISTS 確保 idempotent。
            print("[init_db] ensuring incremental columns ...", flush=True)
            await conn.execute(text(
                "ALTER TABLE orders "
                "ADD COLUMN IF NOT EXISTS shipping_locked BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            await conn.execute(text(
                "ALTER TABLE shipments "
                "ADD COLUMN IF NOT EXISTS cvs_payment_no VARCHAR"
            ))
            await conn.execute(text(
                "ALTER TABLE shipments "
                "ADD COLUMN IF NOT EXISTS cvs_validation_no VARCHAR"
            ))
            # Day 3 webhook 追蹤欄位
            await conn.execute(text(
                "ALTER TABLE shipments "
                "ADD COLUMN IF NOT EXISTS last_rtn_code INTEGER"
            ))
            await conn.execute(text(
                "ALTER TABLE shipments "
                "ADD COLUMN IF NOT EXISTS last_rtn_msg VARCHAR"
            ))
            await conn.execute(text(
                "ALTER TABLE shipments "
                "ADD COLUMN IF NOT EXISTS last_status_at TIMESTAMP WITH TIME ZONE"
            ))
            # admin 在 QuoteDialog 選定的 production_job — 報價綁這個 job 的 filled_template
            # （preview / 規格都從該 job 拿，不再用「最新一筆 filled」的猜測）
            await conn.execute(text(
                "ALTER TABLE custom_requests "
                "ADD COLUMN IF NOT EXISTS quoted_production_job_id UUID "
                "REFERENCES production_jobs(id) ON DELETE SET NULL"
            ))
            # cart_items 支援客製 line：客戶 confirm quote 後加進 cart 跟一般商品合買
            # product_variant_id 改 nullable（custom_request_id 有值時 variant 為 null）
            await conn.execute(text(
                "ALTER TABLE cart_items ALTER COLUMN product_variant_id DROP NOT NULL"
            ))
            await conn.execute(text(
                "ALTER TABLE cart_items "
                "ADD COLUMN IF NOT EXISTS custom_request_id UUID "
                "REFERENCES custom_requests(id) ON DELETE CASCADE"
            ))
            await conn.execute(text(
                "ALTER TABLE cart_items "
                "ADD COLUMN IF NOT EXISTS production_job_id UUID "
                "REFERENCES production_jobs(id) ON DELETE SET NULL"
            ))
            # 客戶是否同意作品於 IG / 網站作品案例展示（spec 第九頁智財權條款）
            # 對應 migration p6k7l8m9n0o1_custom_request_display_consent
            await conn.execute(text(
                "ALTER TABLE custom_requests "
                "ADD COLUMN IF NOT EXISTS display_consent BOOLEAN NOT NULL DEFAULT FALSE"
            ))
            # 系列封面圖 — admin 上傳，給 SeriesDetailPage hero 用
            # 對應 migration q7l8m9n0o1p2_series_sample_cover
            await conn.execute(text(
                "ALTER TABLE product_series "
                "ADD COLUMN IF NOT EXISTS sample_cover_image_url VARCHAR"
            ))
            # 對應完成（finalize）後產出實體色版最終模板
            # 對應 migration r8m9n0o1p2q3_finalize_template_columns
            await conn.execute(text(
                "ALTER TABLE production_jobs "
                "ADD COLUMN IF NOT EXISTS template_final_url VARCHAR"
            ))
            await conn.execute(text(
                "ALTER TABLE production_jobs "
                "ADD COLUMN IF NOT EXISTS palette_final_url VARCHAR"
            ))
            await conn.execute(text(
                "ALTER TABLE production_jobs "
                "ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP WITH TIME ZONE"
            ))
            await conn.execute(text(
                "ALTER TABLE palette_color_mappings "
                "ADD COLUMN IF NOT EXISTS output_label INTEGER"
            ))
            # 實體色版 filled preview（finalize 後產出，給 admin 看真實塗色後效果）
            await conn.execute(text(
                "ALTER TABLE production_jobs "
                "ADD COLUMN IF NOT EXISTS filled_template_final_url VARCHAR"
            ))

            # Backfill：已有 shipment 的訂單視為「已確認出貨資訊」（之前無此欄位的歷史訂單）
            print("[init_db] backfilling shipping_locked for shipped orders ...", flush=True)
            await conn.execute(text(
                "UPDATE orders SET shipping_locked = TRUE "
                "WHERE shipping_locked = FALSE "
                "AND id IN (SELECT DISTINCT order_id FROM shipments)"
            ))
        print("[init_db] schema created/verified", flush=True)
    finally:
        await engine.dispose()


def stamp_alembic_head() -> None:
    print("[init_db] alembic stamp head ...", flush=True)
    result = subprocess.run(
        ["alembic", "stamp", "head"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        print(f"[init_db] alembic stamp warning (non-fatal): {result.stderr}", flush=True)
    else:
        print("[init_db] alembic stamped to head", flush=True)


def main() -> None:
    asyncio.run(init_schema())
    stamp_alembic_head()
    print("[init_db] DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
