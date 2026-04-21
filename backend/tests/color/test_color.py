import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User

COLORS_URL = "/api/v1/admin/colors"

ADMIN_USER = {
    "name": "色庫管理員", "email": "color_admin@example.com", "password": "adminpass123"
}
CUSTOMER_USER = {
    "name": "一般用戶", "email": "color_customer@example.com", "password": "custpass123"
}

VALID_COLOR = {
    "code": "201",
    "name": "SKIN TONE",
    "color_family": "膚色系",
    "brand": None,
    "rgb": {"rgb_r": 247, "rgb_g": 167, "rgb_b": 132},
    "stock_ml": 500.0,
}


async def _make_admin(client, db):
    await client.post("/api/v1/auth/register", json=ADMIN_USER)
    result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    user.role = "admin"
    await db.commit()


async def _make_customer(client, db):
    await client.post("/api/v1/auth/register", json=CUSTOMER_USER)
    result = await db.execute(select(User).where(User.email == CUSTOMER_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    await db.commit()


async def _login(client, email, password):
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])


async def _create_color(client, db, data=None) -> dict:
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(COLORS_URL, json=data or VALID_COLOR)
    return res.json()


# ── GET /admin/colors ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_colors_empty(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(COLORS_URL)
    assert res.status_code == 200
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_list_colors_with_data(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.get(COLORS_URL)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_colors_filter_family(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.get(COLORS_URL, params={"color_family": "膚色系"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = await client.get(COLORS_URL, params={"color_family": "藍色系"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_list_colors_filter_active(client: AsyncClient, db):
    color = await _create_color(client, db)
    await client.patch(f"{COLORS_URL}/{color['id']}/toggle-active")

    res = await client.get(COLORS_URL, params={"is_active": "false"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = await client.get(COLORS_URL, params={"is_active": "true"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_list_colors_search(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.get(COLORS_URL, params={"search": "SKIN"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = await client.get(COLORS_URL, params={"search": "BLUE"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_list_colors_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.get(COLORS_URL)).status_code == 403


@pytest.mark.asyncio
async def test_list_colors_unauthenticated(client: AsyncClient, db):
    assert (await client.get(COLORS_URL)).status_code == 401


# ── POST /admin/colors ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_color_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(COLORS_URL, json=VALID_COLOR)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "201"
    assert data["stock_ml"] == 500.0


@pytest.mark.asyncio
async def test_create_color_duplicate_code(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.post(COLORS_URL, json=VALID_COLOR)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_create_color_invalid_rgb(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    bad = {**VALID_COLOR, "rgb": {"rgb_r": 300, "rgb_g": 0, "rgb_b": 0}}
    res = await client.post(COLORS_URL, json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_color_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.post(COLORS_URL, json=VALID_COLOR)).status_code == 403


@pytest.mark.asyncio
async def test_create_color_unauthenticated(client: AsyncClient, db):
    assert (await client.post(COLORS_URL, json=VALID_COLOR)).status_code == 401


# ── PUT /admin/colors/{id} ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_color_duplicate_code(client: AsyncClient, db):
    color = await _create_color(client, db)
    second = {**VALID_COLOR, "code": "202", "name": "SECOND COLOR"}
    await client.post(COLORS_URL, json=second)
    res = await client.put(
        f"{COLORS_URL}/{color['id']}",
        json={**VALID_COLOR, "code": "202"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_color_ok(client: AsyncClient, db):
    color = await _create_color(client, db)
    updated = {**VALID_COLOR, "name": "UPDATED NAME"}
    res = await client.put(f"{COLORS_URL}/{color['id']}", json=updated)
    assert res.status_code == 200
    assert res.json()["name"] == "UPDATED NAME"


@pytest.mark.asyncio
async def test_update_color_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.put(f"{COLORS_URL}/{uuid.uuid4()}", json=VALID_COLOR)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_color_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.put(f"{COLORS_URL}/{uuid.uuid4()}", json=VALID_COLOR)).status_code == 403


@pytest.mark.asyncio
async def test_update_color_unauthenticated(client: AsyncClient, db):
    assert (await client.put(f"{COLORS_URL}/{uuid.uuid4()}", json=VALID_COLOR)).status_code == 401


# ── PATCH /admin/colors/{id}/toggle-active ────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_active_ok(client: AsyncClient, db):
    color = await _create_color(client, db)
    assert color["is_active"] is True

    res = await client.patch(f"{COLORS_URL}/{color['id']}/toggle-active")
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    res = await client.patch(f"{COLORS_URL}/{color['id']}/toggle-active")
    assert res.json()["is_active"] is True


@pytest.mark.asyncio
async def test_toggle_active_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    assert (await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/toggle-active")).status_code == 404


@pytest.mark.asyncio
async def test_toggle_active_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/toggle-active")).status_code == 403


@pytest.mark.asyncio
async def test_toggle_active_unauthenticated(client: AsyncClient, db):
    assert (await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/toggle-active")).status_code == 401


# ── PATCH /admin/colors/{id}/stock ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_stock_ok(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 250.0})
    assert res.status_code == 200
    data = res.json()
    assert data["new_stock_ml"] == 750.0
    assert data["fulfilled_orders"] == 0


@pytest.mark.asyncio
async def test_add_stock_invalid(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 0})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_add_stock_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    assert (
        await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/stock", json={"add_ml": 100})
    ).status_code == 404


@pytest.mark.asyncio
async def test_add_stock_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (
        await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/stock", json={"add_ml": 100})
    ).status_code == 403


@pytest.mark.asyncio
async def test_add_stock_unauthenticated(client: AsyncClient, db):
    assert (
        await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/stock", json={"add_ml": 100})
    ).status_code == 401


# ── GET /admin/colors/shortage-dashboard ──────────────────────────────────────

@pytest.mark.asyncio
async def test_shortage_dashboard_empty(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(f"{COLORS_URL}/shortage-dashboard")
    assert res.status_code == 200
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_shortage_dashboard_with_shortage(client: AsyncClient, db):
    from uuid import UUID

    from palette.models import PaletteColorMapping
    from production.models import ProductionJob

    color = await _create_color(client, db)
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        palette_json=[{"template_id": 1, "rgb": {"r": 247, "g": 167, "b": 132}, "percent": 0.5}],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    db.add(PaletteColorMapping(
        production_job_id=job.id,
        template_id=1,
        algorithm_rgb=[247, 167, 132],
        physical_color_id=UUID(color["id"]),
        required_ml=9999.0,
    ))
    await db.commit()

    res = await client.get(f"{COLORS_URL}/shortage-dashboard")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["code"] == "201"
    assert items[0]["shortage_ml"] > 0


@pytest.mark.asyncio
async def test_shortage_dashboard_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.get(f"{COLORS_URL}/shortage-dashboard")).status_code == 403


@pytest.mark.asyncio
async def test_shortage_dashboard_unauthenticated(client: AsyncClient, db):
    assert (await client.get(f"{COLORS_URL}/shortage-dashboard")).status_code == 401
