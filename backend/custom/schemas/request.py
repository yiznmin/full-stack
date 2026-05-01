from typing import Literal
from uuid import UUID

from pydantic import BaseModel, model_validator


class CreateCustomRequestRequest(BaseModel):
    request_type: Literal["custom_photo", "custom_spec"]
    photo_url: str | None = None
    ref_product_id: UUID | None = None
    canvas_w_cm: int | None = None
    canvas_h_cm: int | None = None
    difficulty: Literal["beginner", "elementary", "intermediate", "advanced"] | None = None
    detail: Literal["rough", "standard", "detailed", "premium"] | None = None
    customer_notes: str | None = None
    parent_request_id: UUID | None = None

    @model_validator(mode="after")
    def validate_type_specific_fields(self):
        if self.request_type == "custom_photo" and not self.photo_url:
            raise ValueError("custom_photo 必須上傳照片")
        if self.request_type == "custom_spec" and self.ref_product_id is None:
            raise ValueError("custom_spec 必須指定 ref_product_id")
        return self


class PostMessageRequest(BaseModel):
    message: str = ""
    # 訊息附帶圖片（admin 寄範例參考圖、客戶補充照片）
    image_url: str | None = None

    @model_validator(mode="after")
    def validate_message(self):
        # message 與 image_url 至少要有一個 — 純圖片訊息允許 message=""
        if not self.message.strip() and not (self.image_url and self.image_url.strip()):
            raise ValueError("訊息不可全空（需文字或圖片）")
        return self


class UpdatePhotoRequest(BaseModel):
    photo_url: str

    @model_validator(mode="after")
    def validate_url(self):
        if not self.photo_url.strip():
            raise ValueError("photo_url 不可為空")
        return self


class ConfirmQuoteRequest(BaseModel):
    shipping_profile_id: UUID


class RejectQuoteRequest(BaseModel):
    reason: str | None = None


class RequestRevisionRequest(BaseModel):
    reason: str

    @model_validator(mode="after")
    def validate_reason(self):
        if not self.reason.strip():
            raise ValueError("reason 不可為空")
        return self


class AdminSendQuoteRequest(BaseModel):
    quoted_price: float
    detail: Literal["rough", "standard", "detailed", "premium"] | None = None
    surcharge_ids: list[UUID] | None = None
    quote_note: str | None = None

    @model_validator(mode="after")
    def validate_price(self):
        if self.quoted_price <= 0:
            raise ValueError("報價金額需大於 0")
        return self
