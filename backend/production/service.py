import io
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from celery import chain
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestError, NotFoundError
from core.firebase import get_bucket
from production.models import Image, ProductionJob
from production.tasks import cancel_batch_remaining, run_post_process_job, run_production_job

logger = logging.getLogger(__name__)

_UPLOAD_TTL_MINUTES = 15


def generate_upload_signed_url(filename: str, content_type: str) -> dict:
    bucket = get_bucket()
    safe_name = filename.replace(" ", "_")
    path = f"production_images/{uuid.uuid4().hex}_{safe_name}"
    blob = bucket.blob(path)
    ttl = timedelta(minutes=_UPLOAD_TTL_MINUTES)
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=ttl,
        method="PUT",
        content_type=content_type,
    )
    public_url = f"https://storage.googleapis.com/{bucket.name}/{path}"
    return {
        "upload_url": upload_url,
        "public_url": public_url,
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

    batch_id = uuid.uuid4() if len(jobs_params) > 1 else None

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

    _dispatch_tasks(created_jobs, batch_id)

    return {
        "batch_id": batch_id,
        "job_ids": [j.id for j in created_jobs],
    }


def _dispatch_tasks(jobs: list[ProductionJob], batch_id: uuid.UUID | None) -> None:
    tasks = [run_production_job.si(str(j.id)) for j in jobs]
    if len(tasks) == 1:
        tasks[0].delay()
    else:
        error_cb = cancel_batch_remaining.si(str(batch_id))
        chain(*[t.set(link_error=[error_cb]) for t in tasks]).delay()


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
    return list(result.scalars().all()), total


async def get_job(db: AsyncSession, job_id: UUID) -> ProductionJob:
    result = await db.execute(select(ProductionJob).where(ProductionJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("製作任務不存在")
    return job


_FILE_FIELD_MAP = {"svg": "svg_url", "snapped_rgb": "snapped_rgb_url"}


def _make_signed_url(raw_url: str) -> str:
    bucket = get_bucket()
    parts = raw_url.split(f"/{bucket.name}/", 1)
    if len(parts) != 2:
        raise BadRequestError(f"無法解析 Firebase 路徑：{raw_url}")
    blob = bucket.blob(parts[1])
    return blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=_UPLOAD_TTL_MINUTES),
        method="GET",
    )


async def get_job_signed_url(
    db: AsyncSession, job_id: UUID, file: str
) -> str | None:
    field = _FILE_FIELD_MAP.get(file)
    if field is None:
        raise BadRequestError(f"不支援的檔案：{file}，可選值：{', '.join(_FILE_FIELD_MAP)}")
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
    drawing, png_bytes = await _render_svg_with_fallbacks(job.svg_url, w_cm, h_cm)
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
