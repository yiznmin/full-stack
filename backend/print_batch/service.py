"""Module 15 — print_batch service.

責任：
1. 計費：才數計算、雙下限（200 元列印 / 100 元裁切）
2. 補單建議：3 種策略，目標整單 ≥ 20 才避免下限浪費
3. PDF 生成：從 production_jobs.svg_url 拼版（stub URL 上傳）
"""
import io
import logging
import math
import uuid
from decimal import Decimal
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import BadRequestError, NotFoundError
from print_batch.models import (
    PrintBatch,
    PrintBatchItem,
    PrintBatchItemSourceEnum,
    PrintBatchStatusEnum,
)
from product.models import Product, ProductStatusEnum, ProductVariant
from production.models import ProductionJob

logger = logging.getLogger(__name__)


# ── Pricing ───────────────────────────────────────────────────────────────────


PRINT_RATE = Decimal("35")
CUT_RATE = Decimal("5")
PRINT_FLOOR = Decimal("200")
CUT_FLOOR = Decimal("100")
NO_WASTE_THRESHOLD = Decimal("20")  # 20 才以上不浪費（裁切 100/5）
MARGIN_CM = 10  # 每張畫四周各 5cm（含內 → 寬高各 +10）
DIVISOR = Decimal("900")


def inch_per_unit(w, h) -> Decimal:
    """單張展開（含 5cm 留白）後的才數，未取整。w/h 接受 int / float / Decimal。"""
    w_dec = Decimal(str(w))
    h_dec = Decimal(str(h))
    return (w_dec + MARGIN_CM) * (h_dec + MARGIN_CM) / DIVISOR


def billing(total_inch: Decimal) -> dict:
    """套用整單向上取整 + 雙下限。"""
    billable = Decimal(math.ceil(total_inch))
    print_cost = max(billable * PRINT_RATE, PRINT_FLOOR)
    cut_cost = max(billable * CUT_RATE, CUT_FLOOR)
    return {
        "billable_inch_count": billable,
        "print_cost": print_cost,
        "cut_cost": cut_cost,
        "total_cost": print_cost + cut_cost,
    }


def _waste_inch(billable: Decimal) -> Decimal:
    """脫離下限門檻仍欠多少才（不浪費需要 ≥ 20 才）。"""
    return max(Decimal("0"), NO_WASTE_THRESHOLD - billable)


# ── Candidates / Required loading ─────────────────────────────────────────────


async def _load_candidate_pool(db: AsyncSession) -> list[dict]:
    """架上 on_sale + active variant 對應的 production_job 全列。"""
    rows = (await db.execute(
        select(ProductionJob, Product.title)
        .join(ProductVariant, ProductVariant.production_job_id == ProductionJob.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(
            Product.status == ProductStatusEnum.on_sale,
            ProductVariant.is_active.is_(True),
        )
        .distinct()
    )).all()
    items = []
    for job, title in rows:
        w = Decimal(str(job.canvas_w_cm))
        h = Decimal(str(job.canvas_h_cm))
        items.append({
            "production_job_id": job.id,
            "product_title": title,
            "canvas_w_cm": float(w),
            "canvas_h_cm": float(h),
            "inch_per_unit": float(inch_per_unit(w, h)),
        })
    return items


async def _resolve_jobs(
    db: AsyncSession, specs: list[dict]
) -> list[dict]:
    """Resolve [{production_job_id, quantity, ...}] → enriched with canvas + inch."""
    if not specs:
        return []
    job_ids = {s["production_job_id"] for s in specs}
    rows = (await db.execute(
        select(ProductionJob).where(ProductionJob.id.in_(job_ids))
    )).scalars().all()
    by_id = {j.id: j for j in rows}

    title_rows = (await db.execute(
        select(ProductionJob.id, Product.title)
        .join(ProductVariant, ProductVariant.production_job_id == ProductionJob.id)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(ProductionJob.id.in_(job_ids))
        .distinct()
    )).all()
    title_by_job = {row[0]: row[1] for row in title_rows}

    enriched = []
    for s in specs:
        job = by_id.get(s["production_job_id"])
        if job is None:
            raise NotFoundError(f"production_job {s['production_job_id']} 不存在")
        w = Decimal(str(job.canvas_w_cm))
        h = Decimal(str(job.canvas_h_cm))
        enriched.append({
            "production_job_id": job.id,
            "product_title": title_by_job.get(job.id),
            "canvas_w_cm": w,
            "canvas_h_cm": h,
            "inch_per_unit": inch_per_unit(w, h),
            "quantity": int(s["quantity"]),
            "source_type": s.get("source_type", "standalone"),
            "source_order_item_id": s.get("source_order_item_id"),
            "svg_url": job.svg_url,
        })
    return enriched


def _aggregate_inch(items: list[dict]) -> Decimal:
    return sum(
        (item["inch_per_unit"] * item["quantity"] for item in items),
        Decimal("0"),
    )


# ── Suggest combos ─────────────────────────────────────────────────────────────


def _suggest_combos(
    required_inch: Decimal,
    candidates: list[dict],
) -> list[dict]:
    """產出 3 組建議組合，每組目標：required + combo 總才 ≥ 20。

    candidates 是 _load_candidate_pool 的結果，每筆代表「1 張該款」。
    建議組合中每筆 qty 由演算決定。
    """
    if required_inch >= NO_WASTE_THRESHOLD:
        return []  # 已脫離下限，不需補單

    deficit = NO_WASTE_THRESHOLD - required_inch
    suggestions: list[dict] = []

    # 策略 1：單品補滿（找一款，數量最少能達門檻）
    best_single = None
    for c in candidates:
        ipu = Decimal(str(c["inch_per_unit"]))
        if ipu <= 0:
            continue
        qty = math.ceil(float(deficit) / float(ipu))
        if qty < 1:
            qty = 1
        combo_inch = ipu * qty
        total = required_inch + combo_inch
        # 取最接近 20 才（最不浪費 = 超過最少）
        if best_single is None or total < best_single["_total"]:
            best_single = {
                "label": "單品補滿",
                "items": [{
                    "production_job_id": c["production_job_id"],
                    "product_title": c.get("product_title"),
                    "quantity": qty,
                    "inch_per_unit": float(ipu),
                }],
                "_total": total,
                "_combo_inch": combo_inch,
            }
    if best_single:
        suggestions.append(_finalize_suggestion(best_single, required_inch))

    # 策略 2：大尺寸貪心
    sorted_desc = sorted(
        candidates, key=lambda c: c["inch_per_unit"], reverse=True
    )
    combo = _greedy_pack(sorted_desc, deficit)
    if combo:
        suggestions.append(_finalize_suggestion(
            {"label": "大尺寸組合", **combo}, required_inch,
        ))

    # 策略 3：小尺寸貪心
    sorted_asc = sorted(candidates, key=lambda c: c["inch_per_unit"])
    combo = _greedy_pack(sorted_asc, deficit)
    if combo:
        suggestions.append(_finalize_suggestion(
            {"label": "小尺寸組合", **combo}, required_inch,
        ))

    # 去重（如果三策略給出同樣組合）
    seen = set()
    unique: list[dict] = []
    for s in suggestions:
        key = tuple(sorted((str(it["production_job_id"]), it["quantity"]) for it in s["items"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    return unique


def _greedy_pack(sorted_candidates: list[dict], deficit: Decimal) -> dict | None:
    """貪心：依 sorted_candidates 順序，每款各加 1 張直到 combo 才 ≥ deficit。"""
    items_dict: dict[UUID, dict] = {}
    combo_inch = Decimal("0")
    for c in sorted_candidates:
        if combo_inch >= deficit:
            break
        ipu = Decimal(str(c["inch_per_unit"]))
        if ipu <= 0:
            continue
        # 加 1 張
        cid = c["production_job_id"]
        if cid in items_dict:
            items_dict[cid]["quantity"] += 1
        else:
            items_dict[cid] = {
                "production_job_id": cid,
                "product_title": c.get("product_title"),
                "quantity": 1,
                "inch_per_unit": float(ipu),
            }
        combo_inch += ipu
    if not items_dict or combo_inch < deficit:
        return None
    return {
        "items": list(items_dict.values()),
        "_combo_inch": combo_inch,
    }


def _finalize_suggestion(raw: dict, required_inch: Decimal) -> dict:
    combo_inch = raw["_combo_inch"]
    total_inch = required_inch + combo_inch
    bill = billing(total_inch)
    return {
        "label": raw["label"],
        "items": raw["items"],
        "total_inch_count": float(total_inch),
        "billable_inch_count": float(bill["billable_inch_count"]),
        "waste_inch": float(_waste_inch(bill["billable_inch_count"])),
        "cost_breakdown": {
            "print_cost": float(bill["print_cost"]),
            "cut_cost": float(bill["cut_cost"]),
            "total_cost": float(bill["total_cost"]),
        },
    }


# ── Public service: preview / candidates / create / finalize / list ──────────


async def list_candidates(db: AsyncSession) -> dict:
    return {"items": await _load_candidate_pool(db)}


async def preview(
    db: AsyncSession,
    required_specs: list[dict],
    candidate_specs: list[dict] | None,
) -> dict:
    required = await _resolve_jobs(db, required_specs)
    candidates_chosen = await _resolve_jobs(db, candidate_specs or [])

    all_items = required + candidates_chosen
    total_inch = _aggregate_inch(all_items)
    bill = billing(total_inch)

    pool = await _load_candidate_pool(db)
    suggestions = _suggest_combos(total_inch, pool)

    return {
        "required_inch_count": float(total_inch),
        "billable_inch_count": float(bill["billable_inch_count"]),
        "waste_inch": float(_waste_inch(bill["billable_inch_count"])),
        "cost_breakdown": {
            "print_cost": float(bill["print_cost"]),
            "cut_cost": float(bill["cut_cost"]),
            "total_cost": float(bill["total_cost"]),
        },
        "suggestions": suggestions,
        "available_candidates": pool,
    }


async def create_batch(
    db: AsyncSession,
    required_specs: list[dict],
    candidate_specs: list[dict] | None,
    admin_notes: str | None,
    created_by_user_id: UUID | None,
) -> PrintBatch:
    items = await _resolve_jobs(db, required_specs) + \
        await _resolve_jobs(db, candidate_specs or [])

    if not items:
        raise BadRequestError("批次至少需要一個項目")

    total_inch = _aggregate_inch(items)
    bill = billing(total_inch)

    batch = PrintBatch(
        status=PrintBatchStatusEnum.draft,
        total_inch_count=total_inch,
        billable_inch_count=bill["billable_inch_count"],
        print_cost=bill["print_cost"],
        cut_cost=bill["cut_cost"],
        total_cost=bill["total_cost"],
        admin_notes=admin_notes,
        created_by_user_id=created_by_user_id,
    )
    db.add(batch)
    await db.flush()

    for item in items:
        db.add(PrintBatchItem(
            print_batch_id=batch.id,
            source_type=PrintBatchItemSourceEnum(item.get("source_type", "standalone")),
            source_order_item_id=item.get("source_order_item_id"),
            production_job_id=item["production_job_id"],
            quantity=item["quantity"],
            inch_per_unit=item["inch_per_unit"],
            canvas_w_cm=item["canvas_w_cm"],
            canvas_h_cm=item["canvas_h_cm"],
        ))

    await db.commit()
    await db.refresh(batch)
    return batch


async def finalize(db: AsyncSession, batch_id: UUID) -> PrintBatch:
    batch = await _get_batch_or_404(db, batch_id)
    if batch.status == PrintBatchStatusEnum.finalized:
        raise BadRequestError("批次已 finalize", code="ALREADY_FINALIZED")

    items = (await db.execute(
        select(PrintBatchItem, ProductionJob)
        .join(ProductionJob, PrintBatchItem.production_job_id == ProductionJob.id)
        .where(PrintBatchItem.print_batch_id == batch_id)
    )).all()

    # 確認所有 SVG 可用
    for _item, job in items:
        if not job.svg_url:
            raise BadRequestError(
                f"production_job {job.id} 尚未產出 svg，無法送印",
                code="SVG_NOT_READY",
            )

    pdf_url = await _generate_pdf(items)

    from datetime import UTC, datetime
    batch.status = PrintBatchStatusEnum.finalized
    batch.pdf_url = pdf_url
    batch.finalized_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(batch)
    return batch


async def list_batches(
    db: AsyncSession, status: str | None, page: int, page_size: int,
) -> dict:
    query = select(PrintBatch)
    if status:
        query = query.where(PrintBatch.status == status)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    rows = (await db.execute(
        query.order_by(PrintBatch.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    items = []
    for b in rows:
        item_count = (await db.execute(
            select(func.count()).select_from(
                select(PrintBatchItem).where(
                    PrintBatchItem.print_batch_id == b.id
                ).subquery()
            )
        )).scalar() or 0
        items.append(_summary_serialize(b, int(item_count)))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_batch(db: AsyncSession, batch_id: UUID) -> dict:
    batch = await _get_batch_or_404(db, batch_id)
    items = (await db.execute(
        select(PrintBatchItem).where(PrintBatchItem.print_batch_id == batch_id)
    )).scalars().all()
    return _detail_serialize(batch, list(items))


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _get_batch_or_404(db: AsyncSession, batch_id: UUID) -> PrintBatch:
    result = await db.execute(
        select(PrintBatch).where(PrintBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if batch is None:
        raise NotFoundError("列印批次不存在")
    return batch


def _detail_serialize(batch: PrintBatch, items: list[PrintBatchItem]) -> dict:
    return {
        "id": batch.id,
        "status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        "total_inch_count": float(batch.total_inch_count),
        "billable_inch_count": float(batch.billable_inch_count),
        "print_cost": float(batch.print_cost),
        "cut_cost": float(batch.cut_cost),
        "total_cost": float(batch.total_cost),
        "pdf_url": batch.pdf_url,
        "admin_notes": batch.admin_notes,
        "created_at": batch.created_at,
        "finalized_at": batch.finalized_at,
        "items": [
            {
                "id": it.id,
                "source_type": (
                    it.source_type.value
                    if hasattr(it.source_type, "value") else str(it.source_type)
                ),
                "source_order_item_id": it.source_order_item_id,
                "production_job_id": it.production_job_id,
                "quantity": it.quantity,
                "inch_per_unit": float(it.inch_per_unit),
                "canvas_w_cm": float(it.canvas_w_cm),
                "canvas_h_cm": float(it.canvas_h_cm),
            }
            for it in items
        ],
    }


def _summary_serialize(batch: PrintBatch, item_count: int) -> dict:
    return {
        "id": batch.id,
        "status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
        "total_inch_count": float(batch.total_inch_count),
        "total_cost": float(batch.total_cost),
        "pdf_url": batch.pdf_url,
        "item_count": item_count,
        "created_at": batch.created_at,
        "finalized_at": batch.finalized_at,
    }


# ── PDF generation ─────────────────────────────────────────────────────────────


async def _generate_pdf(items: list) -> str:
    """從 production_job.svg_url 抓 SVG → 拼到一份 PDF → 上傳（stub）→ 回 URL。

    Stub 模式：輸出 mock URL；實作時用 svglib + reportlab 拼版。
    若 svglib 解析失敗，fallback 用 Pillow 純黑框佔位。
    """
    try:
        from reportlab.graphics import renderPDF
        from reportlab.lib.units import cm
        from reportlab.pdfgen import canvas as rl_canvas
        from svglib.svglib import svg2rlg
    except ImportError:
        logger.warning(
            "svglib / reportlab 未安裝，PDF 生成走 stub。"
            "執行 pip install svglib reportlab Pillow"
        )
        return _stub_pdf_url()

    # 收集 SVG 內容
    svg_drawings = []
    for item, job in items:
        # NUMERIC → float for reportlab unit math
        w_cm = float(item.canvas_w_cm)
        h_cm = float(item.canvas_h_cm)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(job.svg_url)
                resp.raise_for_status()
                svg_text = resp.text
            drawing = svg2rlg(io.StringIO(svg_text))
            svg_drawings.append({
                "drawing": drawing, "w_cm": w_cm, "h_cm": h_cm,
                "qty": item.quantity,
            })
        except Exception as e:
            logger.warning(f"無法處理 svg {job.svg_url}: {e}")
            svg_drawings.append({
                "drawing": None, "w_cm": w_cm, "h_cm": h_cm,
                "qty": item.quantity,
            })

    # 簡單 layout：依次橫排到固定寬度（200cm），超過則換行
    page_w_cm = 200
    cursor_x = 0
    cursor_y = 0
    row_h = 0
    placements = []
    for d in svg_drawings:
        for _ in range(d["qty"]):
            cell_w = d["w_cm"] + MARGIN_CM
            cell_h = d["h_cm"] + MARGIN_CM
            if cursor_x + cell_w > page_w_cm and cursor_x > 0:
                cursor_x = 0
                cursor_y += row_h
                row_h = 0
            placements.append({
                "drawing": d["drawing"],
                "x_cm": cursor_x + MARGIN_CM / 2,
                "y_cm": cursor_y + MARGIN_CM / 2,
                "w_cm": d["w_cm"],
                "h_cm": d["h_cm"],
            })
            cursor_x += cell_w
            row_h = max(row_h, cell_h)
    if placements:
        total_w_cm = max(
            (p["x_cm"] + p["w_cm"] + MARGIN_CM / 2) for p in placements
        )
    else:
        total_w_cm = page_w_cm
    total_h_cm = (cursor_y + row_h) if placements else 100

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(total_w_cm * cm, total_h_cm * cm))
    for p in placements:
        if p["drawing"] is None:
            # 佔位框
            c.rect(p["x_cm"] * cm, (total_h_cm - p["y_cm"] - p["h_cm"]) * cm,
                   p["w_cm"] * cm, p["h_cm"] * cm, stroke=1, fill=0)
            continue
        # ReportLab Y 軸從下往上，需轉換
        renderPDF.draw(
            p["drawing"], c,
            p["x_cm"] * cm,
            (total_h_cm - p["y_cm"] - p["h_cm"]) * cm,
        )
    c.showPage()
    c.save()
    pdf_bytes = buf.getvalue()
    _ = pdf_bytes  # 實際應上傳到 Firebase；目前 stub

    return _stub_pdf_url()


def _stub_pdf_url() -> str:
    token = uuid.uuid4().hex[:12]
    logger.warning(
        "Print batch PDF upload is STUB — replace with Firebase Admin SDK"
    )
    return f"https://stub.firebase/print_batch/{token}/batch.pdf"
