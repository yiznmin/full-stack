import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
UPLOAD_URL = "/api/v1/upload/production-image"
IMAGES_URL = "/api/v1/admin/images"
JOBS_URL = "/api/v1/admin/production/jobs"

ADMIN_USER = {"name": "製作管理員", "email": "prod_admin@example.com", "password": "adminpass123"}
CUSTOMER_USER = {
    "name": "一般用戶", "email": "prod_customer@example.com", "password": "custpass123"
}

VALID_IMAGE = {
    "original_url": "https://storage.googleapis.com/bucket/test.jpg",
    "filename": "test.jpg",
    "width": 1920,
    "height": 1080,
}

STANDARD_JOB = {
    "detail": "standard",
    "difficulty": "beginner",
    "mode": "standard",
    "canvas_w_cm": 30,
    "canvas_h_cm": 40,
}

SAM_REFINE_JOB = {
    "detail": "detailed",
    "difficulty": "intermediate",
    "mode": "sam_refine",
    "canvas_w_cm": 30,
    "canvas_h_cm": 40,
    "extra_colors": 8,
}

SAM_WEIGHTED_JOB = {
    "detail": "standard",
    "difficulty": "beginner",
    "mode": "sam_weighted",
    "canvas_w_cm": 30,
    "canvas_h_cm": 40,
    "weight_ratio": 0.65,
}


async def _make_admin(client, db):
    await client.post(REGISTER_URL, json=ADMIN_USER)
    result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    user.role = "admin"
    await db.commit()
    await db.refresh(user)
    return user


async def _make_customer(client, db):
    await client.post(REGISTER_URL, json=CUSTOMER_USER)
    result = await db.execute(select(User).where(User.email == CUSTOMER_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client, email, password):
    res = await client.post(LOGIN_URL, json={"email": email, "password": password})
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


async def _create_image(client, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(IMAGES_URL, json=VALID_IMAGE)
    return res.json()


# ── POST /upload/production-image ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_signed_url_admin(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed.url/upload"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.name = "test-bucket"

    with patch("production.service.get_bucket", return_value=mock_bucket):
        res = await client.post(
            UPLOAD_URL,
            json={"filename": "photo.jpg", "content_type": "image/jpeg", "size": 1048576},
        )

    assert res.status_code == 200
    data = res.json()
    assert "upload_url" in data
    assert "public_url" in data
    assert "expires_at" in data


@pytest.mark.asyncio
async def test_upload_signed_url_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])

    res = await client.post(
        UPLOAD_URL, json={"filename": "photo.jpg", "content_type": "image/jpeg", "size": 1048576}
    )
    assert res.status_code == 403


# ── POST /admin/images ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_image_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(IMAGES_URL, json=VALID_IMAGE)
    assert res.status_code == 201
    data = res.json()
    assert data["filename"] == "test.jpg"
    assert data["width"] == 1920


@pytest.mark.asyncio
async def test_create_image_invalid_width(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(IMAGES_URL, json={**VALID_IMAGE, "width": 0})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_image_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])

    res = await client.post(IMAGES_URL, json=VALID_IMAGE)
    assert res.status_code == 403


# ── GET /admin/images ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_images_ok(client: AsyncClient, db):
    image = await _create_image(client, db)
    res = await client.get(IMAGES_URL)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == image["id"]


@pytest.mark.asyncio
async def test_list_images_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get(IMAGES_URL)
    assert res.status_code == 403


# ── POST /admin/production/jobs ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_single_job_ok(client: AsyncClient, db):
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        res = await client.post(JOBS_URL, json={
            "image_id": image["id"],
            "jobs": [STANDARD_JOB],
        })

    assert res.status_code == 201
    data = res.json()
    assert data["batch_id"] is None
    assert len(data["job_ids"]) == 1


@pytest.mark.asyncio
async def test_create_batch_jobs_ok(client: AsyncClient, db):
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        res = await client.post(JOBS_URL, json={
            "image_id": image["id"],
            "jobs": [STANDARD_JOB, SAM_REFINE_JOB],
        })

    assert res.status_code == 201
    data = res.json()
    assert data["batch_id"] is not None
    assert len(data["job_ids"]) == 2


@pytest.mark.asyncio
async def test_create_job_no_source(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(JOBS_URL, json={"jobs": [STANDARD_JOB]})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_job_image_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(JOBS_URL, json={
        "image_id": str(uuid.uuid4()),
        "jobs": [STANDARD_JOB],
    })
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_create_job_sam_refine_missing_extra_colors(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    invalid_job = {**SAM_REFINE_JOB, "extra_colors": None}
    res = await client.post(JOBS_URL, json={
        "image_id": str(uuid.uuid4()),
        "jobs": [invalid_job],
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_job_sam_weighted_invalid_ratio(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    invalid_job = {**SAM_WEIGHTED_JOB, "weight_ratio": 0.9}
    res = await client.post(JOBS_URL, json={
        "image_id": str(uuid.uuid4()),
        "jobs": [invalid_job],
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_job_both_sources_provided(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])

    res = await client.post(JOBS_URL, json={
        "image_id": str(uuid.uuid4()),
        "custom_request_id": str(uuid.uuid4()),
        "jobs": [STANDARD_JOB],
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_job_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])

    res = await client.post(JOBS_URL, json={
        "image_id": str(uuid.uuid4()),
        "jobs": [STANDARD_JOB],
    })
    assert res.status_code == 403


# ── GET /admin/production/jobs ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_jobs_no_filter(client: AsyncClient, db):
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        await client.post(JOBS_URL, json={"image_id": image["id"], "jobs": [STANDARD_JOB]})

    res = await client.get(JOBS_URL)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_jobs_status_filter(client: AsyncClient, db):
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        await client.post(JOBS_URL, json={"image_id": image["id"], "jobs": [STANDARD_JOB]})

    res = await client.get(JOBS_URL, params={"status": "pending"})
    assert res.status_code == 200
    assert res.json()["total"] == 1

    res = await client.get(JOBS_URL, params={"status": "completed"})
    assert res.status_code == 200
    assert res.json()["total"] == 0


@pytest.mark.asyncio
async def test_list_jobs_batch_filter(client: AsyncClient, db):
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        res = await client.post(JOBS_URL, json={
            "image_id": image["id"],
            "jobs": [STANDARD_JOB, SAM_REFINE_JOB],
        })
    batch_id = res.json()["batch_id"]

    result = await client.get(JOBS_URL, params={"batch_id": batch_id})
    assert result.status_code == 200
    assert result.json()["total"] == 2


@pytest.mark.asyncio
async def test_list_jobs_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get(JOBS_URL)
    assert res.status_code == 403


# ── GET /admin/production/jobs/{id} ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_ok(client: AsyncClient, db):
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        res = await client.post(JOBS_URL, json={"image_id": image["id"], "jobs": [STANDARD_JOB]})
    job_id = res.json()["job_ids"][0]

    res = await client.get(f"{JOBS_URL}/{job_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == job_id
    assert data["status"] == "pending"
    assert data["detail"] == "standard"


@pytest.mark.asyncio
async def test_get_job_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_job_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}")
    assert res.status_code == 403


# ── 401 Unauthenticated ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        UPLOAD_URL,
        json={"filename": "x.jpg", "content_type": "image/jpeg", "size": 1024},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_image_unauthenticated(client: AsyncClient, db):
    res = await client.post(IMAGES_URL, json=VALID_IMAGE)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_images_unauthenticated(client: AsyncClient, db):
    res = await client.get(IMAGES_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_job_unauthenticated(client: AsyncClient, db):
    res = await client.post(JOBS_URL, json={"image_id": str(uuid.uuid4()), "jobs": [STANDARD_JOB]})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_list_jobs_unauthenticated(client: AsyncClient, db):
    res = await client.get(JOBS_URL)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_job_unauthenticated(client: AsyncClient, db):
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}")
    assert res.status_code == 401


# ── Batch error-callback dispatch ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_dispatch_attaches_error_callback(client: AsyncClient, db):
    """純 standard 多筆批次：error callback 仍 attach（Phase A：sam_* 不在建立時 dispatch，
    改用兩筆 standard 驗證 chain + cancel_batch_remaining 機制）。"""
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_run, \
         patch("production.service.cancel_batch_remaining") as mock_cancel:
        mock_run.si.return_value = MagicMock()
        mock_cancel.si.return_value = MagicMock()

        res = await client.post(JOBS_URL, json={
            "image_id": image["id"],
            "jobs": [STANDARD_JOB, STANDARD_JOB],
        })

    assert res.status_code == 201
    batch_id = res.json()["batch_id"]
    assert batch_id is not None
    mock_cancel.si.assert_called_once_with(batch_id)


# ── Helpers for Phase 2 ───────────────────────────────────────────────────────

SIGNED_URL_SUFFIX = "/signed-url"
APPROVE_SUFFIX = "/approve"
UNAPPROVE_SUFFIX = "/unapprove"


async def _create_pending_job(client, db) -> str:
    """Creates a job in pending status (Celery task is mocked, not actually run)."""
    image = await _create_image(client, db)
    with patch("production.service.run_production_job") as mock_task:
        mock_task.si.return_value = MagicMock()
        res = await client.post(JOBS_URL, json={"image_id": image["id"], "jobs": [STANDARD_JOB]})
    return res.json()["job_ids"][0]


async def _force_complete(db, job_id: str):
    from sqlalchemy import update

    from production.models import JobStatusEnum, ProductionJob
    await db.execute(
        update(ProductionJob)
        .where(ProductionJob.id == job_id)
        .values(status=JobStatusEnum.completed)
    )
    await db.commit()


# ── GET /admin/production/jobs/{id}/signed-url ────────────────────────────────

@pytest.mark.asyncio
async def test_signed_url_with_svg(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)

    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed.url/svg"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.name = "test-bucket"

    from sqlalchemy import update

    from production.models import ProductionJob
    await db.execute(
        update(ProductionJob)
        .where(ProductionJob.id == job_id)
        .values(svg_url="https://storage.googleapis.com/test-bucket/jobs/file.svg")
    )
    await db.commit()

    with patch("production.service.get_bucket", return_value=mock_bucket):
        res = await client.get(f"{JOBS_URL}/{job_id}{SIGNED_URL_SUFFIX}?file=svg")

    assert res.status_code == 200
    assert res.json()["url"] == "https://signed.url/svg"


@pytest.mark.asyncio
async def test_signed_url_null_when_no_file(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    res = await client.get(f"{JOBS_URL}/{job_id}{SIGNED_URL_SUFFIX}?file=svg")
    assert res.status_code == 200
    assert res.json()["url"] is None


@pytest.mark.asyncio
async def test_signed_url_invalid_field(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    res = await client.get(f"{JOBS_URL}/{job_id}{SIGNED_URL_SUFFIX}?file=filled_template")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_signed_url_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}{SIGNED_URL_SUFFIX}?file=svg")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_signed_url_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}{SIGNED_URL_SUFFIX}?file=svg")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_signed_url_unauthenticated(client: AsyncClient, db):
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}{SIGNED_URL_SUFFIX}?file=svg")
    assert res.status_code == 401


# ── POST /admin/production/jobs/{id}/approve ──────────────────────────────────

@pytest.mark.asyncio
async def test_approve_completed_job(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    res = await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={"notes": "looks good"})
    assert res.status_code == 200
    data = res.json()
    assert data["approved"] is True
    assert data["approved_at"] is not None
    assert data["notes"] == "looks good"


@pytest.mark.asyncio
async def test_approve_without_notes(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    res = await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={})
    assert res.status_code == 200
    assert res.json()["approved"] is True


@pytest.mark.asyncio
async def test_approve_idempotent(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={})
    res = await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={})
    assert res.status_code == 200
    assert res.json()["approved"] is True


@pytest.mark.asyncio
async def test_approve_idempotent_updates_notes(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={"notes": "first"})
    res = await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={"notes": "updated"})
    assert res.status_code == 200
    assert res.json()["notes"] == "updated"


@pytest.mark.asyncio
async def test_approve_pending_job(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    res = await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_approve_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(f"{JOBS_URL}/{uuid.uuid4()}{APPROVE_SUFFIX}", json={})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_approve_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(f"{JOBS_URL}/{uuid.uuid4()}{APPROVE_SUFFIX}", json={})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_approve_unauthenticated(client: AsyncClient, db):
    res = await client.post(f"{JOBS_URL}/{uuid.uuid4()}{APPROVE_SUFFIX}", json={})
    assert res.status_code == 401


# ── DELETE /admin/production/jobs/{id} ────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_pending_job_ok(client: AsyncClient, db):
    """pending 任務可刪 + palette_color_mappings 連帶刪 + 回 204。"""
    from color.models import PhysicalColor
    from palette.models import MappedByEnum, PaletteColorMapping
    from sqlalchemy import select

    job_id = await _create_pending_job(client, db)
    # 加一筆 PhysicalColor 給 mapping 用（physical_color_id NOT NULL）
    color = PhysicalColor(code="C001", name="test", rgb=[10, 20, 30], stock_ml=100, is_active=True)
    db.add(color)
    await db.flush()
    db.add(PaletteColorMapping(
        production_job_id=job_id,
        template_id=1,
        algorithm_rgb=[10, 20, 30],
        physical_color_id=color.id,
        mapped_by=MappedByEnum.system,
    ))
    await db.commit()

    with patch("production.service.get_bucket"):
        res = await client.delete(f"{JOBS_URL}/{job_id}")
    assert res.status_code == 204
    # 連帶子資料也應沒了
    cnt = (await db.execute(
        select(PaletteColorMapping).where(PaletteColorMapping.production_job_id == job_id)
    )).scalars().all()
    assert len(cnt) == 0


@pytest.mark.asyncio
async def test_delete_completed_job_cleans_firebase(client: AsyncClient, db):
    """completed 任務可刪 + 掃 production_jobs/{id}/ prefix 把所有 blob 刪光。"""
    from sqlalchemy import update
    from production.models import ProductionJob

    job_id = await _create_pending_job(client, db)
    await db.execute(
        update(ProductionJob).where(ProductionJob.id == job_id).values(
            status="completed",
            svg_url=f"gs://b/production_jobs/{job_id}/svg.svg",
            filled_template_url=f"gs://b/production_jobs/{job_id}/filled.png",
            snapped_rgb_url=f"gs://b/production_jobs/{job_id}/snapped.png",
            mask_url=f"gs://b/production_jobs/{job_id}/mask.png",
        )
    )
    await db.commit()

    # 模擬 prefix 下有 5 個 blob（含一個 worker 寫的中間檔）
    mock_blobs = [MagicMock(name=f"blob{i}") for i in range(5)]
    for b, name in zip(mock_blobs, [
        f"production_jobs/{job_id}/svg.svg",
        f"production_jobs/{job_id}/filled.png",
        f"production_jobs/{job_id}/snapped.png",
        f"production_jobs/{job_id}/mask.png",
        f"production_jobs/{job_id}/intermediate_v1.png",  # 中間檔
    ]):
        b.name = name

    mock_bucket = MagicMock()
    mock_bucket.name = "b"
    mock_bucket.list_blobs = MagicMock(return_value=mock_blobs)

    with patch("production.service.get_bucket", return_value=mock_bucket):
        res = await client.delete(f"{JOBS_URL}/{job_id}")
    assert res.status_code == 204
    # list_blobs 被呼叫一次以正確 prefix
    mock_bucket.list_blobs.assert_called_once()
    assert mock_bucket.list_blobs.call_args.kwargs.get("prefix") == f"production_jobs/{job_id}/"
    # 每個 blob 都被刪（含中間檔）
    for b in mock_blobs:
        b.delete.assert_called_once()


@pytest.mark.asyncio
async def test_delete_processing_job_rejected(client: AsyncClient, db):
    """processing 任務不可刪（worker 在跑）→ 400。"""
    from sqlalchemy import update
    from production.models import ProductionJob

    job_id = await _create_pending_job(client, db)
    await db.execute(
        update(ProductionJob).where(ProductionJob.id == job_id).values(status="processing")
    )
    await db.commit()

    res = await client.delete(f"{JOBS_URL}/{job_id}")
    assert res.status_code == 400
    assert "處理中" in res.json()["detail"]


@pytest.mark.asyncio
async def test_delete_processing_job_with_force_ok(client: AsyncClient, db):
    """processing 任務 + ?force=true → 允許強制刪除（worker 卡死的 zombie task）+ 排程 90s
    後再清一次 Firebase（防 worker race window 寫新檔）。"""
    from sqlalchemy import select, update
    from production.models import ProductionJob

    job_id = await _create_pending_job(client, db)
    await db.execute(
        update(ProductionJob).where(ProductionJob.id == job_id).values(status="processing")
    )
    await db.commit()

    mock_bucket = MagicMock()
    mock_bucket.name = "b"
    mock_bucket.list_blobs = MagicMock(return_value=[])

    with patch("production.service.get_bucket", return_value=mock_bucket), \
         patch("production.tasks.cleanup_job_firebase") as mock_cleanup:
        res = await client.delete(f"{JOBS_URL}/{job_id}?force=true")
    assert res.status_code == 204

    # row 應已刪
    found = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job_id)
    )).scalar_one_or_none()
    assert found is None

    # 應排程 90 秒後再清一次（force=true 才有）
    mock_cleanup.apply_async.assert_called_once()
    kwargs = mock_cleanup.apply_async.call_args.kwargs
    assert kwargs["countdown"] == 90
    assert kwargs["args"] == [str(job_id)]


@pytest.mark.asyncio
async def test_delete_job_referenced_by_product_rejected(client: AsyncClient, db):
    """job 被 product_variants 引用 → 拒絕 400 + 提示具體引用。"""
    from sqlalchemy import update
    from product.models import Product, ProductVariant
    from production.models import ProductionJob

    job_id = await _create_pending_job(client, db)
    await db.execute(
        update(ProductionJob).where(ProductionJob.id == job_id).values(status="completed")
    )
    # 建一個 product + variant 引用該 job
    prod = Product(title="T", cover_image_url="gs://b/cover.png")
    db.add(prod)
    await db.flush()
    db.add(ProductVariant(
        product_id=prod.id,
        production_job_id=job_id,
        price=100,
        price_formula_base=80,
    ))
    await db.commit()

    res = await client.delete(f"{JOBS_URL}/{job_id}")
    assert res.status_code == 400
    assert "商品 variant" in res.json()["detail"]


@pytest.mark.asyncio
async def test_delete_job_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.delete(f"{JOBS_URL}/{uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_job_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.delete(f"{JOBS_URL}/{uuid.uuid4()}")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_delete_job_unauthenticated(client: AsyncClient, db):
    res = await client.delete(f"{JOBS_URL}/{uuid.uuid4()}")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_delete_job_firebase_failure_does_not_rollback_db(client: AsyncClient, db):
    """Firebase delete 失敗應只 log，不影響 DB（已 commit）→ 仍回 204。"""
    from sqlalchemy import update, select
    from production.models import ProductionJob

    job_id = await _create_pending_job(client, db)
    await db.execute(
        update(ProductionJob).where(ProductionJob.id == job_id).values(
            status="failed",
            svg_url="gs://b/jobs/x.svg",
        )
    )
    await db.commit()

    mock_bucket = MagicMock()
    mock_bucket.name = "b"
    mock_blob = MagicMock()
    mock_blob.delete.side_effect = RuntimeError("firebase fail")
    mock_blob.name = f"production_jobs/{job_id}/x.svg"
    mock_bucket.list_blobs = MagicMock(return_value=[mock_blob])

    with patch("production.service.get_bucket", return_value=mock_bucket):
        res = await client.delete(f"{JOBS_URL}/{job_id}")
    assert res.status_code == 204
    # DB row 確實刪掉
    found = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job_id)
    )).scalar_one_or_none()
    assert found is None


# ── POST /admin/production/jobs/{id}/unapprove ────────────────────────────────

@pytest.mark.asyncio
async def test_unapprove_approved_job(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)
    await client.post(f"{JOBS_URL}/{job_id}{APPROVE_SUFFIX}", json={})

    res = await client.post(f"{JOBS_URL}/{job_id}{UNAPPROVE_SUFFIX}")
    assert res.status_code == 200
    data = res.json()
    assert data["approved"] is False
    assert data["approved_at"] is None


@pytest.mark.asyncio
async def test_unapprove_idempotent(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    res = await client.post(f"{JOBS_URL}/{job_id}{UNAPPROVE_SUFFIX}")
    assert res.status_code == 200
    assert res.json()["approved"] is False


@pytest.mark.asyncio
async def test_unapprove_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(f"{JOBS_URL}/{uuid.uuid4()}{UNAPPROVE_SUFFIX}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_unapprove_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(f"{JOBS_URL}/{uuid.uuid4()}{UNAPPROVE_SUFFIX}")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_unapprove_unauthenticated(client: AsyncClient, db):
    res = await client.post(f"{JOBS_URL}/{uuid.uuid4()}{UNAPPROVE_SUFFIX}")
    assert res.status_code == 401


# ── POST /admin/production/jobs/{id}/post-process/* ───────────────────────────

MERGE_COLOR_URL_SUFFIX = "/post-process/merge-color"
ELIM_BORDER_URL_SUFFIX = "/post-process/eliminate-border"
MERGE_COLOR_BODY = {"polygon_id": "r5", "target_template_id": 1}
ELIM_BORDER_BODY = {"absorbed_polygon_id": "r5", "surviving_polygon_id": "r2"}


@pytest.mark.asyncio
async def test_merge_color_ok(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    with patch("production.service.run_post_process_job") as mock_task:
        mock_task.delay.return_value = None
        res = await client.post(
            f"{JOBS_URL}/{job_id}{MERGE_COLOR_URL_SUFFIX}", json=MERGE_COLOR_BODY
        )

    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "processing"
    assert data["approved"] is False
    mock_task.delay.assert_called_once_with(job_id, MERGE_COLOR_BODY)


@pytest.mark.asyncio
async def test_merge_color_missing_fields(client: AsyncClient, db):
    """新區域層級 schema：polygon_id 與 target_template_id 都是必填。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{MERGE_COLOR_URL_SUFFIX}",
        json={"polygon_id": "r5"},  # 缺 target_template_id
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_merge_color_pending_job(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    res = await client.post(
        f"{JOBS_URL}/{job_id}{MERGE_COLOR_URL_SUFFIX}", json=MERGE_COLOR_BODY
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_merge_color_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{MERGE_COLOR_URL_SUFFIX}", json=MERGE_COLOR_BODY
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_merge_color_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{MERGE_COLOR_URL_SUFFIX}", json=MERGE_COLOR_BODY
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_merge_color_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{MERGE_COLOR_URL_SUFFIX}", json=MERGE_COLOR_BODY
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_eliminate_border_ok(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    with patch("production.service.run_post_process_job") as mock_task:
        mock_task.delay.return_value = None
        res = await client.post(
            f"{JOBS_URL}/{job_id}{ELIM_BORDER_URL_SUFFIX}", json=ELIM_BORDER_BODY
        )

    assert res.status_code == 202
    assert res.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_eliminate_border_same_ids(client: AsyncClient, db):
    """absorbed 與 surviving 不可相同（區域層級用 polygon_id）。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{ELIM_BORDER_URL_SUFFIX}",
        json={"absorbed_polygon_id": "r3", "surviving_polygon_id": "r3"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_eliminate_border_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{ELIM_BORDER_URL_SUFFIX}", json=ELIM_BORDER_BODY
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_eliminate_border_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{ELIM_BORDER_URL_SUFFIX}", json=ELIM_BORDER_BODY
    )
    assert res.status_code == 401


# ── POST /admin/production/jobs/{id}/post-process/batch ───────────────────────

BATCH_URL_SUFFIX = "/post-process/batch"
BATCH_BODY = {
    "operations": [
        {"op": "merge_color", "polygon_id": "r5", "target_template_id": 1},
        {
            "op": "eliminate_border",
            "absorbed_polygon_id": "r3",
            "surviving_polygon_id": "r2",
        },
    ],
}


@pytest.mark.asyncio
async def test_batch_post_process_ok(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    with patch("production.service.run_post_process_job") as mock_task:
        mock_task.delay.return_value = None
        res = await client.post(
            f"{JOBS_URL}/{job_id}{BATCH_URL_SUFFIX}", json=BATCH_BODY
        )

    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "processing"
    assert data["approved"] is False
    # Celery 收到的 params 應為 {operations: [...]} 結構
    args = mock_task.delay.call_args
    assert args.args[0] == job_id
    assert "operations" in args.args[1]
    assert len(args.args[1]["operations"]) == 2


@pytest.mark.asyncio
async def test_batch_post_process_empty_operations(client: AsyncClient, db):
    """operations=[] → 422。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{BATCH_URL_SUFFIX}",
        json={"operations": []},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_batch_post_process_pending_job(client: AsyncClient, db):
    """status=pending → 400。"""
    job_id = await _create_pending_job(client, db)
    res = await client.post(
        f"{JOBS_URL}/{job_id}{BATCH_URL_SUFFIX}", json=BATCH_BODY
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_batch_post_process_duplicate_polygon_id(client: AsyncClient, db):
    """同一 polygon_id 在「被改色」位置重複（silent overwrite trap）→ 422。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{BATCH_URL_SUFFIX}",
        json={
            "operations": [
                {"op": "merge_color", "polygon_id": "r5", "target_template_id": 1},
                {"op": "merge_color", "polygon_id": "r5", "target_template_id": 2},
            ],
        },
    )
    assert res.status_code == 422
    body = res.json()
    assert "polygon_id=r5" in str(body) or "silent overwrite" in str(body)


@pytest.mark.asyncio
async def test_batch_post_process_duplicate_across_op_types(client: AsyncClient, db):
    """同 polygon_id 既當 merge target 又當 eliminate 的 absorbed → 仍 422。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{BATCH_URL_SUFFIX}",
        json={
            "operations": [
                {"op": "merge_color", "polygon_id": "r5", "target_template_id": 1},
                {
                    "op": "eliminate_border",
                    "absorbed_polygon_id": "r5",
                    "surviving_polygon_id": "r3",
                },
            ],
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_batch_post_process_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{BATCH_URL_SUFFIX}", json=BATCH_BODY
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_batch_post_process_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{BATCH_URL_SUFFIX}", json=BATCH_BODY
    )
    assert res.status_code == 401


# ── GET /admin/production/jobs/{id}/export-pdf ────────────────────────────────

EXPORT_PDF_URL_SUFFIX = "/export-pdf"


async def _create_completed_job(client, db, *, with_svg=True) -> dict:
    """Helper：建立 image → 直接在 DB 把 production_job seed 成 completed + svg_url。"""
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="completed",
        approved=True,
        detail="standard",
        difficulty="beginner",
        mode="standard",
        canvas_w_cm=30,
        canvas_h_cm=40,
        min_brush_diam_cm=1.0,
        svg_url=(
            "https://storage.googleapis.com/test-bucket/"
            "production_jobs/test_job/template.svg"
        ) if with_svg else None,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return {"id": str(job.id)}


def _read_pdf_mediabox(pdf_bytes: bytes) -> tuple[float, float]:
    """Decode the MediaBox of page 1 from raw PDF bytes via pypdf."""
    import io as _io

    from pypdf import PdfReader
    reader = PdfReader(_io.BytesIO(pdf_bytes))
    box = reader.pages[0].mediabox
    # mediabox 單位 = pt
    return float(box.width), float(box.height)


@pytest.mark.asyncio
async def test_export_pdf_ok_svglib_path(client: AsyncClient, db):
    """svglib 路徑：頁面尺寸 = (canvas + 2*5cm)；Drawing.scale() 必須被呼叫並真的套用 transform。"""
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.units import cm

    job = await _create_completed_job(client, db)
    # Drawing 預設 viewBox 為 100×100 user units —
    # 若 service 沒呼叫 drawing.scale，transform matrix 會維持 identity，
    # PDF 內向量尺寸只會是 100pt（≈ 3.5cm）而不是 30cm
    fake_drawing = Drawing(100, 100)

    # ReportLab 的 attrmap 不允許直接賦值 fake_drawing.scale = spy
    # 改用 patch.object 在 Drawing class 層級監控（仍保留 wraps 真實執行）
    with patch(
        "print_batch.service._render_svg_with_fallbacks",
        return_value=(fake_drawing, None),
    ), patch.object(
        Drawing, "scale", autospec=True, side_effect=Drawing.scale,
    ) as spy_scale:
        res = await client.get(f"{JOBS_URL}/{job['id']}{EXPORT_PDF_URL_SUFFIX}")

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "filename=" in res.headers.get("content-disposition", "")
    assert res.content[:4] == b"%PDF"

    # 頁面尺寸 = (30 + 10)cm × (40 + 10)cm
    w_pt, h_pt = _read_pdf_mediabox(res.content)
    assert abs(w_pt - 40 * cm) < 0.5, f"page width {w_pt}pt ≠ 40cm"
    assert abs(h_pt - 50 * cm) < 0.5, f"page height {h_pt}pt ≠ 50cm"

    # *核心 regression*：drawing.scale() 必須被呼叫，否則 PDF 內向量尺寸不對
    assert spy_scale.called, "drawing.scale 未被呼叫 — PDF 內向量尺寸會異常"
    # autospec 的 call_args.args 第 0 位是 self（Drawing 實例），1, 2 是 sx, sy
    call_args = spy_scale.call_args.args
    assert len(call_args) == 3, f"drawing.scale 預期 (self, sx, sy)，得到 {call_args}"
    _self, sx, sy = call_args
    assert abs(sx - (30 * cm / 100)) < 0.01, f"sx={sx} 與預期 {30 * cm / 100} 不符"
    assert abs(sy - (40 * cm / 100)) < 0.01, f"sy={sy} 與預期 {40 * cm / 100} 不符"

    # transform matrix 應已被套用（非 identity）
    # ReportLab Drawing.transform 是 6-tuple (a, b, c, d, e, f)；scale 後 a, d 不為 1
    assert fake_drawing.transform[0] != 1.0 or fake_drawing.transform[3] != 1.0, \
        "transform matrix 仍是 identity，scale 沒實際套用"


@pytest.mark.asyncio
async def test_export_pdf_ok_cairosvg_fallback(client: AsyncClient, db):
    """cairosvg 路徑：頁面尺寸與 svglib 路徑一致（兩個 fallback 結果不能不一樣）。"""
    import io as _io

    from PIL import Image
    from reportlab.lib.units import cm

    job = await _create_completed_job(client, db)
    # 用 Pillow 產出有效的 8×8 灰階 PNG bytes
    png_buf = _io.BytesIO()
    Image.new("RGB", (8, 8), color=(128, 128, 128)).save(png_buf, format="PNG")
    png_bytes = png_buf.getvalue()

    with patch(
        "print_batch.service._render_svg_with_fallbacks",
        return_value=(None, png_bytes),
    ):
        res = await client.get(f"{JOBS_URL}/{job['id']}{EXPORT_PDF_URL_SUFFIX}")

    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"
    w_pt, h_pt = _read_pdf_mediabox(res.content)
    assert abs(w_pt - 40 * cm) < 0.5
    assert abs(h_pt - 50 * cm) < 0.5


@pytest.mark.asyncio
async def test_export_pdf_status_not_completed(client: AsyncClient, db):
    """status != completed 回 400."""
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="pending",
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40, min_brush_diam_cm=1.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    res = await client.get(f"{JOBS_URL}/{job.id}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_pdf_no_svg(client: AsyncClient, db):
    """status=completed 但 svg_url 為 None 回 400."""
    job = await _create_completed_job(client, db, with_svg=False)
    res = await client.get(f"{JOBS_URL}/{job['id']}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_pdf_render_failure(client: AsyncClient, db):
    """svglib 與 cairosvg 都失敗 → 400."""
    job = await _create_completed_job(client, db)
    with patch(
        "print_batch.service._render_svg_with_fallbacks",
        return_value=(None, None),
    ):
        res = await client.get(f"{JOBS_URL}/{job['id']}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_pdf_zero_dim_drawing(client: AsyncClient, db):
    """Drawing 維度為 0（svglib 解析異常）→ 400，避免靜默產出未縮放的爛 PDF."""
    from reportlab.graphics.shapes import Drawing

    job = await _create_completed_job(client, db)
    bad_drawing = Drawing(0, 0)

    with patch(
        "print_batch.service._render_svg_with_fallbacks",
        return_value=(bad_drawing, None),
    ):
        res = await client.get(f"{JOBS_URL}/{job['id']}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_export_pdf_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_export_pdf_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_export_pdf_unauthenticated(client: AsyncClient, db):
    res = await client.get(f"{JOBS_URL}/{uuid.uuid4()}{EXPORT_PDF_URL_SUFFIX}")
    assert res.status_code == 401


# ── POST /admin/production/canvas-sizes/recommend ─────────────────────────────

RECOMMEND_URL = "/api/v1/admin/production/canvas-sizes/recommend"


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_landscape(client: AsyncClient, db):
    """橫幅圖（4:3）→ 應推薦橫幅尺寸（如 40×30 / 60×40）。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(RECOMMEND_URL, json={"width": 1920, "height": 1080, "n": 3})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 3
    # 1920×1080 ≈ 1.78，最接近的會是 16:9 邊近的橫幅
    # 至少要有一筆寬 > 高（橫幅）
    assert any(s["w"] > s["h"] for s in items)
    # 按面積由小到大排序
    areas = [s["w"] * s["h"] for s in items]
    assert areas == sorted(areas)


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_square(client: AsyncClient, db):
    """正方圖 → 應有正方尺寸入選（如 30×30）。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(RECOMMEND_URL, json={"width": 1000, "height": 1000})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 3
    # 正方圖第一推薦應是正方尺寸（w==h）
    assert items[0]["w"] == items[0]["h"]
    # ratio_match 接近 1
    assert items[0]["ratio_match"] > 0.99


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_portrait(client: AsyncClient, db):
    """直幅圖 → 至少一筆推薦是直幅（高>寬）。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(RECOMMEND_URL, json={"width": 720, "height": 1280})
    assert res.status_code == 200
    items = res.json()["items"]
    assert any(s["h"] > s["w"] for s in items)


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_invalid_dimensions(client: AsyncClient, db):
    """寬或高 ≤ 0 → 422。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(RECOMMEND_URL, json={"width": 0, "height": 100})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_n_param(client: AsyncClient, db):
    """指定 n=5 應回 5 組。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(RECOMMEND_URL, json={"width": 1000, "height": 800, "n": 5})
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 5


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(RECOMMEND_URL, json={"width": 100, "height": 100})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_recommend_canvas_sizes_unauthenticated(client: AsyncClient, db):
    res = await client.post(RECOMMEND_URL, json={"width": 100, "height": 100})
    assert res.status_code == 401


# ── POST /admin/production/jobs/{id}/sam-mask ────────────────────────────────

SAM_MASK_URL_SUFFIX = "/sam-mask"


async def _create_sam_pending_job(client, db) -> dict:
    """Helper：建 image + 直接在 DB seed 一筆 pending production_job（mode=sam_refine）。

    與 _create_pending_job（在第 450 行）不同 — 那個回傳 string job_id，
    這裡為了 SAM 測試需要 image dimensions，回傳 {id, image_id} 字典。
    """
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="pending",
        approved=False,
        detail="standard",
        difficulty="beginner",
        mode="sam_refine",
        canvas_w_cm=30,
        canvas_h_cm=40,
        min_brush_diam_cm=1.0,
        extra_colors=5,  # sam_refine 需要 extra_colors > 0（呼應 JobParams.validate_mode_params）
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return {"id": str(job.id), "image_id": image["id"]}


@pytest.mark.asyncio
async def test_sam_mask_with_polygons_ok(client: AsyncClient, db):
    """polygons 提供時，遮罩 PNG 即時產出（mock Firebase upload）。"""
    job = await _create_sam_pending_job(client, db)

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.name = "test-bucket"

    with patch("production.service.get_bucket", return_value=mock_bucket):
        res = await client.post(
            f"{JOBS_URL}/{job['id']}{SAM_MASK_URL_SUFFIX}",
            json={
                "polygons": [[[100, 100], [500, 100], [500, 400], [100, 400]]],
                "mode": "sam_refine",
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data["mask_url"] is not None  # 上傳成功應回 gs:// URL
    # 0~1 比例（與 api.md 範例 0.42 一致），不是 0~100 百分比
    assert 0 < data["mask_coverage"] <= 1


@pytest.mark.asyncio
async def test_sam_mask_with_only_points(client: AsyncClient, db):
    """純 sam_points 路徑（Phase B）：mock SAM runtime → 即時推論 → 寫 mask_url + coverage。"""
    import numpy as np

    job = await _create_sam_pending_job(client, db)

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.name = "test-bucket"

    # mock SAM runtime：直接回固定 mask（80x80 圖、選 40x40 區域 → coverage=0.25）
    fake_mask = np.zeros((80, 80), dtype=bool)
    fake_mask[20:60, 20:60] = True

    with patch("production.service.get_bucket", return_value=mock_bucket), \
         patch("production.service._run_sam_predict", return_value=fake_mask):
        res = await client.post(
            f"{JOBS_URL}/{job['id']}{SAM_MASK_URL_SUFFIX}",
            json={
                "sam_points": [{"x": 40, "y": 40, "label": 1}],
                "mode": "sam_refine",
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["mask_url"] is not None
    assert data["mask_url"].startswith("gs://test-bucket/")
    assert data["mask_coverage"] is not None
    assert 0 <= data["mask_coverage"] <= 1


@pytest.mark.asyncio
async def test_sam_mask_union_polygons_and_points(client: AsyncClient, db):
    """polygons + sam_points 都給 → 聯集（Phase B）。"""
    import numpy as np

    job = await _create_sam_pending_job(client, db)

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.name = "test-bucket"

    # SAM 回的 mask 跟 polygon 不重疊 → 聯集面積 > 任一單獨
    # 注意：image dimensions 1920x1080（VALID_IMAGE）；mask 必須對齊
    fake_mask = np.zeros((1080, 1920), dtype=bool)
    fake_mask[0:100, 0:100] = True  # 左上角 100x100 區塊

    captured_png_bytes: list[bytes] = []

    def _capture_upload(payload, content_type=None):
        captured_png_bytes.append(payload)

    mock_blob.upload_from_string.side_effect = _capture_upload

    with patch("production.service.get_bucket", return_value=mock_bucket), \
         patch("production.service._run_sam_predict", return_value=fake_mask):
        res = await client.post(
            f"{JOBS_URL}/{job['id']}{SAM_MASK_URL_SUFFIX}",
            json={
                "sam_points": [{"x": 50, "y": 50, "label": 1}],
                # polygon 在右下角，跟 SAM mask 不重疊
                "polygons": [[[1800, 1000], [1900, 1000], [1900, 1080], [1800, 1080]]],
                "mode": "sam_refine",
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data["mask_url"] is not None
    assert data["mask_coverage"] is not None
    # 聯集面積：SAM 100x100 + polygon ~100x80 = ~18000 pixels；total=1920*1080=2073600
    # coverage 應 > 0（有非零選取區）
    assert data["mask_coverage"] > 0
    # 確認真的有上傳一個 PNG
    assert len(captured_png_bytes) == 1
    assert captured_png_bytes[0].startswith(b"\x89PNG")  # PNG magic bytes


@pytest.mark.asyncio
async def test_sam_mask_sam_runtime_error_returns_400(client: AsyncClient, db):
    """純 sam_points 但 SAM 推論失敗（如模型路徑缺）→ 400 BadRequest（無 polygons 可 fallback）。"""
    job = await _create_sam_pending_job(client, db)

    with patch(
        "production.service._run_sam_predict",
        side_effect=ValueError("settings.sam_model_path 未設定"),
    ):
        res = await client.post(
            f"{JOBS_URL}/{job['id']}{SAM_MASK_URL_SUFFIX}",
            json={
                "sam_points": [{"x": 50, "y": 50, "label": 1}],
                "mode": "sam_refine",
            },
        )
    assert res.status_code == 400
    assert "SAM 推論失敗" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_sam_mask_sam_failure_fallback_to_polygons(client: AsyncClient, db):
    """polygons + sam_points 都有，SAM 失敗 → 退化用純 polygons mask（200，仍寫 mask_url）。

    符合規格 §1.3「兩種模式聯集」精神：一邊掛掉時不應整批拒絕，admin 至少能保留多邊形選取。
    """
    job = await _create_sam_pending_job(client, db)

    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.name = "test-bucket"

    with patch("production.service.get_bucket", return_value=mock_bucket), \
         patch(
             "production.service._run_sam_predict",
             side_effect=ValueError("SAM model not loaded"),
         ):
        res = await client.post(
            f"{JOBS_URL}/{job['id']}{SAM_MASK_URL_SUFFIX}",
            json={
                "sam_points": [{"x": 50, "y": 50, "label": 1}],
                "polygons": [[[100, 100], [200, 100], [200, 200], [100, 200]]],
                "mode": "sam_refine",
            },
        )
    assert res.status_code == 200
    data = res.json()
    # polygons 成功產生 mask（不被 SAM 失敗連帶丟棄）
    assert data["mask_url"] is not None
    assert data["mask_coverage"] is not None


@pytest.mark.asyncio
async def test_sam_mask_status_not_pending(client: AsyncClient, db):
    """status != pending → 400."""
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="processing",
        detail="standard", difficulty="beginner", mode="sam_refine",
        canvas_w_cm=30, canvas_h_cm=40, min_brush_diam_cm=1.0,
        extra_colors=5,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    res = await client.post(
        f"{JOBS_URL}/{job.id}{SAM_MASK_URL_SUFFIX}",
        json={"polygons": [[[0, 0], [10, 0], [10, 10]]], "mode": "sam_refine"},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_sam_mask_empty_payload(client: AsyncClient, db):
    """sam_points 與 polygons 都沒給 → 422."""
    job = await _create_sam_pending_job(client, db)
    res = await client.post(
        f"{JOBS_URL}/{job['id']}{SAM_MASK_URL_SUFFIX}",
        json={"mode": "sam_refine"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_sam_mask_approved_reset(client: AsyncClient, db):
    """編輯遮罩後 approved 必須退回 false."""
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="pending",
        approved=True,  # 假設已被某邊際情境設成 true
        detail="standard", difficulty="beginner", mode="sam_refine",
        canvas_w_cm=30, canvas_h_cm=40, min_brush_diam_cm=1.0,
        extra_colors=5,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = MagicMock()
    mock_bucket.name = "test-bucket"
    with patch("production.service.get_bucket", return_value=mock_bucket):
        res = await client.post(
            f"{JOBS_URL}/{job.id}{SAM_MASK_URL_SUFFIX}",
            json={"polygons": [[[0, 0], [50, 0], [50, 50]]], "mode": "sam_refine"},
        )
    assert res.status_code == 200

    # 驗證 DB 內 approved 退回 false
    from sqlalchemy import select as _sel
    refreshed = (
        await db.execute(_sel(ProductionJob).where(ProductionJob.id == job.id))
    ).scalar_one()
    assert refreshed.approved is False


@pytest.mark.asyncio
async def test_sam_mask_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SAM_MASK_URL_SUFFIX}",
        json={"polygons": [[[0, 0], [10, 0], [10, 10]]], "mode": "sam_refine"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_sam_mask_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SAM_MASK_URL_SUFFIX}",
        json={"polygons": [[[0, 0], [10, 0], [10, 10]]], "mode": "sam_refine"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_sam_mask_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SAM_MASK_URL_SUFFIX}",
        json={"polygons": [[[0, 0], [10, 0], [10, 10]]], "mode": "sam_refine"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_sam_mask_switch_to_sam_refine_without_extra_colors(
    client: AsyncClient, db
):
    """job 缺 extra_colors 時切換 mode=sam_refine → 400（避免 worker crash）。"""
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="pending",
        approved=False,
        detail="standard",
        difficulty="beginner",
        mode="sam_weighted",  # 既有狀態：sam_weighted + weight_ratio
        weight_ratio=0.6,
        canvas_w_cm=30,
        canvas_h_cm=40,
        min_brush_diam_cm=1.0,
        # 故意不給 extra_colors
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    res = await client.post(
        f"{JOBS_URL}/{job.id}{SAM_MASK_URL_SUFFIX}",
        json={
            "polygons": [[[0, 0], [10, 0], [10, 10]]],
            "mode": "sam_refine",
        },
    )
    assert res.status_code == 400
    assert "extra_colors" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_sam_mask_switch_to_sam_weighted_with_invalid_weight_ratio(
    client: AsyncClient, db
):
    """weight_ratio 超出 0.5~0.8 時切換 mode=sam_weighted → 400。"""
    from production.models import ProductionJob

    image = await _create_image(client, db)
    job = ProductionJob(
        image_id=uuid.UUID(image["id"]),
        status="pending",
        approved=False,
        detail="standard",
        difficulty="beginner",
        mode="sam_refine",
        extra_colors=5,
        weight_ratio=0.3,  # 故意超範圍
        canvas_w_cm=30,
        canvas_h_cm=40,
        min_brush_diam_cm=1.0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    res = await client.post(
        f"{JOBS_URL}/{job.id}{SAM_MASK_URL_SUFFIX}",
        json={
            "polygons": [[[0, 0], [10, 0], [10, 10]]],
            "mode": "sam_weighted",
        },
    )
    assert res.status_code == 400
    assert "weight_ratio" in res.json().get("detail", "")


# ── POST /admin/production/batches/{batch_id}/start（Phase A.4）──────────────


async def _seed_batch_jobs(db, image_id, *, modes_with_mask: list[tuple[str, bool]]):
    """建立指定 mode 與 mask_url 狀態的 job 列表（共用同一 batch_id）。"""
    from production.models import (
        DetailEnum,
        DifficultyEnum,
        JobStatusEnum,
        ModeEnum,
        ProductionJob,
    )

    batch_id = uuid.uuid4()
    jobs = []
    mode_map = {
        "standard": ModeEnum.standard,
        "sam_refine": ModeEnum.sam_refine,
        "sam_weighted": ModeEnum.sam_weighted,
    }
    for idx, (mode_str, has_mask) in enumerate(modes_with_mask):
        job = ProductionJob(
            image_id=image_id,
            batch_id=batch_id,
            status=JobStatusEnum.pending,
            approved=False,
            detail=DetailEnum.standard,
            difficulty=DifficultyEnum.beginner,
            mode=mode_map[mode_str],
            canvas_w_cm=30,
            canvas_h_cm=40,
            min_brush_diam_cm=1.0,
            mask_url=f"gs://x/mask{idx}.png" if has_mask else None,
            extra_colors=5 if mode_str == "sam_refine" else None,
            weight_ratio=0.65 if mode_str == "sam_weighted" else None,
        )
        db.add(job)
        jobs.append(job)
    await db.commit()
    for j in jobs:
        await db.refresh(j)
    return batch_id, jobs


@pytest.mark.asyncio
async def test_batch_start_all_ready(client: AsyncClient, db):
    """整批 sam_* + 都有 mask_url → 全部 enqueue。"""
    image_data = await _create_image(client, db)
    batch_id, jobs = await _seed_batch_jobs(
        db, image_data["id"],
        modes_with_mask=[("sam_refine", True), ("sam_weighted", True)],
    )

    with patch("production.service._dispatch_tasks") as mock_dispatch:
        res = await client.post(f"/api/v1/admin/production/batches/{batch_id}/start")

    assert res.status_code == 200
    body = res.json()
    assert body["enqueued"] == 2
    assert body["skipped"] == []
    assert mock_dispatch.call_count == 1
    # 兩個 job 都被傳給 _dispatch_tasks
    dispatched_jobs = mock_dispatch.call_args.args[0]
    assert len(dispatched_jobs) == 2


@pytest.mark.asyncio
async def test_batch_start_partial_missing_mask(client: AsyncClient, db):
    """部分 sam_* 缺 mask_url → 200 部分成功，缺的列在 skipped。"""
    image_data = await _create_image(client, db)
    batch_id, jobs = await _seed_batch_jobs(
        db, image_data["id"],
        modes_with_mask=[("sam_refine", True), ("sam_refine", False)],
    )

    with patch("production.service._dispatch_tasks") as mock_dispatch:
        res = await client.post(f"/api/v1/admin/production/batches/{batch_id}/start")

    assert res.status_code == 200
    body = res.json()
    assert body["enqueued"] == 1
    assert len(body["skipped"]) == 1
    assert body["skipped"][0]["reason"] == "missing mask_url"
    assert body["skipped"][0]["job_id"] == str(jobs[1].id)
    # 只 dispatch 一個（有 mask 的那個）
    assert mock_dispatch.call_count == 1
    dispatched_jobs = mock_dispatch.call_args.args[0]
    assert len(dispatched_jobs) == 1


@pytest.mark.asyncio
async def test_batch_start_skips_standard(client: AsyncClient, db):
    """batch 內含 standard（防禦：前端應已擋掉混批）→ standard 跳過、sam_* enqueue。"""
    image_data = await _create_image(client, db)
    batch_id, jobs = await _seed_batch_jobs(
        db, image_data["id"],
        modes_with_mask=[("standard", False), ("sam_refine", True)],
    )

    with patch("production.service._dispatch_tasks") as mock_dispatch:
        res = await client.post(f"/api/v1/admin/production/batches/{batch_id}/start")

    assert res.status_code == 200
    body = res.json()
    assert body["enqueued"] == 1
    assert len(body["skipped"]) == 1
    assert "standard" in body["skipped"][0]["reason"]
    assert body["skipped"][0]["job_id"] == str(jobs[0].id)
    assert mock_dispatch.call_count == 1


@pytest.mark.asyncio
async def test_batch_start_uses_advisory_lock_for_serialization(
    client: AsyncClient, db, monkeypatch,
):
    """start_batch 用 PostgreSQL advisory_xact_lock 序列化同 batch 的 concurrent 觸發。

    本測試驗證：start_batch 內部呼叫 pg_advisory_xact_lock。徹底並發 race 測試需要
    兩個 worker process 跑（pytest 單 process 環境難測），此處只驗 SQL 有發出。

    註：admin 連點按鈕的 race 視窗極小；advisory lock 序列化已能讓重複 dispatch
    機率降到極低（要兩個 admin 在毫秒內同時點擊）。徹底防重複需新增 dispatched_at
    欄位（schema 變更，非 Phase A 範圍），列為 known limitation。
    """
    image_data = await _create_image(client, db)
    batch_id, jobs = await _seed_batch_jobs(
        db, image_data["id"],
        modes_with_mask=[("sam_refine", True)],
    )

    captured_sql: list[str] = []
    from sqlalchemy.ext.asyncio import AsyncSession
    original_execute = AsyncSession.execute

    async def _spy_execute(self, statement, *args, **kwargs):
        captured_sql.append(str(statement))
        return await original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", _spy_execute)

    with patch("production.service._dispatch_tasks"):
        res = await client.post(f"/api/v1/admin/production/batches/{batch_id}/start")
    assert res.status_code == 200

    advisory_calls = [s for s in captured_sql if "pg_advisory_xact_lock" in s]
    assert len(advisory_calls) >= 1, "start_batch 必須呼叫 pg_advisory_xact_lock 序列化"


@pytest.mark.asyncio
async def test_batch_start_idempotent_when_already_processing(client: AsyncClient, db):
    """status 已不是 pending（如 processing）→ skipped，不重複觸發。"""
    from production.models import JobStatusEnum

    image_data = await _create_image(client, db)
    batch_id, jobs = await _seed_batch_jobs(
        db, image_data["id"],
        modes_with_mask=[("sam_refine", True)],
    )
    # 把唯一的 job 設成 processing（模擬已開始跑）
    jobs[0].status = JobStatusEnum.processing
    await db.commit()

    with patch("production.service._dispatch_tasks") as mock_dispatch:
        res = await client.post(f"/api/v1/admin/production/batches/{batch_id}/start")

    assert res.status_code == 200
    body = res.json()
    assert body["enqueued"] == 0
    assert len(body["skipped"]) == 1
    assert "processing" in body["skipped"][0]["reason"]
    assert mock_dispatch.call_count == 0


@pytest.mark.asyncio
async def test_batch_start_not_found(client: AsyncClient, db):
    """batch_id 不存在 → 404。"""
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    fake_id = uuid.uuid4()
    res = await client.post(f"/api/v1/admin/production/batches/{fake_id}/start")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_batch_start_non_admin(client: AsyncClient, db):
    """非 admin → 403。"""
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    fake_id = uuid.uuid4()
    res = await client.post(f"/api/v1/admin/production/batches/{fake_id}/start")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_batch_start_unauthenticated(client: AsyncClient, db):
    """未認證 → 401。"""
    fake_id = uuid.uuid4()
    res = await client.post(f"/api/v1/admin/production/batches/{fake_id}/start")
    assert res.status_code == 401
