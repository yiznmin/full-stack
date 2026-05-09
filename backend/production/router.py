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
    BatchPostProcessRequest,
    CreateImageRequest,
    CreateJobsRequest,
    EliminateBorderRequest,
    MergeColorRequest,
    SamMaskRequest,
    SuggestCanvasSizesRequest,
)
from production.schemas.response import (
    BatchStartResponse,
    CreateJobsResponse,
    ImageListResponse,
    ImageResponse,
    JobDetailResponse,
    JobListResponse,
    SamMaskResponse,
    SignedUrlResponse,
    SuggestCanvasSizesResponse,
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


@router.post(
    "/admin/production/batches/{batch_id}/start",
    response_model=BatchStartResponse,
)
async def start_batch(
    batch_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """admin 編完 sam_* 批次的所有遮罩後，觸發整批進 Celery 佇列。

    詳見 api.md POST /admin/production/batches/{batch_id}/start。
    """
    return await service.start_batch(db, batch_id)


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


@router.delete(
    "/admin/production/jobs/{job_id}",
    status_code=204,
    response_class=Response,
)
async def delete_job(
    job_id: UUID,
    force: bool = Query(default=False),
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """硬刪除製作任務 + 連帶子資料 + Firebase 物件。

    安全規則：
    - status=processing → 400（worker 在跑）
      - 但若帶 ?force=true，允許強制刪除（用於 worker 卡死 / 永遠不結束的 zombie task；
        DB row 直接刪掉，背景 worker 仍會跑但完工後找不到 row 會 silent 失敗，
        產出的 Firebase 物件成 orphan — caller 已知接受此 trade-off）
    - 被 product_variants / print_batches / order_items 引用 → 400 含計數
    - palette_color_mappings 自動連帶刪
    - Firebase svg/filled/snapped_rgb/mask 物件 best-effort 刪
    """
    await service.delete_job(db, job_id, force=force)
    return Response(status_code=204)


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
    "/admin/production/jobs/{job_id}/post-process/batch",
    response_model=JobDetailResponse,
    status_code=202,
)
async def post_process_batch(
    job_id: UUID,
    body: BatchPostProcessRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """批次後處理：在同一個 Celery 任務內按順序套用所有 ops，僅一次 SVG 重產 + 上傳。"""
    ops = [op.model_dump() for op in body.operations]
    return await service.post_process(db, job_id, {"operations": ops})


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
    "/admin/production/jobs/{job_id}/sam-mask",
    response_model=SamMaskResponse,
)
async def update_sam_mask(
    job_id: UUID,
    body: SamMaskRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """SAM 遮罩編輯（僅 status=pending 可改；polygons 即時生成 PNG，sam_points 等 Celery 推論）。"""
    return await service.update_sam_mask(
        db,
        job_id,
        sam_points=[p.model_dump() for p in body.sam_points] if body.sam_points else None,
        polygons=body.polygons,
        mode=body.mode,
    )


@router.post(
    "/admin/production/canvas-sizes/recommend",
    response_model=SuggestCanvasSizesResponse,
)
async def recommend_canvas_sizes(
    body: SuggestCanvasSizesRequest,
    operator=Depends(require_admin),
):
    """根據圖片像素比例，從 17 種標準畫布規格中推薦比例最接近的 N 個。"""
    items = service.suggest_canvas_sizes(body.width, body.height, body.n)
    return {"items": items}


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
