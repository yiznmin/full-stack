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
    "rgb": [247, 167, 132],
    "stock_ml": 500.0,
}

COLOR_B = {
    "code": "PAL-002",
    "name": "BLUE",
    "color_family": "藍色系",
    "brand": None,
    "rgb": [100, 50, 200],
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
    assert isinstance(first["algorithm_rgb"], list) and len(first["algorithm_rgb"]) == 3
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


# ── finalize_template (對應完成後產出實體色版最終模板) ──────────────────────

# palette_json 帶 pixels，模擬 pbn_gen 的真實輸出
_PALETTE_FOR_FINALIZE = [
    {"template_id": 1, "rgb": [247, 167, 132], "percent": 0.40, "pixels": 4000},
    {"template_id": 2, "rgb": [100, 50, 200],  "percent": 0.35, "pixels": 3500},
    {"template_id": 3, "rgb": [50, 200, 100],  "percent": 0.25, "pixels": 2500},
]

# pbn_gen 的 polygon fill = 25% 原色 + 75% 白；mock 必須對得起來才能讓
# svg_consolidate 真的跑 union（不會 fallback 到只換文字）。
# tid 1 [247,167,132] → #FDE9E0; tid 2 [100,50,200] → #D8CBF1; tid 3 [50,200,100] → #CBF1D8
_SVG_TEMPLATE = (
    b'<?xml version="1.0" encoding="UTF-8"?>'
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<rect x="0" y="0" width="100" height="100" fill="white"/>'
    b'<polygon id="r0" points="0,0 40,0 0,40" fill="#FDE9E0" stroke="#AAAAAA" stroke-width="0.5"/>'   # tid 1
    b'<polygon id="r1" points="60,0 100,0 60,40" fill="#D8CBF1" stroke="#AAAAAA" stroke-width="0.5"/>'  # tid 2
    b'<polygon id="r2" points="0,60 40,60 0,100" fill="#CBF1D8" stroke="#AAAAAA" stroke-width="0.5"/>'  # tid 3
    b'<g id="0"><text x="10" y="10">1</text></g>'
    b'<g id="1"><text x="20" y="20">2</text></g>'
    b'<g id="2"><text x="30" y="30">3</text></g>'
    b'</svg>'
)


async def _setup_job_for_finalize(db, mappings_spec: list[tuple[int, str]]):
    """建立 svg_url+palette_json 齊全的 job + 對應 mappings。
    mappings_spec: [(template_id, color_code), ...]，color_code 找 PhysicalColor。
    """
    from palette.models import MappedByEnum, PaletteColorMapping
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        palette_json=_PALETTE_FOR_FINALIZE,
        svg_url="gs://test-bucket/production_jobs/xxx/template.svg",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    job.svg_url = f"gs://test-bucket/production_jobs/{job.id}/template.svg"
    code_to_color = {}
    for _, code in mappings_spec:
        if code in code_to_color:
            continue
        result = await db.execute(select(PhysicalColor).where(PhysicalColor.code == code))
        code_to_color[code] = result.scalar_one()
    for tid, code in mappings_spec:
        db.add(PaletteColorMapping(
            production_job_id=job.id,
            template_id=tid,
            algorithm_rgb=[0, 0, 0],
            physical_color_id=code_to_color[code].id,
            mapped_by=MappedByEnum.system,
        ))
    await db.commit()
    return job


def _mock_bucket_for_finalize(svg_bytes: bytes = _SVG_TEMPLATE):
    """產生 mock bucket：download_as_bytes 回 svg_bytes；upload_from_string 收 capture。"""
    from unittest.mock import MagicMock
    captured: dict[str, bytes] = {}

    def make_blob(path: str):
        b = MagicMock(name=f"blob:{path}")
        b.download_as_bytes = MagicMock(return_value=svg_bytes)
        def _upload(data, content_type=None):  # noqa: ARG001
            captured[path] = data if isinstance(data, bytes) else data.encode("utf-8")
        b.upload_from_string = MagicMock(side_effect=_upload)
        return b

    bucket = MagicMock()
    bucket.name = "test-bucket"
    bucket.blob = MagicMock(side_effect=make_blob)
    return bucket, captured


@pytest.mark.asyncio
async def test_finalize_groups_by_physical_color(db):
    """3 個 template 對到 2 個物理色 → output_label 應為 {1: 不重複, 2: 不重複}。
    同物理色的 template 拿到同一 label。"""
    from unittest.mock import patch
    from palette.service import finalize_template
    from palette.models import PaletteColorMapping
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    # template 1, 3 → COLOR_A；template 2 → COLOR_B
    job = await _setup_job_for_finalize(db, [(1, "PAL-001"), (2, "PAL-002"), (3, "PAL-001")])

    bucket, captured = _mock_bucket_for_finalize()
    with patch("core.firebase.get_bucket", return_value=bucket):
        result = await finalize_template(db, job.id)

    assert result["output_labels_count"] == 2
    # 重抓 mappings 確認 output_label 寫進去
    rows = list((await db.execute(
        select(PaletteColorMapping).where(PaletteColorMapping.production_job_id == job.id)
    )).scalars().all())
    by_tid = {m.template_id: m.output_label for m in rows}
    # template 1 跟 3 對到同色 → 應同 label
    assert by_tid[1] == by_tid[3]
    # template 2 對到別色 → 不同 label
    assert by_tid[2] != by_tid[1]
    # 兩個 label 必為 {1, 2}
    assert set(by_tid.values()) == {1, 2}


@pytest.mark.asyncio
async def test_finalize_largest_area_gets_label_1(db):
    """COLOR_A 對 template 1+3（pixels 4000+2500=6500），COLOR_B 對 template 2（3500）
    → COLOR_A 面積大 → label 1，COLOR_B → label 2"""
    from unittest.mock import patch
    from palette.service import finalize_template
    from palette.models import PaletteColorMapping
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _setup_job_for_finalize(db, [(1, "PAL-001"), (2, "PAL-002"), (3, "PAL-001")])

    bucket, _ = _mock_bucket_for_finalize()
    with patch("core.firebase.get_bucket", return_value=bucket):
        await finalize_template(db, job.id)

    rows = list((await db.execute(
        select(PaletteColorMapping).where(PaletteColorMapping.production_job_id == job.id)
    )).scalars().all())
    by_tid = {m.template_id: m.output_label for m in rows}
    # COLOR_A 群（template 1, 3）label = 1
    assert by_tid[1] == 1
    assert by_tid[3] == 1
    # COLOR_B 群（template 2）label = 2
    assert by_tid[2] == 2


@pytest.mark.asyncio
async def test_finalize_uploads_svg_and_palette_final(db):
    """確認 template_final.svg 與 palette_final.json 都被上傳到正確路徑。"""
    from unittest.mock import patch
    from palette.service import finalize_template
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _setup_job_for_finalize(db, [(1, "PAL-001"), (2, "PAL-002"), (3, "PAL-001")])

    bucket, captured = _mock_bucket_for_finalize()
    with patch("core.firebase.get_bucket", return_value=bucket):
        await finalize_template(db, job.id)

    svg_key = f"production_jobs/{job.id}/template_final.svg"
    json_key = f"production_jobs/{job.id}/palette_final.json"
    assert svg_key in captured
    assert json_key in captured

    # SVG 內容應該已換 label：原 template_id 1/2/3 → output_label 1/2/1
    # 經 consolidate 後 tid 1+3 合併（兩個分離 polygon → MultiPolygon → 各 part 各放
    # 一個 label "1"），tid 2 → 單一 polygon 放一個 label "2"
    # 順序由 polygons_by_label 插入順序決定（label 1 先，label 2 後）
    import xml.etree.ElementTree as ET
    root = ET.fromstring(captured[svg_key])
    texts = [t.text for t in root.iter("{http://www.w3.org/2000/svg}text")]
    # 計數比順序穩：2 個 "1"（label 1 兩個分離 part）+ 1 個 "2"
    assert sorted(texts) == ["1", "1", "2"], f"got texts={texts}"

    # 應該只有 2 個 <path>（每個 output_label 一個）
    paths = root.findall("{http://www.w3.org/2000/svg}path")
    assert len(paths) == 2

    # palette_final.json 結構正確、按 output_label 排序
    import json
    palette = json.loads(captured[json_key])
    assert len(palette) == 2
    assert palette[0]["output_label"] == 1
    assert palette[1]["output_label"] == 2
    # 大面積的色（label 1）member_template_ids 應該含 1, 3
    assert sorted(palette[0]["member_template_ids"]) == [1, 3]
    assert palette[1]["member_template_ids"] == [2]


@pytest.mark.asyncio
async def test_finalize_updates_job_columns(db):
    """job.template_final_url / palette_final_url / finalized_at 都該被寫入。"""
    from unittest.mock import patch
    from palette.service import finalize_template
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _setup_job_for_finalize(db, [(1, "PAL-001"), (2, "PAL-002"), (3, "PAL-001")])

    bucket, _ = _mock_bucket_for_finalize()
    with patch("core.firebase.get_bucket", return_value=bucket):
        await finalize_template(db, job.id)

    await db.refresh(job)
    assert job.template_final_url is not None
    assert job.template_final_url.endswith("/template_final.svg")
    assert job.palette_final_url is not None
    assert job.palette_final_url.endswith("/palette_final.json")
    assert job.finalized_at is not None


@pytest.mark.asyncio
async def test_finalize_idempotent(db):
    """重跑 finalize → 結果一致、不爆。"""
    from unittest.mock import patch
    from palette.service import finalize_template
    from palette.models import PaletteColorMapping
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _setup_job_for_finalize(db, [(1, "PAL-001"), (2, "PAL-002"), (3, "PAL-001")])

    bucket, _ = _mock_bucket_for_finalize()
    with patch("core.firebase.get_bucket", return_value=bucket):
        await finalize_template(db, job.id)
        first = {m.template_id: m.output_label for m in (await db.execute(
            select(PaletteColorMapping).where(PaletteColorMapping.production_job_id == job.id)
        )).scalars().all()}
        # 重跑（mock 一樣返回原 svg）
        await finalize_template(db, job.id)
        second = {m.template_id: m.output_label for m in (await db.execute(
            select(PaletteColorMapping).where(PaletteColorMapping.production_job_id == job.id)
        )).scalars().all()}
    assert first == second


@pytest.mark.asyncio
async def test_finalize_generates_filled_template_final_png(db):
    """job.snapped_rgb_url 存在時，finalize 額外產出物理色版 filled preview PNG。

    流程：讀 snapped_rgb.png → 每個 algorithm RGB pixel 替換為對應物理色 RGB
    → 上傳 filled_template_final.png + 寫入 job.filled_template_final_url。
    """
    import io
    from unittest.mock import MagicMock, patch

    import numpy as np
    from PIL import Image

    from palette.service import finalize_template

    # 用獨特的 RGB 確保替換可驗證（避免 algorithm 與 physical 同色）
    custom_a = {**COLOR_A, "code": "FF-A", "rgb": [10, 20, 30]}
    custom_b = {**COLOR_B, "code": "FF-B", "rgb": [40, 50, 60]}
    await _create_color(db, custom_a)
    await _create_color(db, custom_b)

    # 用 _setup_job_for_finalize 建 job + mappings；但 PAL-001/PAL-002 不存在，自建
    from palette.models import MappedByEnum, PaletteColorMapping
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        palette_json=_PALETTE_FOR_FINALIZE,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    job.svg_url = f"gs://test-bucket/production_jobs/{job.id}/template.svg"
    job.snapped_rgb_url = f"gs://test-bucket/production_jobs/{job.id}/snapped_rgb.png"

    pc_a = (await db.execute(select(PhysicalColor).where(PhysicalColor.code == "FF-A"))).scalar_one()
    pc_b = (await db.execute(select(PhysicalColor).where(PhysicalColor.code == "FF-B"))).scalar_one()
    # template 1, 3 → custom_a；template 2 → custom_b
    for tid, color in [(1, pc_a), (2, pc_b), (3, pc_a)]:
        # algorithm_rgb 必須跟 palette_json 同步（pixel-replacement 用這個 key 查 mapping）
        alg_rgb = next(e for e in _PALETTE_FOR_FINALIZE if e["template_id"] == tid)["rgb"]
        db.add(PaletteColorMapping(
            production_job_id=job.id,
            template_id=tid,
            algorithm_rgb=alg_rgb,
            physical_color_id=color.id,
            mapped_by=MappedByEnum.system,
        ))
    await db.commit()

    # 構造 mock snapped PNG：6 pixel，3 種 algorithm RGB
    # row 0: [247,167,132] [100,50,200] [50,200,100]   (tid 1, 2, 3)
    # row 1: 同上
    snapped_data = np.array([
        [[247, 167, 132], [100, 50, 200], [50, 200, 100]],
        [[247, 167, 132], [100, 50, 200], [50, 200, 100]],
    ], dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(snapped_data).save(buf, format="PNG")
    snapped_png_bytes = buf.getvalue()

    captured: dict[str, bytes] = {}
    def make_blob(path: str):
        b = MagicMock(name=f"blob:{path}")
        if "snapped_rgb" in path:
            b.download_as_bytes = MagicMock(return_value=snapped_png_bytes)
        else:
            b.download_as_bytes = MagicMock(return_value=_SVG_TEMPLATE)
        def _upload(data, content_type=None):  # noqa: ARG001
            captured[path] = data if isinstance(data, bytes) else data.encode("utf-8")
        b.upload_from_string = MagicMock(side_effect=_upload)
        return b

    bucket = MagicMock()
    bucket.name = "test-bucket"
    bucket.blob = MagicMock(side_effect=make_blob)

    with patch("core.firebase.get_bucket", return_value=bucket):
        await finalize_template(db, job.id)

    # 1. filled_template_final.png 應被上傳
    filled_path = f"production_jobs/{job.id}/filled_template_final.png"
    assert filled_path in captured, f"expected {filled_path} in {list(captured.keys())}"

    # 2. job.filled_template_final_url 應該被寫入
    await db.refresh(job)
    assert job.filled_template_final_url is not None
    assert job.filled_template_final_url.endswith("/filled_template_final.png")

    # 3. PNG 內容：每個 pixel 都替換為對應物理色 RGB
    out_img = np.array(Image.open(io.BytesIO(captured[filled_path])).convert("RGB"))
    assert out_img.shape == (2, 3, 3)
    # column 0: algorithm [247,167,132] → tid 1 → physical [10,20,30]
    assert tuple(out_img[0, 0]) == (10, 20, 30)
    assert tuple(out_img[1, 0]) == (10, 20, 30)
    # column 1: algorithm [100,50,200] → tid 2 → physical [40,50,60]
    assert tuple(out_img[0, 1]) == (40, 50, 60)
    assert tuple(out_img[1, 1]) == (40, 50, 60)
    # column 2: algorithm [50,200,100] → tid 3 → physical [10,20,30]（同 tid 1）
    assert tuple(out_img[0, 2]) == (10, 20, 30)
    assert tuple(out_img[1, 2]) == (10, 20, 30)


@pytest.mark.asyncio
async def test_finalize_skips_filled_final_when_no_snapped_url(db):
    """job.snapped_rgb_url=None → 不產 filled_template_final.png（best-effort skip）。
    其他 finalize 產物（template_final.svg、palette_final.json）正常產生。"""
    from unittest.mock import patch
    from palette.service import finalize_template
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = await _setup_job_for_finalize(db, [(1, "PAL-001"), (2, "PAL-002"), (3, "PAL-001")])
    # _setup_job_for_finalize 沒設 snapped_rgb_url

    bucket, captured = _mock_bucket_for_finalize()
    with patch("core.firebase.get_bucket", return_value=bucket):
        await finalize_template(db, job.id)

    # filled_template_final.png 不應該被上傳
    filled_path = f"production_jobs/{job.id}/filled_template_final.png"
    assert filled_path not in captured

    # 但其他 final 產物正常
    assert f"production_jobs/{job.id}/template_final.svg" in captured
    assert f"production_jobs/{job.id}/palette_final.json" in captured

    await db.refresh(job)
    assert job.filled_template_final_url is None
    assert job.template_final_url is not None


@pytest.mark.asyncio
async def test_finalize_no_svg_url_raises(db):
    """job.svg_url=None → BadRequestError（呼叫端 complete_mappings 會吞掉）。"""
    from palette.service import finalize_template
    from core.exceptions import BadRequestError
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        status=JobStatusEnum.completed,
        palette_json=_PALETTE_FOR_FINALIZE,
        svg_url=None,
    )
    db.add(job)
    await db.commit()
    with pytest.raises(BadRequestError, match="template.svg"):
        await finalize_template(db, job.id)


@pytest.mark.asyncio
async def test_complete_mappings_finalize_failure_does_not_break(db, client: AsyncClient):
    """既有 complete_mappings 測試已涵蓋的場景：svg_url=None / Firebase fail
    都應被 best-effort 吞掉，complete API 仍回 200。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    await _create_color(db, COLOR_A)
    await _create_color(db, COLOR_B)
    await _seed_settings(db)
    # job 沒 svg_url → finalize 必失敗，但 complete 仍應 200
    job = await _create_job_with_palette(db)
    assert job.svg_url is None

    await client.get(_palette_url(job.id))   # 自動 mapping
    res = await client.post(f"{_palette_url(job.id)}/complete")
    assert res.status_code == 200
