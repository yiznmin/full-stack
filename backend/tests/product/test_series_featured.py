"""Series is_featured 欄位測試（Module 18）。"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User
from product.models import ProductSeries

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ADMIN_SERIES_URL = "/api/v1/admin/series"
PUBLIC_SERIES_URL = "/api/v1/series"

ADMIN_USER = {
    "name": "系列精選管理員",
    "email": "series_featured_admin@example.com",
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


# ── 預設值 ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_series_default_not_featured(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(ADMIN_SERIES_URL, json={"name": "預設系列"})
    assert res.status_code == 201
    body = res.json()
    assert body["is_featured"] is False


@pytest.mark.asyncio
async def test_create_series_with_featured_true(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(
        ADMIN_SERIES_URL,
        json={"name": "精選系列", "is_featured": True},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["is_featured"] is True


# ── Update toggle ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_series_toggle_featured_on(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    series = ProductSeries(name="待精選系列")
    db.add(series)
    await db.commit()
    await db.refresh(series)

    res = await client.put(
        f"{ADMIN_SERIES_URL}/{series.id}",
        json={"name": "待精選系列", "is_featured": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_featured"] is True


@pytest.mark.asyncio
async def test_update_series_toggle_featured_off(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    series = ProductSeries(name="精選後撤回", is_featured=True)
    db.add(series)
    await db.commit()
    await db.refresh(series)

    res = await client.put(
        f"{ADMIN_SERIES_URL}/{series.id}",
        json={"name": "精選後撤回", "is_featured": False},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["is_featured"] is False


# ── Public list with featured filter ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_public_list_series_default_includes_is_featured(client: AsyncClient, db):
    """無 query 預設回全部，每筆 response 含 is_featured 欄位。"""
    db.add_all([
        ProductSeries(name="一般系列 A"),
        ProductSeries(name="精選系列 B", is_featured=True),
    ])
    await db.commit()

    res = await client.get(PUBLIC_SERIES_URL)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 2
    assert all("is_featured" in s for s in items)
    by_name = {s["name"]: s for s in items}
    assert by_name["一般系列 A"]["is_featured"] is False
    assert by_name["精選系列 B"]["is_featured"] is True


@pytest.mark.asyncio
async def test_public_list_series_featured_true_filter(client: AsyncClient, db):
    db.add_all([
        ProductSeries(name="一般系列 X"),
        ProductSeries(name="精選 Y", is_featured=True),
        ProductSeries(name="精選 Z", is_featured=True),
    ])
    await db.commit()

    res = await client.get(PUBLIC_SERIES_URL, params={"featured": "true"})
    assert res.status_code == 200
    items = res.json()["items"]
    names = sorted(s["name"] for s in items)
    assert names == ["精選 Y", "精選 Z"]
    assert all(s["is_featured"] is True for s in items)


@pytest.mark.asyncio
async def test_public_list_series_featured_false_filter(client: AsyncClient, db):
    db.add_all([
        ProductSeries(name="一般 P"),
        ProductSeries(name="精選 Q", is_featured=True),
    ])
    await db.commit()

    res = await client.get(PUBLIC_SERIES_URL, params={"featured": "false"})
    assert res.status_code == 200
    items = res.json()["items"]
    names = [s["name"] for s in items]
    assert names == ["一般 P"]
    assert items[0]["is_featured"] is False


# ── Admin list response includes is_featured ────────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_series_with_featured(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    db.add_all([
        ProductSeries(name="admin 一般"),
        ProductSeries(name="admin 精選", is_featured=True),
    ])
    await db.commit()

    res = await client.get(ADMIN_SERIES_URL)
    assert res.status_code == 200
    items = res.json()["items"]
    by_name = {s["name"]: s for s in items}
    assert by_name["admin 一般"]["is_featured"] is False
    assert by_name["admin 精選"]["is_featured"] is True
