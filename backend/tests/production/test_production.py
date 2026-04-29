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
    image = await _create_image(client, db)

    with patch("production.service.run_production_job") as mock_run, \
         patch("production.service.cancel_batch_remaining") as mock_cancel:
        mock_run.si.return_value = MagicMock()
        mock_cancel.si.return_value = MagicMock()

        res = await client.post(JOBS_URL, json={
            "image_id": image["id"],
            "jobs": [STANDARD_JOB, SAM_REFINE_JOB],
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
SMOOTH_CONTOUR_URL_SUFFIX = "/post-process/smooth-contour"

MERGE_COLOR_BODY = {"source_template_id": 3, "target_template_id": 1}
ELIM_BORDER_BODY = {"absorbed_template_id": 3, "surviving_template_id": 1}
SMOOTH_CONTOUR_BODY = {"border_between": [1, 3], "smoothness": 3}


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
async def test_merge_color_same_ids(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{MERGE_COLOR_URL_SUFFIX}",
        json={"source_template_id": 1, "target_template_id": 1},
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
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{ELIM_BORDER_URL_SUFFIX}",
        json={"absorbed_template_id": 2, "surviving_template_id": 2},
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


@pytest.mark.asyncio
async def test_smooth_contour_ok(client: AsyncClient, db):
    job_id = await _create_pending_job(client, db)
    await _force_complete(db, job_id)

    with patch("production.service.run_post_process_job") as mock_task:
        mock_task.delay.return_value = None
        res = await client.post(
            f"{JOBS_URL}/{job_id}{SMOOTH_CONTOUR_URL_SUFFIX}", json=SMOOTH_CONTOUR_BODY
        )

    assert res.status_code == 202
    assert res.json()["status"] == "processing"


@pytest.mark.asyncio
async def test_smooth_contour_invalid_smoothness(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SMOOTH_CONTOUR_URL_SUFFIX}",
        json={"border_between": [1, 3], "smoothness": 11},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_smooth_contour_wrong_border_length(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SMOOTH_CONTOUR_URL_SUFFIX}",
        json={"border_between": [1, 2, 3], "smoothness": 3},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_smooth_contour_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SMOOTH_CONTOUR_URL_SUFFIX}", json=SMOOTH_CONTOUR_BODY
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_smooth_contour_unauthenticated(client: AsyncClient, db):
    res = await client.post(
        f"{JOBS_URL}/{uuid.uuid4()}{SMOOTH_CONTOUR_URL_SUFFIX}", json=SMOOTH_CONTOUR_BODY
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
