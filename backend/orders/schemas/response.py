from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel


class CartItemResponse(BaseModel):
    id: UUID
    is_custom: bool = False
    variant_id: UUID | None = None
    product_id: UUID | None = None
    product_title: str
    product_image_url: str | None = None
    variant_image_url: str | None = None
    thumb_url: str | None = None
    variant_spec: dict
    # 客製 line（non-custom 為 None）
    custom_request_id: UUID | None = None
    production_job_id: UUID | None = None
    quote_status: str | None = None
    quote_expires_at: datetime | None = None
    quote_expired: bool = False
    unit_price: float
    quantity: int
    fulfilled_units: int
    preorder_units: int
    is_active: bool

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    subtotal: float


class CheckoutPreviewResponse(BaseModel):
    subtotal: float
    # 一般商品 subtotal（免運門檻計算用，排除客製）
    non_custom_subtotal: float | None = None
    non_custom_qty: int | None = None
    expired_custom_count: int | None = None
    discount_amount: float
    discount_source: str | None
    shipping_fee: float
    total: float
    free_shipping_reason: str | None
    has_preorder: bool
    split_items: list[dict]


class CreateOrderResponse(BaseModel):
    order_id: UUID
    order_number: str
    total: float
    payment_deadline: datetime
    payment_info: dict


class ProductionProgressResponse(BaseModel):
    id: UUID
    order_item_id: UUID
    status: str
    notes: str | None
    updated_at: datetime

    class Config:
        from_attributes = True


class ShipmentResponse(BaseModel):
    id: UUID
    shipment_type: str
    status: str
    tracking_number: str | None
    ecpay_logistics_id: str | None = None
    cvs_payment_no: str | None = None        # 寄貨編號（CVS）
    cvs_validation_no: str | None = None     # 驗證碼（7-Eleven C2C）
    last_rtn_code: int | None = None         # 最後收到的 ECpay 狀態碼
    last_rtn_msg: str | None = None          # 最後狀態文字
    last_status_at: datetime | None = None   # 最後狀態時間
    shipped_at: datetime | None
    delivered_at: datetime | None

    class Config:
        from_attributes = True


class PaymentSubmissionResponse(BaseModel):
    id: UUID
    transfer_amount: float
    transfer_date: date
    transfer_time: time
    account_last5: str
    is_flagged: bool
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class OrderItemResponse(BaseModel):
    id: UUID
    product_variant_id: UUID | None
    product_title_snapshot: str
    variant_spec_snapshot: dict
    unit_price: float
    quantity: int
    fulfilled_qty: int
    preorder_qty: int
    is_returned: bool
    production_progress: ProductionProgressResponse | None = None

    class Config:
        from_attributes = True


class OrderListItemResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    total: float
    item_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class OrderDetailResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    subtotal: float
    discount_amount: float
    discount_source: str | None
    auto_checkout_config_id: UUID | None
    shipping_fee: float
    total: float
    shipping_type: str
    shipping_preference: str | None
    shipping_snapshot: dict
    shipping_locked: bool = False
    payment_deadline: datetime | None
    paid_at: datetime | None
    completed_at: datetime | None
    cancel_reason_code: str | None
    cancel_reason_note: str | None
    refund_amount: float | None
    refunded_at: datetime | None
    refund_confirmed_at: datetime | None
    customer_notes: str | None
    items: list[OrderItemResponse]
    shipments: list[ShipmentResponse]
    payment_submissions: list[PaymentSubmissionResponse]
    can_cancel: bool
    can_confirm_received: bool
    can_modify_shipping: bool = False  # 客戶端用：true 才顯示「修改」按鈕
    created_at: datetime

    class Config:
        from_attributes = True


class AdminOrderListItemResponse(BaseModel):
    id: UUID
    order_number: str
    user_id: UUID
    user_name: str
    user_email: str
    status: str
    total: float
    item_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class AdminOrderDetailResponse(BaseModel):
    id: UUID
    order_number: str
    user_id: UUID
    user_name: str
    user_email: str
    status: str
    subtotal: float
    discount_amount: float
    discount_source: str | None
    auto_checkout_config_id: UUID | None
    shipping_fee: float
    total: float
    shipping_type: str
    shipping_preference: str | None
    shipping_snapshot: dict
    shipping_locked: bool = False
    payment_deadline: datetime | None
    paid_at: datetime | None
    completed_at: datetime | None
    cancel_reason_code: str | None
    cancel_reason_note: str | None
    refund_amount: float | None
    refunded_at: datetime | None
    refund_confirmed_at: datetime | None
    customer_notes: str | None
    admin_notes: str | None
    items: list[OrderItemResponse]
    shipments: list[ShipmentResponse]
    payment_submissions: list[PaymentSubmissionResponse]
    created_at: datetime

    class Config:
        from_attributes = True


class CreateShipmentResponse(BaseModel):
    shipment_id: UUID
    tracking_number: str
    ecpay_logistics_id: str

    class Config:
        from_attributes = True


class BatchShipmentResultItem(BaseModel):
    """批次建單單筆結果（成功 or 失敗）."""
    order_id: UUID
    ok: bool
    tracking_number: str | None = None
    ecpay_logistics_id: str | None = None
    error: str | None = None


class BatchCreateShipmentResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: list[BatchShipmentResultItem]


class FlagPaymentSubmissionResponse(BaseModel):
    payment_deadline: datetime


class CartItemMutationResponse(BaseModel):
    id: UUID
    variant_id: UUID | None = None
    quantity: int | None = None
    deleted: bool | None = None


class OkResponse(BaseModel):
    ok: bool = True


class OrderListResponse(BaseModel):
    items: list[OrderListItemResponse]
    total: int
    page: int
    page_size: int


class AdminOrderListResponse(BaseModel):
    items: list[AdminOrderListItemResponse]
    total: int
    page: int
    page_size: int


class OrderStatusUpdateResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    paid_at: datetime | None
    completed_at: datetime | None
    refunded_at: datetime | None
    admin_notes: str | None
    cancel_reason_code: str | None
    updated_at: datetime


class RefundResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    refund_amount: float
    refunded_at: datetime | None
    cancel_reason_note: str | None
    returned_item_count: int


class AdminNotesUpdateResponse(BaseModel):
    id: UUID
    admin_notes: str | None
    updated_at: datetime


class CancelOrderResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    cancel_reason_code: str | None
    cancel_reason_note: str | None
    refund_amount: float | None
    refunded_at: datetime | None


class ConfirmReceivedResponse(BaseModel):
    id: UUID
    order_number: str
    status: str
    completed_at: datetime | None
