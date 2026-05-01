"""Engine wrapper 單元測試 — 不經 DB / Celery，只驗 generate_standard 行為。"""
import os
import tempfile

import cv2
import numpy as np
import pytest

from production.engine import (
    DETAIL_PRESETS,
    DIFFICULTY_LEVELS,
    _calc_min_radius_px,
    generate_sam_refine,
    generate_sam_weighted,
    generate_standard,
    resolve_engine_params,
)


def _write_test_image(path: str, w: int = 80, h: int = 80) -> None:
    """寫一張有 6 色塊的 BGR 圖（夠 KMeans 分得出色）。"""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # 6 個色塊
    colors_bgr = [
        (255, 0, 0),    # blue
        (0, 255, 0),    # green
        (0, 0, 255),    # red
        (200, 200, 0),  # cyan
        (0, 200, 200),  # yellow
        (200, 0, 200),  # magenta
    ]
    cw = w // 3
    ch = h // 2
    for i, c in enumerate(colors_bgr):
        r = i // 3
        col = i % 3
        img[r * ch:(r + 1) * ch, col * cw:(col + 1) * cw] = c
    cv2.imwrite(path, img)


def test_calc_min_radius_px_basic():
    # 30cm 畫布 / 1500px 寬 / 1cm 筆觸 → 25px 半徑
    radius = _calc_min_radius_px(canvas_w_cm=30, img_w_px=1500, min_brush_diam_cm=1.0)
    assert radius == pytest.approx(25.0, rel=0.01)


def test_calc_min_radius_px_smaller_brush():
    # 30cm / 1500px / 0.4cm → 10px
    radius = _calc_min_radius_px(canvas_w_cm=30, img_w_px=1500, min_brush_diam_cm=0.4)
    assert radius == pytest.approx(10.0, rel=0.01)


def test_generate_standard_small_image_produces_files():
    """小圖 80×80 跑完 standard 流程，確認 4 個產出檔實際存在 + palette 結構。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        out = os.path.join(tmp, "out")
        _write_test_image(src, w=80, h=80)

        result = generate_standard(
            src,
            out,
            num_colors=6,
            pruning_threshold=8e-4,
            blur_ksize=7,
            blur_sigma_color=7,
            blur_sigma_space=5,
            prune_iterations=1,
            canvas_w_cm=30,
            canvas_h_cm=30,
            min_brush_diam_cm=0.5,
            min_ratio_multiplier=0.3,
        )

        # 檔案產出
        assert os.path.exists(result["svg_path"])
        assert os.path.exists(result["filled_path"])
        assert os.path.exists(result["snapped_rgb_path"])
        assert os.path.getsize(result["svg_path"]) > 0
        assert os.path.getsize(result["filled_path"]) > 0

        # palette 結構
        assert isinstance(result["palette_data"], list)
        assert result["num_colors_used"] == len(result["palette_data"])
        assert result["num_colors_used"] >= 1

        # 每筆 palette 的欄位（schema.md palette_json 規範）
        for item in result["palette_data"]:
            assert isinstance(item["template_id"], int)
            assert item["template_id"] >= 1
            assert len(item["rgb"]) == 3
            assert all(0 <= c <= 255 for c in item["rgb"])
            assert item["hex"].startswith("#")
            assert len(item["hex"]) == 7
            assert isinstance(item["pixels"], int)
            assert item["pixels"] >= 0
            assert 0 <= item["percent"] <= 100

        # 寬高
        assert result["image_width"] == 80
        assert result["image_height"] == 80


def test_generate_standard_invalid_image_raises():
    """壞圖路徑或非圖片內容 → ValueError。"""
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "not_image.jpg")
        with open(bad, "wb") as f:
            f.write(b"not actually an image")
        with pytest.raises(ValueError, match="無法讀取圖片"):
            generate_standard(
                bad, os.path.join(tmp, "out"),
                num_colors=6, pruning_threshold=8e-4,
                blur_ksize=7, blur_sigma_color=7, blur_sigma_space=5, prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
            )


def test_difficulty_levels_complete():
    """4 種 difficulty 都有 num_colors / pruning_threshold / refine_extra_colors。"""
    for diff in ("beginner", "elementary", "intermediate", "advanced"):
        preset = DIFFICULTY_LEVELS[diff]
        assert preset["num_colors"] > 0
        assert 0 < preset["pruning_threshold"] < 1
        assert preset["refine_extra_colors"] > 0


def test_detail_presets_complete():
    """4 種 detail 都有完整 5 個參數。"""
    for d in ("粗糙", "標準", "細緻", "高級"):
        preset = DETAIL_PRESETS[d]
        assert preset["blur_ksize"] > 0
        assert preset["blur_sigma_color"] > 0
        assert preset["blur_sigma_space"] > 0
        assert preset["prune_iterations"] > 0
        assert preset["min_ratio_multiplier"] > 0


class _FakeJob:
    """模擬 ProductionJob 物件給 resolve_engine_params 用（避免依賴 DB）。"""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_resolve_engine_params_uses_difficulty_default():
    """difficulty=beginner、其他欄位皆 None → 用 difficulty preset + 標準 detail。"""
    job = _FakeJob(
        difficulty="beginner",
        canvas_w_cm=30, canvas_h_cm=40,
        num_colors=None, blur_ksize=None, blur_sigma_color=None, blur_sigma_space=None,
        prune_iterations=None, pruning_threshold=None, min_ratio_multiplier=None,
        min_brush_diam_cm=None,
    )
    params = resolve_engine_params(job)
    assert params["num_colors"] == 18  # beginner
    assert params["pruning_threshold"] == pytest.approx(8e-4)
    assert params["blur_ksize"] == 21  # 標準 detail
    assert params["min_ratio_multiplier"] == pytest.approx(1.0)
    assert params["canvas_w_cm"] == 30.0
    assert params["min_brush_diam_cm"] == 1.0  # default fallback


def test_resolve_engine_params_overrides_take_priority():
    """job 上有覆蓋值時，優先使用覆蓋值。"""
    job = _FakeJob(
        difficulty="advanced",
        canvas_w_cm=40, canvas_h_cm=60,
        num_colors=42,
        blur_ksize=15,
        blur_sigma_color=10,
        blur_sigma_space=8,
        prune_iterations=5,
        pruning_threshold=1e-3,
        min_ratio_multiplier=0.8,
        min_brush_diam_cm=0.5,
    )
    params = resolve_engine_params(job)
    assert params["num_colors"] == 42  # overridden, not advanced default 50
    assert params["blur_ksize"] == 15
    assert params["pruning_threshold"] == pytest.approx(1e-3)
    assert params["min_brush_diam_cm"] == 0.5


def test_resolve_engine_params_unknown_difficulty_raises():
    job = _FakeJob(
        difficulty="ultra-hard",
        canvas_w_cm=30, canvas_h_cm=40, min_brush_diam_cm=1.0,
    )
    with pytest.raises(ValueError, match="未支援的難易度"):
        resolve_engine_params(job)


# ── SAM wrapper tests ────────────────────────────────────────────────────────

def _write_test_mask(path: str, w: int, h: int, fg_box: tuple[int, int, int, int]) -> None:
    """寫一張灰階 mask PNG，fg_box=(x0, y0, x1, y1) 區域填 255、其餘 0。"""
    mask = np.zeros((h, w), dtype=np.uint8)
    x0, y0, x1, y1 = fg_box
    mask[y0:y1, x0:x1] = 255
    cv2.imwrite(path, mask)


def test_generate_sam_refine_small_image_produces_files():
    """sam_refine 完整跑通：圖、mask 同尺寸，refine_region 增加色數。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        out = os.path.join(tmp, "out")
        _write_test_image(src, w=80, h=80)
        _write_test_mask(mask, 80, 80, fg_box=(20, 20, 60, 60))

        result = generate_sam_refine(
            src,
            out,
            mask_path=mask,
            num_colors=6,
            pruning_threshold=8e-4,
            blur_ksize=7,
            blur_sigma_color=7,
            blur_sigma_space=5,
            prune_iterations=1,
            canvas_w_cm=30,
            canvas_h_cm=30,
            min_brush_diam_cm=0.5,
            extra_colors=4,
            min_ratio_multiplier=0.3,
        )

        assert os.path.exists(result["svg_path"])
        assert os.path.exists(result["filled_path"])
        assert os.path.exists(result["snapped_rgb_path"])
        assert result["num_colors_used"] >= 1
        assert result["image_width"] == 80
        assert result["image_height"] == 80


def test_generate_sam_refine_invalid_extra_colors_raises():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        _write_test_image(src, w=80, h=80)
        _write_test_mask(mask, 80, 80, fg_box=(20, 20, 60, 60))
        with pytest.raises(ValueError, match="extra_colors"):
            generate_sam_refine(
                src, os.path.join(tmp, "out"),
                mask_path=mask,
                num_colors=6, pruning_threshold=8e-4,
                blur_ksize=7, blur_sigma_color=7, blur_sigma_space=5, prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
                extra_colors=0,
            )


def test_generate_sam_refine_empty_mask_raises():
    """mask 全 0 → 裁切後仍為空 → 拒絕（避免下游 refine_region 噴錯）。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        _write_test_image(src, w=80, h=80)
        # 全 0 mask
        cv2.imwrite(mask, np.zeros((80, 80), dtype=np.uint8))
        with pytest.raises(ValueError, match="mask 裁切後為空"):
            generate_sam_refine(
                src, os.path.join(tmp, "out"),
                mask_path=mask,
                num_colors=6, pruning_threshold=8e-4,
                blur_ksize=7, blur_sigma_color=7, blur_sigma_space=5, prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
                extra_colors=4,
            )


def test_generate_sam_refine_unreadable_mask_raises():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        bad_mask = os.path.join(tmp, "mask.png")
        _write_test_image(src, w=80, h=80)
        with open(bad_mask, "wb") as f:
            f.write(b"not actually a png")
        with pytest.raises(ValueError, match="無法讀取 mask"):
            generate_sam_refine(
                src, os.path.join(tmp, "out"),
                mask_path=bad_mask,
                num_colors=6, pruning_threshold=8e-4,
                blur_ksize=7, blur_sigma_color=7, blur_sigma_space=5, prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
                extra_colors=4,
            )


def test_generate_sam_refine_mask_resized_when_dimensions_differ():
    """mask 與圖片不同尺寸時，自動 INTER_NEAREST resize 到圖片尺寸。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        _write_test_image(src, w=80, h=80)
        # mask 故意較小：40x40，內部 fg_box
        _write_test_mask(mask, 40, 40, fg_box=(10, 10, 30, 30))
        # 不應拋例外（會 auto-resize）
        result = generate_sam_refine(
            src, os.path.join(tmp, "out"),
            mask_path=mask,
            num_colors=6, pruning_threshold=8e-4,
            blur_ksize=7, blur_sigma_color=7, blur_sigma_space=5, prune_iterations=1,
            canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
            extra_colors=4,
        )
        assert result["num_colors_used"] >= 1


def test_generate_sam_weighted_small_image_produces_files():
    """sam_weighted 完整跑通。"""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        out = os.path.join(tmp, "out")
        _write_test_image(src, w=80, h=80)
        _write_test_mask(mask, 80, 80, fg_box=(20, 20, 60, 60))

        result = generate_sam_weighted(
            src,
            out,
            mask_path=mask,
            num_colors=6,
            pruning_threshold=8e-4,
            prune_iterations=1,
            canvas_w_cm=30,
            canvas_h_cm=30,
            min_brush_diam_cm=0.5,
            weight_ratio=0.65,
            bg_extra_blur=0,
            min_ratio_multiplier=0.3,
        )

        assert os.path.exists(result["svg_path"])
        assert os.path.exists(result["filled_path"])
        assert os.path.exists(result["snapped_rgb_path"])
        assert result["num_colors_used"] >= 1


def test_generate_sam_weighted_invalid_weight_ratio_raises():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        _write_test_image(src, w=80, h=80)
        _write_test_mask(mask, 80, 80, fg_box=(20, 20, 60, 60))
        with pytest.raises(ValueError, match="weight_ratio"):
            generate_sam_weighted(
                src, os.path.join(tmp, "out"),
                mask_path=mask,
                num_colors=6, pruning_threshold=8e-4,
                prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
                weight_ratio=0.4,  # < 0.5
            )
        with pytest.raises(ValueError, match="weight_ratio"):
            generate_sam_weighted(
                src, os.path.join(tmp, "out"),
                mask_path=mask,
                num_colors=6, pruning_threshold=8e-4,
                prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
                weight_ratio=0.9,  # > 0.8
            )


def test_generate_sam_weighted_empty_mask_raises():
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src.jpg")
        mask = os.path.join(tmp, "mask.png")
        _write_test_image(src, w=80, h=80)
        cv2.imwrite(mask, np.zeros((80, 80), dtype=np.uint8))
        with pytest.raises(ValueError, match="mask 裁切後為空"):
            generate_sam_weighted(
                src, os.path.join(tmp, "out"),
                mask_path=mask,
                num_colors=6, pruning_threshold=8e-4,
                prune_iterations=1,
                canvas_w_cm=30, canvas_h_cm=30, min_brush_diam_cm=0.5,
                weight_ratio=0.65,
            )
