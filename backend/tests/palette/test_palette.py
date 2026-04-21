import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User
from color.models import PhysicalColor, SystemSetting
from palette.models import MappedByEnum, PaletteColorMapping
from production.models import JobStatusEnum, ProductionJob

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"

ADMIN_USER = {
    "name": "調色管理員", "email": "palette_admin@example.com", "password": "adminpass123"
}
CUSTOMER_USER = {
    "name": "一般用戶", "email": "palette_customer@example.com", "password": "custpass123"
}

PALETTE_JSON = [
    {"template_id": 1, "rgb": {"r": 247, "g": 167, "b": 132}, "percent": 0.40},
    {"template_id": 2, "rgb": {"r": 100, "g": 50, "b": 200}, "percent": 0.35},
]

VALID_JOB = {
    "detail": "standard",
    "difficulty": "beginner",
    "mode": "standard",
    "canvas_w_cm": 30,
    "canvas_h_cm": 40,
    "palette_json": PALETTE_JSON,
    "status": "completed",
}

COLOR_A = {
    "code": "PAL-001",
    "name": "SKIN",
    "color_family": "膚色系",
    "brand": None,
    "rgb": {"rgb_r": 247, "rgb_g": 167, "rgb_b": 132},
    "stock_ml": 500.0,
}

COLOR_B = {
    "code": "PAL-002",
    "name": "BLUE",
    "color_family": "藍色系",
    "brand": None,
    "rgb": {"rgb_r": 100, "rgb_g": 50, "rgb_b": 200},
    "stock_ml": 300.0,
}


def _palette_url(job_id):
    return f"/api/v1/admin/production/jobs/{job_id}/palette-mappings"


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


_UNSET = object()


async def _create_job_with_palette(db, palette_json=_UNSET) -> ProductionJob:
    job = ProductionJob(
        detail="standard",
        difficulty="beginner",
        mode="standard",
        canvas_w_cm=30,
        canvas_h_cm=40,
        status=JobStatusEnum.completed,
        palette_json=PALETTE_JSON if palette_json is _UNSET else palette_json,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _create_color(db, data: dict) -> PhysicalColor:
    color = PhysicalColor(**data)
    db.add(color)
    await db.commit()
    await db.refresh(color)
    return color


async def _seed_settings(db):
    for key, value in [
        ("paint_ml_per_cm2", "0.05"),
        ("paint_min_ml", "5.0"),
        ("paint_buffer_ratio", "1.2"),
    ]:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        if not result.scalar_one_or_none():
            db.add(SystemSetting(key=key, value=value))
    await db.commit()


# ── GET palette-mappings ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_mappings_auto_creates(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _create_job_with_palette(db)

    res = await client.get(_palette_url(job.id))
    assert res.status_code == 200
    data = res.json()
    assert len(data["mappings"]) == len(PALETTE_JSON)
    first = data["mappings"][0]
    assert first["mapped_by"] == "system"
    assert "rgb_r" in first["algorithm_rgb"]
    assert "id" in first["physical_color"]


@pytest.mark.asyncio
async def test_get_mappings_does_not_duplicate(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _create_job_with_palette(db)

    await client.get(_palette_url(job.id))
    res = await client.get(_palette_url(job.id))
    assert res.status_code == 200
    assert len(res.json()["mappings"]) == len(PALETTE_JSON)


@pytest.mark.asyncio
async def test_get_mappings_no_palette_json(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = await _create_job_with_palette(db, palette_json=None)

    res = await client.get(_palette_url(job.id))
    assert res.status_code == 200
    assert res.json()["mappings"] == []


@pytest.mark.asyncio
async def test_get_mappings_no_active_colors(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = await _create_job_with_palette(db)

    res = await client.get(_palette_url(job.id))
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_get_mappings_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(_palette_url(uuid.uuid4()))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_mappings_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get(_palette_url(uuid.uuid4()))
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_mappings_unauthenticated(client: AsyncClient, db):
    res = await client.get(_palette_url(uuid.uuid4()))
    assert res.status_code == 401


# ── PUT palette-mappings/{template_id} ────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_mapping_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    color_b = await _create_color(db, COLOR_B)
    job = await _create_job_with_palette(db)

    await client.get(_palette_url(job.id))

    res = await client.put(
        f"{_palette_url(job.id)}/1",
        json={"physical_color_id": str(color_b.id)},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["mapped_by"] == "manual"
    assert data["physical_color"]["id"] == str(color_b.id)
    assert data["required_ml"] is None


@pytest.mark.asyncio
async def test_update_mapping_color_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    job = await _create_job_with_palette(db)
    await client.get(_palette_url(job.id))

    res = await client.put(
        f"{_palette_url(job.id)}/1",
        json={"physical_color_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_mapping_inactive_color(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    color_b = await _create_color(db, COLOR_B)
    job = await _create_job_with_palette(db)
    await client.get(_palette_url(job.id))

    result = await db.execute(select(PhysicalColor).where(PhysicalColor.id == color_b.id))
    pc = result.scalar_one()
    pc.is_active = False
    await db.commit()

    res = await client.put(
        f"{_palette_url(job.id)}/1",
        json={"physical_color_id": str(color_b.id)},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_mapping_template_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    color_a = await _create_color(db, COLOR_A)
    job = await _create_job_with_palette(db)

    res = await client.put(
        f"{_palette_url(job.id)}/999",
        json={"physical_color_id": str(color_a.id)},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_mapping_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.put(
        f"{_palette_url(uuid.uuid4())}/1",
        json={"physical_color_id": str(uuid.uuid4())},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_update_mapping_unauthenticated(client: AsyncClient, db):
    res = await client.put(
        f"{_palette_url(uuid.uuid4())}/1",
        json={"physical_color_id": str(uuid.uuid4())},
    )
    assert res.status_code == 401


# ── POST palette-mappings/copy-from/{source_job_id} ───────────────────────────

@pytest.mark.asyncio
async def test_copy_from_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)

    source_job = await _create_job_with_palette(db)
    target_job = await _create_job_with_palette(db)

    await client.get(_palette_url(source_job.id))

    res = await client.post(
        f"{_palette_url(target_job.id)}/copy-from/{source_job.id}"
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["mappings"]) == len(PALETTE_JSON)
    assert all(m["mapped_by"] == "manual" for m in data["mappings"])


@pytest.mark.asyncio
async def test_copy_from_source_no_mappings(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    source_job = await _create_job_with_palette(db)
    target_job = await _create_job_with_palette(db)

    res = await client.post(
        f"{_palette_url(target_job.id)}/copy-from/{source_job.id}"
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_copy_from_overwrites_existing(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    color_b = await _create_color(db, COLOR_B)

    source_job = await _create_job_with_palette(db)
    target_job = await _create_job_with_palette(db)

    await client.get(_palette_url(source_job.id))
    await client.get(_palette_url(target_job.id))

    await client.put(
        f"{_palette_url(source_job.id)}/1",
        json={"physical_color_id": str(color_b.id)},
    )

    res = await client.post(
        f"{_palette_url(target_job.id)}/copy-from/{source_job.id}"
    )
    assert res.status_code == 200
    mappings = {m["template_id"]: m for m in res.json()["mappings"]}
    assert mappings[1]["physical_color"]["id"] == str(color_b.id)


@pytest.mark.asyncio
async def test_copy_from_inactive_source_color(client: AsyncClient, db):
    """Source job has mapping pointing to a now-inactive color → 400."""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    color_b = await _create_color(db, COLOR_B)
    source_job = await _create_job_with_palette(db)
    target_job = await _create_job_with_palette(db)

    await client.get(_palette_url(source_job.id))

    # Deactivate color_b (mapped to template_id=2 after auto-map)
    result = await db.execute(select(PhysicalColor).where(PhysicalColor.id == color_b.id))
    pc = result.scalar_one()
    pc.is_active = False
    await db.commit()

    res = await client.post(f"{_palette_url(target_job.id)}/copy-from/{source_job.id}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_copy_from_self_reference(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    job = await _create_job_with_palette(db)
    await client.get(_palette_url(job.id))

    res = await client.post(f"{_palette_url(job.id)}/copy-from/{job.id}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_copy_from_source_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    target_job = await _create_job_with_palette(db)

    res = await client.post(
        f"{_palette_url(target_job.id)}/copy-from/{uuid.uuid4()}"
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_copy_from_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(
        f"{_palette_url(uuid.uuid4())}/copy-from/{uuid.uuid4()}"
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_copy_from_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        f"{_palette_url(uuid.uuid4())}/copy-from/{uuid.uuid4()}"
    )
    assert res.status_code == 401


# ── POST palette-mappings/complete ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_complete_all_stocked(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    await _seed_settings(db)
    job = await _create_job_with_palette(db)

    await client.get(_palette_url(job.id))

    res = await client.post(f"{_palette_url(job.id)}/complete")
    assert res.status_code == 200
    data = res.json()
    assert data["all_stocked"] is True
    assert data["shortage_colors"] == []


@pytest.mark.asyncio
async def test_complete_with_shortage(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    low_stock = {**COLOR_A, "code": "PAL-LOW", "stock_ml": 0.1}
    await _create_color(db, low_stock)
    await _create_color(db, COLOR_B)
    await _seed_settings(db)
    job = await _create_job_with_palette(db)

    await client.get(_palette_url(job.id))

    res = await client.post(f"{_palette_url(job.id)}/complete")
    assert res.status_code == 200
    data = res.json()
    assert data["all_stocked"] is False
    assert len(data["shortage_colors"]) >= 1


@pytest.mark.asyncio
async def test_complete_no_mappings(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    job = await _create_job_with_palette(db, palette_json=None)

    res = await client.post(f"{_palette_url(job.id)}/complete")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_complete_partial_mappings(client: AsyncClient, db):
    """palette_json has 2 template_ids but only 1 is mapped → 400."""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    color_a = await _create_color(db, COLOR_A)
    await _seed_settings(db)
    job = await _create_job_with_palette(db)

    # Only map template_id=1, leave template_id=2 unmapped
    db.add(PaletteColorMapping(
        production_job_id=job.id,
        template_id=1,
        algorithm_rgb=[247, 167, 132],
        physical_color_id=color_a.id,
        mapped_by=MappedByEnum.system,
    ))
    await db.commit()

    res = await client.post(f"{_palette_url(job.id)}/complete")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_complete_job_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(f"{_palette_url(uuid.uuid4())}/complete")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_complete_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(f"{_palette_url(uuid.uuid4())}/complete")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_complete_unauthenticated(client: AsyncClient, db):
    res = await client.post(f"{_palette_url(uuid.uuid4())}/complete")
    assert res.status_code == 401
