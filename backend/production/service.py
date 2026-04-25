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
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=timedelta(minutes=_UPLOAD_TTL_MINUTES),
        method="PUT",
        content_type=content_type,
    )
    public_url = f"https://storage.googleapis.com/{bucket.name}/{path}"
    return {"upload_url": upload_url, "public_url": public_url}


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
