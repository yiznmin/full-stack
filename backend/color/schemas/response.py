from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RgbResponse(BaseModel):
    rgb_r: int
    rgb_g: int
    rgb_b: int


class PhysicalColorResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    code: str
    name: str
    color_family: str | None
    brand: str | None
    rgb: dict
    stock_ml: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ColorListResponse(BaseModel):
    items: list[PhysicalColorResponse]


class AddStockResponse(BaseModel):
    new_stock_ml: float
    fulfilled_orders: int


class ShortageItem(BaseModel):
    color_id: UUID
    code: str
    name: str
    stock_ml: float
    required_ml: float
    shortage_ml: float
    waiting_orders: int


class ShortageDashboardResponse(BaseModel):
    items: list[ShortageItem]
