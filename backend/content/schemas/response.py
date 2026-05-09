from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PageResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    content: str
    updated_at: datetime


class PageListResponse(BaseModel):
    items: list[PageResponse]


class SystemSettingResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime


class SystemSettingListResponse(BaseModel):
    items: list[SystemSettingResponse]


class PublicSettingsResponse(BaseModel):
    items: dict[str, str]


class CaseImageItem(BaseModel):
    id: UUID
    image_url: str
    sort_order: int


class CustomCaseResponse(BaseModel):
    id: UUID
    image_url: str  # 主圖（= images sort_order=0 的快取，前端列表縮圖直接讀此欄位）
    title: str
    description: str | None
    category_id: UUID | None
    canvas_w_cm: int | None
    canvas_h_cm: int | None
    difficulty: str | None
    is_published: bool
    created_at: datetime
    images: list[CaseImageItem] = []


class CustomCaseListResponse(BaseModel):
    items: list[CustomCaseResponse]
    total: int
    page: int
    page_size: int


class CaseCategoryResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime


class CaseCategoryListResponse(BaseModel):
    items: list[CaseCategoryResponse]


class CustomPhotoPriceResponse(BaseModel):
    id: UUID
    canvas_w: int
    canvas_h: int
    difficulty: str
    price: float


class CustomPhotoPriceListResponse(BaseModel):
    items: list[CustomPhotoPriceResponse]


class CustomPhotoSurchargeResponse(BaseModel):
    id: UUID
    category: str
    label: str
    amount: float
    is_active: bool
    created_at: datetime


class CustomPhotoSurchargeListResponse(BaseModel):
    items: list[CustomPhotoSurchargeResponse]
