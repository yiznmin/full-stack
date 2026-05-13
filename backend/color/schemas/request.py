import re

from pydantic import BaseModel, field_validator, model_validator

_HEX_PATTERN = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _hex_to_rgb(hex_str: str) -> list[int]:
    m = _HEX_PATTERN.match(hex_str.strip())
    if not m:
        raise ValueError("hex 格式應為 #RRGGBB 或 RRGGBB（六位 0-9/a-f）")
    h = m.group(1)
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)]


class CreateColorRequest(BaseModel):
    code: str
    name: str
    color_family: str | None = None
    brand: str | None = None
    rgb: list[int]

    @field_validator("rgb")
    @classmethod
    def validate_rgb(cls, v: list[int]) -> list[int]:
        if len(v) != 3:
            raise ValueError("rgb 必須為 3 個元素的陣列 [R, G, B]")
        if not all(0 <= c <= 255 for c in v):
            raise ValueError("RGB 各值必須在 0 ~ 255 之間")
        return v
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


class UpdateColorRequest(BaseModel):
    """部分更新實體色 metadata（PATCH 語義）。

    所有欄位皆 optional —— 前端 EditColorDialog 只送有變動的欄位以避免不必要寫入。
    RGB 校正必須走 PATCH /admin/colors/{id}/rgb（保留 audit trail）。

    注意：欄位有提供時不可為空字串；未提供（None）= 不改該欄位。
    """
    code: str | None = None
    name: str | None = None
    color_family: str | None = None
    brand: str | None = None
    stock_ml: float | None = None

    @field_validator("code", "name")
    @classmethod
    def validate_not_empty(cls, v: str | None) -> str | None:
        # None = 不更新該欄位；有提供就必須非空白
        if v is None:
            return v
        if not v.strip():
            raise ValueError("不可為空白字串")
        return v

    @field_validator("stock_ml")
    @classmethod
    def validate_stock(cls, v: float | None) -> float | None:
        if v is None:
            return v
        if v < 0:
            raise ValueError("stock_ml 不可為負數")
        return v

    @model_validator(mode="after")
    def validate_set_fields(self) -> "UpdateColorRequest":
        # 用 model_fields_set 區分「省略」vs「顯式 null」：
        # - 前端 undefined → 欄位不在 model_fields_set → 不改該欄位
        # - 前端 null → 在 set 但值為 None → 顯式清空（只 color_family / brand 可清）
        if not self.model_fields_set:
            raise ValueError("至少需提供一個要更新的欄位")
        # code / name / stock_ml 顯式設 null 不合法（DB NOT NULL）
        for f in ("code", "name", "stock_ml"):
            if f in self.model_fields_set and getattr(self, f) is None:
                raise ValueError(f"{f} 不可設為 null")
        return self


class AddStockRequest(BaseModel):
    add_ml: float

    @field_validator("add_ml")
    @classmethod
    def validate_range(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("add_ml 必須大於 0")
        # NUMERIC(10,2) 理論上限近 1 億，單次進貨設個合理上限避免誤打
        if v > 1_000_000:
            raise ValueError("add_ml 單次最多 1,000,000 ml")
        # 保留兩位小數（NUMERIC(10,2) 對齊）
        if round(v * 100) / 100 != v:
            raise ValueError("add_ml 最多兩位小數")
        return v


class UpdateRgbRequest(BaseModel):
    """校正實體色 RGB 用的彈跳視窗輸入：hex 或 rgb 二擇一必填。"""
    hex: str | None = None
    rgb: list[int] | None = None

    @model_validator(mode="after")
    def normalize(self):
        if self.hex is None and self.rgb is None:
            raise ValueError("hex 或 rgb 至少需提供一個")
        if self.hex is not None and self.rgb is not None:
            raise ValueError("hex 與 rgb 不能同時提供，請二擇一")
        if self.hex is not None:
            # 統一在 model_validator 把 hex 轉成 rgb
            self.rgb = _hex_to_rgb(self.hex)
        if len(self.rgb) != 3:
            raise ValueError("rgb 必須為 3 個元素的陣列 [R, G, B]")
        if not all(isinstance(c, int) and 0 <= c <= 255 for c in self.rgb):
            raise ValueError("RGB 各值必須為 0-255 整數")
        return self


class RevertRgbRequest(BaseModel):
    """還原 RGB 到指定的歷史版本。"""
    history_id: str

    @field_validator("history_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        from uuid import UUID
        try:
            UUID(v)
        except ValueError as exc:
            raise ValueError("history_id 必須為合法 UUID") from exc
        return v
