"""Production Celery tasks — 真實 PBN 引擎整合（Phase 2）。

run_production_job：DB 取 job → 下載原圖 → 跑引擎 → 上傳 Firebase → 寫回 DB。
失敗回滾：刪除已上傳的 Firebase 物件、status=failed、notes 寫錯誤摘要。
"""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import traceback
import uuid
from typing import Any

from core.celery_app import celery_app
from production.engine import (
    apply_color_replacement,
    generate_standard,
    resolve_engine_params,
)

logger = logging.getLogger(__name__)


# ── helpers (Celery worker 是同步 process，async 用 asyncio.run 包住) ───────────


def _run_async(coro):
    """同步 worker 中跑 async 程式碼。"""
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(coro)


async def _load_job(session, job_id: str):
    from sqlalchemy import select  # noqa: PLC0415

    from production.models import ProductionJob  # noqa: PLC0415

    result = await session.execute(
        select(ProductionJob).where(ProductionJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def _load_image(session, image_id):
    from sqlalchemy import select  # noqa: PLC0415

    from production.models import Image  # noqa: PLC0415

    result = await session.execute(
        select(Image).where(Image.id == image_id)
    )
    return result.scalar_one_or_none()


def _download_image_to_path(image_url: str, dest_path: str) -> None:
    """從 Firebase Storage 下載原圖。

    image_url 可能是 gs://bucket/path 或 https://storage.googleapis.com/... 格式。
    """
    from core.firebase import get_bucket  # noqa: PLC0415

    bucket = get_bucket()
    blob_path = _parse_blob_path(image_url, bucket.name)
    blob = bucket.blob(blob_path)
    blob.download_to_filename(dest_path)


def _parse_blob_path(url: str, bucket_name: str) -> str:
    """從 gs:// 或 https:// URL 中萃取 blob 路徑。"""
    if url.startswith("gs://"):
        prefix = f"gs://{bucket_name}/"
        if not url.startswith(prefix):
            raise ValueError(f"URL bucket 不符：{url}")
        return url[len(prefix):]
    if "/" + bucket_name + "/" in url:
        # https://storage.googleapis.com/<bucket>/<path>?<query>
        path = url.split("/" + bucket_name + "/", 1)[1]
        return path.split("?", 1)[0]
    raise ValueError(f"無法從 URL 解出 blob 路徑：{url}")


def _upload_file(local_path: str, blob_path: str, content_type: str) -> str:
    """上傳本地檔到 Firebase 並回傳 gs:// 路徑。

    公開讀取一律走 signed URL（與 upload/service.py、production.create_image 模式一致）。
    Bucket 啟用 uniform bucket-level access 時 make_public() 會 raise 400 — 不採用。
    """
    from core.firebase import get_bucket  # noqa: PLC0415

    bucket = get_bucket()
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(local_path, content_type=content_type)
    return f"gs://{bucket.name}/{blob_path}"


def _delete_blob(blob_path: str) -> None:
    """刪除 Firebase 物件（回滾用）— 失敗只記 log，不再 raise。"""
    try:
        from core.firebase import get_bucket  # noqa: PLC0415

        bucket = get_bucket()
        bucket.blob(blob_path).delete()
    except Exception as e:  # noqa: BLE001
        logger.warning("Firebase delete failed (orphan may remain): %s — %s", blob_path, e)


def _delete_blob_by_url(url: str | None) -> None:
    """從 gs:// 或 https URL 解出 blob path 並刪除。容錯：解析或刪除失敗只 log。

    用於 post-process 完成後清舊版本的 svg/filled/snapped；既然新版本已寫回 DB，
    舊版本就是 orphan，主動清掉避免 Firebase 累積成本。
    """
    if not url:
        return
    try:
        from core.firebase import get_bucket  # noqa: PLC0415

        bucket = get_bucket()
        blob_path = _parse_blob_path(url, bucket.name)
        _delete_blob(blob_path)
    except Exception as e:  # noqa: BLE001
        logger.warning("delete-by-url failed (orphan may remain): %s — %s", url, e)


# ── Main task ─────────────────────────────────────────────────────────────────


@celery_app.task(bind=True, name="production.run_job", max_retries=0)
def run_production_job(self, job_id: str) -> None:
    """跑單筆 production_job：引擎產出 → Firebase 上傳 → DB 回寫。

    僅支援 mode=standard。sam_refine / sam_weighted 留 Phase 2-B。
    """
    _run_async(_run_production_job_async(job_id))


def _get_db_url() -> str:
    """允許測試 monkey-patch 這個函式來指向 test DB。"""
    from core.config import settings  # noqa: PLC0415

    return settings.database_url


async def _mark_job_failed(job_id: str, notes: str) -> None:
    """用獨立 engine 標 job=failed + notes。專供主 session 連線壞掉的回滾路徑使用。

    任何步驟失敗都吞例外只 log — 因為這已是「最後一道保險」，再 raise 會讓 Celery
    把整個 task 標 failed 反而看不到我們已寫好的 notes。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415
    from sqlalchemy.pool import NullPool  # noqa: PLC0415

    from production.models import JobStatusEnum  # noqa: PLC0415

    fallback_engine = create_async_engine(_get_db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(fallback_engine, expire_on_commit=False) as session:
            job = await _load_job(session, job_id)
            if job is None:
                logger.warning("_mark_job_failed: job %s not found in fallback session", job_id)
                return
            job.status = JobStatusEnum.failed
            job.notes = notes[:500]
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception("_mark_job_failed itself failed for %s: %s", job_id, e)
    finally:
        try:
            await fallback_engine.dispose()
        except Exception as e:  # noqa: BLE001
            logger.warning("fallback engine dispose failed: %s", e)


async def _run_production_job_async(job_id: str) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415
    from sqlalchemy.pool import NullPool  # noqa: PLC0415

    from production.models import JobStatusEnum  # noqa: PLC0415

    engine_db = create_async_engine(_get_db_url(), poolclass=NullPool)
    uploaded_blob_paths: list[str] = []

    try:
        async with AsyncSession(engine_db, expire_on_commit=False) as session:
            job = await _load_job(session, job_id)
            if not job:
                logger.warning("run_production_job: job %s not found", job_id)
                return

            if job.mode != "standard":
                # sam_refine / sam_weighted 留 Phase 2-B
                job.status = JobStatusEnum.failed
                job.notes = f"目前僅支援 standard 模式，收到 mode={job.mode}（Phase 2-B 將補上）"
                await session.commit()
                return

            if job.image_id is None:
                job.status = JobStatusEnum.failed
                job.notes = "缺少 image_id（custom_request 路徑請先指派 image）"
                await session.commit()
                return

            image = await _load_image(session, job.image_id)
            if image is None:
                job.status = JobStatusEnum.failed
                job.notes = f"找不到 image_id={job.image_id}"
                await session.commit()
                return

            # status pending → processing
            job.status = JobStatusEnum.processing
            await session.commit()

            # 跑引擎（在 temp dir 內）+ 上傳
            try:
                result = await asyncio.to_thread(
                    _run_engine_and_upload, str(job.id), image.original_url, _resolve_params(job),
                    uploaded_blob_paths,
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("run_production_job: engine/upload failed for %s", job_id)
                # 回滾：刪已上傳
                for p in uploaded_blob_paths:
                    _delete_blob(p)
                job.status = JobStatusEnum.failed
                job.notes = f"引擎或上傳失敗：{type(e).__name__}: {e}"[:500]
                await session.commit()
                return

            # 寫回 DB（commit 失敗 → blob 已上傳但無法落地，必須回滾刪 blob 並標 failed）
            job.svg_url = result["svg_url"]
            job.filled_template_url = result["filled_template_url"]
            job.snapped_rgb_url = result["snapped_rgb_url"]
            job.palette_json = result["palette_data"]
            job.num_colors_used = result["num_colors_used"]
            job.status = JobStatusEnum.completed
            try:
                await session.commit()
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "run_production_job: final commit failed for %s — rolling back blobs",
                    job_id,
                )
                # rollback 也可能失敗（連線斷）— 不能擋下標 failed 的關鍵動作
                try:
                    await session.rollback()
                except Exception as rb:  # noqa: BLE001
                    logger.warning("session rollback also failed: %s", rb)
                for p in uploaded_blob_paths:
                    _delete_blob(p)
                # 用獨立 engine + session 標 failed（避免共用同一個壞掉的連線
                # 而導致 job 永遠卡 processing）
                await _mark_job_failed(
                    job_id,
                    f"DB 寫回失敗（已清 Firebase orphan）：{type(e).__name__}: {e}",
                )
                return
            logger.info(
                "run_production_job: %s completed (%d colors)",
                job_id, result["num_colors_used"],
            )
    finally:
        await engine_db.dispose()


def _resolve_params(job) -> dict[str, Any]:
    return resolve_engine_params(job)


def _run_engine_and_upload(
    job_id: str,
    image_url: str,
    params: dict[str, Any],
    uploaded_blob_paths_out: list[str],
) -> dict[str, Any]:
    """同步部分：下載 → 引擎 → 上傳。在 thread 中跑（避免 block event loop）。

    uploaded_blob_paths_out 是個 list，會 in-place append 已上傳的 blob path，
    讓外層在後續失敗時可以反向刪除。
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"prod_{job_id}_")
    try:
        # 1. 下載原圖
        ext = os.path.splitext(image_url.split("?", 1)[0])[1] or ".jpg"
        src_path = os.path.join(tmp_dir, f"src{ext}")
        _download_image_to_path(image_url, src_path)

        # 2. 跑引擎
        out_dir = os.path.join(tmp_dir, "out")
        engine_result = generate_standard(src_path, out_dir, **params)

        # 3. 上傳 3 個檔（svg / snapped 私有；filled 公開讀，admin UI 直接 <img>）
        token = uuid.uuid4().hex[:8]
        svg_blob = f"production_jobs/{job_id}/template_{token}.svg"
        filled_blob = f"production_jobs/{job_id}/filled_{token}.png"
        snapped_blob = f"production_jobs/{job_id}/snapped_{token}.png"

        svg_url = _upload_file(engine_result["svg_path"], svg_blob, "image/svg+xml")
        uploaded_blob_paths_out.append(svg_blob)
        filled_url = _upload_file(engine_result["filled_path"], filled_blob, "image/png")
        uploaded_blob_paths_out.append(filled_blob)
        snapped_url = _upload_file(engine_result["snapped_rgb_path"], snapped_blob, "image/png")
        uploaded_blob_paths_out.append(snapped_blob)

        return {
            "svg_url": svg_url,
            "filled_template_url": filled_url,
            "snapped_rgb_url": snapped_url,
            "palette_data": engine_result["palette_data"],
            "num_colors_used": engine_result["num_colors_used"],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Post-process task（合併色塊 / 消除邊界 真實實作 — Phase 2-A.2）──────────────


@celery_app.task(bind=True, name="production.run_post_process", max_retries=0)
def run_post_process_job(self, job_id: str, params: dict) -> None:
    """後處理：合併色塊 / 消除邊界。沿用 snapped_rgb 不重跑 KMeans。

    （原規劃的「輪廓平滑」已下架，見 admin_production.md §1.6 註）
    """
    _run_async(_run_post_process_async(job_id, params))


_PHASE2B_NOTE_PREFIX = "[Phase 2-B]"


def _resolve_post_process_op(params: dict) -> tuple[int, int]:
    """從 params dict 解出 (src_template_id, tgt_template_id)。

    A 格子合併：{source_template_id, target_template_id}
    B 消除邊界：{absorbed_template_id, surviving_template_id}
    其他形狀 → ValueError
    """
    if "source_template_id" in params and "target_template_id" in params:
        return int(params["source_template_id"]), int(params["target_template_id"])
    if "absorbed_template_id" in params and "surviving_template_id" in params:
        return int(params["absorbed_template_id"]), int(params["surviving_template_id"])
    raise ValueError(
        f"無法判斷後處理操作類型；params keys={sorted(params.keys())}"
    )


def _find_rgb_in_palette(palette_json: list, template_id: int) -> tuple[int, int, int] | None:
    """從 palette_json 中找對應 template_id 的 RGB（list[int] 三元組）。"""
    for item in palette_json or []:
        if int(item.get("template_id", -1)) == template_id:
            rgb = item.get("rgb")
            if isinstance(rgb, list) and len(rgb) == 3:
                return tuple(int(v) for v in rgb)
    return None


async def _remap_palette_color_mappings(session, job_id: str, new_palette: list) -> None:
    """合併後 output_to_svg 會重編號 template_id；用 algorithm_rgb 對 palette_color_mappings
    重新匹配，找不到的（即被合併掉的色號）DELETE，找到的 UPDATE template_id。

    注意：palette_color_mappings 有 UniqueConstraint(production_job_id, template_id)，
    直接 UPDATE 會在 row 之間互相衝突（如 row A 從 3→2 但 row B 仍佔 2）。
    所以分兩 phase：先全部 UPDATE 到暫時值（負數，必不衝突），再改成最終值。
    """
    from sqlalchemy import delete, select  # noqa: PLC0415

    from palette.models import PaletteColorMapping  # noqa: PLC0415

    rows = (
        await session.execute(
            select(PaletteColorMapping).where(
                PaletteColorMapping.production_job_id == job_id
            )
        )
    ).scalars().all()

    rgb_to_new_id: dict[tuple[int, int, int], int] = {}
    for item in new_palette:
        rgb = item.get("rgb")
        if isinstance(rgb, list) and len(rgb) == 3:
            rgb_to_new_id[tuple(int(v) for v in rgb)] = int(item["template_id"])

    to_delete_ids: list = []
    pending_updates: list[tuple] = []  # (row, new_template_id)

    for r in rows:
        old_rgb = r.algorithm_rgb
        if not (isinstance(old_rgb, list) and len(old_rgb) == 3):
            continue
        key = tuple(int(v) for v in old_rgb)
        new_id = rgb_to_new_id.get(key)
        if new_id is None:
            to_delete_ids.append(r.id)
        elif r.template_id != new_id:
            pending_updates.append((r, new_id))

    # 先 DELETE 被合併色號的 row（不卡 UNIQUE）
    if to_delete_ids:
        await session.execute(
            delete(PaletteColorMapping).where(PaletteColorMapping.id.in_(to_delete_ids))
        )
        await session.flush()

    # Phase 1: 全部移到負數臨時值（避開 UNIQUE 衝突）
    if pending_updates:
        for i, (row, _new_id) in enumerate(pending_updates):
            row.template_id = -(i + 1)  # -1, -2, -3, ...
        await session.flush()

        # Phase 2: 改成最終值
        for row, new_id in pending_updates:
            row.template_id = new_id
        await session.flush()


async def _run_post_process_async(job_id: str, params: dict) -> None:
    """合併色塊 / 消除邊界 — 從 snapped_rgb 下載、pixel replace、重跑 SVG/filled、
    上傳取代舊 url、重建 palette_color_mappings、寫回 DB。

    流程與 run_production_job 同模式：失敗時清 orphan blob、用獨立 engine 標 failed。
    """
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415
    from sqlalchemy.pool import NullPool  # noqa: PLC0415

    from production.models import JobStatusEnum  # noqa: PLC0415

    engine_db = create_async_engine(_get_db_url(), poolclass=NullPool)
    uploaded_blob_paths: list[str] = []

    try:
        async with AsyncSession(engine_db, expire_on_commit=False) as session:
            job = await _load_job(session, job_id)
            if not job:
                logger.warning("run_post_process_job: job %s not found", job_id)
                return

            # 0. 解析 op type + 找 src/tgt RGB
            try:
                src_id, tgt_id = _resolve_post_process_op(params)
                src_rgb = _find_rgb_in_palette(job.palette_json or [], src_id)
                tgt_rgb = _find_rgb_in_palette(job.palette_json or [], tgt_id)
                if src_rgb is None:
                    raise ValueError(f"找不到 template_id={src_id} 在 palette_json 中")
                if tgt_rgb is None:
                    raise ValueError(f"找不到 template_id={tgt_id} 在 palette_json 中")
                if src_rgb == tgt_rgb:
                    # 兩個 template_id 不同但 RGB 恰好相同 — palette_json 異常或測試
                    # 資料；繼續跑會 noop pixel replace 但 mappings 仍被重編號（破壞性）
                    raise ValueError(
                        f"src 與 tgt 的 RGB 相同（{src_rgb}），無變更但會重編號 mappings — "
                        f"拒絕執行（template_id={src_id}/{tgt_id}）"
                    )
            except (ValueError, KeyError, TypeError) as e:
                logger.warning("post_process: bad params for %s — %s", job_id, e)
                job.status = JobStatusEnum.failed
                job.notes = f"後處理參數錯誤：{e}"[:500]
                await session.commit()
                return

            if not job.snapped_rgb_url:
                job.status = JobStatusEnum.failed
                job.notes = "缺少 snapped_rgb_url（job 可能未跑過引擎或檔案被清掉）"
                await session.commit()
                return

            # 0a. 記住舊 url，commit 成功後清 Firebase orphan（避免累積成本）
            old_svg_url = job.svg_url
            old_filled_url = job.filled_template_url
            old_snapped_url = job.snapped_rgb_url

            # 1. 下載 snapped + 跑引擎 + 上傳新檔
            try:
                result = await asyncio.to_thread(
                    _run_post_process_engine_and_upload,
                    str(job.id),
                    job.snapped_rgb_url,
                    src_rgb,
                    tgt_rgb,
                    {
                        "canvas_w_cm": float(job.canvas_w_cm),
                        "canvas_h_cm": float(job.canvas_h_cm),
                        "min_brush_diam_cm": float(job.min_brush_diam_cm or 1.0),
                        "min_ratio_multiplier": float(job.min_ratio_multiplier or 1.0),
                    },
                    uploaded_blob_paths,
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("run_post_process_job: engine/upload failed for %s", job_id)
                for p in uploaded_blob_paths:
                    _delete_blob(p)
                job.status = JobStatusEnum.failed
                job.notes = f"後處理失敗：{type(e).__name__}: {e}"[:500]
                await session.commit()
                return

            # 2. 重建 palette_color_mappings（用 algorithm_rgb 重匹配 template_id）
            await _remap_palette_color_mappings(
                session, str(job.id), result["palette_data"]
            )

            # 3. 寫回 job
            job.svg_url = result["svg_url"]
            job.filled_template_url = result["filled_template_url"]
            job.snapped_rgb_url = result["snapped_rgb_url"]
            job.palette_json = result["palette_data"]
            job.num_colors_used = result["num_colors_used"]
            job.status = JobStatusEnum.completed
            # 清掉舊的 [Phase 2-B] 標記（如果先前 stub 階段留下）
            if job.notes and _PHASE2B_NOTE_PREFIX in job.notes:
                cleaned = "\n".join(
                    line for line in job.notes.split("\n")
                    if _PHASE2B_NOTE_PREFIX not in line
                ).strip()
                job.notes = cleaned or None

            try:
                await session.commit()
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "run_post_process_job: final commit failed for %s — rolling back blobs",
                    job_id,
                )
                try:
                    await session.rollback()
                except Exception as rb:  # noqa: BLE001
                    logger.warning("session rollback also failed: %s", rb)
                for p in uploaded_blob_paths:
                    _delete_blob(p)
                await _mark_job_failed(
                    job_id,
                    f"後處理寫回失敗（已清 Firebase orphan）：{type(e).__name__}: {e}",
                )
                return

            # 4. commit 成功 → 清舊 Firebase blob（best-effort，失敗只 log）
            for old_url in (old_svg_url, old_filled_url, old_snapped_url):
                _delete_blob_by_url(old_url)

            logger.info(
                "run_post_process_job: %s completed (palette %d colors)",
                job_id, result["num_colors_used"],
            )
    finally:
        await engine_db.dispose()


def _run_post_process_engine_and_upload(
    job_id: str,
    snapped_rgb_url: str,
    src_rgb: tuple[int, int, int],
    tgt_rgb: tuple[int, int, int],
    engine_params: dict[str, Any],
    uploaded_blob_paths_out: list[str],
) -> dict[str, Any]:
    """同步部分：下載 snapped → 引擎 → 上傳 3 檔（新 token，避免覆蓋舊版本）。"""
    tmp_dir = tempfile.mkdtemp(prefix=f"postproc_{job_id}_")
    try:
        # 1. 下載 snapped_rgb
        src_path = os.path.join(tmp_dir, "snapped_in.png")
        _download_image_to_path(snapped_rgb_url, src_path)

        # 2. 跑引擎
        out_dir = os.path.join(tmp_dir, "out")
        engine_result = apply_color_replacement(
            src_path, out_dir,
            src_rgb=src_rgb,
            tgt_rgb=tgt_rgb,
            **engine_params,
        )

        # 3. 上傳 3 檔（新 token，舊 url 留在 Firebase 不刪 — admin 看歷史用）
        token = uuid.uuid4().hex[:8]
        svg_blob = f"production_jobs/{job_id}/template_{token}.svg"
        filled_blob = f"production_jobs/{job_id}/filled_{token}.png"
        snapped_blob = f"production_jobs/{job_id}/snapped_{token}.png"

        svg_url = _upload_file(engine_result["svg_path"], svg_blob, "image/svg+xml")
        uploaded_blob_paths_out.append(svg_blob)
        filled_url = _upload_file(engine_result["filled_path"], filled_blob, "image/png")
        uploaded_blob_paths_out.append(filled_blob)
        snapped_url = _upload_file(
            engine_result["snapped_rgb_path"], snapped_blob, "image/png",
        )
        uploaded_blob_paths_out.append(snapped_blob)

        return {
            "svg_url": svg_url,
            "filled_template_url": filled_url,
            "snapped_rgb_url": snapped_url,
            "palette_data": engine_result["palette_data"],
            "num_colors_used": engine_result["num_colors_used"],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Cancel batch（既有，不動）──────────────────────────────────────────────────


@celery_app.task(bind=True, name="production.cancel_batch")
def cancel_batch_remaining(self, batch_id: str) -> None:
    """Cancel all pending jobs in a batch after a failure."""
    _run_async(_cancel_batch_async(batch_id))


async def _cancel_batch_async(batch_id: str) -> None:
    from sqlalchemy import update  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: PLC0415
    from sqlalchemy.pool import NullPool  # noqa: PLC0415

    from production.models import JobStatusEnum, ProductionJob  # noqa: PLC0415

    engine_db = create_async_engine(_get_db_url(), poolclass=NullPool)
    try:
        async with AsyncSession(engine_db, expire_on_commit=False) as session:
            await session.execute(
                update(ProductionJob)
                .where(
                    ProductionJob.batch_id == batch_id,
                    ProductionJob.status == JobStatusEnum.pending,
                )
                .values(status=JobStatusEnum.cancelled)
            )
            await session.commit()
    finally:
        await engine_db.dispose()


# silence unused-import linting in some envs
_ = traceback
