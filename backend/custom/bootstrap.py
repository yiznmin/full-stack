"""Idempotent canvas_sizes seed — 啟動時補種子，避免某些環境 alembic bulk_insert 沒生效。

設計：
- ON CONFLICT DO NOTHING — 永不覆蓋既有資料（admin 後台改的不會被洗）
- 只塞 17 個 pricing_formula.md 標準尺寸
- failure 不阻擋啟動（log 警告即可，prod alembic seed 仍是主要途徑）
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

CANVAS_SIZE_SEEDS = [
    (20, 20, "20×20 cm", 1),
    (30, 30, "30×30 cm", 2),
    (30, 40, "30×40 cm", 3),
    (40, 30, "40×30 cm", 4),
    (30, 50, "30×50 cm", 5),
    (40, 40, "40×40 cm", 6),
    (50, 30, "50×30 cm", 7),
    (30, 60, "30×60 cm", 8),
    (40, 50, "40×50 cm", 9),
    (50, 40, "50×40 cm", 10),
    (40, 60, "40×60 cm", 11),
    (60, 40, "60×40 cm", 12),
    (50, 50, "50×50 cm", 13),
    (50, 60, "50×60 cm", 14),
    (60, 50, "60×50 cm", 15),
    (60, 60, "60×60 cm", 16),
    (70, 50, "70×50 cm", 17),
]


async def ensure_canvas_sizes(engine: AsyncEngine) -> None:
    """啟動時呼叫一次。若某些尺寸缺，補進去；既有不動。"""
    try:
        async with engine.begin() as conn:
            count_result = await conn.execute(
                text("SELECT count(*) FROM canvas_sizes WHERE is_active = true")
            )
            existing = count_result.scalar() or 0

            inserted = 0
            for w, h, name, order in CANVAS_SIZE_SEEDS:
                r = await conn.execute(
                    text(
                        "INSERT INTO canvas_sizes "
                        "(id, canvas_w_cm, canvas_h_cm, display_name, sort_order, is_active) "
                        "VALUES (:id, :w, :h, :name, :sort, true) "
                        "ON CONFLICT (canvas_w_cm, canvas_h_cm) DO NOTHING"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "w": w,
                        "h": h,
                        "name": name,
                        "sort": order,
                    },
                )
                if r.rowcount and r.rowcount > 0:
                    inserted += 1

        if inserted > 0:
            logger.info(
                f"[bootstrap] canvas_sizes seeded: existing={existing}, inserted={inserted}"
            )
    except Exception as e:
        logger.warning(f"[bootstrap] canvas_sizes seed failed (non-fatal): {e}")
