from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CustomRequestMessageResponse(BaseModel):
    id: UUID
    request_id: UUID
    sender_type: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class CustomRequestSummary(BaseModel):
    id: UUID
    request_type: str
    status: str
    quoted_price: float | None
    quote_expires_at: datetime | None
    is_extended: bool
    revision_count: int
    order_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class CustomRequestListResponse(BaseModel):
    items: list[CustomRequestSummary]
    total: int
    page: int
    page_size: int


class CustomRequestDetailResponse(BaseModel):
    id: UUID
    user_id: UUID
    request_type: str
    status: str
    photo_url: str | None
    ref_product_id: UUID | None
    canvas_w_cm: int | None
    canvas_h_cm: int | None
    difficulty: str | None
    detail: str | None
    customer_notes: str | None
    quoted_price: float | None
    quote_expires_at: datetime | None
    is_extended: bool
    revision_count: int
    parent_request_id: UUID | None
    order_id: UUID | None
    created_at: datetime
    quoted_at: datetime | None
    rejected_at: datetime | None
    messages: list[CustomRequestMessageResponse]


class AdminCustomRequestSummary(BaseModel):
    id: UUID
    request_type: str
    status: str
    user_id: UUID
    user_name: str
    user_email: str
    quoted_price: float | None
    quote_expires_at: datetime | None
    revision_count: int
    created_at: datetime


class AdminCustomRequestListResponse(BaseModel):
    items: list[AdminCustomRequestSummary]
    total: int
    page: int
    page_size: int


class AdminCustomRequestDetailResponse(CustomRequestDetailResponse):
    user_name: str
    user_email: str
    admin_notes: str | None


class CreateCustomRequestResponse(BaseModel):
    id: UUID
    request_type: str
    status: str
    created_at: datetime


class UpdatePhotoResponse(BaseModel):
    id: UUID
    photo_url: str
    updated_at: datetime


class QuoteSummaryResponse(BaseModel):
    custom_request_id: UUID
    spec_summary: dict
    quoted_price: float
    quote_expires_at: datetime
    is_extended: bool
    revision_count: int


class ConfirmQuoteResponse(BaseModel):
    order_id: UUID
    order_number: str
    total: float
    payment_deadline: datetime
    payment_info: dict


class RejectQuoteResponse(BaseModel):
    id: UUID
    status: str
    rejected_at: datetime


class ExtendQuoteResponse(BaseModel):
    id: UUID
    quote_expires_at: datetime
    is_extended: bool


class RequestRevisionResponse(BaseModel):
    id: UUID
    status: str
    revision_count: int


class AdminSendQuoteResponse(BaseModel):
    id: UUID
    status: str
    quote_expires_at: datetime
    quoted_at: datetime
    quoted_price: float


class AdminMarkNegotiatingResponse(BaseModel):
    id: UUID
    status: str


class PhotoSignedUrlResponse(BaseModel):
    url: str
    expires_at: datetime


class StatusUpdateResponse(BaseModel):
    id: UUID
    status: str
