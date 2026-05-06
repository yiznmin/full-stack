"""把幾個測試商品塞進 DB 讓 store cart 流程可以走。

跳過 PBN 引擎，直接 INSERT production_jobs + products + variants 用 dummy URLs。
僅用於開發測試 — 不適合給真實顧客看到的商品。

執行方式（從 Railway CLI，避免本機暴露 DB URL）：
    railway run python scripts/seed_test_products.py

或本機（需設 DATABASE_URL）：
    DATABASE_URL=postgresql+asyncpg://... python scripts/seed_test_products.py

idempotent：同名商品已存在則跳過。
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# 觸發 SQLAlchemy 載入所有 models（避免 FK 找不到）
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
from product.models import Product, ProductSeries, ProductVariant
from production.models import (
    DetailEnum,
    DifficultyEnum,
    JobStatusEnum,
    ModeEnum,
    ProductionJob,
)


# 既有的 series ids（從 store/docs/dev_db_operations.md）
SERIES_KYOTO = UUID("6d3a0dc1-6083-4187-b1ee-7ab640d80a58")  # 京都四季 / 風景
SERIES_HAIAN = UUID("9605b792-a7d9-445e-88d5-34ca6ac36358")  # 海岸印象 / 風景
SERIES_LANGCHIN = UUID("38ff8d67-5bba-43fa-a493-03ae9de46fca")  # 浪犬與牠 / 萌寵
SERIES_YINSI = UUID("03feca0f-6604-4571-b69f-122550107bca")  # 印象派經典 / 藝術畫


PLACEHOLDER_COVER = "https://images.unsplash.com/photo-1580136608043-3a4abe35d013?w=800&q=70"

# 4 個測試商品 — 每個一個 production_job、一個 product、2 個 variants（30x40 入門 / 40x50 中級）
PRODUCTS_TO_SEED = [
    {
        "title": "京都嵐山的秋",
        "description": "京都四季中最詩意的時節 — 紅葉、楓林、嵐山的山嵐。",
        "series_id": SERIES_KYOTO,
        "series_order": 1,
        "is_featured": True,
        "cover_image_url": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=800&q=70",
        "variants": [
            {"w": 30, "h": 40, "difficulty": "beginner", "detail": "standard", "price": 397},
            {"w": 40, "h": 50, "difficulty": "intermediate", "detail": "standard", "price": 580},
        ],
    },
    {
        "title": "藍色海岸的午後",
        "description": "希臘式海岸線的純白屋簷與愛琴海藍。",
        "series_id": SERIES_HAIAN,
        "series_order": 1,
        "is_featured": False,
        "cover_image_url": "https://images.unsplash.com/photo-1516483638261-f4dbaf036963?w=800&q=70",
        "variants": [
            {"w": 30, "h": 40, "difficulty": "elementary", "detail": "standard", "price": 460},
            {"w": 50, "h": 60, "difficulty": "intermediate", "detail": "detailed", "price": 780},
        ],
    },
    {
        "title": "毛孩的午睡",
        "description": "貓在窗台、狗在地毯 — 平靜的家居午後。",
        "series_id": SERIES_LANGCHIN,
        "series_order": 1,
        "is_featured": True,
        "cover_image_url": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=800&q=70",
        "variants": [
            {"w": 30, "h": 30, "difficulty": "beginner", "detail": "standard", "price": 380},
            {"w": 40, "h": 40, "difficulty": "elementary", "detail": "standard", "price": 540},
        ],
    },
    {
        "title": "莫內的睡蓮",
        "description": "印象派的水波光影練習 — 紫色與綠的層次。",
        "series_id": SERIES_YINSI,
        "series_order": 1,
        "is_featured": True,
        "cover_image_url": "https://images.unsplash.com/photo-1578321272176-b7bbc0679853?w=800&q=70",
        "variants": [
            {"w": 40, "h": 50, "difficulty": "intermediate", "detail": "detailed", "price": 720},
            {"w": 50, "h": 60, "difficulty": "advanced", "detail": "premium", "price": 1180},
        ],
    },
]


async def seed(db: AsyncSession) -> None:
    # 找一個 admin user 作為 production_job 的 uploader（非必要欄位但放著）
    # 跳過 image_id，FK 是 nullable
    created_count = 0
    skipped_count = 0

    for p in PRODUCTS_TO_SEED:
        # idempotent — 同名已存在跳過
        existing = await db.execute(
            select(Product).where(Product.title == p["title"])
        )
        if existing.scalar_one_or_none():
            print(f"[skip] {p['title']} already exists")
            skipped_count += 1
            continue

        # 建立 product
        prod = Product(
            id=uuid4(),
            title=p["title"],
            description=p["description"],
            cover_image_url=p["cover_image_url"],
            series_id=p["series_id"],
            series_order=p["series_order"],
            status="on_sale",
            is_featured=p["is_featured"],
        )
        db.add(prod)
        await db.flush()

        # 為每個 variant 建立 production_job + variant
        for v in p["variants"]:
            job = ProductionJob(
                id=uuid4(),
                image_id=None,  # 跳過 image，FK nullable
                custom_request_id=None,
                status=JobStatusEnum.completed,
                approved=True,
                detail=DetailEnum(v["detail"]),
                difficulty=DifficultyEnum(v["difficulty"]),
                mode=ModeEnum.standard,
                canvas_w_cm=Decimal(str(v["w"])),
                canvas_h_cm=Decimal(str(v["h"])),
                num_colors=24,
                num_colors_used=24,
                min_brush_diam_cm=Decimal("1.0"),
                # dummy URLs — 實際 PBN engine 跑過會有真連結
                svg_url=f"https://example.com/svg/{v['w']}x{v['h']}_{v['difficulty']}.svg",
                filled_template_url=f"https://example.com/filled/{v['w']}x{v['h']}_{v['difficulty']}.png",
                snapped_rgb_url=f"https://example.com/rgb/{v['w']}x{v['h']}_{v['difficulty']}.png",
                palette_json=[
                    {"id": i, "rgb": [100 + i * 5, 80 + i * 4, 60 + i * 3], "name": f"色 {i}"}
                    for i in range(1, 25)
                ],
            )
            db.add(job)
            await db.flush()

            variant = ProductVariant(
                id=uuid4(),
                product_id=prod.id,
                production_job_id=job.id,
                price=Decimal(str(v["price"])),
                price_formula_base=Decimal(str(v["price"])),
                is_active=True,
            )
            db.add(variant)

        created_count += 1
        print(f"[ok] {p['title']}: {len(p['variants'])} variants 建好")

    await db.commit()
    print(f"\n[summary] created {created_count}, skipped {skipped_count}")


async def main() -> None:
    print(f"[seed] DB: {settings.database_url[:60]}...")
    engine = create_async_engine(settings.database_url, echo=False)
    async with AsyncSession(bind=engine, expire_on_commit=False) as db:
        await seed(db)
    await engine.dispose()
    print("[done]")


if __name__ == "__main__":
    asyncio.run(main())
