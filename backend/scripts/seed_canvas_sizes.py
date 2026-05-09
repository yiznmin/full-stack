"""Seed canvas_sizes table (補種子，因為某些 dev DB 沒從 migration 拿到 seed)."""
import asyncio
import os
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

SEEDS = [
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


async def main() -> None:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:dev123@localhost:1128/yiimui",
    )
    eng = create_async_engine(url)
    async with eng.begin() as conn:
        for w, h, name, order in SEEDS:
            await conn.execute(
                text(
                    "INSERT INTO canvas_sizes (id, canvas_w_cm, canvas_h_cm, display_name, sort_order, is_active) "
                    "VALUES (:id, :w, :h, :name, :sort, true) "
                    "ON CONFLICT (canvas_w_cm, canvas_h_cm) DO NOTHING"
                ),
                {"id": uuid.uuid4(), "w": w, "h": h, "name": name, "sort": order},
            )
    async with eng.connect() as conn:
        n = (await conn.execute(text("SELECT count(*) FROM canvas_sizes WHERE is_active=true"))).scalar()
    print(f"seeded canvas_sizes: {n} active rows")


if __name__ == "__main__":
    asyncio.run(main())
