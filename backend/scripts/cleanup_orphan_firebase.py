"""一次性：清掉 Firebase 上沒對應 DB row 的孤兒物件。

掃描 prefix：
  - production_jobs/{job_id}/* — DB 沒對應 production_jobs.id 即孤兒（含 worker 卡死沒寫回 row 的中間檔）
  - production_images/{filename} — DB 沒任何 images.original_url 引用即孤兒

預設 dry-run 列出將刪檔；加 --apply 真的刪。

用法：
    cd backend
    venv/Scripts/python scripts/cleanup_orphan_firebase.py            # dry-run 列出
    venv/Scripts/python scripts/cleanup_orphan_firebase.py --apply    # 真刪

如要清特定 job_id：
    venv/Scripts/python scripts/cleanup_orphan_firebase.py --job-id 08f5da75-... --apply
"""
import argparse
import asyncio
import os
import re
import sys
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
import production.models  # noqa: F401, E402  required for ORM init
from core.config import settings  # noqa: E402
from core.firebase import get_bucket  # noqa: E402
from production.models import Image, ProductionJob  # noqa: E402

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


async def _get_db_uuids() -> tuple[set[str], set[str]]:
    """回傳 (job_ids, image_filename_substrings)。"""
    engine = create_async_engine(settings.database_url, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        job_rows = (await db.execute(select(ProductionJob.id))).scalars().all()
        image_rows = (await db.execute(select(Image.original_url))).scalars().all()
    await engine.dispose()

    job_ids = {str(r) for r in job_rows}
    # 從 image.original_url 抽出 path 內檔名（gs://bucket/production_images/<filename>）
    image_paths = set()
    for url in image_rows:
        if not url:
            continue
        # 找 production_images/ 開始的 substring
        m = re.search(r"production_images/[^?]+", url)
        if m:
            image_paths.add(m.group(0))
    return job_ids, image_paths


def _scan_prefix(bucket, prefix: str) -> list:
    return list(bucket.list_blobs(prefix=prefix))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="實際刪除（預設 dry-run）")
    parser.add_argument("--job-id", help="只處理指定 job_id（其他全略過）")
    args = parser.parse_args()

    bucket = get_bucket()
    print(f"Bucket: {bucket.name}")
    print(f"Mode: {'APPLY (real delete)' if args.apply else 'DRY-RUN'}")
    print()

    if args.job_id:
        # 單 job 模式：直接刪 production_jobs/{job_id}/* 全部
        prefix = f"production_jobs/{args.job_id}/"
        blobs = _scan_prefix(bucket, prefix)
        print(f"Found {len(blobs)} blob(s) under {prefix}")
        for blob in blobs:
            print(f"  {'DELETE' if args.apply else 'WOULD DELETE'} {blob.name} ({blob.size} bytes)")
            if args.apply:
                try:
                    blob.delete()
                except Exception as e:  # noqa: BLE001
                    print(f"    ! failed: {e}")
        print(f"\nDone. {len(blobs)} blob(s) {'deleted' if args.apply else 'would be deleted'}.")
        return

    # 全掃描模式
    print("Loading DB job_ids + image paths...")
    db_job_ids, db_image_paths = await _get_db_uuids()
    print(f"DB has {len(db_job_ids)} jobs, {len(db_image_paths)} image paths")
    print()

    # 1. 掃描 production_jobs/
    print("Scanning production_jobs/...")
    job_blobs = _scan_prefix(bucket, "production_jobs/")
    orphan_job_blobs = []
    for blob in job_blobs:
        # 路徑格式 production_jobs/{job_id}/<filename>
        parts = blob.name.split("/", 2)
        if len(parts) < 3:
            continue
        job_id = parts[1]
        if not UUID_RE.match(job_id):
            continue
        if job_id not in db_job_ids:
            orphan_job_blobs.append(blob)

    print(f"Found {len(orphan_job_blobs)} orphan blob(s) under production_jobs/ (job not in DB)")
    total_orphan_size = sum(b.size or 0 for b in orphan_job_blobs)
    print(f"  Total size: {total_orphan_size / 1024 / 1024:.2f} MB")

    # 2. 掃描 production_images/
    print("\nScanning production_images/...")
    img_blobs = _scan_prefix(bucket, "production_images/")
    orphan_img_blobs = []
    for blob in img_blobs:
        if blob.name not in db_image_paths:
            # DB 有 url 含 production_images/path，blob.name 應該完全 match
            orphan_img_blobs.append(blob)

    print(f"Found {len(orphan_img_blobs)} orphan blob(s) under production_images/ (no DB row)")
    total_img_orphan_size = sum(b.size or 0 for b in orphan_img_blobs)
    print(f"  Total size: {total_img_orphan_size / 1024 / 1024:.2f} MB")

    print()
    all_orphans = orphan_job_blobs + orphan_img_blobs
    if not all_orphans:
        print("[OK] No orphans found.")
        return

    print(f"Total orphans: {len(all_orphans)} blob(s), {(total_orphan_size + total_img_orphan_size) / 1024 / 1024:.2f} MB")
    print()

    if args.apply:
        deleted = 0
        for blob in all_orphans:
            try:
                blob.delete()
                deleted += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ! failed to delete {blob.name}: {e}")
        print(f"[OK] Deleted {deleted}/{len(all_orphans)} blobs.")
    else:
        print("(dry-run) sample of orphans (first 20):")
        for blob in all_orphans[:20]:
            print(f"  {blob.name} ({(blob.size or 0) / 1024:.1f} KB)")
        if len(all_orphans) > 20:
            print(f"  ... and {len(all_orphans) - 20} more")
        print("\nRun with --apply to actually delete.")


if __name__ == "__main__":
    asyncio.run(main())
