import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User
from product.models import (
    Product,
    ProductImage,
    ProductSeries,
    ProductStatusEnum,
    ProductTag,
    ProductVariant,
    Tag,
)
from product.service import calc_price_formula_base
from production.models import JobStatusEnum, ProductionJob

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PRODUCTS_URL = "/api/v1/admin/products"

ADMIN_USER = {
    "name": "商品管理員", "email": "prod_admin@example.com", "password": "adminpass123"
}
CUSTOMER_USER = {
    "name": "一般用戶", "email": "prod_customer@example.com", "password": "custpass123"
}


async def _make_admin(client, db):
    await client.post(REGISTER_URL, json=ADMIN_USER)
    result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    user.role = "admin"
    await db.commit()


async def _make_customer(client, db):
    await client.post(REGISTER_URL, json=CUSTOMER_USER)
    result = await db.execute(select(User).where(User.email == CUSTOMER_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    await db.commit()


async def _login(client, email, password):
    res = await client.post(LOGIN_URL, json={"email": email, "password": password})
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])


async def _create_approved_job(db, num_colors_used=18) -> ProductionJob:
    job = ProductionJob(
        detail="rough", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        approved=True,
        num_colors_used=num_colors_used,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _create_tag(db, name="標籤") -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


async def _create_product(db, title="商品A", status=ProductStatusEnum.draft) -> Product:
    product = Product(
        title=title, cover_image_url="http://img.test/a.png", status=status
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


# ── Pricing formula unit test ─────────────────────────────────────────────────

def test_calc_price_formula_base():
    result = calc_price_formula_base(30, 40, "rough", 18)
    assert result == Decimal("397")


def test_calc_price_formula_base_premium():
    result = calc_price_formula_base(30, 40, "premium", 18)
    assert result == Decimal("459")


# ── GET /admin/products ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_products_empty(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(PRODUCTS_URL)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_products_filter_status(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_product(db, title="草稿A", status=ProductStatusEnum.draft)
    await _create_product(db, title="上架B", status=ProductStatusEnum.on_sale)

    res = await client.get(PRODUCTS_URL, params={"status": "draft"})
    assert len(res.json()["items"]) == 1

    res = await client.get(PRODUCTS_URL, params={"status": "on_sale"})
    assert len(res.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_products_search(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_product(db, title="貓咪主題")
    await _create_product(db, title="風景畫")

    res = await client.get(PRODUCTS_URL, params={"search": "貓"})
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["title"] == "貓咪主題"


@pytest.mark.asyncio
async def test_list_products_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.get(PRODUCTS_URL)).status_code == 403


@pytest.mark.asyncio
async def test_list_products_unauthenticated(client: AsyncClient, db):
    assert (await client.get(PRODUCTS_URL)).status_code == 401


# ── POST /admin/products ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_product_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    tag = await _create_tag(db)
    res = await client.post(PRODUCTS_URL, json={
        "title": "新商品", "cover_image_url": "http://img.test/new.png",
        "status": "draft", "tag_ids": [str(tag.id)],
    })
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "新商品"
    assert len(data["tags"]) == 1


@pytest.mark.asyncio
async def test_create_product_invalid_tag(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(PRODUCTS_URL, json={
        "title": "商品", "cover_image_url": "http://img.test/x.png",
        "status": "draft", "tag_ids": [str(uuid.uuid4())],
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_product_invalid_series(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(PRODUCTS_URL, json={
        "title": "商品", "cover_image_url": "http://img.test/x.png",
        "status": "draft", "series_id": str(uuid.uuid4()),
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_product_with_series(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    series = ProductSeries(name="春季")
    db.add(series)
    await db.commit()
    await db.refresh(series)

    res = await client.post(PRODUCTS_URL, json={
        "title": "春商品", "cover_image_url": "http://img.test/s.png",
        "status": "draft", "series_id": str(series.id), "series_order": 1,
    })
    assert res.status_code == 201
    assert res.json()["series_id"] == str(series.id)


@pytest.mark.asyncio
async def test_create_product_series_without_order(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    from product.models import ProductSeries
    series = ProductSeries(name="無序系列")
    db.add(series)
    await db.commit()
    await db.refresh(series)

    res = await client.post(PRODUCTS_URL, json={
        "title": "無序商品", "cover_image_url": "http://img.test/ns.png",
        "status": "draft", "series_id": str(series.id),
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_product_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(PRODUCTS_URL, json={
        "title": "X", "cover_image_url": "http://img.test/x.png", "status": "draft"
    })
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_product_unauthenticated(client: AsyncClient, db):
    res = await client.post(PRODUCTS_URL, json={
        "title": "X", "cover_image_url": "http://img.test/x.png", "status": "draft"
    })
    assert res.status_code == 401


# ── GET /admin/products/{id} ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_product_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    res = await client.get(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 200
    assert res.json()["id"] == str(product.id)


@pytest.mark.asyncio
async def test_get_product_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    assert (await client.get(f"{PRODUCTS_URL}/{uuid.uuid4()}")).status_code == 404


# ── PUT /admin/products/{id} ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_product_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    tag = await _create_tag(db, name="更新標籤")
    res = await client.put(f"{PRODUCTS_URL}/{product.id}", json={
        "title": "更新商品", "cover_image_url": "http://img.test/upd.png",
        "status": "on_sale", "tag_ids": [str(tag.id)],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "更新商品"
    assert data["status"] == "on_sale"
    assert len(data["tags"]) == 1


@pytest.mark.asyncio
async def test_update_product_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.put(f"{PRODUCTS_URL}/{uuid.uuid4()}", json={
        "title": "X", "cover_image_url": "http://img.test/x.png", "status": "draft"
    })
    assert res.status_code == 404


# ── DELETE /admin/products/{id} ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_product_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.off_sale)
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_product_with_inactive_variant_ok(client: AsyncClient, db):
    """含 is_active=False 的變體可刪除（CASCADE 移除）。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.off_sale)
    job = await _create_approved_job(db)
    db.add(ProductVariant(
        product_id=product.id, production_job_id=job.id,
        price=Decimal("399"), price_formula_base=Decimal("397"), is_active=False,
    ))
    await db.commit()
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_product_not_off_sale(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.on_sale)
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_delete_product_with_active_variant(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.off_sale)
    job = await _create_approved_job(db)
    db.add(ProductVariant(
        product_id=product.id, production_job_id=job.id,
        price=Decimal("399"), price_formula_base=Decimal("397"), is_active=True,
    ))
    await db.commit()
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_delete_draft_product_with_active_variant_ok(client: AsyncClient, db):
    """draft（從未上架）可直接刪，即使 variant.is_active=True 也行（無訂單引用前提下）。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.draft)
    job = await _create_approved_job(db)
    db.add(ProductVariant(
        product_id=product.id, production_job_id=job.id,
        price=Decimal("399"), price_formula_base=Decimal("397"), is_active=True,
    ))
    await db.commit()
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_draft_with_referenced_variant_409(client: AsyncClient, db):
    """draft 商品若有 variant 被 OrderItem 引用 → 409，不可硬刪（避免 IntegrityError）。

    防護 update_product 把 on_sale → off_sale → draft 反向降級後變體仍被舊訂單引用的情境。
    """
    from datetime import UTC, datetime

    from auth.models import User
    from orders.models import Order, OrderItem, OrderStatusEnum

    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.draft)
    job = await _create_approved_job(db)
    variant = ProductVariant(
        product_id=product.id, production_job_id=job.id,
        price=Decimal("399"), price_formula_base=Decimal("397"), is_active=True,
    )
    db.add(variant)
    await db.flush()

    customer = User(
        name="cust",
        email=f"cust_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="x",
        role="customer",
        is_active=True,
        is_email_verified=True,
    )
    db.add(customer)
    await db.flush()
    order = Order(
        order_number=f"PL-{uuid.uuid4().hex[:8]}",
        user_id=customer.id, status=OrderStatusEnum.paid,
        subtotal=399, discount_amount=0, shipping_fee=0, total=399,
        shipping_type="home", shipping_snapshot={},
        created_at=datetime.now(UTC),
    )
    db.add(order)
    await db.flush()
    db.add(OrderItem(
        order_id=order.id,
        product_variant_id=variant.id,
        product_title_snapshot="x",
        variant_spec_snapshot={},
        unit_price=399, quantity=1, fulfilled_qty=0, preorder_qty=0,
        is_returned=False,
    ))
    await db.commit()

    res = await client.delete(f"{PRODUCTS_URL}/{product.id}")
    assert res.status_code == 409
    body = res.json()
    assert "訂單" in body.get("detail", "")


@pytest.mark.asyncio
async def test_delete_product_cascades_product_tags(client: AsyncClient, db):
    """刪除商品後 product_tags 關聯應自動移除。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db, status=ProductStatusEnum.off_sale)
    tag = Tag(name="刪除測試標籤")
    db.add(tag)
    await db.flush()
    db.add(ProductTag(product_id=product.id, tag_id=tag.id))
    await db.commit()

    await client.delete(f"{PRODUCTS_URL}/{product.id}")

    remaining = await db.execute(
        select(ProductTag).where(ProductTag.product_id == product.id)
    )
    assert remaining.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_product_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    assert (await client.delete(f"{PRODUCTS_URL}/{uuid.uuid4()}")).status_code == 404


# ── Images ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_image_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    res = await client.post(
        f"{PRODUCTS_URL}/{product.id}/images",
        json={"image_url": "http://img.test/1.png", "sort_order": 0},
    )
    assert res.status_code == 201
    assert res.json()["image_url"] == "http://img.test/1.png"


@pytest.mark.asyncio
async def test_delete_image_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    image = ProductImage(product_id=product.id, image_url="http://img.test/x.png", sort_order=0)
    db.add(image)
    await db.commit()
    await db.refresh(image)

    res = await client.delete(f"{PRODUCTS_URL}/{product.id}/images/{image.id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_image_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}/images/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reorder_images_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    img1 = ProductImage(product_id=product.id, image_url="http://img.test/1.png", sort_order=0)
    img2 = ProductImage(product_id=product.id, image_url="http://img.test/2.png", sort_order=1)
    db.add_all([img1, img2])
    await db.commit()
    await db.refresh(img1)
    await db.refresh(img2)

    res = await client.patch(
        f"{PRODUCTS_URL}/{product.id}/images/reorder",
        json={"order": [str(img2.id), str(img1.id)]},
    )
    assert res.status_code == 200
    items = res.json()["items"]
    assert items[0]["id"] == str(img2.id)
    assert items[0]["sort_order"] == 0
    assert items[1]["sort_order"] == 1


@pytest.mark.asyncio
async def test_reorder_images_wrong_product(client: AsyncClient, db):
    """order 裡包含不屬於此商品的 image_id → 400。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    img = ProductImage(product_id=product.id, image_url="http://img.test/x.png", sort_order=0)
    db.add(img)
    await db.commit()
    await db.refresh(img)

    res = await client.patch(
        f"{PRODUCTS_URL}/{product.id}/images/reorder",
        json={"order": [str(img.id), str(uuid.uuid4())]},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_reorder_images_partial_order(client: AsyncClient, db):
    """order 未包含全部圖片（缺少一張）→ 400。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    img1 = ProductImage(product_id=product.id, image_url="http://img.test/a.png", sort_order=0)
    img2 = ProductImage(product_id=product.id, image_url="http://img.test/b.png", sort_order=1)
    db.add_all([img1, img2])
    await db.commit()
    await db.refresh(img1)

    res = await client.patch(
        f"{PRODUCTS_URL}/{product.id}/images/reorder",
        json={"order": [str(img1.id)]},
    )
    assert res.status_code == 400


# ── Variants ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_variant_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)

    res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 450,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["price"] == "450.00"
    assert data["price_formula_base"] == "397.00"
    assert data["job_spec"]["difficulty"] == "beginner"


@pytest.mark.asyncio
async def test_create_variant_unapproved_job(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        approved=False,
        num_colors_used=18,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_variant_missing_num_colors(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        approved=True,
        num_colors_used=None,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_create_variant_conflict_overwrites(client: AsyncClient, db):
    """同 product + job 再次建立 → 覆蓋價格，不回 409。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)

    await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })
    res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 500,
    })
    assert res.status_code == 200
    assert res.json()["price"] == "500.00"

    count = await db.execute(
        select(ProductVariant).where(ProductVariant.product_id == product.id)
    )
    assert len(list(count.scalars().all())) == 1


@pytest.mark.asyncio
async def test_update_variant_price(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)
    create_res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })
    variant_id = create_res.json()["id"]

    res = await client.patch(f"{PRODUCTS_URL}/{product.id}/variants/{variant_id}", json={
        "price": 420
    })
    assert res.status_code == 200
    assert res.json()["price"] == "420.00"


@pytest.mark.asyncio
async def test_update_variant_deactivate(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)
    create_res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })
    variant_id = create_res.json()["id"]

    res = await client.patch(f"{PRODUCTS_URL}/{product.id}/variants/{variant_id}", json={
        "is_active": False
    })
    assert res.status_code == 200
    assert res.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_variant_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    res = await client.patch(
        f"{PRODUCTS_URL}/{product.id}/variants/{uuid.uuid4()}",
        json={"price": 400},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_variant_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)
    create_res = await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })
    variant_id = create_res.json()["id"]

    res = await client.delete(f"{PRODUCTS_URL}/{product.id}/variants/{variant_id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_variant_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    res = await client.delete(f"{PRODUCTS_URL}/{product.id}/variants/{uuid.uuid4()}")
    assert res.status_code == 404


# ── Available jobs ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_available_jobs_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_approved_job(db)

    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert "price_formula_base" in items[0]


@pytest.mark.asyncio
async def test_list_available_jobs_excludes_unapproved(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        approved=False, num_colors_used=18,
    )
    db.add(job)
    await db.commit()

    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_list_available_jobs_excludes_existing_variant(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)

    await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 397,
    })

    res = await client.get(
        "/api/v1/admin/production/jobs/available-for-variant",
        params={"product_id": str(product.id)},
    )
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_list_available_jobs_unfinalized_uses_filled_template(client: AsyncClient, db):
    """job 沒 filled_template_final_url → cover 來自 filled_template_url；is_finalized=False"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = await _create_approved_job(db)
    job.filled_template_url = "gs://test-bucket/production_jobs/x/filled_template.png"
    await db.commit()

    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["is_finalized"] is False
    # cover_url 用 _persistent_firebase_url 純字串轉換，不依賴 Firebase auth → 測試可靠
    assert items[0]["cover_url"] is not None
    assert "filled_template.png" in items[0]["cover_url"]
    # 不該指向 _final
    assert "filled_template_final" not in items[0]["cover_url"]


@pytest.mark.asyncio
async def test_list_available_jobs_finalized_prefers_final_filled(client: AsyncClient, db):
    """job 已 finalize（有 filled_template_final_url）→ cover 用 final 版；is_finalized=True

    Regression：之前永遠用 filled_template_url（演算法量化色版），導致商品封面跟塗色者
    真正畫出來的色彩有差。修正後優先用實體色版。
    """
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = await _create_approved_job(db)
    # 同時設兩個 url，模擬已 finalize 的 job
    job.filled_template_url = "gs://test-bucket/production_jobs/x/filled_template.png"
    job.filled_template_final_url = "gs://test-bucket/production_jobs/x/filled_template_final.png"
    await db.commit()

    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["is_finalized"] is True
    # cover_url 應該指向 _final.png（_persistent_firebase_url 純字串組裝，保留 path）
    assert items[0]["cover_url"] is not None
    assert "filled_template_final" in items[0]["cover_url"]


@pytest.mark.asyncio
async def test_list_available_jobs_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_list_available_jobs_unauthenticated(client: AsyncClient, db):
    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    assert res.status_code == 401


# ── Regression: cover_url 必須是 persistent firebase URL ─────────────────────────

@pytest.mark.asyncio
async def test_variant_job_spec_cover_url_is_persistent(client: AsyncClient, db):
    """Regression：admin 從變體模板選封面時，job_spec.cover_url 必須是
    Firebase download URL（無 TTL），而非 15-min signed URL；
    否則寫入 products.cover_image_url 後 15 分鐘就失效。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    product = await _create_product(db)
    job = await _create_approved_job(db)
    job.filled_template_url = "gs://test-bucket/production_jobs/abc/filled.png"
    await db.commit()

    await client.post(f"{PRODUCTS_URL}/{product.id}/variants", json={
        "production_job_id": str(job.id), "price": 450,
    })
    res = await client.get(f"{PRODUCTS_URL}/{product.id}/variants")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    cover = items[0]["job_spec"]["cover_url"]
    # 必須是 Firebase download URL 形式，不可是 signed URL（含 X-Goog-Signature）
    assert cover is not None
    assert cover.startswith("https://firebasestorage.googleapis.com/v0/b/"), (
        f"cover_url 必須是 persistent firebase download URL — 收到 {cover!r}"
    )
    assert "X-Goog-Signature" not in cover


@pytest.mark.asyncio
async def test_available_jobs_cover_url_is_persistent(client: AsyncClient, db):
    """Regression：available-for-variant endpoint 回的 cover_url 也必須是 persistent。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = await _create_approved_job(db)
    job.filled_template_url = "gs://test-bucket/production_jobs/abc/filled.png"
    await db.commit()

    res = await client.get("/api/v1/admin/production/jobs/available-for-variant")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    cover = items[0]["cover_url"]
    assert cover is not None
    assert cover.startswith("https://firebasestorage.googleapis.com/v0/b/"), (
        f"cover_url 必須是 persistent firebase download URL — 收到 {cover!r}"
    )
    assert "X-Goog-Signature" not in cover


# ── Auth guards (products) ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_product_endpoints_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    fake_id = uuid.uuid4()
    assert (await client.get(f"{PRODUCTS_URL}/{fake_id}")).status_code == 403
    assert (await client.put(f"{PRODUCTS_URL}/{fake_id}", json={
        "title": "X", "cover_image_url": "http://x", "status": "draft"
    })).status_code == 403
    assert (await client.delete(f"{PRODUCTS_URL}/{fake_id}")).status_code == 403
