import io
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from celery import chain
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestError, NotFoundError
from core.firebase import get_bucket
from production.models import Image, ProductionJob
from production.tasks import cancel_batch_remaining, run_post_process_job, run_production_job

logger = logging.getLogger(__name__)

_UPLOAD_TTL_MINUTES = 15


# ── Canvas size suggestion ────────────────────────────────────────────────────
# 沿用 paint-by-number/src/run.py 的 suggest_canvas_sizes 邏輯（保持與引擎一致）。
# 17 種標準尺寸：正方 5 + 直幅 6 + 橫幅 6
_STANDARD_CANVAS_SIZES_CM: list[tuple[int, int]] = [
    # 正方形
    (20, 20), (30, 30), (40, 40), (50, 50), (60, 60),
    # 直幅
    (30, 40), (30, 50), (30, 60),
    (40, 50), (40, 60),
    (50, 60),
    # 橫幅
    (40, 30), (50, 30), (60, 30),
    (50, 40), (60, 40),
    (60, 50),
]


def suggest_canvas_sizes(img_w_px: int, img_h_px: int, n: int = 3) -> list[dict]:
    """根據圖片長寬比，從 17 種標準畫布規格中挑比例最接近的 n 個（去重後按面積排序）。

    回傳格式：[{'w': 30, 'h': 40, 'ratio_match': 0.998}, ...]
    `ratio_match` 為 0~1，1 = 比例完全相符。
    """
    if img_w_px <= 0 or img_h_px <= 0:
        raise BadRequestError("圖片寬高必須 > 0")
    img_ratio = img_w_px / img_h_px
    scored = []
    for w, h in _STANDARD_CANVAS_SIZES_CM:
        ratio_diff = abs((w / h) - img_ratio)
        area = w * h
        scored.append((ratio_diff, area, (w, h)))
    scored.sort(key=lambda x: (round(x[0], 3), x[1]))
    seen_ratios: set[float] = set()
    result: list[tuple[int, int]] = []
    for _, _area, size in scored:
        r = round(size[0] / size[1], 3)
        if r not in seen_ratios:
            seen_ratios.add(r)
            result.append(size)
        if len(result) == n:
            break
    result.sort(key=lambda s: s[0] * s[1])
    return [
        {
            "w": w,
            "h": h,
            "ratio_match": round(1 - abs((w / h) - img_ratio) / max(w / h, img_ratio), 4),
        }
        for w, h in result
    ]


def generate_upload_signed_url(filename: str, content_type: str) -> dict:
    """產出 production_images 的 PUT signed URL + 短效 GET signed URL。

    production_images 是 admin 內部資產（不開放公開讀），rules 禁讀；admin 端要看圖必須走
    signed URL。為了讓前端上傳完立刻能 preview（且減少多一次 round-trip），這裡回傳一個
    15-min TTL 的 GET signed URL 作為 `public_url`（命名沿用 API 契約，但實際是私有簽章）。

    若需要長期顯示，前端應在 detail 頁時呼叫專屬 signed-url 端點重新取一份。
    """
    bucket = get_bucket()
    safe_name = filename.replace(" ", "_").replace("/", "_")
    path = f"production_images/{uuid.uuid4().hex}_{safe_name}"
    blob = bucket.blob(path)
    ttl = timedelta(minutes=_UPLOAD_TTL_MINUTES)
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=ttl,
        method="PUT",
        content_type=content_type,
    )
    read_url = blob.generate_signed_url(
        version="v4",
        expiration=ttl,
        method="GET",
    )
    return {
        "upload_url": upload_url,
        "public_url": read_url,
        "expires_at": datetime.now(UTC) + ttl,
    }


async def create_image(
    db: AsyncSession, uploader_id: UUID, data: dict
) -> Image:
    image = Image(uploader_id=uploader_id, **data)
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


async def list_images(
    db: AsyncSession, page: int, page_size: int
) -> tuple[list[Image], int]:
    base = select(Image)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        base.order_by(Image.created_at.desc()).offset(offset).limit(page_size)
    )
    return list(result.scalars().all()), total


async def create_jobs(
    db: AsyncSession,
    image_id: UUID | None,
    custom_request_id: UUID | None,
    jobs_params: list[dict[str, Any]],
) -> dict:
    if image_id:
        exists = (await db.execute(select(Image).where(Image.id == image_id))).scalar_one_or_none()
        if not exists:
            raise NotFoundError("圖片不存在")

    # batch_id 分配規則（Phase A 行為擴張）：
    # - N > 1：照舊
    # - N == 1 但 mode != standard：也分配 batch_id（讓 batch start endpoint 能找到）
    # - N == 1 且 standard：null（與既有行為一致）
    has_sam = any(
        str(p.get("mode", "standard")) != "standard" for p in jobs_params
    )
    batch_id = uuid.uuid4() if (len(jobs_params) > 1 or has_sam) else None

    created_jobs: list[ProductionJob] = []
    for params in jobs_params:
        job = ProductionJob(
            image_id=image_id,
            custom_request_id=custom_request_id,
            batch_id=batch_id,
            **params,
        )
        db.add(job)
        created_jobs.append(job)

    # E26: auto-transition custom_request quote_pending → negotiating
    if custom_request_id is not None:
        from custom.service import auto_mark_negotiating_on_production_job
        await auto_mark_negotiating_on_production_job(db, custom_request_id)

    await db.commit()
    for job in created_jobs:
        await db.refresh(job)

    # sam_* 模式不在建立時 enqueue；等 admin 透過 sam-mask endpoint 編完遮罩後，
    # 由 POST /admin/production/batches/{batch_id}/start 觸發。
    standard_jobs = [j for j in created_jobs if str(j.mode) == "standard"]
    if standard_jobs:
        _dispatch_tasks(standard_jobs, batch_id)

    return {
        "batch_id": batch_id,
        "job_ids": [j.id for j in created_jobs],
    }


def _dispatch_tasks(jobs: list[ProductionJob], batch_id: uuid.UUID | None) -> None:
    """送到 Celery 佇列。若 broker（Redis）不可用，job 仍在 DB 內 status=pending，
    等 worker 上線後可由 admin 重新派工或自動撿件。
    """
    try:
        tasks = [run_production_job.si(str(j.id)) for j in jobs]
        if len(tasks) == 1:
            tasks[0].delay()
        else:
            error_cb = cancel_batch_remaining.si(str(batch_id))
            chain(*[t.set(link_error=[error_cb]) for t in tasks]).delay()
    except Exception as e:  # noqa: BLE001  — kombu / connection errors caught broadly by design
        logger.warning(
            "Celery dispatch failed (broker offline?): %s — jobs created in DB but not queued",
            e,
        )


async def start_batch(db: AsyncSession, batch_id: UUID) -> dict:
    """admin 編完 mask 後觸發整批 sam_* job 進 Celery（Phase A.4）。

    api.md 規範：
      - 只 enqueue mode != standard 且 status = pending 且 mask_url != null 的 job
      - 缺 mask_url → skipped 列「missing mask_url」，不整批拒絕
      - 已 processing/completed/failed → skipped，避免重複觸發
      - mode=standard 已在建立時 enqueue → skipped
      - batch_id 不存在 → 404

    並發保護：用 PostgreSQL advisory_xact_lock 序列化同 batch_id 的 concurrent
    start_batch 呼叫。第一個取到 lock 的 dispatch 完整批；第二個等到第一個 commit
    後才繼續，看到 worker 已撈起的 job status=processing 會 skip。
    註：lock 釋放至 worker pick up 之間仍有極小 race window；admin 連點按鈕的
    現實視窗內 worst case 是重複 dispatch（worker 浪費資源跑兩次），非資料 corruption。

    回傳 {enqueued: int, skipped: [{job_id, reason}]}.
    """
    # advisory_xact_lock 用 batch_id hash 為 key（int8）；transaction 結束自動釋放
    lock_key = int.from_bytes(batch_id.bytes[:8], "big", signed=True)
    await db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    rows = (await db.execute(
        select(ProductionJob).where(ProductionJob.batch_id == batch_id)
    )).scalars().all()
    if not rows:
        raise NotFoundError(f"批次不存在：{batch_id}")

    enqueueable: list[ProductionJob] = []
    skipped: list[dict] = []

    for job in rows:
        mode = str(job.mode)
        status = str(job.status)
        if mode == "standard":
            skipped.append({"job_id": job.id, "reason": "standard already enqueued at creation"})
            continue
        if status != "pending":
            skipped.append({"job_id": job.id, "reason": f"already {status}"})
            continue
        if not job.mask_url:
            skipped.append({"job_id": job.id, "reason": "missing mask_url"})
            continue
        enqueueable.append(job)

    if enqueueable:
        _dispatch_tasks(enqueueable, batch_id)

    return {
        "enqueued": len(enqueueable),
        "skipped": skipped,
    }


async def list_jobs(
    db: AsyncSession,
    status: str | None,
    approved: bool | None,
    batch_id: UUID | None,
    image_id: UUID | None,
    custom_request_id: UUID | None,
    page: int,
    page_size: int,
) -> tuple[list[ProductionJob], int]:
    q = select(ProductionJob)
    if status:
        q = q.where(ProductionJob.status == status)
    if approved is not None:
        q = q.where(ProductionJob.approved == approved)
    if batch_id:
        q = q.where(ProductionJob.batch_id == batch_id)
    if image_id:
        q = q.where(ProductionJob.image_id == image_id)
    if custom_request_id:
        q = q.where(ProductionJob.custom_request_id == custom_request_id)

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    offset = (page - 1) * page_size
    result = await db.execute(
        q.order_by(ProductionJob.created_at.desc()).offset(offset).limit(page_size)
    )
    jobs = list(result.scalars().all())

    # 補 image_preview_url：等待中 / 失敗 / processing 的 job 沒有 filled_template，
    # 列表頁需要原圖 thumbnail 才能視覺辨識。Schema validator 會把 gs:// 簽成 https。
    image_ids = {j.image_id for j in jobs if j.image_id is not None}
    if image_ids:
        img_rows = (
            await db.execute(
                select(Image.id, Image.original_url).where(Image.id.in_(image_ids))
            )
        ).all()
        url_map: dict[UUID, str] = {row.id: row.original_url for row in img_rows}
        for j in jobs:
            # 動態屬性 — Pydantic from_attributes 會讀到（不寫 DB）
            j.image_preview_url = url_map.get(j.image_id)  # type: ignore[attr-defined]
    else:
        for j in jobs:
            j.image_preview_url = None  # type: ignore[attr-defined]

    return jobs, total


async def get_job(db: AsyncSession, job_id: UUID) -> ProductionJob:
    result = await db.execute(select(ProductionJob).where(ProductionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("製作任務不存在")
    return job


async def delete_job(db: AsyncSession, job_id: UUID, *, force: bool = False) -> None:
    """硬刪除任務 row + palette_color_mappings 子資料 + Firebase 物件。

    安全規則：
    - status=processing → BadRequestError（worker 可能還在寫入，刪了會 race）
      - force=True 時繞過此檢查，用於 worker 卡死永不結束的 zombie task
    - 被 product_variants / print_batches / order_items 引用 → BadRequestError 拒絕
    - palette_color_mappings 連帶刪（FK NOT NULL，不刪 cascade 會 IntegrityError）
    - Firebase 物件（svg / filled / snapped_rgb / mask）best-effort 刪：
      失敗只 log warning，不回滾 DB（DB 已 commit）
    """
    from palette.models import PaletteColorMapping  # noqa: PLC0415

    job = await get_job(db, job_id)

    if job.status == "processing" and not force:
        raise BadRequestError(
            "任務正在處理中，無法刪除（請等待完成或失敗後再試）。"
            "若 worker 確認卡死，可改用 force=true 強制刪除（產生的 Firebase 物件可能成 orphan）。"
        )

    # 檢查是否被其他表引用 — 一律拒絕，防止商品/訂單/批次斷鏈
    refs = await _check_job_references(db, job_id)
    if refs:
        raise BadRequestError(
            f"任務被以下資料引用，無法刪除：{'、'.join(refs)}"
        )

    # DB 刪除：先刪子資料再刪 job row（palette_color_mappings FK NOT NULL，
    # 不能 SET NULL；schema 沒 ondelete CASCADE 所以手動 DELETE）
    await db.execute(
        PaletteColorMapping.__table__.delete().where(
            PaletteColorMapping.production_job_id == job_id
        )
    )
    await db.delete(job)
    await db.commit()

    # Firebase 清理 — 掃整個 production_jobs/{job_id}/ prefix 把所有 blob 刪光
    # （比僅刪 4 個 URL 欄位更徹底：worker 寫的中間檔 / mask 多版本 / 異常產生的孤兒
    #  都會一併清掉）。失敗只 log，不回滾 DB（DB 已 commit）。
    _delete_firebase_job_prefix(job_id)

    # force=True 取消 processing 任務時，worker 可能還在跑（最壞情況 OOM 卡死中），
    # 仍會繼續寫 Firebase。schedule 90 秒後再做一次 cleanup 把 race window 內
    # worker 寫的新 blob 也清掉（雙重保險）。一般刪除不需此步。
    if force:
        try:
            from production.tasks import cleanup_job_firebase  # noqa: PLC0415
            cleanup_job_firebase.apply_async(args=[str(job_id)], countdown=90)
        except Exception as e:  # noqa: BLE001
            logger.warning("schedule deferred firebase cleanup failed for %s: %s", job_id, e)


async def _check_job_references(db: AsyncSession, job_id: UUID) -> list[str]:
    """回傳所有引用此 job_id 的表標籤（中文），空 list 代表沒引用可安全刪。"""
    from orders.models import OrderItem  # noqa: PLC0415
    from print_batch.models import PrintBatchItem  # noqa: PLC0415
    from product.models import ProductVariant  # noqa: PLC0415

    refs = []
    for model, label in (
        (ProductVariant, "商品 variant"),
        (PrintBatchItem, "列印批次"),
        (OrderItem, "訂單項目"),
    ):
        cnt = (
            await db.execute(
                select(func.count()).select_from(model).where(
                    model.production_job_id == job_id
                )
            )
        ).scalar() or 0
        if cnt > 0:
            refs.append(f"{label}（{cnt} 筆）")
    return refs


def _delete_firebase_job_prefix(job_id: UUID) -> None:
    """掃 Firebase production_jobs/{job_id}/ prefix 下所有 blob 刪光。

    比逐一刪 4 個 URL 欄位徹底：worker 中間檔 / mask 多版本 / 異常孤兒都包含。
    任一失敗只 log，不影響其他 blob 與 DB（DB 已 commit）。
    """
    try:
        bucket = get_bucket()
        prefix = f"production_jobs/{job_id}/"
        blobs = list(bucket.list_blobs(prefix=prefix))
    except Exception as e:  # noqa: BLE001
        logger.warning("delete-job firebase list failed for %s — %s", job_id, e)
        return

    if not blobs:
        return

    deleted, failed = 0, 0
    for blob in blobs:
        try:
            blob.delete()
            deleted += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("delete-job firebase blob failed (orphan): %s — %s", blob.name, e)
            failed += 1
    logger.info(
        "delete-job firebase cleanup for %s: prefix=%s deleted=%d failed=%d",
        job_id, prefix, deleted, failed,
    )


_FILE_FIELD_MAP = {
    "svg": "svg_url",
    "snapped_rgb": "snapped_rgb_url",
    "filled": "filled_template_url",
}


# Module-level cache：blob path → (signed_url, expires_at)
# 同一張圖在 TTL 內重複請求回同一個簽名 URL，避免每次 polling 都換新 URL 導致瀏覽器重抓
# (admin 頁面 5 秒輪詢時 <img> 會閃)。簽名仍 15 分鐘有效；cache TTL 比簽名稍短保留緩衝。
_SIGNED_URL_CACHE: dict[str, tuple[str, datetime]] = {}
_SIGNED_URL_CACHE_TTL = timedelta(minutes=10)  # < _UPLOAD_TTL_MINUTES


def _make_signed_url(raw_url: str) -> str:
    bucket = get_bucket()
    parts = raw_url.split(f"/{bucket.name}/", 1)
    if len(parts) != 2:
        raise BadRequestError(f"無法解析 Firebase 路徑：{raw_url}")
    # raw_url 可能是：
    #   gs://bucket/path/to/file.jpg                                  → blob_path 含路徑
    #   https://storage.googleapis.com/bucket/path/to/file.jpg        → 同上
    #   https://storage.googleapis.com/bucket/path/to/file.jpg?X-... → 已是 signed URL（過期會重簽）
    # 後者要剝掉 query string 才是純 blob path，否則 blob.generate_signed_url 會把整個 ? 編成 %3F
    # 變雙重 query 的壞 URL（已遇過 bug）。
    blob_path = parts[1].split("?", 1)[0]
    now = datetime.now(UTC)

    cached = _SIGNED_URL_CACHE.get(blob_path)
    if cached and cached[1] > now:
        return cached[0]

    blob = bucket.blob(blob_path)
    url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=_UPLOAD_TTL_MINUTES),
        method="GET",
    )
    _SIGNED_URL_CACHE[blob_path] = (url, now + _SIGNED_URL_CACHE_TTL)
    return url


async def get_job_signed_url(
    db: AsyncSession, job_id: UUID, file: str
) -> str | None:
    """取 job 相關檔案的 signed URL。

    - file=svg/snapped_rgb/filled → 從 production_jobs 同名欄位取（Phase A/B 結果）
    - file=image / mask → 跨表取：image 從 images.original_url（job.image_id），
      mask 從 production_jobs.mask_url。Phase C 遮罩編輯用。
    - file=custom_photo → 從 custom_requests.photo_url（job.custom_request_id）
    """
    if file == "mask":
        job = await get_job(db, job_id)
        return _make_signed_url(job.mask_url) if job.mask_url else None
    if file == "image":
        job = await get_job(db, job_id)
        if not job.image_id:
            return None
        from sqlalchemy import select  # noqa: PLC0415

        from production.models import Image  # noqa: PLC0415
        result = await db.execute(select(Image).where(Image.id == job.image_id))
        image = result.scalar_one_or_none()
        if not image or not image.original_url:
            return None
        return _make_signed_url(image.original_url)
    field = _FILE_FIELD_MAP.get(file)
    if field is None:
        raise BadRequestError(
            f"不支援的檔案：{file}，可選值：{', '.join(list(_FILE_FIELD_MAP) + ['image', 'mask'])}"
        )
    job = await get_job(db, job_id)
    raw = getattr(job, field, None)
    return _make_signed_url(raw) if raw else None


async def approve_job(db: AsyncSession, job_id: UUID, notes: str | None) -> ProductionJob:
    job = await get_job(db, job_id)
    if not job.approved and job.status != "completed":
        raise BadRequestError("只有 status=completed 的任務才能核准")
    if notes is not None:
        job.notes = notes
    if not job.approved:
        job.approved = True
        job.approved_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    return job


async def unapprove_job(db: AsyncSession, job_id: UUID) -> ProductionJob:
    job = await get_job(db, job_id)
    if not job.approved:
        return job
    job.approved = False
    job.approved_at = None
    await db.commit()
    await db.refresh(job)
    return job


# ── SAM mask edit ──────────────────────────────────────────────────────────────

async def update_sam_mask(
    db: AsyncSession,
    job_id: UUID,
    sam_points: list[dict] | None,
    polygons: list[list[list[float]]] | None,
    mode: str,
) -> dict:
    """admin_production.md §1.3「遮罩編輯時機限制」：僅 status=pending 可改。

    - 寫回 sam_points / polygons（作為可編輯狀態的原始資料）
    - polygons 給定 → PIL 畫多邊形 mask（純幾何）
    - sam_points 給定 → 下載原圖 + SAM 模型推論（Phase B）
    - 兩者都有 → 聯集；最後上傳同一張 PNG
    - approved 退回 false（與「合併色塊 / 消邊界」一致）
    - mask_coverage 為 0~1 比例（與 api.md 範例 0.42 一致；不是百分比）

    mode 改動需與 job 既有 extra_colors / weight_ratio 一致，否則 worker 會 crash。
    """
    job = await get_job(db, job_id)
    if job.status != "pending":
        raise BadRequestError(
            f"遮罩僅在 status=pending 時可編輯（目前 {job.status}）"
        )

    # 沿用 JobParams.validate_mode_params 的一致性檢查（避免切換 mode 但缺對應參數）
    if mode == "sam_refine":
        if job.extra_colors is None or job.extra_colors <= 0:
            raise BadRequestError(
                "切換為 sam_refine 需先在建立任務時提供 extra_colors（> 0）"
            )
    elif mode == "sam_weighted":
        if job.weight_ratio is None or not (0.5 <= float(job.weight_ratio) <= 0.8):
            raise BadRequestError(
                "切換為 sam_weighted 需先在建立任務時提供 weight_ratio（0.5 ~ 0.8）"
            )

    if not job.image_id:
        raise BadRequestError("此任務無 image_id，無法計算遮罩")

    image = (
        await db.execute(select(Image).where(Image.id == job.image_id))
    ).scalar_one_or_none()
    if image is None:
        raise BadRequestError("找不到對應的 image 紀錄")

    img_w = int(image.width)
    img_h = int(image.height)

    # 寫回原始資料（供之後重建用）
    job.sam_points = [p for p in (sam_points or [])]  # list[dict]
    job.polygons = polygons or []
    job.mode = mode

    coverage, mask_url = await _compute_and_upload_mask(
        job, image, sam_points, polygons, img_w, img_h,
    )

    job.mask_url = mask_url
    job.mask_coverage = coverage
    job.approved = False
    job.approved_at = None

    await db.commit()
    await db.refresh(job)
    return {
        "mask_url": job.mask_url,
        "mask_coverage": float(job.mask_coverage) if job.mask_coverage is not None else None,
    }


async def _compute_and_upload_mask(
    job: ProductionJob,
    image: Image,
    sam_points: list[dict] | None,
    polygons: list[list[list[float]]] | None,
    img_w: int,
    img_h: int,
) -> tuple[float | None, str | None]:
    """合併 polygons + sam_points 兩種來源的 mask，計 coverage、上傳 Firebase。

    - polygons 為空且 sam_points 為空 → (None, None)（caller 不該走到這裡，validator 已擋）
    - 任一為空 → 用另一個的 mask
    - 都有 → 聯集
    上傳失敗 → mask_url=None，sam_points/polygons 仍保留，admin 可重試。
    """
    import asyncio  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    poly_mask = _polygons_to_mask(polygons, img_w, img_h) if polygons else None
    sam_mask: np.ndarray | None = None
    if sam_points:
        try:
            sam_mask = await asyncio.to_thread(
                _run_sam_predict, image.original_url, sam_points,
            )
        except (ValueError, FileNotFoundError, ImportError) as e:
            # SAM 推論失敗時：
            # - 若同時有 polygons → 退化為 polygons-only（規格 §1.3 兩種模式聯集，
            #   一邊掛掉時不應整批拒絕，admin 至少能保留多邊形選取）+ log warning
            # - 若純 sam_points 沒有 polygons → 真的無 mask 可產，必須拒絕
            if poly_mask is not None:
                logger.warning(
                    "SAM 推論失敗，退化為純 polygons mask：%s", e,
                )
                sam_mask = None
            else:
                raise BadRequestError(f"SAM 推論失敗：{e}") from e

    # 聯集
    final_mask: np.ndarray | None = None
    if poly_mask is not None and sam_mask is not None:
        final_mask = np.logical_or(poly_mask > 127, sam_mask).astype(np.uint8) * 255
    elif poly_mask is not None:
        final_mask = poly_mask
    elif sam_mask is not None:
        final_mask = (sam_mask.astype(np.uint8)) * 255

    if final_mask is None or not np.any(final_mask):
        return None, None

    # coverage（0~1，兩位精度，與 DB Numeric(6,2) 一致）
    white_pixels = int(np.sum(final_mask > 127))
    coverage = round(white_pixels / (img_w * img_h), 2)

    # 編碼 PNG + 上傳 Firebase
    import io  # noqa: PLC0415

    from PIL import Image as PILImage  # noqa: PLC0415

    buf = io.BytesIO()
    PILImage.fromarray(final_mask, mode="L").save(buf, format="PNG")
    png_bytes = buf.getvalue()

    try:
        bucket = get_bucket()
        path = f"production_jobs/{job.id}/mask_{uuid.uuid4().hex[:8]}.png"
        blob = bucket.blob(path)
        blob.upload_from_string(png_bytes, content_type="image/png")
        return coverage, f"gs://{bucket.name}/{path}"
    except Exception as e:  # noqa: BLE001
        logger.warning("Firebase upload failed for mask: %s", e)
        # 上傳失敗 → coverage 已算但無 url；保留 sam_points/polygons 等下次重試
        return None, None


def _polygons_to_mask(
    polygons: list[list[list[float]]],
    img_w: int,
    img_h: int,
):
    """用 PIL 畫多 polygon 聯集成 mask（uint8 0/255）。"""
    import numpy as np  # noqa: PLC0415
    from PIL import Image as PILImage  # noqa: PLC0415
    from PIL import ImageDraw  # noqa: PLC0415

    mask = PILImage.new("L", (img_w, img_h), 0)
    draw = ImageDraw.Draw(mask)
    for poly in polygons:
        if len(poly) < 3:
            continue
        pts = [(float(x), float(y)) for x, y in poly]
        draw.polygon(pts, fill=255)
    return np.array(mask, dtype=np.uint8)


def _run_sam_predict(image_url: str, sam_points: list[dict]):
    """同步：下載原圖 + SAM 推論 → 回 bool mask。供 update_sam_mask 用 to_thread 包。

    image_url 可能是 gs:// 或 https://（既有圖片儲存格式）。
    走 in-memory bytes（避免 Windows 上 tempfile race + 累積 %TEMP% 殘檔）。

    優化：sam_runtime 已 cache 此圖 embedding（is_image_cached）→ 跳過下載+解碼，
    直接用 cached embedding 走 predict（同 admin 連點 SAM 第二次起每次省 1-2 秒）。
    """
    from production.sam_runtime import (  # noqa: PLC0415
        get_sam_predictor,
        is_image_cached,
        predict_mask,
    )

    predictor = get_sam_predictor()

    if is_image_cached(image_url):
        # cache hit：predictor 已 set_image 過此圖，predict 不需要原圖
        return predict_mask(predictor, None, sam_points, image_key=image_url)

    # cache miss：下載 + 解碼 + set_image
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    from production.tasks import _parse_blob_path  # noqa: PLC0415

    bucket = get_bucket()
    blob_path = _parse_blob_path(image_url, bucket.name)
    blob = bucket.blob(blob_path)
    image_bytes = blob.download_as_bytes()

    img_bgr = cv2.imdecode(
        np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR,
    )
    if img_bgr is None:
        raise ValueError(f"無法解碼下載的圖片：{image_url}")

    return predict_mask(predictor, img_bgr, sam_points, image_key=image_url)


# ── PDF export ─────────────────────────────────────────────────────────────────

# 規格：admin_production.md §6 — 匯出 PDF 時 SVG viewBox 四周各擴展 5cm（裝訂留白）
_PDF_MARGIN_CM = 5.0


async def export_job_pdf(db: AsyncSession, job_id: UUID) -> bytes:
    """SVG → 單頁 PDF（四周 5cm 邊框）。沿用 print_batch 的 svglib→cairosvg fallback。"""
    job = await get_job(db, job_id)
    if job.status != "completed":
        raise BadRequestError("僅 completed 任務可匯出 PDF")
    # 資料異常情境（completed 但無 svg_url）刻意回 400 而非 500：
    # 理論上 worker 寫完 svg_url 才會把 status 設 completed；若真的發生不一致，
    # 4xx 讓前端能顯示「請聯繫管理員」友善訊息，而非通用 5xx tomato page。
    if not job.svg_url:
        raise BadRequestError("此任務無 SVG 檔案")

    try:
        from reportlab.graphics import renderPDF
        from reportlab.lib.units import cm
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas as rl_canvas

        from print_batch.service import _render_svg_with_fallbacks
    except ImportError as e:
        raise BadRequestError(
            "PDF 引擎未就緒（缺 reportlab/svglib/cairosvg）。"
            "請執行 pip install svglib reportlab Pillow cairosvg"
        ) from e

    w_cm = float(job.canvas_w_cm)
    h_cm = float(job.canvas_h_cm)
    # SVG 存的是 gs:// URL（私有），httpx 不認識；需要先轉 https signed URL。
    # 已是 http/https 的（測試 fixture 或先前簽過）直接傳給 httpx，不重簽，
    # 避免 _make_signed_url 對 bucket name 不匹配的測試 URL 失敗。
    if job.svg_url and job.svg_url.startswith("gs://"):
        svg_fetch_url = _make_signed_url(job.svg_url)
    else:
        svg_fetch_url = job.svg_url
    drawing, png_bytes = await _render_svg_with_fallbacks(svg_fetch_url, w_cm, h_cm)
    if drawing is None and png_bytes is None:
        raise BadRequestError("SVG 渲染失敗（svglib 與 cairosvg 皆無法解析此檔案）")

    page_w_cm = w_cm + 2 * _PDF_MARGIN_CM
    page_h_cm = h_cm + 2 * _PDF_MARGIN_CM
    target_w_pt = w_cm * cm
    target_h_pt = h_cm * cm
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_w_cm * cm, page_h_cm * cm))
    x_pt = _PDF_MARGIN_CM * cm
    y_pt = _PDF_MARGIN_CM * cm  # ReportLab Y 軸自下而上
    if drawing is not None:
        # svg2rlg Drawing 的 width/height 是 SVG viewBox 的 user units（不等於 PDF point）。
        # 必須縮放，否則向量內容尺寸 ≠ canvas 尺寸（會與 PNG fallback 結果不一致）。
        if not (drawing.width and drawing.height):
            # 0 維 Drawing 代表 SVG 解析異常（empty 或 viewBox 缺失）。
            # 不能靜默放掉縮放再渲染（會輸出沒被縮放的爛 PDF），直接走錯誤路徑。
            raise BadRequestError(
                "SVG 渲染失敗（svglib 解析後 Drawing 維度為 0，可能 viewBox 缺失或檔案損毀）"
            )
        sx = target_w_pt / float(drawing.width)
        sy = target_h_pt / float(drawing.height)
        drawing.scale(sx, sy)  # 真正影響 transform matrix；下兩行只是同步 metadata
        drawing.width = target_w_pt
        drawing.height = target_h_pt
        renderPDF.draw(drawing, c, x_pt, y_pt)
    else:
        img = ImageReader(io.BytesIO(png_bytes))
        c.drawImage(img, x_pt, y_pt, width=target_w_pt, height=target_h_pt)
    c.showPage()
    c.save()
    return buf.getvalue()


async def post_process(
    db: AsyncSession, job_id: UUID, params: dict[str, Any]
) -> ProductionJob:
    from production.models import JobStatusEnum

    job = await get_job(db, job_id)
    if job.status != "completed":
        raise BadRequestError("只有 status=completed 的任務才能執行後製處理")
    job.approved = False
    job.status = JobStatusEnum.processing
    await db.commit()
    await db.refresh(job)
    run_post_process_job.delay(str(job_id), params)
    return job
