from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import require_admin
from palette import service
from palette.schemas.request import UpdateMappingRequest
from palette.schemas.response import (
    CompleteResponse,
    CopyCandidateItem,
    CopyCandidatesResponse,
    PaletteMappingListResponse,
    PaletteMappingResponse,
)

router = APIRouter(tags=["Admin - Palette Mappings"])

BASE = "/admin/production/jobs/{job_id}/palette-mappings"


@router.get(BASE, response_model=PaletteMappingListResponse)
async def get_mappings(
    job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    mappings = await service.get_mappings(db, job_id)
    return PaletteMappingListResponse(
        mappings=[PaletteMappingResponse(**m) for m in mappings]
    )


@router.put(BASE + "/{template_id}", response_model=PaletteMappingResponse)
async def update_mapping(
    job_id: UUID,
    template_id: int,
    body: UpdateMappingRequest,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    mapping = await service.update_mapping(db, job_id, template_id, body.physical_color_id)
    return PaletteMappingResponse(**mapping)


@router.get(BASE + "/copy-candidates", response_model=CopyCandidatesResponse)
async def list_copy_candidates(
    job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """admin_color.md §2.2：列出可複製對應的 source jobs（同 batch_id / image_id 且已對應完整）。"""
    items = await service.list_copy_candidates(db, job_id)
    return CopyCandidatesResponse(items=[CopyCandidateItem(**i) for i in items])


@router.post(BASE + "/copy-from/{source_job_id}", response_model=PaletteMappingListResponse)
async def copy_from_job(
    job_id: UUID,
    source_job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    mappings = await service.copy_from_job(db, job_id, source_job_id)
    return PaletteMappingListResponse(
        mappings=[PaletteMappingResponse(**m) for m in mappings]
    )


@router.post(BASE + "/complete", response_model=CompleteResponse)
async def complete_mappings(
    job_id: UUID,
    operator=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await service.complete_mappings(db, job_id)
    return CompleteResponse(**result)
