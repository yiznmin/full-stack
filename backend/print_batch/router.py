from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import require_admin
from print_batch import service
from print_batch.schemas.request import CreateBatchRequest, PreviewRequest
from print_batch.schemas.response import (
    CandidateListResponse,
    PreviewResponse,
    PrintBatchDetailResponse,
    PrintBatchListResponse,
)

router = APIRouter(tags=["Admin - Print Batch"])


@router.post(
    "/admin/print-batches/preview", response_model=PreviewResponse
)
async def preview_batch(
    body: PreviewRequest,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.preview(
        db,
        [s.model_dump() for s in body.required],
        [s.model_dump() for s in (body.candidates or [])],
    )


@router.get(
    "/admin/print-batches/candidates", response_model=CandidateListResponse
)
async def list_candidates(
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_candidates(db)


@router.post(
    "/admin/print-batches",
    status_code=201,
    response_model=PrintBatchDetailResponse,
)
async def create_batch(
    body: CreateBatchRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    batch = await service.create_batch(
        db,
        [s.model_dump() for s in body.required],
        [s.model_dump() for s in (body.candidates or [])],
        body.admin_notes,
        operator.id,
    )
    return await service.get_batch(db, batch.id)


@router.post(
    "/admin/print-batches/{batch_id}/finalize",
    response_model=PrintBatchDetailResponse,
)
async def finalize_batch(
    batch_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    batch = await service.finalize(db, batch_id)
    return await service.get_batch(db, batch.id)


@router.get(
    "/admin/print-batches", response_model=PrintBatchListResponse
)
async def list_batches(
    _=Depends(require_admin),
    status: Literal["draft", "finalized"] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_batches(db, status, page, page_size)


@router.get(
    "/admin/print-batches/{batch_id}", response_model=PrintBatchDetailResponse
)
async def get_batch(
    batch_id: UUID,
    _=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_batch(db, batch_id)
