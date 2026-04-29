"""一次性：seed 270 種實體色（從 migrations/versions/seed_data/physical_colors_seed.csv）。

reset_test_db.py 用 Base.metadata.create_all（非 alembic），不會跑 seed migration。
此腳本獨立執行 — 重複跑會跳過已存在的 code。

用法：
    cd backend && venv/Scripts/python scripts/seed_physical_colors.py
"""
import asyncio
import csv
import os
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import auth.models  # noqa: F401, E402
import color.models  # noqa: F401, E402

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from color.models import PhysicalColor, PhysicalColorRgbHistory  # noqa: E402
from core.config import settings  # noqa: E402

CSV_PATH = (
    Path(__file__).parent.parent
    / "migrations" / "versions" / "seed_data" / "physical_colors_seed.csv"
)


def _load_rows():
    rows = []
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "code": r["code"].strip(),
                "name": r["name"].strip(),
                "color_family": (r.get("color_family") or "").strip() or None,
                "brand": (r.get("brand") or "").strip() or None,
                "rgb": [int(r["rgb_r"]), int(r["rgb_g"]), int(r["rgb_b"])],
                "stock_ml": Decimal(str(r["stock_ml"] or 0)),
                "is_active": str(r["is_active"]).strip().lower() == "true",
            })
    return rows


async def main():
    if not CSV_PATH.exists():
        print(f"ERROR: 找不到 CSV {CSV_PATH}")
        return
    rows = _load_rows()
    print(f"Loaded {len(rows)} rows from CSV")

    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        existing_codes = set(
            (await db.execute(select(PhysicalColor.code))).scalars().all()
        )
        added = 0
        for r in rows:
            if r["code"] in existing_codes:
                continue
            color = PhysicalColor(**r)
            db.add(color)
            await db.flush()  # 取 id 給 history
            db.add(PhysicalColorRgbHistory(
                physical_color_id=color.id,
                rgb=r["rgb"],
                changed_by_user_id=None,
                note="initial",
            ))
            added += 1
        await db.commit()

    print(f"Seeded {added} new physical colors (skipped {len(rows) - added} existing)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
