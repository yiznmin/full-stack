"""Module 15 — print_batch tests."""

import uuid
from decimal import Decimal
from unittest.mock import patch

import bcrypt
import pytest
from sqlalchemy import select

from auth.models import User
from print_batch.service import (
    NO_WASTE_THRESHOLD,
    billing,
    inch_per_unit,
)
from product.models import (
    Product,
    ProductStatusEnum,
    ProductVariant,
)
from production.models import ProductionJob

ADMIN_EMAIL = "print_admin@test.com"
ADMIN_PASS = "adminpass123"
URL = "/api/v1/admin/print-batches"


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_admin(db):
    a = User(
        name="PrintAdmin",
        email=ADMIN_EMAIL,
        password_hash=bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode(),
        role="admin",
        is_active=True,
        is_email_verified=True,
    )
    db.add(a)
    await db.commit()
    return a


async def _make_customer(db, email="cust@test.com"):
    u = User(
        name="cust",
        email=email,
        password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()).decode(),
        role="customer",
        is_active=True,
        is_email_verified=True,
    )
    db.add(u)
    await db.commit()
    return u


async def _login_admin(client):
    res = await client.post("/api/v1/admin/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASS,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])


async def _make_job(db, *, w=30, h=40, svg_url="https://example.com/x.svg"):
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=w, canvas_h_cm=h, svg_url=svg_url,
        approved=True, status="completed",
    )
    db.add(job)
    await db.flush()
    return job


async def _make_product_with_variant(db, job_id, *, title="畫"):
    p = Product(
        title=title, description="", cover_image_url="x",
        status=ProductStatusEnum.on_sale,
    )
    db.add(p)
    await db.flush()
    v = ProductVariant(
        product_id=p.id, production_job_id=job_id,
        price=500, price_formula_base=500, is_active=True,
    )
    db.add(v)
    await db.flush()
    return p, v


# ── Pure pricing ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inch_per_unit():
    """30×40 含留白 → (40 × 50) / 900 = 2.2222 才。"""
    assert abs(float(inch_per_unit(30, 40)) - 2.2222) < 0.001


@pytest.mark.asyncio
async def test_total_billing_below_floor():
    """16 才 → 列印 max(560, 200)=560，裁切 max(80, 100)=100，總 660。"""
    bill = billing(Decimal("16"))
    assert bill["billable_inch_count"] == Decimal("16")
    assert bill["print_cost"] == Decimal("560")
    assert bill["cut_cost"] == Decimal("100")
    assert bill["total_cost"] == Decimal("660")


@pytest.mark.asyncio
async def test_total_billing_above_floor():
    """30 才 → 列印 1050，裁切 150，總 1200。"""
    bill = billing(Decimal("30"))
    assert bill["print_cost"] == Decimal("1050")
    assert bill["cut_cost"] == Decimal("150")
    assert bill["total_cost"] == Decimal("1200")


@pytest.mark.asyncio
async def test_total_billing_ceil_partial():
    """47.3 才 → 整單 ceil 為 48 才。"""
    bill = billing(Decimal("47.3"))
    assert bill["billable_inch_count"] == Decimal("48")


# ── Endpoints ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_only_unauthenticated(client, db):
    res = await client.get(URL)
    assert res.status_code == 401
    res = await client.post(f"{URL}/preview", json={"required": []})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_only_customer_blocked(client, db):
    await _make_customer(db)
    res = await client.post("/api/v1/auth/login", json={
        "email": "cust@test.com", "password": "x",
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    res = await client.get(URL)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_candidates_filter_on_sale_active(client, db):
    """候選池只列 product.status=on_sale + variant.is_active=true 對應的 production_job。"""
    await _make_admin(db)
    job_a = await _make_job(db, w=30, h=40)  # 在架上
    job_b = await _make_job(db, w=50, h=50)  # draft 商品
    job_c = await _make_job(db, w=60, h=60)  # variant inactive

    p_a = Product(title="架上", description="", cover_image_url="x",
                  status=ProductStatusEnum.on_sale)
    db.add(p_a)
    await db.flush()
    db.add(ProductVariant(product_id=p_a.id, production_job_id=job_a.id,
                          price=500, price_formula_base=500, is_active=True))

    p_b = Product(title="草稿", description="", cover_image_url="x",
                  status=ProductStatusEnum.draft)
    db.add(p_b)
    await db.flush()
    db.add(ProductVariant(product_id=p_b.id, production_job_id=job_b.id,
                          price=500, price_formula_base=500, is_active=True))

    p_c = Product(title="架上但變體停用", description="", cover_image_url="x",
                  status=ProductStatusEnum.on_sale)
    db.add(p_c)
    await db.flush()
    db.add(ProductVariant(product_id=p_c.id, production_job_id=job_c.id,
                          price=500, price_formula_base=500, is_active=False))
    await db.commit()

    await _login_admin(client)
    res = await client.get(f"{URL}/candidates")
    assert res.status_code == 200
    items = res.json()["items"]
    titles = [i["product_title"] for i in items]
    assert "架上" in titles
    assert "草稿" not in titles
    assert "架上但變體停用" not in titles


@pytest.mark.asyncio
async def test_preview_required_only(client, db):
    """純必印 16 才 → 660 元 + 候選 suggestions。"""
    await _make_admin(db)
    j1 = await _make_job(db, w=30, h=40)
    j2 = await _make_job(db, w=50, h=60)
    await _make_product_with_variant(db, j1.id, title="A")
    await _make_product_with_variant(db, j2.id, title="B")
    await db.commit()

    await _login_admin(client)
    res = await client.post(f"{URL}/preview", json={
        "required": [
            {"production_job_id": str(j1.id), "quantity": 3},
            {"production_job_id": str(j2.id), "quantity": 2},
        ],
    })
    assert res.status_code == 200
    body = res.json()
    # 3 × 2.222 + 2 × 4.667 = 15.999... → ceil 16
    assert body["billable_inch_count"] == 16.0
    assert body["cost_breakdown"]["print_cost"] == 560.0
    assert body["cost_breakdown"]["cut_cost"] == 100.0
    assert body["cost_breakdown"]["total_cost"] == 660.0
    assert body["waste_inch"] == 4.0  # 20 - 16
    assert len(body["suggestions"]) > 0


@pytest.mark.asyncio
async def test_preview_no_waste_when_above_threshold(client, db):
    """整單 30 才已超過 20，不需補單建議。"""
    await _make_admin(db)
    j = await _make_job(db, w=50, h=60)  # 4.67 才/張
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    res = await client.post(f"{URL}/preview", json={
        "required": [{"production_job_id": str(j.id), "quantity": 7}],  # 32.67 才
    })
    body = res.json()
    assert body["waste_inch"] == 0.0
    assert body["suggestions"] == []


@pytest.mark.asyncio
async def test_preview_required_empty_rejected(client, db):
    await _make_admin(db)
    await _login_admin(client)
    res = await client.post(f"{URL}/preview", json={"required": []})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_preview_unknown_job_404(client, db):
    await _make_admin(db)
    await _login_admin(client)
    fake = str(uuid.uuid4())
    res = await client.post(f"{URL}/preview", json={
        "required": [{"production_job_id": fake, "quantity": 1}],
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_batch_draft(client, db):
    """POST /admin/print-batches → 建 draft，不產 PDF。"""
    await _make_admin(db)
    j = await _make_job(db, w=30, h=40)
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    res = await client.post(URL, json={
        "required": [{"production_job_id": str(j.id), "quantity": 5}],
        "admin_notes": "test",
    })
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "draft"
    assert body["pdf_url"] is None
    assert len(body["items"]) == 1
    assert body["items"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_finalize_creates_pdf(client, db):
    """Finalize → status=finalized + pdf_url 填值。"""
    await _make_admin(db)
    j = await _make_job(db, w=30, h=40)
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    create_res = await client.post(URL, json={
        "required": [{"production_job_id": str(j.id), "quantity": 5}],
    })
    batch_id = create_res.json()["id"]

    # Mock httpx 避免實際呼叫 example.com
    with patch("print_batch.service._generate_pdf") as mock_pdf:
        mock_pdf.return_value = "https://stub.firebase/print_batch/abc/batch.pdf"
        res = await client.post(f"{URL}/{batch_id}/finalize")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "finalized"
    assert body["pdf_url"] is not None


@pytest.mark.asyncio
async def test_finalize_already_finalized_rejected(client, db):
    await _make_admin(db)
    j = await _make_job(db, w=30, h=40)
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    create_res = await client.post(URL, json={
        "required": [{"production_job_id": str(j.id), "quantity": 5}],
    })
    batch_id = create_res.json()["id"]
    with patch("print_batch.service._generate_pdf") as mock_pdf:
        mock_pdf.return_value = "https://stub/x.pdf"
        await client.post(f"{URL}/{batch_id}/finalize")
        res = await client.post(f"{URL}/{batch_id}/finalize")
    assert res.status_code == 400
    assert res.json().get("code") == "ALREADY_FINALIZED"


@pytest.mark.asyncio
async def test_finalize_svg_not_ready_rejected(client, db):
    """svg_url 為 null → 拒絕 finalize 並回 SVG_NOT_READY。"""
    await _make_admin(db)
    j = await _make_job(db, w=30, h=40, svg_url=None)
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    create_res = await client.post(URL, json={
        "required": [{"production_job_id": str(j.id), "quantity": 1}],
    })
    batch_id = create_res.json()["id"]
    res = await client.post(f"{URL}/{batch_id}/finalize")
    assert res.status_code == 400
    assert res.json().get("code") == "SVG_NOT_READY"


@pytest.mark.asyncio
async def test_finalize_does_not_touch_production_progress(client, db):
    """Finalize 後 production_progress 不被修改。"""
    from orders.models import (
        Order,
        OrderItem,
        OrderStatusEnum,
        ProductionProgress,
        ProductionProgressStatusEnum,
    )
    await _make_admin(db)
    user = await _make_customer(db)
    j = await _make_job(db, w=30, h=40)
    await _make_product_with_variant(db, j.id)

    order = Order(
        order_number=f"PL-{uuid.uuid4().hex[:8]}",
        user_id=user.id, status=OrderStatusEnum.paid,
        subtotal=100, discount_amount=0, shipping_fee=0, total=100,
        shipping_type="home", shipping_snapshot={},
    )
    db.add(order)
    await db.flush()
    item = OrderItem(
        order_id=order.id, production_job_id=j.id,
        product_title_snapshot="x", variant_spec_snapshot={},
        unit_price=100, quantity=1, fulfilled_qty=1, preorder_qty=0,
        is_returned=False,
    )
    db.add(item)
    await db.flush()
    progress = ProductionProgress(order_item_id=item.id)
    db.add(progress)
    await db.commit()

    await _login_admin(client)
    create_res = await client.post(URL, json={
        "required": [{
            "production_job_id": str(j.id),
            "quantity": 1,
            "source_type": "order_item",
            "source_order_item_id": str(item.id),
        }],
    })
    batch_id = create_res.json()["id"]
    with patch("print_batch.service._generate_pdf") as mock_pdf:
        mock_pdf.return_value = "https://stub/x.pdf"
        await client.post(f"{URL}/{batch_id}/finalize")

    # progress 保持 pending（finalize 不動它）
    refreshed = (await db.execute(
        select(ProductionProgress).where(ProductionProgress.id == progress.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed.status == ProductionProgressStatusEnum.pending


@pytest.mark.asyncio
async def test_list_batches_pagination(client, db):
    await _make_admin(db)
    j = await _make_job(db, w=30, h=40)
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    for _ in range(3):
        await client.post(URL, json={
            "required": [{"production_job_id": str(j.id), "quantity": 1}],
        })
    res = await client.get(f"{URL}?page=1&page_size=2")
    body = res.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_get_batch_detail(client, db):
    await _make_admin(db)
    j = await _make_job(db, w=30, h=40)
    await _make_product_with_variant(db, j.id)
    await db.commit()

    await _login_admin(client)
    create_res = await client.post(URL, json={
        "required": [{"production_job_id": str(j.id), "quantity": 1}],
    })
    batch_id = create_res.json()["id"]
    res = await client.get(f"{URL}/{batch_id}")
    assert res.status_code == 200
    assert res.json()["id"] == batch_id


@pytest.mark.asyncio
async def test_no_waste_threshold_constant():
    """門檻常數 = 20 才（裁切 100/5）。"""
    assert NO_WASTE_THRESHOLD == Decimal("20")


# ── Non-integer canvas dimension regression ───────────────────────────────────


@pytest.mark.asyncio
async def test_non_integer_canvas_cm_round_trips_through_endpoints(client, db):
    """Numeric(6,1) 的 canvas_w_cm=30.5 / h=40.5 不可在 response 觸發 500。"""
    await _make_admin(db)
    j = await _make_job(db, w=Decimal("30.5"), h=Decimal("40.5"))
    await _make_product_with_variant(db, j.id, title="小數尺寸")
    await db.commit()

    await _login_admin(client)

    cand_res = await client.get(f"{URL}/candidates")
    assert cand_res.status_code == 200
    cand_items = cand_res.json()["items"]
    assert any(
        it["canvas_w_cm"] == 30.5 and it["canvas_h_cm"] == 40.5
        for it in cand_items
    )

    create_res = await client.post(URL, json={
        "required": [{"production_job_id": str(j.id), "quantity": 1}],
    })
    assert create_res.status_code == 201
    body = create_res.json()
    assert body["items"][0]["canvas_w_cm"] == 30.5
    assert body["items"][0]["canvas_h_cm"] == 40.5

    detail_res = await client.get(f"{URL}/{body['id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["items"][0]["canvas_w_cm"] == 30.5


# ── PDF generation path ───────────────────────────────────────────────────────


class _MockHttpResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class _MockHttpClient:
    """模擬 httpx.AsyncClient，避免真實對外請求。"""

    def __init__(self, svg_text: str):
        self._svg_text = svg_text

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url):
        return _MockHttpResponse(self._svg_text)


@pytest.mark.asyncio
async def test_generate_pdf_with_parseable_svg_returns_url(db):
    """_generate_pdf 在 SVG 可解析時走完拼版流程，回傳 stub URL。"""
    from print_batch.models import PrintBatchItem, PrintBatchItemSourceEnum
    from print_batch.service import _generate_pdf

    j = await _make_job(db, w=30, h=40, svg_url="https://example.com/ok.svg")
    await db.commit()

    item = PrintBatchItem(
        print_batch_id=uuid.uuid4(),
        source_type=PrintBatchItemSourceEnum.standalone,
        production_job_id=j.id,
        quantity=2,
        inch_per_unit=Decimal("2.2222"),
        canvas_w_cm=Decimal("30.0"),
        canvas_h_cm=Decimal("40.0"),
    )

    valid_svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="30mm" height="40mm" viewBox="0 0 30 40">'
        '<rect width="30" height="40" fill="none" stroke="black"/>'
        '</svg>'
    )

    def mock_client_factory(*args, **kwargs):
        return _MockHttpClient(valid_svg)

    with patch("print_batch.service.httpx.AsyncClient", mock_client_factory):
        url = await _generate_pdf([(item, j)])

    assert isinstance(url, str)
    assert url.startswith("https://stub.firebase/print_batch/")
    assert url.endswith("/batch.pdf")


@pytest.mark.asyncio
async def test_generate_pdf_falls_back_on_unparseable_svg(db):
    """SVG 解析失敗時走佔位框 fallback，仍回傳 URL 不爆。"""
    from print_batch.models import PrintBatchItem, PrintBatchItemSourceEnum
    from print_batch.service import _generate_pdf

    j = await _make_job(db, w=20, h=30, svg_url="https://example.com/broken.svg")
    await db.commit()

    item = PrintBatchItem(
        print_batch_id=uuid.uuid4(),
        source_type=PrintBatchItemSourceEnum.standalone,
        production_job_id=j.id,
        quantity=1,
        inch_per_unit=Decimal("1.0"),
        canvas_w_cm=Decimal("20.0"),
        canvas_h_cm=Decimal("30.0"),
    )

    def mock_client_factory(*args, **kwargs):
        return _MockHttpClient("not a valid svg")

    with patch("print_batch.service.httpx.AsyncClient", mock_client_factory):
        url = await _generate_pdf([(item, j)])

    assert isinstance(url, str)
    assert url.startswith("https://stub.firebase/print_batch/")
