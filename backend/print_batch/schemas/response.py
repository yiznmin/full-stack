from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CostBreakdown(BaseModel):
    print_cost: float
    cut_cost: float
    total_cost: float


class CandidateInfo(BaseModel):
    production_job_id: UUID
    product_title: str | None
    canvas_w_cm: float
    canvas_h_cm: float
    inch_per_unit: float


class CandidateListResponse(BaseModel):
    items: list[CandidateInfo]


class SuggestedComboItem(BaseModel):
    production_job_id: UUID
    product_title: str | None
    quantity: int
    inch_per_unit: float


class SuggestedCombo(BaseModel):
    label: str
    items: list[SuggestedComboItem]
    total_inch_count: float
    billable_inch_count: float
    waste_inch: float
    cost_breakdown: CostBreakdown


class PreviewResponse(BaseModel):
    required_inch_count: float
    billable_inch_count: float
    waste_inch: float
    cost_breakdown: CostBreakdown
    suggestions: list[SuggestedCombo]
    available_candidates: list[CandidateInfo]


class BatchItemResponse(BaseModel):
    id: UUID
    source_type: str
    source_order_item_id: UUID | None
    production_job_id: UUID
    quantity: int
    inch_per_unit: float
    canvas_w_cm: float
    canvas_h_cm: float


class PrintBatchDetailResponse(BaseModel):
    id: UUID
    status: str
    total_inch_count: float
    billable_inch_count: float
    print_cost: float
    cut_cost: float
    total_cost: float
    pdf_url: str | None
    admin_notes: str | None
    created_at: datetime
    finalized_at: datetime | None
    items: list[BatchItemResponse]


class PrintBatchSummary(BaseModel):
    id: UUID
    status: str
    total_inch_count: float
    total_cost: float
    pdf_url: str | None
    item_count: int
    created_at: datetime
    finalized_at: datetime | None


class PrintBatchListResponse(BaseModel):
    items: list[PrintBatchSummary]
    total: int
    page: int
    page_size: int
