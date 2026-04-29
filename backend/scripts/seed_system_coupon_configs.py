"""一次性：seed 4 種系統 coupon_config（new_user / spend_reward / returning_loyal / manual）。

每種類型在 coupon_configs 表中只允許一筆（auto_checkout 例外可多筆）。
若該類型已存在則跳過，避免覆蓋管理員後台調過的參數。

用法：
    cd backend && venv/Scripts/python scripts/seed_system_coupon_configs.py
"""
import asyncio
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import auth.models  # noqa: F401, E402
import color.models  # noqa: F401, E402
import custom.models  # noqa: F401, E402
import orders.models  # noqa: F401, E402
import product.models  # noqa: F401, E402
import production.models  # noqa: F401, E402

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from core.config import settings  # noqa: E402
from discount.models import CouponConfig  # noqa: E402

DEFAULTS = [
    {
        "coupon_type": "new_user",
        "discount_type": "percentage",
        "discount_value": Decimal("10"),  # 10%
        "min_purchase": Decimal("300"),
        "is_active": True,
        "params": {"valid_days": 30},
    },
    {
        "coupon_type": "spend_reward",
        "discount_type": "fixed",
        "discount_value": Decimal("100"),
        "min_purchase": Decimal("500"),
        "is_active": True,
        "params": {"trigger_threshold": 1000, "valid_days": 30},
    },
    {
        "coupon_type": "returning_loyal",
        "discount_type": "percentage",
        "discount_value": Decimal("10"),  # 10%
        "min_purchase": Decimal("500"),
        "is_active": True,
        "params": {"trigger_threshold": 1000, "valid_days": 60},
    },
    {
        "coupon_type": "manual",
        "discount_type": "fixed",
        "discount_value": Decimal("50"),  # placeholder; admin 發券時可覆寫
        "min_purchase": Decimal("0"),
        "is_active": True,
        "params": {},
    },
]


async def main():
    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        existing = (await db.execute(select(CouponConfig.coupon_type))).scalars().all()
        existing_types = {str(t) for t in existing}
        added = []
        for d in DEFAULTS:
            if d["coupon_type"] in existing_types:
                continue
            db.add(CouponConfig(**d))
            added.append(d["coupon_type"])
        await db.commit()

    if added:
        print(f"Seeded {len(added)} system coupon configs: {', '.join(added)}")
    else:
        print("All 4 system coupon configs already exist — skipped.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
