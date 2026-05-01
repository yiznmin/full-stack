"""production/tasks.py — sam_refine / sam_weighted worker 整合測試（Phase A）。

直接呼叫 _run_production_job_async；不啟 Celery worker、不打真 Firebase。
驗 mode dispatch、mask 下載、缺 mask_url 的 fail 路徑、引擎失敗的 cleanup。

與 test_tasks.py 並列；helper 故意有少量重複（決議：不抽 conftest，避免汙染既有測試）。
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
    """tasks.py 的 _get_db_url() 預設讀 settings.database_url；測試指向 test DB。"""
    test_url = settings.test_database_url or settings.database_url
    with patch("production.tasks._get_db_url", return_value=test_url):
        yield


async def _seed_admin(db) -> User:
    admin = User(
        name="ProdSamAdmin",
        email=f"sam_admin_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="admin",
        is_email_verified=True,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def _seed_sam_job(
    db,
    *,
    mode: ModeEnum,
    mask_url: str | None = "gs://test-bucket/production_jobs/abc/mask.png",
    extra_colors: int | None = 5,
    weight_ratio: float | None = 0.65,
    bg_extra_blur: int | None = 0,
    image: Image | None = None,
) -> tuple[Image, ProductionJob]:
    if image is None:
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
        difficulty=DifficultyEnum.beginner,
        mode=mode,
        canvas_w_cm=30,
        canvas_h_cm=30,
        min_brush_diam_cm=0.5,
        mask_url=mask_url,
        extra_colors=extra_colors,
        weight_ratio=weight_ratio,
        bg_extra_blur=bg_extra_blur,
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
async def test_run_job_sam_refine_ok(db):
    """sam_refine happy path：mock generate_sam_refine 成功 → status=completed。"""
    image, job = await _seed_sam_job(db, mode=ModeEnum.sam_refine)

    with patch("production.tasks._download_image_to_path") as mock_download, \
         patch(
             "production.tasks.generate_sam_refine", return_value=_ENGINE_RESULT,
         ) as mock_engine, \
         patch("production.tasks.generate_standard") as mock_standard, \
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
    assert refreshed.svg_url.startswith("gs://")
    assert refreshed.filled_template_url.startswith("gs://")
    assert refreshed.snapped_rgb_url.startswith("gs://")
    assert refreshed.num_colors_used == 2
    assert mock_engine.called
    assert mock_standard.called is False
    # 下載被呼叫兩次：原圖 + mask
    assert mock_download.call_count == 2
    # 第二次下載是 mask
    second_call_args = mock_download.call_args_list[1].args
    assert second_call_args[0] == "gs://test-bucket/production_jobs/abc/mask.png"
    # extra_colors 確實傳給引擎
    engine_kwargs = mock_engine.call_args.kwargs
    assert engine_kwargs["extra_colors"] == 5


@pytest.mark.asyncio
async def test_run_job_sam_weighted_ok(db):
    """sam_weighted happy path：weight_ratio + bg_extra_blur 正確傳入。"""
    image, job = await _seed_sam_job(
        db, mode=ModeEnum.sam_weighted,
        weight_ratio=0.7, bg_extra_blur=15,
    )

    with patch("production.tasks._download_image_to_path"), \
         patch(
             "production.tasks.generate_sam_weighted", return_value=_ENGINE_RESULT,
         ) as mock_engine, \
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
    engine_kwargs = mock_engine.call_args.kwargs
    assert engine_kwargs["weight_ratio"] == pytest.approx(0.7)
    assert engine_kwargs["bg_extra_blur"] == 15
    # weighted 不收 blur_*
    assert "blur_ksize" not in engine_kwargs


@pytest.mark.asyncio
async def test_run_job_sam_refine_missing_mask(db):
    """sam_refine 缺 mask_url → status=failed、引擎不被呼叫。"""
    image, job = await _seed_sam_job(
        db, mode=ModeEnum.sam_refine, mask_url=None,
    )

    with patch("production.tasks._download_image_to_path") as mock_download, \
         patch("production.tasks.generate_sam_refine") as mock_engine:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    notes = refreshed.notes or ""
    assert "sam_refine" in notes
    assert "mask_url" in notes
    assert mock_engine.call_count == 0
    assert mock_download.call_count == 0


@pytest.mark.asyncio
async def test_run_job_sam_weighted_missing_mask(db):
    """sam_weighted 缺 mask_url → status=failed。"""
    image, job = await _seed_sam_job(
        db, mode=ModeEnum.sam_weighted, mask_url=None,
    )

    with patch("production.tasks.generate_sam_weighted") as mock_engine:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    notes = refreshed.notes or ""
    assert "sam_weighted" in notes
    assert "mask_url" in notes
    assert mock_engine.call_count == 0


@pytest.mark.asyncio
async def test_run_job_sam_refine_engine_failure_no_upload(db):
    """sam_refine 引擎拋例外於上傳前 → status=failed、沒上傳 → 沒得清。"""
    image, job = await _seed_sam_job(db, mode=ModeEnum.sam_refine)

    with patch("production.tasks._download_image_to_path"), \
         patch(
             "production.tasks.generate_sam_refine",
             side_effect=ValueError("sam engine boom"),
         ), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "sam engine boom" in (refreshed.notes or "")
    assert mock_upload.call_count == 0
    assert mock_delete.call_count == 0


@pytest.mark.asyncio
async def test_run_job_sam_refine_upload_error_rolls_back(db):
    """sam_refine 引擎成功、上傳第 2 個檔失敗 → 已上傳的第 1 個被清掉。"""
    image, job = await _seed_sam_job(db, mode=ModeEnum.sam_refine)

    with patch("production.tasks._download_image_to_path"), \
         patch(
             "production.tasks.generate_sam_refine", return_value=_ENGINE_RESULT,
         ), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
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


# ── create_jobs 行為調整測試（Phase A.3）─────────────────────────────────────


@pytest.mark.asyncio
async def test_create_jobs_sam_skips_enqueue(db):
    """create_jobs 收到 mode=sam_refine：建 job、status=pending、Celery 沒被 enqueue。"""
    from production.service import create_jobs

    admin = await _seed_admin(db)
    image = Image(
        uploader_id=admin.id,
        original_url="gs://test-bucket/production_images/x.jpg",
        filename="x.jpg",
        width=80, height=80,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    with patch("production.service.run_production_job") as mock_task:
        result = await create_jobs(
            db,
            image_id=image.id,
            custom_request_id=None,
            jobs_params=[{
                "detail": "standard", "difficulty": "beginner",
                "mode": "sam_refine",
                "canvas_w_cm": 30, "canvas_h_cm": 30,
                "min_brush_diam_cm": 1.0,
                "extra_colors": 5,
            }],
        )

    # job 建立成功
    assert len(result["job_ids"]) == 1
    # 單筆 sam_* 也分配 batch_id
    assert result["batch_id"] is not None

    # Celery task 沒被 enqueue
    assert mock_task.si.call_count == 0
    assert mock_task.delay.call_count == 0

    # DB 狀態 pending
    job = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == result["job_ids"][0])
    )).scalar_one()
    assert job.status == JobStatusEnum.pending


@pytest.mark.asyncio
async def test_create_jobs_standard_still_enqueues(db):
    """standard mode 維持既有行為：建 job + 立即 enqueue Celery。"""
    from production.service import create_jobs

    admin = await _seed_admin(db)
    image = Image(
        uploader_id=admin.id,
        original_url="gs://test-bucket/production_images/y.jpg",
        filename="y.jpg",
        width=80, height=80,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    with patch("production.service.run_production_job") as mock_task:
        result = await create_jobs(
            db,
            image_id=image.id,
            custom_request_id=None,
            jobs_params=[{
                "detail": "standard", "difficulty": "beginner",
                "mode": "standard",
                "canvas_w_cm": 30, "canvas_h_cm": 30,
                "min_brush_diam_cm": 1.0,
            }],
        )

    assert len(result["job_ids"]) == 1
    # 單筆 standard 仍 batch_id=None
    assert result["batch_id"] is None
    # task signature 被建立
    assert mock_task.si.call_count == 1


@pytest.mark.asyncio
async def test_create_jobs_single_sam_assigns_batch_id(db):
    """Phase A 行為擴張：單筆 sam_refine 也要有 batch_id（non-null）。"""
    from production.service import create_jobs

    admin = await _seed_admin(db)
    image = Image(
        uploader_id=admin.id,
        original_url="gs://test-bucket/production_images/z.jpg",
        filename="z.jpg",
        width=80, height=80,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    with patch("production.service.run_production_job"):
        result = await create_jobs(
            db,
            image_id=image.id,
            custom_request_id=None,
            jobs_params=[{
                "detail": "standard", "difficulty": "beginner",
                "mode": "sam_weighted",
                "canvas_w_cm": 30, "canvas_h_cm": 30,
                "min_brush_diam_cm": 1.0,
                "weight_ratio": 0.65,
            }],
        )

    assert result["batch_id"] is not None
    # 該 job 的 batch_id 也已寫入 DB
    job = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == result["job_ids"][0])
    )).scalar_one()
    assert job.batch_id == result["batch_id"]


# ── _resolve_sam_kwargs 預設值（reviewer #4：bg_extra_blur 應從 detail preset）─

def test_resolve_sam_kwargs_sam_weighted_uses_detail_preset_default():
    """sam_weighted 沒填 bg_extra_blur → 取 DETAIL_PRESETS["標準"]["bg_extra_blur"]=21。"""
    from production.tasks import _resolve_sam_kwargs

    class _FakeJob:
        mode = "sam_weighted"
        weight_ratio = None
        bg_extra_blur = None  # 沒填

    kwargs = _resolve_sam_kwargs(_FakeJob())
    assert kwargs["bg_extra_blur"] == 21  # 標準 detail preset
    assert kwargs["weight_ratio"] == 0.65  # schema DEFAULT


def test_resolve_sam_kwargs_sam_weighted_override():
    """sam_weighted 有填 bg_extra_blur → 用覆蓋值。"""
    from production.tasks import _resolve_sam_kwargs

    class _FakeJob:
        mode = "sam_weighted"
        weight_ratio = 0.7
        bg_extra_blur = 5

    kwargs = _resolve_sam_kwargs(_FakeJob())
    assert kwargs["bg_extra_blur"] == 5
    assert kwargs["weight_ratio"] == 0.7


def test_resolve_sam_kwargs_standard_returns_empty():
    from production.tasks import _resolve_sam_kwargs

    class _FakeJob:
        mode = "standard"

    assert _resolve_sam_kwargs(_FakeJob()) == {}


# ── cancel_batch_remaining filter（reviewer #2）─────────────────────────────

@pytest.mark.asyncio
async def test_cancel_batch_skips_sam_pending_without_mask(db):
    """cancel_batch_remaining 不誤殺等待補 mask 的 sam_* pending（mask_url=null）。

    standard pending 仍會被 cancel；sam_* mask_url 不為 null 的 pending 也會被 cancel
    （那是「已就緒但 worker 還沒撿」狀態）。
    """
    from production.tasks import _cancel_batch_async

    admin = await _seed_admin(db)
    image = Image(
        uploader_id=admin.id,
        original_url="gs://test-bucket/production_images/c.jpg",
        filename="c.jpg",
        width=80, height=80,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    batch_id = uuid.uuid4()
    # 三筆同 batch：standard pending、sam_* with mask、sam_* without mask
    standard_job = ProductionJob(
        image_id=image.id, batch_id=batch_id,
        status=JobStatusEnum.pending, approved=False,
        detail=DetailEnum.standard, difficulty=DifficultyEnum.beginner,
        mode=ModeEnum.standard,
        canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
    )
    sam_with_mask = ProductionJob(
        image_id=image.id, batch_id=batch_id,
        status=JobStatusEnum.pending, approved=False,
        detail=DetailEnum.standard, difficulty=DifficultyEnum.beginner,
        mode=ModeEnum.sam_refine,
        canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
        mask_url="gs://test-bucket/mask.png",
        extra_colors=5,
    )
    sam_without_mask = ProductionJob(
        image_id=image.id, batch_id=batch_id,
        status=JobStatusEnum.pending, approved=False,
        detail=DetailEnum.standard, difficulty=DifficultyEnum.beginner,
        mode=ModeEnum.sam_refine,
        canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
        mask_url=None,
        extra_colors=5,
    )
    db.add_all([standard_job, sam_with_mask, sam_without_mask])
    await db.commit()

    await _cancel_batch_async(str(batch_id))

    # 重新讀
    await db.refresh(standard_job)
    await db.refresh(sam_with_mask)
    await db.refresh(sam_without_mask)

    assert standard_job.status == JobStatusEnum.cancelled
    assert sam_with_mask.status == JobStatusEnum.cancelled
    assert sam_without_mask.status == JobStatusEnum.pending  # 不誤殺


# 註：sam_refine 但 image 找不到的 case 在 DB 層被 FK 約束保證不會發生
# （image_id FK → images.id；image 被 job 參考時刪不掉）。既有 standard worker
# 也沒測這個 path。略過。


@pytest.mark.asyncio
async def test_run_job_sam_refine_mask_download_failure(db):
    """mask 下載失敗 → status=failed、notes 含錯誤摘要。"""
    image, job = await _seed_sam_job(db, mode=ModeEnum.sam_refine)

    # 第一次下載原圖成功、第二次下載 mask 炸
    download_calls = []

    def _download(url, path):
        download_calls.append(url)
        if "mask" in url:
            raise RuntimeError("mask blob 404")

    with patch("production.tasks._download_image_to_path", side_effect=_download), \
         patch("production.tasks.generate_sam_refine") as mock_engine, \
         patch("production.tasks._upload_file") as mock_upload:
        await _run_production_job_async(str(job.id))

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "mask blob 404" in (refreshed.notes or "")
    assert mock_engine.call_count == 0
    assert mock_upload.call_count == 0
