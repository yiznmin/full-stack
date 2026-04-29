from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import require_admin
from product import service as product_service
from product.schemas.response import AvailableJobListResponse
from production import service
from production.schemas.request import (
    ApproveRequest,
    CreateImageRequest,
    CreateJobsRequest,
    EliminateBorderRequest,
    MergeColorRequest,
    SmoothContourRequest,
)
from production.schemas.response import (
    CreateJobsResponse,
    ImageListResponse,
    ImageResponse,
    JobDetailResponse,
    JobListResponse,
    SignedUrlResponse,
)

router = APIRouter(tags=["Admin - Production"])


@router.post("/admin/images", response_model=ImageResponse, status_code=201)
async def create_image(
    body: CreateImageRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.create_image(db, operator.id, body.model_dump())


@router.get("/admin/images", response_model=ImageListResponse)
async def list_images(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    images, total = await service.list_images(db, page, page_size)
    return ImageListResponse(items=images, total=total, page=page, page_size=page_size)


@router.post("/admin/production/jobs", response_model=CreateJobsResponse, status_code=201)
async def create_jobs(
    body: CreateJobsRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    jobs_params = [j.model_dump() for j in body.jobs]
    result = await service.create_jobs(
        db, body.image_id, body.custom_request_id, jobs_params
    )
    return CreateJobsResponse(**result)


@router.get("/admin/production/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Literal[
        "pending", "processing", "completed", "failed", "cancelled"
    ] | None = Query(default=None),
    approved: bool | None = Query(default=None),
    batch_id: UUID | None = Query(default=None),
    image_id: UUID | None = Query(default=None),
    custom_request_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    jobs, total = await service.list_jobs(
        db, status, approved, batch_id, image_id, custom_request_id, page, page_size
    )
    return JobListResponse(items=jobs, total=total, page=page, page_size=page_size)


@router.get(
    "/admin/production/jobs/available-for-variant",
    response_model=AvailableJobListResponse,
)
async def list_available_jobs(
    product_id: UUID | None = Query(default=None),
    _: None = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    items = await product_service.list_available_jobs(db, product_id)
    return {"items": items}


@router.get("/admin/production/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_job(db, job_id)


@router.get("/admin/production/jobs/{job_id}/signed-url", response_model=SignedUrlResponse)
async def get_job_signed_url(
    job_id: UUID,
    file: str = Query(),
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    url = await service.get_job_signed_url(db, job_id, file)
    return SignedUrlResponse(url=url)


@router.post("/admin/production/jobs/{job_id}/approve", response_model=JobDetailResponse)
async def approve_job(
    job_id: UUID,
    body: ApproveRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.approve_job(db, job_id, body.notes)


@router.post("/admin/production/jobs/{job_id}/unapprove", response_model=JobDetailResponse)
async def unapprove_job(
    job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.unapprove_job(db, job_id)


@router.post(
    "/admin/production/jobs/{job_id}/post-process/merge-color",
    response_model=JobDetailResponse,
    status_code=202,
)
async def post_process_merge_color(
    job_id: UUID,
    body: MergeColorRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.post_process(db, job_id, body.model_dump())


@router.post(
    "/admin/production/jobs/{job_id}/post-process/eliminate-border",
    response_model=JobDetailResponse,
    status_code=202,
)
async def post_process_eliminate_border(
    job_id: UUID,
    body: EliminateBorderRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.post_process(db, job_id, body.model_dump())


@router.post(
    "/admin/production/jobs/{job_id}/post-process/smooth-contour",
    response_model=JobDetailResponse,
    status_code=202,
)
async def post_process_smooth_contour(
    job_id: UUID,
    body: SmoothContourRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.post_process(db, job_id, body.model_dump())


@router.get(
    "/admin/production/jobs/{job_id}/export-pdf",
    response_model=None,  # binary stream — no Pydantic model
    response_class=Response,
)
async def export_job_pdf(
    job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """SVG → 單頁 PDF（即時轉換 + 四周 5cm 留白），直接 stream 下載。"""
    pdf_bytes = await service.export_job_pdf(db, job_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="job-{job_id}.pdf"'},
    )
