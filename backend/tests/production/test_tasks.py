"""production/tasks.py 整合測試 — 直接呼叫 _run_production_job_async（同步引擎+Firebase mock）。

不啟 Celery worker、不打真 Firebase；只驗 task 內 DB 狀態轉換、上傳調用、回滾邏輯。
"""
import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import select

from auth.models import User
from core.config import settings
from production.models import (
    DetailEnum,
    DifficultyEnum,
    Image,
    JobStatusEnum,
    ModeEnum,
    ProductionJob,
)
from production.tasks import _run_production_job_async


@pytest.fixture(autouse=True)
def _force_test_db():
    """tasks.py 的 _get_db_url() 預設讀 settings.database_url（dev DB）；
    測試需把它指向 test DB，否則 task 看不到測試資料。"""
    test_url = settings.test_database_url or settings.database_url
    with patch("production.tasks._get_db_url", return_value=test_url):
        yield


async def _seed_admin(db) -> User:
    admin = User(
        name="ProdTaskAdmin",
        email=f"task_admin_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="admin",
        is_email_verified=True,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def _seed_image_and_job(
    db,
    *,
    mode: ModeEnum = ModeEnum.standard,
    difficulty: DifficultyEnum = DifficultyEnum.beginner,
) -> tuple[Image, ProductionJob]:
    admin = await _seed_admin(db)
    image = Image(
        uploader_id=admin.id,
        original_url="gs://test-bucket/production_images/abc.jpg",
        filename="abc.jpg",
        width=80, height=80,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    job = ProductionJob(
        image_id=image.id,
        status=JobStatusEnum.pending,
        approved=False,
        detail=DetailEnum.standard,
        difficulty=difficulty,
        mode=mode,
        canvas_w_cm=30,
        canvas_h_cm=30,
        min_brush_diam_cm=0.5,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return image, job


_ENGINE_RESULT = {
    "svg_path": "/tmp/fake/template.svg",
    "filled_path": "/tmp/fake/filled.png",
    "snapped_rgb_path": "/tmp/fake/snapped.png",
    "palette_data": [
        {
            "template_id": 1, "master_id": "N/A", "rgb": [255, 0, 0],
            "hex": "#FF0000", "pixels": 1000, "percent": 41.7,
        },
        {
            "template_id": 2, "master_id": "N/A", "rgb": [0, 255, 0],
            "hex": "#00FF00", "pixels": 1400, "percent": 58.3,
        },
    ],
    "num_colors_used": 2,
    "image_width": 80,
    "image_height": 80,
}


@pytest.mark.asyncio
async def test_run_production_job_success(db):
    """happy path：DB 從 pending → completed，3 個 url + palette + num_colors 寫入。"""
    image, job = await _seed_image_and_job(db)

    # mock：跳過下載 + 直接回 engine 結果 + mock _upload_file 回假 URL
    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.generate_standard", return_value=_ENGINE_RESULT) as mock_engine, \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template.svg",
            "gs://test-bucket/production_jobs/x/filled.png",
            "gs://test-bucket/production_jobs/x/snapped.png",
        ]

        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.completed
    # 全部 gs://（公開讀走 signed URL，與 upload/service.py 模式一致）
    assert refreshed.svg_url.startswith("gs://")
    assert refreshed.filled_template_url.startswith("gs://")
    assert refreshed.snapped_rgb_url.startswith("gs://")
    assert len(refreshed.palette_json) == 2
    assert refreshed.num_colors_used == 2
    assert mock_engine.called
    assert mock_upload.call_count == 3


@pytest.mark.asyncio
async def test_run_production_job_engine_error_marks_failed(db):
    """引擎 raise → status=failed、notes 含錯誤摘要、未上傳。"""
    image, job = await _seed_image_and_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.generate_standard", side_effect=ValueError("engine boom")), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "engine boom" in (refreshed.notes or "")
    assert refreshed.svg_url is None
    assert mock_upload.call_count == 0
    # 沒有上傳就沒得刪
    assert mock_delete.call_count == 0


@pytest.mark.asyncio
async def test_run_production_job_upload_error_rolls_back(db):
    """第 2 個檔上傳失敗 → 已上傳的第 1 個被刪、status=failed。"""
    image, job = await _seed_image_and_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.generate_standard", return_value=_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        # 第 1 個上傳成功，第 2 個炸
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template.svg",
            RuntimeError("firebase 503"),
        ]
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "firebase 503" in (refreshed.notes or "")
    # 已上傳的 svg blob 應被刪除
    assert mock_delete.call_count == 1
    deleted_path = mock_delete.call_args_list[0].args[0]
    assert "template_" in deleted_path and deleted_path.endswith(".svg")


@pytest.mark.asyncio
async def test_run_production_job_db_commit_error_rolls_back_blobs(db):
    """3 個 blob 全上傳成功，但最後 commit 失敗 → 3 個 blob 都被刪、status=failed。

    保護重點：避免 job 卡 processing（admin 看到假成功）+ 避免 Firebase orphan。
    """
    image, job = await _seed_image_and_job(db)

    # 用 mock 攔截 commit：第一次 commit（status=processing）成功，第二次（completed）炸
    real_commit_count = {"n": 0}
    original_commit = None

    async def _maybe_fail_commit(self):
        real_commit_count["n"] += 1
        if real_commit_count["n"] == 2:
            raise RuntimeError("connection lost mid-commit")
        return await original_commit(self)

    from sqlalchemy.ext.asyncio import AsyncSession
    original_commit = AsyncSession.commit

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.generate_standard", return_value=_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete, \
         patch.object(AsyncSession, "commit", _maybe_fail_commit):
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template.svg",
            "gs://test-bucket/production_jobs/x/filled.png",
            "gs://test-bucket/production_jobs/x/snapped.png",
        ]
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "DB 寫回失敗" in (refreshed.notes or "")
    # 3 個已上傳 blob 全被刪
    assert mock_delete.call_count == 3


@pytest.mark.asyncio
async def test_run_production_job_image_download_error(db):
    """Firebase 下載原圖失敗 → status=failed。"""
    image, job = await _seed_image_and_job(db)

    with patch(
        "production.tasks._download_image_to_path",
        side_effect=RuntimeError("blob 404"),
    ), patch("production.tasks._upload_file") as mock_upload:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "blob 404" in (refreshed.notes or "")
    assert mock_upload.call_count == 0


@pytest.mark.asyncio
async def test_run_production_job_not_found_silent_return(db):
    """job_id 不存在 → silent return（log warning），不 raise。"""
    fake_id = str(uuid.uuid4())
    # Should not raise
    await _run_production_job_async(fake_id)


@pytest.mark.asyncio
async def test_run_production_job_unsupported_mode(db):
    """mode=sam_refine 暫不支援 → status=failed、notes 提示 Phase 2-B。"""
    image, job = await _seed_image_and_job(db, mode=ModeEnum.sam_refine)
    # 補 extra_colors 避免 model 約束（雖然這 test 不會跑到引擎，不影響）
    job.extra_colors = 5
    await db.commit()

    with patch("production.tasks.generate_standard") as mock_engine:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "standard" in (refreshed.notes or "")
    # 引擎不該被呼叫
    assert mock_engine.call_count == 0


@pytest.mark.asyncio
async def test_run_production_job_no_image_id(db):
    """custom_request 路徑：image_id is None → status=failed、提示要先指派 image。"""
    await _seed_admin(db)
    job = ProductionJob(
        image_id=None,
        custom_request_id=None,
        status=JobStatusEnum.pending,
        approved=False,
        detail=DetailEnum.standard,
        difficulty=DifficultyEnum.beginner,
        mode=ModeEnum.standard,
        canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    with patch("production.tasks.generate_standard") as mock_engine:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "image_id" in (refreshed.notes or "")
    assert mock_engine.call_count == 0


# ── _parse_blob_path 純函式 ────────────────────────────────────────────────────


def test_parse_blob_path_gs_url():
    from production.tasks import _parse_blob_path
    assert _parse_blob_path("gs://my-bucket/foo/bar.jpg", "my-bucket") == "foo/bar.jpg"


def test_parse_blob_path_https_url_with_query():
    from production.tasks import _parse_blob_path
    url = "https://storage.googleapis.com/my-bucket/foo/bar.jpg?token=abc"
    assert _parse_blob_path(url, "my-bucket") == "foo/bar.jpg"


def test_parse_blob_path_unknown_format_raises():
    from production.tasks import _parse_blob_path
    with pytest.raises(ValueError):
        _parse_blob_path("ftp://strange/", "my-bucket")
