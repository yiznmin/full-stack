from pydantic import BaseModel, field_validator


class RgbValue(BaseModel):
    rgb_r: int
    rgb_g: int
    rgb_b: int

    @field_validator("rgb_r", "rgb_g", "rgb_b")
    @classmethod
    def validate_channel(cls, v: int) -> int:
        if not (0 <= v <= 255):
            raise ValueError("RGB 各值必須在 0 ~ 255 之間")
        return v


class CreateColorRequest(BaseModel):
    code: str
    name: str
    color_family: str | None = None
    brand: str | None = None
    rgb: RgbValue
    stock_ml: float = 0.0

    @field_validator("code", "name")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("不可為空白字串")
        return v

    @field_validator("stock_ml")
    @classmethod
    def validate_stock(cls, v: float) -> float:
        if v < 0:
            raise ValueError("stock_ml 不可為負數")
        return v


class UpdateColorRequest(CreateColorRequest):
    pass


class AddStockRequest(BaseModel):
    add_ml: float

    @field_validator("add_ml")
    @classmethod
    def validate_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("add_ml 必須大於 0")
        return v
