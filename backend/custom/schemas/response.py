from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CustomRequestMessageResponse(BaseModel):
    id: UUID
    request_id: UUID
    sender_type: str
    message: str
    image_url: str | None = None
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
    # plain token — owner 從 detail 直接 router.push 到 /custom/quote/:token
    # （該 endpoint 已驗 owner，所以 token 對 owner 不是 secret）
    quote_token: str | None = None
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
    # 客戶 quote viewer 訪問追蹤（admin 監看用）
    view_count: int = 0
    last_viewed_at: datetime | None = None


class CreateCustomRequestResponse(BaseModel):
    id: UUID
    request_type: str
    status: str
    created_at: datetime


class UpdatePhotoResponse(BaseModel):
    id: UUID
    photo_url: str
    updated_at: datetime


class QuoteMessageItem(BaseModel):
    id: UUID
    sender_type: str  # 'admin' | 'customer'
    message: str
    image_url: str | None
    created_at: datetime


class QuoteSummaryResponse(BaseModel):
    custom_request_id: UUID
    spec_summary: dict
    quoted_price: float
    quote_expires_at: datetime
    is_extended: bool
    revision_count: int
    # 客戶看到的訊息對話（admin/customer 雙向）
    messages: list[QuoteMessageItem]
    # 是否有可預覽的 production_job → 客戶 viewer 才顯示預覽圖區塊
    preview_available: bool
    # 查看追蹤（防客戶把連結轉給競品看太多次）
    view_count: int
    max_views: int


class ConfirmQuoteResponse(BaseModel):
    """確認報價後 → cart_item 已建立。前端跳 /cart。"""
    cart_item_id: UUID
    custom_request_id: UUID
    quantity: int
    quoted_price: float


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


# ── Public reference data（CustomPage 表單下拉 + PriceRangeHint）──────────────


class CanvasSizeItem(BaseModel):
    id: UUID
    canvas_w_cm: int
    canvas_h_cm: int
    display_name: str


class CanvasSizeListResponse(BaseModel):
    items: list[CanvasSizeItem]


class PhotoPriceItem(BaseModel):
    id: UUID
    canvas_w: int
    canvas_h: int
    difficulty: str
    price: float | None


class PhotoPriceListResponse(BaseModel):
    items: list[PhotoPriceItem]
