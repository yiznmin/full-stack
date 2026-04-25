from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PageUpsertRequest(BaseModel):
    title: str
    content: str


class SystemSettingUpsertRequest(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    value: str


class CustomCaseCreateRequest(BaseModel):
    image_url: str
    title: str
    description: str | None = None
    category_id: UUID | None = None
    canvas_w_cm: int | None = None
    canvas_h_cm: int | None = None
    difficulty: (
        Literal["beginner", "elementary", "intermediate", "advanced"] | None
    ) = None
    is_published: bool = False


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
