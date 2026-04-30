"""Phase 2-A.2 真實後處理測試 — A 格子合併 + B 消除邊界共用引擎。

engine layer 用 80×80 真小圖跑；task layer 全 mock 引擎+Firebase。
"""
import os
import tempfile
import uuid
from unittest.mock import patch

import cv2
import numpy as np
import pytest
from sqlalchemy import select

from auth.models import User
from core.config import settings
from palette.models import MappedByEnum, PaletteColorMapping
from production.engine import apply_color_replacement
from production.models import (
    DetailEnum,
    DifficultyEnum,
    Image,
    JobStatusEnum,
    ModeEnum,
    ProductionJob,
)
from production.tasks import (
    _find_rgb_in_palette,
    _resolve_post_process_op,
    _run_post_process_async,
)


@pytest.fixture(autouse=True)
def _force_test_db():
    """tasks.py 預設用 dev DB；測試指向 test DB。"""
    test_url = settings.test_database_url or settings.database_url
    with patch("production.tasks._get_db_url", return_value=test_url):
        yield


# ── Helpers ───────────────────────────────────────────────────────────────────


def _write_two_color_image(path: str, w: int = 80, h: int = 80):
    """半半圖：左半紅、右半綠（cv2 寫入是 BGR）。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, : w // 2] = (0, 0, 255)  # BGR red
    img[:, w // 2 :] = (0, 255, 0)  # BGR green
    cv2.imwrite(path, img)


async def _seed_admin(db) -> User:
    admin = User(
        name="PostProcAdmin",
        email=f"pp_admin_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="x",
        role="admin",
        is_email_verified=True,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def _seed_completed_job(db) -> ProductionJob:
    """建一個假 completed job：palette_json 含 3 色、3 個 url 全 gs://、num_colors_used=3。"""
    admin = await _seed_admin(db)
    image = Image(
        uploader_id=admin.id,
        original_url="gs://test-bucket/production_images/orig.jpg",
        filename="orig.jpg",
        width=80, height=80,
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)

    job = ProductionJob(
        image_id=image.id,
        status=JobStatusEnum.processing,  # service.post_process 已設這個狀態
        approved=False,
        detail=DetailEnum.standard,
        difficulty=DifficultyEnum.beginner,
        mode=ModeEnum.standard,
        canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
        svg_url="gs://test-bucket/production_jobs/x/template_old.svg",
        filled_template_url="gs://test-bucket/production_jobs/x/filled_old.png",
        snapped_rgb_url="gs://test-bucket/production_jobs/x/snapped_old.png",
        palette_json=[
            {
                "template_id": 1, "rgb": [255, 0, 0], "hex": "#FF0000",
                "pixels": 1000, "percent": 50.0, "master_id": "N/A",
            },
            {
                "template_id": 2, "rgb": [0, 255, 0], "hex": "#00FF00",
                "pixels": 800, "percent": 40.0, "master_id": "N/A",
            },
            {
                "template_id": 3, "rgb": [0, 0, 255], "hex": "#0000FF",
                "pixels": 200, "percent": 10.0, "master_id": "N/A",
            },
        ],
        num_colors_used=3,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


# ── Engine layer pure function tests ──────────────────────────────────────────


def test_apply_color_replacement_replaces_pixels():
    """80×80 半紅半綠圖 → red→green → 應該全綠（output_to_svg 後僅剩 1 色）。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.png")
        _write_two_color_image(src)

        result = apply_color_replacement(
            src, os.path.join(tmp, "out"),
            src_rgb=(255, 0, 0),
            tgt_rgb=(0, 255, 0),
            canvas_w_cm=30, canvas_h_cm=30,
            min_brush_diam_cm=0.5,
            min_ratio_multiplier=0.3,
        )
        # 全綠 → palette 應只剩 1 色（[0,255,0]）
        assert result["num_colors_used"] == 1
        assert result["palette_data"][0]["rgb"] == [0, 255, 0]


def test_apply_color_replacement_produces_files():
    """3 個輸出檔實際存在 + palette_data 結構符合 schema。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.png")
        _write_two_color_image(src)

        result = apply_color_replacement(
            src, os.path.join(tmp, "out"),
            src_rgb=(255, 0, 0), tgt_rgb=(0, 255, 0),
            canvas_w_cm=30, canvas_h_cm=30,
            min_brush_diam_cm=0.5, min_ratio_multiplier=0.3,
        )
        for k in ("svg_path", "filled_path", "snapped_rgb_path"):
            assert os.path.exists(result[k])
            assert os.path.getsize(result[k]) > 0
        for item in result["palette_data"]:
            assert isinstance(item["template_id"], int) and item["template_id"] >= 1
            assert len(item["rgb"]) == 3
            assert item["hex"].startswith("#") and len(item["hex"]) == 7
            assert isinstance(item["pixels"], int)
            assert 0 <= item["percent"] <= 100


def test_apply_color_replacement_src_not_in_image_no_raise():
    """src_rgb 圖中不存在 → mask 全 False → 不 raise，正常產出（兩色）。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.png")
        _write_two_color_image(src)

        result = apply_color_replacement(
            src, os.path.join(tmp, "out"),
            src_rgb=(123, 45, 67),  # 不存在
            tgt_rgb=(0, 255, 0),
            canvas_w_cm=30, canvas_h_cm=30,
            min_brush_diam_cm=0.5, min_ratio_multiplier=0.3,
        )
        # 圖完全沒變，仍是兩色
        assert result["num_colors_used"] >= 1


# ── Pure helper tests ─────────────────────────────────────────────────────────


def test_resolve_post_process_op_merge_color():
    src, tgt = _resolve_post_process_op({"source_template_id": 3, "target_template_id": 1})
    assert (src, tgt) == (3, 1)


def test_resolve_post_process_op_eliminate_border():
    src, tgt = _resolve_post_process_op(
        {"absorbed_template_id": 5, "surviving_template_id": 2}
    )
    assert (src, tgt) == (5, 2)


def test_resolve_post_process_op_unknown_shape_raises():
    with pytest.raises(ValueError, match="無法判斷後處理操作類型"):
        _resolve_post_process_op({"foo": 1, "bar": 2})


def test_find_rgb_in_palette_hit():
    palette = [
        {"template_id": 1, "rgb": [10, 20, 30]},
        {"template_id": 2, "rgb": [40, 50, 60]},
    ]
    assert _find_rgb_in_palette(palette, 2) == (40, 50, 60)


def test_find_rgb_in_palette_miss():
    palette = [{"template_id": 1, "rgb": [10, 20, 30]}]
    assert _find_rgb_in_palette(palette, 99) is None


# ── Task layer integration tests (mock engine + Firebase) ─────────────────────


_FAKE_NEW_PALETTE = [
    {
        "template_id": 1, "rgb": [0, 255, 0], "hex": "#00FF00",
        "pixels": 1800, "percent": 90.0, "master_id": "N/A",
    },
    {
        "template_id": 2, "rgb": [0, 0, 255], "hex": "#0000FF",
        "pixels": 200, "percent": 10.0, "master_id": "N/A",
    },
]

_FAKE_ENGINE_RESULT = {
    "svg_path": "/tmp/fake/template.svg",
    "filled_path": "/tmp/fake/filled.png",
    "snapped_rgb_path": "/tmp/fake/snapped.png",
    "palette_data": _FAKE_NEW_PALETTE,
    "num_colors_used": 2,
    "image_width": 80,
    "image_height": 80,
    "min_radius_px": 13.3,
}


@pytest.mark.asyncio
async def test_run_post_process_merge_color_success(db):
    job = await _seed_completed_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.apply_color_replacement", return_value=_FAKE_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template_new.svg",
            "gs://test-bucket/production_jobs/x/filled_new.png",
            "gs://test-bucket/production_jobs/x/snapped_new.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.completed
    assert refreshed.num_colors_used == 2
    assert len(refreshed.palette_json) == 2
    assert refreshed.svg_url == "gs://test-bucket/production_jobs/x/template_new.svg"
    assert refreshed.filled_template_url == "gs://test-bucket/production_jobs/x/filled_new.png"
    assert refreshed.snapped_rgb_url == "gs://test-bucket/production_jobs/x/snapped_new.png"


@pytest.mark.asyncio
async def test_run_post_process_eliminate_border_success(db):
    """B 消除邊界（absorbed/surviving naming）— 與 A 共用引擎，行為應一致。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.apply_color_replacement", return_value=_FAKE_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template_b.svg",
            "gs://test-bucket/production_jobs/x/filled_b.png",
            "gs://test-bucket/production_jobs/x/snapped_b.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"absorbed_template_id": 3, "surviving_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.completed
    assert refreshed.num_colors_used == 2


@pytest.mark.asyncio
async def test_run_post_process_palette_mappings_remapped(db):
    """前置 seed 3 個 mappings → 合併後驗：A/B 的 mapping 仍存在但 template_id 已重新匹配；
    被合併色號的 mapping row 被刪。

    舊 palette: 1=red, 2=green, 3=blue
    新 palette: 1=green, 2=blue（red 被合併掉）
    舊 mappings: (1, red), (2, green), (3, blue)
    新 mappings 應該: (green→1), (blue→2)；red 那筆 DELETE
    """
    job = await _seed_completed_job(db)

    # 先 seed physical_color（FK 需要）
    from color.models import PhysicalColor
    pc = PhysicalColor(
        code=f"TEST-{uuid.uuid4().hex[:6]}",
        name="test color",
        rgb=[0, 0, 0],
        brand="A",
        is_active=True,
    )
    db.add(pc)
    await db.commit()
    await db.refresh(pc)

    # seed 3 個 mappings
    for tid, rgb in [(1, [255, 0, 0]), (2, [0, 255, 0]), (3, [0, 0, 255])]:
        db.add(PaletteColorMapping(
            production_job_id=job.id,
            template_id=tid,
            algorithm_rgb=rgb,
            physical_color_id=pc.id,
            mapped_by=MappedByEnum.system,
        ))
    await db.commit()

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.apply_color_replacement", return_value=_FAKE_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://x/svg.svg", "gs://x/filled.png", "gs://x/snapped.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    rows = (await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job.id
        ).order_by(PaletteColorMapping.template_id)
    )).scalars().all()
    for r in rows:
        await db.refresh(r)

    # 應剩 2 個 mappings：green→1, blue→2
    rgbs_to_ids = {tuple(r.algorithm_rgb): r.template_id for r in rows}
    assert (0, 255, 0) in rgbs_to_ids
    assert rgbs_to_ids[(0, 255, 0)] == 1  # green 在新 palette 是 #1
    assert (0, 0, 255) in rgbs_to_ids
    assert rgbs_to_ids[(0, 0, 255)] == 2  # blue 在新 palette 是 #2
    # red 那筆應被刪除
    assert (255, 0, 0) not in rgbs_to_ids
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_run_post_process_template_id_not_in_palette(db):
    """params 帶不存在的 template_id → status=failed，notes 含「找不到 template_id」。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks.apply_color_replacement") as mock_engine, \
         patch("production.tasks._upload_file") as mock_upload:
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 999, "target_template_id": 1},  # 999 不存在
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "template_id" in (refreshed.notes or "")
    assert mock_engine.call_count == 0
    assert mock_upload.call_count == 0


@pytest.mark.asyncio
async def test_run_post_process_engine_error_marks_failed(db):
    """引擎 raise → status=failed、notes 含錯誤、未上傳。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch(
             "production.tasks.apply_color_replacement",
             side_effect=ValueError("engine boom"),
         ), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "engine boom" in (refreshed.notes or "")
    assert mock_upload.call_count == 0
    assert mock_delete.call_count == 0


@pytest.mark.asyncio
async def test_run_post_process_upload_error_rolls_back(db):
    """第 2 個檔上傳失敗 → 第 1 個被刪、status=failed。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.apply_color_replacement", return_value=_FAKE_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        mock_upload.side_effect = [
            "gs://x/template.svg",
            RuntimeError("firebase 503"),
        ]
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "firebase 503" in (refreshed.notes or "")
    assert mock_delete.call_count == 1


@pytest.mark.asyncio
async def test_run_post_process_unknown_op_shape(db):
    """params 既無 src/tgt 也無 absorbed/surviving → status=failed。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks.apply_color_replacement") as mock_engine:
        await _run_post_process_async(str(job.id), {"foo": "bar"})

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "無法判斷後處理操作類型" in (refreshed.notes or "")
    assert mock_engine.call_count == 0


@pytest.mark.asyncio
async def test_run_post_process_clears_phase2b_note(db):
    """job.notes 之前因 stub 留下 [Phase 2-B] → 真實成功後 notes 清空。"""
    job = await _seed_completed_job(db)
    job.notes = "[Phase 2-B] post-process 尚未實作，本次操作未變更檔案"
    await db.commit()

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.apply_color_replacement", return_value=_FAKE_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://x/svg.svg", "gs://x/filled.png", "gs://x/snapped.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.completed
    # [Phase 2-B] 應該被清掉
    assert "[Phase 2-B]" not in (refreshed.notes or "")


@pytest.mark.asyncio
async def test_run_post_process_same_rgb_guard(db):
    """src 與 tgt 不同 template_id 但 RGB 相同（palette_json 異常）→ status=failed。

    避免 noop pixel replace 但 mappings 仍被重編號（破壞性）。
    """
    job = await _seed_completed_job(db)
    # 故意把 template_id=1 和 2 設成同 RGB
    job.palette_json = [
        {
            "template_id": 1, "rgb": [100, 100, 100], "hex": "#646464",
            "pixels": 1, "percent": 0.1, "master_id": "N/A",
        },
        {
            "template_id": 2, "rgb": [100, 100, 100], "hex": "#646464",
            "pixels": 1, "percent": 0.1, "master_id": "N/A",
        },
    ]
    await db.commit()

    with patch("production.tasks.apply_color_replacement") as mock_engine:
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "RGB 相同" in (refreshed.notes or "")
    assert mock_engine.call_count == 0


@pytest.mark.asyncio
async def test_run_post_process_deletes_old_blobs_on_success(db):
    """成功後舊 svg/filled/snapped 3 個 blob 必須被刪（避免 Firebase orphan 累積）。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks.apply_color_replacement", return_value=_FAKE_ENGINE_RESULT), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob_by_url") as mock_delete_old:
        mock_upload.side_effect = [
            "gs://x/svg.svg", "gs://x/filled.png", "gs://x/snapped.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    # 3 個舊 url 都該被嘗試刪除
    assert mock_delete_old.call_count == 3
    deleted_urls = {c.args[0] for c in mock_delete_old.call_args_list}
    assert "gs://test-bucket/production_jobs/x/template_old.svg" in deleted_urls
    assert "gs://test-bucket/production_jobs/x/filled_old.png" in deleted_urls
    assert "gs://test-bucket/production_jobs/x/snapped_old.png" in deleted_urls


@pytest.mark.asyncio
async def test_run_post_process_no_snapped_rgb_url(db):
    """job 缺 snapped_rgb_url → status=failed（無法下載原圖）。"""
    job = await _seed_completed_job(db)
    job.snapped_rgb_url = None
    await db.commit()

    with patch("production.tasks.apply_color_replacement") as mock_engine:
        await _run_post_process_async(
            str(job.id),
            {"source_template_id": 1, "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "snapped_rgb_url" in (refreshed.notes or "")
    assert mock_engine.call_count == 0
