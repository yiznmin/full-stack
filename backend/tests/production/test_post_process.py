"""區域層級後處理測試（A 格子合併 + B 消除邊界）— 共用 apply_region_replacement 引擎。

engine layer 用真小圖跑 + 自製 SVG 驗 polygon 解析；task layer 全 mock 引擎+Firebase。
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
from production.engine import (
    _extract_polygon_points,
    _polygon_to_mask,
    apply_region_replacement,
    get_polygon_rgb,
)
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


def _write_three_color_image(path: str, w: int = 90, h: int = 90):
    """三段圖：左 1/3 紅、中 1/3 綠、右 1/3 藍。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, : w // 3] = (0, 0, 255)
    img[:, w // 3 : 2 * w // 3] = (0, 255, 0)
    img[:, 2 * w // 3 :] = (255, 0, 0)
    cv2.imwrite(path, img)


def _write_test_svg(path: str, polygons: list[tuple[str, list[tuple[int, int]]]],
                    img_w: int, img_h: int):
    """寫 SVG 給 _extract_polygon_points 等測試用。

    polygons: [(id, [(x, y), ...]), ...]
    """
    parts = [
        f'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{img_w}px" height="{img_h}px" viewBox="0 0 {img_w} {img_h}">',
    ]
    for pid, pts in polygons:
        pts_str = " ".join(f"{x},{y}" for x, y in pts)
        parts.append(f'<polygon id="{pid}" points="{pts_str}" fill="#ABCDEF"/>')
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(parts))


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
        status=JobStatusEnum.processing,
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


# ── SVG parsing pure-function tests ───────────────────────────────────────────


def test_extract_polygon_points_finds_by_id():
    with tempfile.TemporaryDirectory() as tmp:
        svg = os.path.join(tmp, "t.svg")
        _write_test_svg(svg, [
            ("r0", [(0, 0), (10, 0), (10, 10), (0, 10)]),
            ("r1", [(20, 0), (30, 0), (30, 10), (20, 10)]),
        ], 100, 100)

        pts = _extract_polygon_points(svg, "r1")
        assert pts == [(20, 0), (30, 0), (30, 10), (20, 10)]


def test_extract_polygon_points_unknown_id_raises():
    with tempfile.TemporaryDirectory() as tmp:
        svg = os.path.join(tmp, "t.svg")
        _write_test_svg(svg, [("r0", [(0, 0), (10, 0), (5, 5)])], 100, 100)
        with pytest.raises(ValueError, match="找不到 polygon"):
            _extract_polygon_points(svg, "r99")


def test_polygon_to_mask_basic():
    """10×10 矩形 polygon → mask 內全 True，外全 False。"""
    pts = [(0, 0), (10, 0), (10, 10), (0, 10)]
    mask = _polygon_to_mask(pts, 20, 20)
    assert mask[5, 5]  # 內部
    assert not mask[15, 15]  # 外部
    assert mask.dtype == bool


def test_get_polygon_rgb_returns_pixel_color():
    """SVG polygon 對應到 snapped_rgb 圖某一格 → 採樣 RGB 應為該格的色。"""
    with tempfile.TemporaryDirectory() as tmp:
        img_path = os.path.join(tmp, "snap.png")
        svg = os.path.join(tmp, "t.svg")
        # 80×80 半紅半綠 BGR
        _write_two_color_image(img_path, 80, 80)
        # polygon r0 在右半（綠色）
        _write_test_svg(svg, [
            ("r0", [(50, 10), (70, 10), (70, 30), (50, 30)]),
        ], 80, 80)

        rgb = get_polygon_rgb(img_path, svg, "r0")
        # 右半綠：BGR (0,255,0) → 讀回 imdecode 還是 BGR → cvt RGB = (0,255,0)
        assert rgb == (0, 255, 0)


# ── apply_region_replacement integration tests ────────────────────────────────


def test_apply_region_replacement_replaces_only_polygon_area():
    """3 色圖中 polygon 對應到中間綠段 → 改成藍 → 最後應只剩紅+藍兩色（綠 0 像素）。

    test fixture 模擬真實 pbn_gen 輸出：polygon 在原始綠區（x=30~60）外擴 1 px → x=29~61。
    經過 _polygon_to_mask 的 erode 後 mask 縮回 x=30~60，剛好涵蓋整個綠區。
    """
    with tempfile.TemporaryDirectory() as tmp:
        img_path = os.path.join(tmp, "snap.png")
        svg = os.path.join(tmp, "t.svg")
        _write_three_color_image(img_path, 90, 90)
        # polygon 涵蓋綠段並外擴 1 px 模擬 pbn_gen 的 dilation
        _write_test_svg(svg, [
            ("r0", [(29, -1), (61, -1), (61, 91), (29, 91)]),
        ], 90, 90)

        result = apply_region_replacement(
            img_path, svg, os.path.join(tmp, "out"),
            polygon_ids=["r0"],
            tgt_rgb=(0, 0, 255),  # 改成藍（RGB）
            canvas_w_cm=30, canvas_h_cm=30,
            min_brush_diam_cm=0.5,
            min_ratio_multiplier=0.3,
        )

        # 綠色已 0 像素 → palette 自動縮減
        rgbs = {tuple(item["rgb"]) for item in result["palette_data"]}
        assert (0, 255, 0) not in rgbs  # 綠不見了


def test_apply_region_replacement_does_not_pollute_neighbors():
    """erode 1px 補償後：合併單一 polygon 不會吃到鄰格 1px 邊。

    3 色圖 R|G|B；polygon 模擬 pbn_gen 對綠區的 dilated 版本（x=29~61）。
    替換綠成藍後，紅區（x=0~30）應完全不變，不會出現第三色或鄰格被污染。
    """
    with tempfile.TemporaryDirectory() as tmp:
        img_path = os.path.join(tmp, "snap.png")
        svg = os.path.join(tmp, "t.svg")
        _write_three_color_image(img_path, 90, 90)
        _write_test_svg(svg, [
            ("r0", [(29, -1), (61, -1), (61, 91), (29, 91)]),
        ], 90, 90)

        result = apply_region_replacement(
            img_path, svg, os.path.join(tmp, "out"),
            polygon_ids=["r0"],
            tgt_rgb=(0, 0, 255),
            canvas_w_cm=30, canvas_h_cm=30,
            min_brush_diam_cm=0.5,
            min_ratio_multiplier=0.3,
        )
        # palette 應仍含紅與藍（紅完全沒被污染），無第三色
        rgbs = {tuple(item["rgb"]) for item in result["palette_data"]}
        assert (255, 0, 0) in rgbs, f"紅色不見了：{rgbs}"
        assert (0, 0, 255) in rgbs, f"藍色不見了：{rgbs}"


def test_apply_region_replacement_unknown_polygon_id_raises():
    with tempfile.TemporaryDirectory() as tmp:
        img_path = os.path.join(tmp, "snap.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(img_path, 80, 80)
        _write_test_svg(svg, [("r0", [(0, 0), (10, 0), (5, 5)])], 80, 80)
        with pytest.raises(ValueError, match="找不到 polygon"):
            apply_region_replacement(
                img_path, svg, os.path.join(tmp, "out"),
                polygon_ids=["r99"],
                tgt_rgb=(0, 0, 255),
                canvas_w_cm=30, canvas_h_cm=30,
                min_brush_diam_cm=0.5, min_ratio_multiplier=0.3,
            )


# ── _resolve_post_process_op tests（要 SVG + snapped 真實檔）─────────────────


def test_resolve_op_merge_color():
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        _write_test_svg(svg, [("r0", [(0, 0), (10, 0), (5, 5)])], 80, 80)

        palette = [
            {"template_id": 1, "rgb": [10, 20, 30]},
            {"template_id": 2, "rgb": [40, 50, 60]},
        ]
        ops = _resolve_post_process_op(
            {"polygon_id": "r5", "target_template_id": 2},
            palette, snapped, svg,
        )
        assert len(ops) == 1
        assert ops[0].polygon_ids == ["r5"]
        assert ops[0].tgt_rgb == (40, 50, 60)


def test_resolve_op_merge_color_unknown_target_template_id():
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        _write_test_svg(svg, [("r0", [(0, 0), (10, 0), (5, 5)])], 80, 80)
        palette = [{"template_id": 1, "rgb": [10, 20, 30]}]
        with pytest.raises(ValueError, match="找不到 target_template_id"):
            _resolve_post_process_op(
                {"polygon_id": "r5", "target_template_id": 99},
                palette, snapped, svg,
            )


def test_resolve_op_eliminate_border():
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        # surviving polygon r2 在右半（綠）
        _write_test_svg(svg, [
            ("r1", [(0, 10), (20, 10), (20, 30), (0, 30)]),  # 左半（紅）
            ("r2", [(50, 10), (70, 10), (70, 30), (50, 30)]),  # 右半（綠）
        ], 80, 80)

        ops = _resolve_post_process_op(
            {"absorbed_polygon_id": "r1", "surviving_polygon_id": "r2"},
            [],  # palette 不需要（B 操作從 SVG 採樣）
            snapped, svg,
        )
        assert len(ops) == 1
        assert ops[0].polygon_ids == ["r1"]
        assert ops[0].tgt_rgb == (0, 255, 0)  # 右半綠


def test_resolve_op_eliminate_border_same_id_raises():
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        _write_test_svg(svg, [("r1", [(0, 0), (10, 0), (5, 5)])], 80, 80)
        with pytest.raises(ValueError, match="不可相同"):
            _resolve_post_process_op(
                {"absorbed_polygon_id": "r1", "surviving_polygon_id": "r1"},
                [], snapped, svg,
            )


def test_resolve_op_batch_mixed():
    """Batch params {operations: [...]} 解出多個 ops。"""
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        _write_test_svg(svg, [
            ("r0", [(0, 10), (20, 10), (20, 30), (0, 30)]),
            ("r1", [(50, 10), (70, 10), (70, 30), (50, 30)]),
        ], 80, 80)
        palette = [
            {"template_id": 1, "rgb": [10, 20, 30]},
            {"template_id": 2, "rgb": [40, 50, 60]},
        ]
        ops = _resolve_post_process_op(
            {
                "operations": [
                    {
                        "op": "merge_color",
                        "polygon_id": "r0",
                        "target_template_id": 2,
                    },
                    {
                        "op": "eliminate_border",
                        "absorbed_polygon_id": "r0",
                        "surviving_polygon_id": "r1",
                    },
                ],
            },
            palette, snapped, svg,
        )
        assert len(ops) == 2
        # op1 merge_color: r0 → palette[2].rgb
        assert ops[0].polygon_ids == ["r0"]
        assert ops[0].tgt_rgb == (40, 50, 60)
        # op2 eliminate_border: r0 → r1 採樣（右半綠）
        assert ops[1].polygon_ids == ["r0"]
        assert ops[1].tgt_rgb == (0, 255, 0)


def test_resolve_op_batch_empty_raises():
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        _write_test_svg(svg, [("r0", [(0, 0), (10, 0), (5, 5)])], 80, 80)
        with pytest.raises(ValueError, match="operations 不能為空"):
            _resolve_post_process_op(
                {"operations": []},
                [], snapped, svg,
            )


def test_resolve_op_unknown_shape_raises():
    with tempfile.TemporaryDirectory() as tmp:
        snapped = os.path.join(tmp, "s.png")
        svg = os.path.join(tmp, "t.svg")
        _write_two_color_image(snapped, 80, 80)
        _write_test_svg(svg, [("r0", [(0, 0), (10, 0), (5, 5)])], 80, 80)
        with pytest.raises(ValueError, match="無法判斷後處理操作類型"):
            _resolve_post_process_op({"foo": "bar"}, [], snapped, svg)


def test_find_rgb_in_palette_hit():
    palette = [{"template_id": 1, "rgb": [10, 20, 30]}, {"template_id": 2, "rgb": [40, 50, 60]}]
    assert _find_rgb_in_palette(palette, 2) == (40, 50, 60)


def test_find_rgb_in_palette_miss():
    assert _find_rgb_in_palette([{"template_id": 1, "rgb": [10, 20, 30]}], 99) is None


# ── Task layer integration tests (mock 大部分) ────────────────────────────────


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


def _patch_post_process_engine(extra_patches: dict | None = None):
    """共用 patch context：跳過 SVG/snapped 下載、攔住 _resolve_post_process_op
    與 apply_region_replacement、上傳回假 url。
    """
    from contextlib import ExitStack
    stack = ExitStack()

    # 跳過 download — _download_image_to_path 只是寫檔
    stack.enter_context(patch("production.tasks._download_image_to_path"))
    # 跳過 op 解析（不用真讀 SVG/snapped）— 回 list（batch 路徑）
    fake_op = type("Op", (), {"polygon_ids": ["r0"], "tgt_rgb": (0, 255, 0)})()
    stack.enter_context(
        patch("production.tasks._resolve_post_process_op", return_value=[fake_op])
    )
    # 攔引擎本體（batch 版本）
    stack.enter_context(
        patch("production.tasks.apply_region_replacements", return_value=_FAKE_ENGINE_RESULT)
    )
    if extra_patches:
        for path, kwargs in extra_patches.items():
            stack.enter_context(patch(path, **kwargs))
    return stack


@pytest.mark.asyncio
async def test_run_post_process_merge_color_success(db):
    job = await _seed_completed_job(db)

    with _patch_post_process_engine() as _, \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template_new.svg",
            "gs://test-bucket/production_jobs/x/filled_new.png",
            "gs://test-bucket/production_jobs/x/snapped_new.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.completed
    assert refreshed.num_colors_used == 2
    assert len(refreshed.palette_json) == 2
    assert refreshed.svg_url.startswith("gs://")


@pytest.mark.asyncio
async def test_run_post_process_eliminate_border_success(db):
    job = await _seed_completed_job(db)

    with _patch_post_process_engine() as _, \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://test-bucket/production_jobs/x/template_b.svg",
            "gs://test-bucket/production_jobs/x/filled_b.png",
            "gs://test-bucket/production_jobs/x/snapped_b.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"absorbed_polygon_id": "r3", "surviving_polygon_id": "r1"},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.completed
    assert refreshed.num_colors_used == 2


@pytest.mark.asyncio
async def test_run_post_process_palette_mappings_remapped(db):
    """seed 3 mappings → 合併後紅色被砍 → 剩 green→1, blue→2 兩 mapping，紅 row 被刪。"""
    job = await _seed_completed_job(db)

    from color.models import PhysicalColor
    pc = PhysicalColor(
        code=f"TEST-{uuid.uuid4().hex[:6]}",
        name="test",
        rgb=[0, 0, 0],
        brand="A",
        is_active=True,
    )
    db.add(pc)
    await db.commit()
    await db.refresh(pc)

    for tid, rgb in [(1, [255, 0, 0]), (2, [0, 255, 0]), (3, [0, 0, 255])]:
        db.add(PaletteColorMapping(
            production_job_id=job.id,
            template_id=tid,
            algorithm_rgb=rgb,
            physical_color_id=pc.id,
            mapped_by=MappedByEnum.system,
        ))
    await db.commit()

    with _patch_post_process_engine() as _, \
         patch("production.tasks._upload_file") as mock_upload:
        mock_upload.side_effect = [
            "gs://x/svg.svg", "gs://x/filled.png", "gs://x/snapped.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
        )

    rows = (await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job.id
        )
    )).scalars().all()
    for r in rows:
        await db.refresh(r)

    rgbs_to_ids = {tuple(r.algorithm_rgb): r.template_id for r in rows}
    assert (0, 255, 0) in rgbs_to_ids and rgbs_to_ids[(0, 255, 0)] == 1
    assert (0, 0, 255) in rgbs_to_ids and rgbs_to_ids[(0, 0, 255)] == 2
    assert (255, 0, 0) not in rgbs_to_ids
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_run_post_process_bad_params_marks_failed(db):
    """SVG 解析失敗 / palette 找不到 target_template_id → status=failed、不上傳。"""
    job = await _seed_completed_job(db)

    with patch("production.tasks._download_image_to_path"), \
         patch(
             "production.tasks._resolve_post_process_op",
             side_effect=ValueError("找不到 polygon r999"),
         ), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks.apply_region_replacements") as mock_engine:
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r999", "target_template_id": 1},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "找不到 polygon" in (refreshed.notes or "")
    assert mock_upload.call_count == 0
    assert mock_engine.call_count == 0


@pytest.mark.asyncio
async def test_run_post_process_engine_error_marks_failed(db):
    job = await _seed_completed_job(db)

    fake_op = type("Op", (), {"polygon_ids": ["r0"], "tgt_rgb": (0, 255, 0)})()
    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks._resolve_post_process_op", return_value=[fake_op]), \
         patch(
             "production.tasks.apply_region_replacements",
             side_effect=RuntimeError("engine boom"),
         ), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
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
    job = await _seed_completed_job(db)

    fake_op = type("Op", (), {"polygon_ids": ["r0"], "tgt_rgb": (0, 255, 0)})()
    with patch("production.tasks._download_image_to_path"), \
         patch("production.tasks._resolve_post_process_op", return_value=[fake_op]), \
         patch(
             "production.tasks.apply_region_replacements",
             return_value=_FAKE_ENGINE_RESULT,
         ), \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete:
        mock_upload.side_effect = [
            "gs://x/template.svg",
            RuntimeError("firebase 503"),
        ]
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "firebase 503" in (refreshed.notes or "")
    assert mock_delete.call_count == 1


@pytest.mark.asyncio
async def test_run_post_process_deletes_old_blobs_on_success(db):
    job = await _seed_completed_job(db)

    with _patch_post_process_engine() as _, \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob_by_url") as mock_delete_old:
        mock_upload.side_effect = [
            "gs://x/svg.svg", "gs://x/filled.png", "gs://x/snapped.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
        )

    assert mock_delete_old.call_count == 3
    deleted_urls = {c.args[0] for c in mock_delete_old.call_args_list}
    assert "gs://test-bucket/production_jobs/x/template_old.svg" in deleted_urls
    assert "gs://test-bucket/production_jobs/x/filled_old.png" in deleted_urls
    assert "gs://test-bucket/production_jobs/x/snapped_old.png" in deleted_urls


def test_polygon_to_mask_erodes_dilation():
    """SVG polygon 是 dilated 1px 版（pbn_gen.py:1385）；mask 必須 erode 1px 抵銷，
    否則會吃到鄰格 1px 邊。"""
    # 5x5 polygon，erode 後內部還剩 3x3
    pts = [(2.0, 2.0), (7.0, 2.0), (7.0, 7.0), (2.0, 7.0)]
    mask = _polygon_to_mask(pts, 10, 10)
    # 中心應為 True
    assert mask[4, 4]
    # erode 後外圍 1px 應為 False（這就是抵銷 dilation 的結果）
    # raw fillPoly 會讓 (2,2)~(7,7) 含邊都是 True；erode 後只剩內部
    # 邊界 (2, 4) 應為 False（被 erode 掉）
    assert not mask[2, 4]


def test_get_polygon_rgb_samples_interior_not_dilated_edge():
    """三色圖 R|G|B（豎直分三段），polygon 蓋住中段 + 1px 溢出到 R/B：
    fillPoly raw mask 會包含 R/B 的邊界 1px；erode 後 mask 只剩 G 內部 → 採樣應為 G。"""
    with tempfile.TemporaryDirectory() as tmp:
        img = os.path.join(tmp, "snap.png")
        svg = os.path.join(tmp, "t.svg")
        # 90×90，左 30 紅、中 30 綠、右 30 藍（BGR）
        _write_three_color_image(img, 90, 90)
        # polygon 從 x=29 到 x=61（左右各溢出 G 範圍 1px 進 R 與 B）
        _write_test_svg(svg, [
            ("r0", [(29, 10), (61, 10), (61, 80), (29, 80)]),
        ], 90, 90)

        rgb = get_polygon_rgb(img, svg, "r0")
        # 必須是 G（綠），不是 R 或 B
        assert rgb == (0, 255, 0), f"採樣到鄰格色：{rgb}"


@pytest.mark.asyncio
async def test_run_post_process_remap_error_marks_failed_and_cleans_blobs(db):
    """_remap_palette_color_mappings 失敗 → 新 blob 必須被刪、status=failed，
    避免 job 永遠卡 processing + Firebase orphan。"""
    job = await _seed_completed_job(db)

    with _patch_post_process_engine() as _, \
         patch("production.tasks._upload_file") as mock_upload, \
         patch("production.tasks._delete_blob") as mock_delete, \
         patch(
             "production.tasks._remap_palette_color_mappings",
             side_effect=RuntimeError("remap boom"),
         ):
        mock_upload.side_effect = [
            "gs://x/svg.svg", "gs://x/filled.png", "gs://x/snapped.png",
        ]
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "remap boom" in (refreshed.notes or "")
    # 3 個新 blob 全部被刪（避免 orphan）
    assert mock_delete.call_count == 3


@pytest.mark.asyncio
async def test_run_post_process_no_snapped_or_svg_url(db):
    """job 缺 snapped_rgb_url 或 svg_url → status=failed。"""
    job = await _seed_completed_job(db)
    job.snapped_rgb_url = None
    await db.commit()

    with patch("production.tasks.apply_region_replacements") as mock_engine:
        await _run_post_process_async(
            str(job.id),
            {"polygon_id": "r5", "target_template_id": 2},
        )

    refreshed = (await db.execute(
        select(ProductionJob).where(ProductionJob.id == job.id)
    )).scalar_one()
    await db.refresh(refreshed)

    assert refreshed.status == JobStatusEnum.failed
    assert "snapped_rgb_url" in (refreshed.notes or "")
    assert mock_engine.call_count == 0
