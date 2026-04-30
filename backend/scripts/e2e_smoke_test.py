"""End-to-end smoke test：上傳 Mom.jpg 到 Firebase → 建 image + production_job →
Celery worker 跑真引擎 → 回讀 DB 確認 svg/filled/snapped/palette。

需要：
- backend uvicorn 跑著（用於 Firebase init）
- celery worker 跑著（pool=solo）
- Redis 跑著
- yiimui DB 已建表 + 有 admin user

用法：
    cd backend && venv/Scripts/python scripts/e2e_smoke_test.py
"""
import asyncio
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import auth.models  # noqa: F401, E402
import color.models  # noqa: F401, E402
import content.models  # noqa: F401, E402
import custom.models  # noqa: F401, E402
import discount.models  # noqa: F401, E402
import notifications.models  # noqa: F401, E402
import orders.models  # noqa: F401, E402
import palette.models  # noqa: F401, E402
import print_batch.models  # noqa: F401, E402
import product.models  # noqa: F401, E402
import production.models  # noqa: E402
import users.models  # noqa: F401, E402
from auth.models import User  # noqa: E402
from core.config import settings  # noqa: E402
from core.firebase import get_bucket  # noqa: E402
from production.models import (  # noqa: E402
    DetailEnum,
    DifficultyEnum,
    Image,
    JobStatusEnum,
    ModeEnum,
    ProductionJob,
)
from production.tasks import run_production_job  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[2] / "paint-by-number" / "images" / "Mom.jpg"
ADMIN_EMAIL = "yizn.min@gmail.com"


async def main():
    if not SAMPLE.exists():
        print(f"[ERR] sample not found: {SAMPLE}")
        return

    # 1. 上傳 Mom.jpg 到 Firebase
    print(f"[1/5] uploading {SAMPLE.name} → Firebase...")
    bucket = get_bucket()
    blob_name = f"production_images/{uuid.uuid4().hex}_Mom.jpg"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(SAMPLE), content_type="image/jpeg")
    image_gs_url = f"gs://{bucket.name}/{blob_name}"
    print(f"      uploaded → {image_gs_url}")

    # 2. 建 image record
    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        admin = (await db.execute(select(User).where(User.email == ADMIN_EMAIL))).scalar_one()

        # 取圖片實際 width/height
        import cv2  # noqa: PLC0415
        img = cv2.imread(str(SAMPLE))
        h, w = img.shape[:2]

        image = Image(
            uploader_id=admin.id,
            original_url=image_gs_url,
            filename="Mom.jpg",
            width=w, height=h,
        )
        db.add(image)
        await db.commit()
        await db.refresh(image)
        print(f"[2/5] image record: id={image.id} ({w}×{h})")

        # 3. 建 production_job：standard / 入門 / 30×40 cm
        job = ProductionJob(
            image_id=image.id,
            status=JobStatusEnum.pending,
            approved=False,
            detail=DetailEnum.standard,
            difficulty=DifficultyEnum.beginner,
            mode=ModeEnum.standard,
            canvas_w_cm=30,
            canvas_h_cm=40,
            min_brush_diam_cm=1.0,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = str(job.id)
        print(f"[3/5] job created: id={job_id}")

    # 4. 派到 Celery
    print("[4/5] dispatching to Celery worker...")
    run_production_job.delay(job_id)

    # 5. 輪詢 job 狀態（最多 5 分鐘）
    print("[5/5] polling job status (max 5 min)...")
    deadline = time.time() + 300
    final_status = None
    final_job = None
    while time.time() < deadline:
        async with sf() as db:
            j = (await db.execute(
                select(ProductionJob).where(ProductionJob.id == job.id)
            )).scalar_one()
            print(f"      status={j.status}")
            if j.status in (JobStatusEnum.completed, JobStatusEnum.failed):
                final_status = j.status
                final_job = j
                break
        await asyncio.sleep(5)

    if final_status == JobStatusEnum.completed:
        print()
        print("=" * 60)
        print("[OK] job completed!")
        print(f"  svg_url:            {final_job.svg_url}")
        print(f"  filled_template_url:{final_job.filled_template_url}")
        print(f"  snapped_rgb_url:    {final_job.snapped_rgb_url}")
        print(f"  num_colors_used:    {final_job.num_colors_used}")
        print(f"  palette[0]:         {final_job.palette_json[0] if final_job.palette_json else None}")
        print("=" * 60)
    elif final_status == JobStatusEnum.failed:
        print()
        print(f"[FAIL] job failed: {final_job.notes}")
    else:
        print(f"[TIMEOUT] job 仍在 {final_job.status if final_job else 'unknown'} — celery worker 可能沒在跑？")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
