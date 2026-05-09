from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PageUpsertRequest(BaseModel):
    title: str
    content: str


class SystemSettingUpsertRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    value: str


class CaseImageInputItem(BaseModel):
    """case_images 上傳項：URL 必填，sort_order 由陣列順序決定（service 端重新編號）。"""
    image_url: str = Field(min_length=1)


class CustomCaseCreateRequest(BaseModel):
    # image_url 為向後相容；前端可只傳 images（service 自動把 images[0] 同步進 image_url）
    image_url: str | None = None
    title: str
    description: str | None = None
    category_id: UUID | None = None
    canvas_w_cm: int | None = None
    canvas_h_cm: int | None = None
    difficulty: (
        Literal["beginner", "elementary", "intermediate", "advanced"] | None
    ) = None
    is_published: bool = False
    # 多圖。若提供且非空，service 會以這個 list 為準同步 case_images；
    # 沒提供 → 退回 image_url 單張行為（向後相容）。
    images: list[CaseImageInputItem] | None = None


class CustomCaseUpdateRequest(BaseModel):
    image_url: str | None = None
    title: str | None = None
    description: str | None = None
    category_id: UUID | None = None
    canvas_w_cm: int | None = None
    canvas_h_cm: int | None = None
    difficulty: (
        Literal["beginner", "elementary", "intermediate", "advanced"] | None
    ) = None
    is_published: bool | None = None
    # 提供 images 才動 case_images（即使空陣列也視為「清空」）；不傳 = 不動
    images: list[CaseImageInputItem] | None = None


class CaseCategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class CaseCategoryUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class CustomPhotoPriceUpdateRequest(BaseModel):
    price: float = Field(gt=0)


class CustomPhotoSurchargeCreateRequest(BaseModel):
    category: str
    label: str
    amount: float = Field(gt=0)
    is_active: bool = True


class CustomPhotoSurchargeUpdateRequest(BaseModel):
    category: str | None = None
    label: str | None = None
    amount: float | None = Field(default=None, gt=0)
    is_active: bool | None = None
