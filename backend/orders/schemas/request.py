from datetime import date, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


class AddCartItemRequest(BaseModel):
    variant_id: UUID
    quantity: int = 1

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v < 1:
            raise ValueError("數量至少為 1")
        return v


class UpdateCartItemRequest(BaseModel):
    quantity: int

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v < 0:
            raise ValueError("數量不可為負數")
        return v


class CheckoutPreviewRequest(BaseModel):
    shipping_type: Literal["home", "seven_eleven", "family_mart"]
    user_coupon_id: UUID | None = None
    promo_code: str | None = None


class CreateOrderRequest(BaseModel):
    shipping_profile_id: UUID
    shipping_preference: Literal["together", "separate"] | None = None
    user_coupon_id: UUID | None = None
    promo_code: str | None = None
    customer_notes: str | None = None


class PaymentSubmissionRequest(BaseModel):
    transfer_amount: float
    transfer_date: date
    transfer_time: time
    account_last5: str
    notes: str | None = None

    @field_validator("account_last5")
    @classmethod
    def validate_account_last5(cls, v: str) -> str:
        if len(v) != 5 or not v.isdigit():
            raise ValueError("末五碼須為 5 位數字")
        return v


class AdminUpdateOrderStatusRequest(BaseModel):
    status: Literal[
        "paid", "processing", "shipped", "completed",
        "refund_processing", "cancelled"
    ]
    admin_notes: str | None = None


class FlagPaymentSubmissionRequest(BaseModel):
    is_flagged: Literal[True]
    admin_note: str | None = None


class UpdateShippingRequest(BaseModel):
    """修改訂單出貨資訊（user / admin 共用）。

    所有欄位 optional — caller 只送要改的欄位即可。
    對應 ShippingProfile 同樣的驗證規則（recipient_name 1-30、phone 09xxxxxxxx 等）。
    shipping_type 不可改（會影響運費計算 / 改超商需重選門市）。
    """
    recipient_name: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    district: str | None = None
    address_detail: str | None = None
    store_id: str | None = None
    store_name: str | None = None

    @field_validator("recipient_name")
    @classmethod
    def _v_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("收件人姓名不可空白")
        if len(v) > 30:
            raise ValueError("收件人姓名不可超過 30 字")
        return v

    @field_validator("phone")
    @classmethod
    def _v_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re as _re
        if not _re.fullmatch(r"09\d{8}", v):
            raise ValueError("電話格式錯誤，需為 09xxxxxxxx")
        return v

    @field_validator("city", "district")
    @classmethod
    def _v_addr(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("欄位過長")
        return v

    @field_validator("address_detail")
    @classmethod
    def _v_addr_detail(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 200:
            raise ValueError("地址不可超過 200 字")
        return v

    @field_validator("store_id")
    @classmethod
    def _v_store_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re as _re
        v = v.strip()
        if not v:
            return None
        if len(v) > 9 or not _re.fullmatch(r"[A-Za-z0-9]+", v):
            raise ValueError("門市代碼格式錯誤")
        return v

    @field_validator("store_name")
    @classmethod
    def _v_store_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("門市名稱過長")
        return v


class CreateShipmentRequest(BaseModel):
    shipment_type: Literal["fulfilled", "preorder"]


class BatchCreateShipmentRequest(BaseModel):
    """批次建單 request — 一次最多 50 筆訂單。"""
    order_ids: list[UUID]
    shipment_type: Literal["fulfilled", "preorder"] = "fulfilled"

    @field_validator("order_ids")
    @classmethod
    def validate_order_ids(cls, v: list[UUID]) -> list[UUID]:
        if not v:
            raise ValueError("至少需提供 1 筆訂單")
        if len(v) > 50:
            raise ValueError("單次批次最多 50 筆訂單")
        if len(set(v)) != len(v):
            raise ValueError("訂單 ID 不可重複")
        return v


class UpdateProductionProgressRequest(BaseModel):
    status: Literal["manufacturing", "packaging", "ready_to_ship"]
    notes: str | None = None


class RefundRequest(BaseModel):
    refund_amount: float
    returned_item_ids: list[UUID]
    cancel_reason: str | None = None

    @field_validator("refund_amount")
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("退款金額須大於 0")
        return v


class CancelOrderRequest(BaseModel):
    cancel_reason: str | None = None


class AdminNotesRequest(BaseModel):
    admin_notes: str
