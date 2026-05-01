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
    apply_region_replacements,
    generate_sam_refine,
    generate_sam_weighted,
    generate_standard,
    get_polygon_rgb,
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

    支援三種 mode：standard / sam_refine / sam_weighted。
    sam_* 路徑要求 mask_url 已存在（admin 透過 sam-mask endpoint 編輯後寫入）。
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

            if job.image_id is None:
                job.status = JobStatusEnum.failed
                job.notes = "缺少 image_id（custom_request 路徑請先指派 image）"
                await session.commit()
                return

            # sam_* 模式必須先有 mask_url（admin 透過 sam-mask endpoint 編輯後才會有）
            if job.mode != "standard" and not job.mask_url:
                job.status = JobStatusEnum.failed
                job.notes = (
                    f"mode={job.mode} 但缺 mask_url（請先在製作系統編輯遮罩再送出）"
                )
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
            sam_kwargs = _resolve_sam_kwargs(job)
            try:
                result = await asyncio.to_thread(
                    _run_engine_and_upload,
                    str(job.id),
                    image.original_url,
                    _resolve_params(job),
                    uploaded_blob_paths,
                    str(job.mode),
                    job.mask_url,
                    sam_kwargs,
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


def _resolve_sam_kwargs(job) -> dict[str, Any]:
    """解 sam_refine / sam_weighted 額外參數。standard mode 回空 dict（無作用）。

    - extra_colors：sam_refine 用，從 job 取（建立時 validator 已驗 > 0）
    - weight_ratio：sam_weighted 用，預設 0.65（schema DEFAULT 一致；建立時 validator 已驗 0.5~0.8）
    - bg_extra_blur：sam_weighted 用，缺失時取 detail preset 值（admin_production.md §1.2 表）；
      與 resolve_engine_params 同樣假設 admin 後台目前只暴露 difficulty，detail 用「標準」。
    """
    from production.engine import DETAIL_PRESETS  # noqa: PLC0415

    mode = str(job.mode)
    if mode == "sam_refine":
        return {"extra_colors": int(job.extra_colors) if job.extra_colors is not None else 0}
    if mode == "sam_weighted":
        # 標準 detail 的 bg_extra_blur=21（admin_production.md §1.2 表）
        bg_default = DETAIL_PRESETS["標準"]["bg_extra_blur"]
        return {
            "weight_ratio": float(job.weight_ratio) if job.weight_ratio is not None else 0.65,
            "bg_extra_blur": (
                int(job.bg_extra_blur) if job.bg_extra_blur is not None else bg_default
            ),
        }
    return {}


def _run_engine_and_upload(
    job_id: str,
    image_url: str,
    params: dict[str, Any],
    uploaded_blob_paths_out: list[str],
    mode: str = "standard",
    mask_url: str | None = None,
    sam_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """同步部分：下載 → 引擎 → 上傳。在 thread 中跑（避免 block event loop）。

    uploaded_blob_paths_out 是個 list，會 in-place append 已上傳的 blob path，
    讓外層在後續失敗時可以反向刪除。

    mode / mask_url / sam_kwargs 用於 sam_refine / sam_weighted 路徑（Phase A）。
    """
    sam_kwargs = sam_kwargs or {}
    tmp_dir = tempfile.mkdtemp(prefix=f"prod_{job_id}_")
    try:
        # 1. 下載原圖
        ext = os.path.splitext(image_url.split("?", 1)[0])[1] or ".jpg"
        src_path = os.path.join(tmp_dir, f"src{ext}")
        _download_image_to_path(image_url, src_path)

        # 2. 跑引擎（依 mode dispatch）
        out_dir = os.path.join(tmp_dir, "out")
        if mode == "standard":
            engine_result = generate_standard(src_path, out_dir, **params)
        else:
            # sam_refine / sam_weighted：先下載 mask
            if not mask_url:
                raise ValueError(f"mode={mode} 缺 mask_url（外層應已早 fail）")
            mask_path = os.path.join(tmp_dir, "mask.png")
            _download_image_to_path(mask_url, mask_path)

            if mode == "sam_refine":
                engine_result = generate_sam_refine(
                    src_path, out_dir,
                    mask_path=mask_path,
                    **params,
                    **sam_kwargs,
                )
            elif mode == "sam_weighted":
                # sam_weighted 不走 set_final_pbn，砍掉 blur_*
                weighted_params = {
                    k: v for k, v in params.items()
                    if k not in ("blur_ksize", "blur_sigma_color", "blur_sigma_space")
                }
                engine_result = generate_sam_weighted(
                    src_path, out_dir,
                    mask_path=mask_path,
                    **weighted_params,
                    **sam_kwargs,
                )
            else:
                raise ValueError(f"未支援的 mode：{mode}")

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


class _PostProcessOp:
    """區域層級後處理 op 描述。

    - polygon_ids：要被改色的 polygon id 列表（A 是 1 個、B 也是 1 個 = absorbed）
    - tgt_rgb：目標 RGB；A 從 target_template_id 對應，B 從 surviving_polygon_id 對應
    """
    def __init__(self, polygon_ids: list[str], tgt_rgb: tuple[int, int, int]):
        self.polygon_ids = polygon_ids
        self.tgt_rgb = tgt_rgb


def _find_rgb_in_palette(palette_json: list, template_id: int) -> tuple[int, int, int] | None:
    """從 palette_json 中找對應 template_id 的 RGB（list[int] 三元組）。"""
    for item in palette_json or []:
        if int(item.get("template_id", -1)) == template_id:
            rgb = item.get("rgb")
            if isinstance(rgb, list) and len(rgb) == 3:
                return tuple(int(v) for v in rgb)
    return None


def _resolve_single_op(
    params: dict,
    palette_json: list,
    snapped_rgb_path: str,
    svg_path: str,
) -> _PostProcessOp:
    """單一 op：A {polygon_id, target_template_id} 或 B {absorbed_polygon_id, surviving_polygon_id}
    或 batch op {op: "merge_color"/"eliminate_border", ...}。
    """
    op_type = params.get("op")

    # 原 single op 格式（A）或 batch op="merge_color"
    if op_type == "merge_color" or (
        op_type is None and "polygon_id" in params and "target_template_id" in params
    ):
        polygon_id = params.get("polygon_id")
        target_template_id = params.get("target_template_id")
        if polygon_id is None or target_template_id is None:
            raise ValueError(
                "merge_color op 缺欄位（需要 polygon_id 與 target_template_id）"
            )
        tgt_rgb = _find_rgb_in_palette(palette_json or [], int(target_template_id))
        if tgt_rgb is None:
            raise ValueError(
                f"找不到 target_template_id={target_template_id} 在 palette_json 中"
            )
        return _PostProcessOp(polygon_ids=[str(polygon_id)], tgt_rgb=tgt_rgb)

    # 原 single op 格式（B）或 batch op="eliminate_border"
    if op_type == "eliminate_border" or (
        op_type is None
        and "absorbed_polygon_id" in params
        and "surviving_polygon_id" in params
    ):
        absorbed = params.get("absorbed_polygon_id")
        surviving = params.get("surviving_polygon_id")
        if absorbed is None or surviving is None:
            raise ValueError(
                "eliminate_border op 缺欄位（需要 absorbed_polygon_id 與 surviving_polygon_id）"
            )
        absorbed = str(absorbed)
        surviving = str(surviving)
        if absorbed == surviving:
            raise ValueError("absorbed_polygon_id 與 surviving_polygon_id 不可相同")
        tgt_rgb = get_polygon_rgb(snapped_rgb_path, svg_path, surviving)
        return _PostProcessOp(polygon_ids=[absorbed], tgt_rgb=tgt_rgb)

    raise ValueError(
        f"無法判斷後處理操作類型；params keys={sorted(params.keys())}"
    )


def _resolve_post_process_op(
    params: dict,
    palette_json: list,
    snapped_rgb_path: str,
    svg_path: str,
) -> list[_PostProcessOp]:
    """解出 op list（可能 1 個或多個）。

    支援兩種輸入：
    1. **Batch**：{operations: [{op, ...}, {op, ...}, ...]}
    2. **Single**（向後相容）：{polygon_id, target_template_id} 或
       {absorbed_polygon_id, surviving_polygon_id}
    """
    if isinstance(params.get("operations"), list):
        if not params["operations"]:
            raise ValueError("operations 不能為空")
        return [
            _resolve_single_op(o, palette_json, snapped_rgb_path, svg_path)
            for o in params["operations"]
        ]
    # 向後相容：單一 op
    return [_resolve_single_op(params, palette_json, snapped_rgb_path, svg_path)]


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

            if not job.snapped_rgb_url or not job.svg_url:
                job.status = JobStatusEnum.failed
                job.notes = (
                    "缺少 snapped_rgb_url 或 svg_url（job 可能未跑過引擎或檔案被清掉）"
                )
                await session.commit()
                return

            # 0a. 記住舊 url，commit 成功後清 Firebase orphan
            old_svg_url = job.svg_url
            old_filled_url = job.filled_template_url
            old_snapped_url = job.snapped_rgb_url

            # 1. 下載 snapped+SVG、解析 op、跑引擎、上傳新檔
            try:
                result = await asyncio.to_thread(
                    _run_post_process_engine_and_upload,
                    str(job.id),
                    job.snapped_rgb_url,
                    job.svg_url,
                    params,
                    list(job.palette_json or []),
                    {
                        "canvas_w_cm": float(job.canvas_w_cm),
                        "canvas_h_cm": float(job.canvas_h_cm),
                        "min_brush_diam_cm": float(job.min_brush_diam_cm or 1.0),
                        "min_ratio_multiplier": float(job.min_ratio_multiplier or 1.0),
                    },
                    uploaded_blob_paths,
                )
            except ValueError as e:
                # ValueError = 參數錯誤（polygon_id 不在 SVG、palette 找不到 target_template_id）
                logger.warning("post_process: bad params for %s — %s", job_id, e)
                for p in uploaded_blob_paths:
                    _delete_blob(p)
                job.status = JobStatusEnum.failed
                job.notes = f"後處理參數錯誤：{e}"[:500]
                await session.commit()
                return
            except Exception as e:  # noqa: BLE001
                logger.exception("run_post_process_job: engine/upload failed for %s", job_id)
                for p in uploaded_blob_paths:
                    _delete_blob(p)
                job.status = JobStatusEnum.failed
                job.notes = f"後處理失敗：{type(e).__name__}: {e}"[:500]
                await session.commit()
                return

            # 2-3. 寫回 job 欄位（不 commit）
            job.svg_url = result["svg_url"]
            job.filled_template_url = result["filled_template_url"]
            job.snapped_rgb_url = result["snapped_rgb_url"]
            job.palette_json = result["palette_data"]
            job.num_colors_used = result["num_colors_used"]
            job.status = JobStatusEnum.completed
            if job.notes and _PHASE2B_NOTE_PREFIX in job.notes:
                cleaned = "\n".join(
                    line for line in job.notes.split("\n")
                    if _PHASE2B_NOTE_PREFIX not in line
                ).strip()
                job.notes = cleaned or None

            # 4. remap mappings + commit 包在同一個 try 區塊：
            # remap 失敗（如 UNIQUE 衝突或 DB 暫時錯）必須走 rollback + 清 blob 路徑，
            # 否則新 blob 會 orphan + job 卡 processing
            try:
                await _remap_palette_color_mappings(
                    session, str(job.id), result["palette_data"]
                )
                await session.commit()
            except Exception as e:  # noqa: BLE001
                logger.exception(
                    "run_post_process_job: remap or commit failed for %s — rolling back blobs",
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
    svg_url: str,
    params: dict,
    palette_json: list,
    engine_params: dict[str, Any],
    uploaded_blob_paths_out: list[str],
) -> dict[str, Any]:
    """同步部分：下載 snapped + SVG → 解析 op（區域層級）→ 跑引擎 → 上傳 3 檔。

    parse op 在這裡跑（不在外層 async）的理由：op 解析需要存取 SVG 檔案來確認
    polygon_id 存在 + 採樣 surviving 格 RGB（B 操作），SVG 必須先下載到 tmp。
    """
    tmp_dir = tempfile.mkdtemp(prefix=f"postproc_{job_id}_")
    try:
        # 1. 下載 snapped + svg
        snapped_path = os.path.join(tmp_dir, "snapped_in.png")
        svg_in_path = os.path.join(tmp_dir, "template_in.svg")
        _download_image_to_path(snapped_rgb_url, snapped_path)
        _download_image_to_path(svg_url, svg_in_path)

        # 2. 解析 ops（list）— 可能 raise ValueError → 外層轉 status=failed
        ops = _resolve_post_process_op(params, palette_json, snapped_path, svg_in_path)

        # 3. 跑引擎（批次 — 多個 ops 一次性套用，只重產一次 SVG/filled）
        out_dir = os.path.join(tmp_dir, "out")
        engine_result = apply_region_replacements(
            snapped_path,
            svg_in_path,
            out_dir,
            ops=[
                {"polygon_ids": op.polygon_ids, "tgt_rgb": op.tgt_rgb}
                for op in ops
            ],
            **engine_params,
        )

        # 4. 上傳 3 檔（新 token；舊 blob 在外層 commit 成功後另外清掉，避免 orphan）
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
    """Cancel batch 內仍 pending 的 job。

    sam_* 模式只 cancel **已就緒**（mask_url 不為 null）的 pending；等待補 mask 的
    pending sam_* job（mask_url=null）不該被誤 cancel — admin 補完 mask 還能重點 start_batch。
    """
    from sqlalchemy import or_, update  # noqa: PLC0415
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
                    or_(
                        ProductionJob.mode == "standard",
                        ProductionJob.mask_url.is_not(None),
                    ),
                )
                .values(status=JobStatusEnum.cancelled)
            )
            await session.commit()
    finally:
        await engine_db.dispose()


# silence unused-import linting in some envs
_ = traceback
