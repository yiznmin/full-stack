"""Product is_featured 欄位測試（Module 19）。"""
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User
from product.models import Product, ProductStatusEnum, ProductVariant
from production.models import ProductionJob

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ADMIN_PRODUCTS_URL = "/api/v1/admin/products"
PUBLIC_PRODUCTS_URL = "/api/v1/products"

ADMIN_USER = {
    "name": "商品精選管理員",
    "email": "product_featured_admin@example.com",
    "password": "adminpass123",
}


async def _make_admin(client, db):
    await client.post(REGISTER_URL, json=ADMIN_USER)
    result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    user.role = "admin"
    await db.commit()


async def _login(client, email, password):
    res = await client.post(LOGIN_URL, json={"email": email, "password": password})
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])


async def _create_on_sale_product(db, title="測試商品", is_featured=False):
    """建一個 on_sale 商品 + 一個 active variant（讓 public list 撈得到）"""
    product = Product(
        title=title,
        cover_image_url="http://img.test/cover.png",
        status=ProductStatusEnum.on_sale,
        is_featured=is_featured,
    )
    db.add(product)
    await db.flush()

    job = ProductionJob(
        canvas_w_cm=30,
        canvas_h_cm=40,
        difficulty="beginner",
        detail="standard",
        num_colors_used=18,
        approved=True,
        status="completed",
        filled_template_url="http://example.com/filled.png",
    )
    db.add(job)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        production_job_id=job.id,
        price=Decimal("397"),
        price_formula_base=Decimal("397"),
        is_active=True,
    )
    db.add(variant)
    await db.commit()
    await db.refresh(product)
    return product


# ── 預設值 ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_product_default_not_featured(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(
        ADMIN_PRODUCTS_URL,
        json={
            "title": "預設商品",
            "cover_image_url": "http://img.test/x.png",
            "status": "draft",
        },
    )
    assert res.status_code == 201
    assert res.json()["is_featured"] is False


@pytest.mark.asyncio
async def test_create_product_with_featured_true(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(
        ADMIN_PRODUCTS_URL,
        json={
            "title": "精選商品",
            "cover_image_url": "http://img.test/x.png",
            "status": "draft",
            "is_featured": True,
        },
    )
    assert res.status_code == 201
    assert res.json()["is_featured"] is True


# ── Update toggle ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_product_toggle_featured(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    product = Product(
        title="待精選商品",
        cover_image_url="http://img.test/x.png",
        status=ProductStatusEnum.draft,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    res = await client.put(
        f"{ADMIN_PRODUCTS_URL}/{product.id}",
        json={
            "title": "待精選商品",
            "cover_image_url": "http://img.test/x.png",
            "status": "draft",
            "is_featured": True,
        },
    )
    assert res.status_code == 200
    assert res.json()["is_featured"] is True


# ── Public list with featured filter ────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_list_products_default_includes_is_featured(client: AsyncClient, db):
    await _create_on_sale_product(db, "一般商品", is_featured=False)
    await _create_on_sale_product(db, "精選商品", is_featured=True)

    res = await client.get(PUBLIC_PRODUCTS_URL)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 2
    assert all("is_featured" in p for p in items)
    by_title = {p["title"]: p for p in items}
    assert by_title["一般商品"]["is_featured"] is False
    assert by_title["精選商品"]["is_featured"] is True


@pytest.mark.asyncio
async def test_public_list_products_featured_true_filter(client: AsyncClient, db):
    await _create_on_sale_product(db, "一般 X", is_featured=False)
    await _create_on_sale_product(db, "精選 Y", is_featured=True)
    await _create_on_sale_product(db, "精選 Z", is_featured=True)

    res = await client.get(PUBLIC_PRODUCTS_URL, params={"featured": "true"})
    assert res.status_code == 200
    items = res.json()["items"]
    titles = sorted(p["title"] for p in items)
    assert titles == ["精選 Y", "精選 Z"]
    assert all(p["is_featured"] is True for p in items)
