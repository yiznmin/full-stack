from uuid import UUID

from pydantic import BaseModel


class AlgorithmRgbResponse(BaseModel):
    rgb_r: int
    rgb_g: int
    rgb_b: int


class PhysicalColorBriefResponse(BaseModel):
    id: UUID
    code: str
    name: str
    rgb: dict
    stock_ml: float


class PaletteMappingResponse(BaseModel):
    template_id: int
    algorithm_rgb: AlgorithmRgbResponse
    physical_color: PhysicalColorBriefResponse | None
    required_ml: float | None
    mapped_by: str


class PaletteMappingListResponse(BaseModel):
    mappings: list[PaletteMappingResponse]


class ShortageColorItem(BaseModel):
    template_id: int
    physical_color_id: UUID
    code: str
    name: str


class CompleteResponse(BaseModel):
    all_stocked: bool
    shortage_colors: list[ShortageColorItem]
