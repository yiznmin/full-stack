"""PBN 引擎 wrapper：把 production_job 的參數餵進 paint-by-number/src/pbn_gen.py。

不修改 paint-by-number/src/* 的核心程式碼（依 CLAUDE.md 強制）。
此 module 沿用 paint-by-number/src/run.py 的 run_single_level 順序（KMeans → set_final_pbn
→ merge_tiny_colors → output_to_svg → output_filled_from_template），但改成可呼叫的純函式介面。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 把 paint-by-number/src 加到 import path（CLAUDE.md 規範：不複製、只 import）
_PBN_SRC = Path(__file__).resolve().parents[2] / "paint-by-number" / "src"
if str(_PBN_SRC) not in sys.path:
    sys.path.insert(0, str(_PBN_SRC))


def _calc_min_radius_px(canvas_w_cm: float, img_w_px: int, min_brush_diam_cm: float) -> float:
    """畫布實體寬度 → 對應像素半徑（沿用 run.py:129 calc_min_radius_px）。"""
    pixel_size_cm = canvas_w_cm / img_w_px
    return (min_brush_diam_cm / 2) / pixel_size_cm


def generate_standard(
    image_path: str,
    output_dir: str,
    *,
    num_colors: int,
    pruning_threshold: float,
    blur_ksize: int,
    blur_sigma_color: float,
    blur_sigma_space: float,
    prune_iterations: int,
    canvas_w_cm: float,
    canvas_h_cm: float,
    min_brush_diam_cm: float,
    min_ratio_multiplier: float = 1.0,
) -> dict[str, Any]:
    """跑 standard 模式：KMeans → blur+prune → 合併小色塊 → 輸出 SVG / filled / palette。

    回傳 {svg_path, filled_path, snapped_rgb_path, palette_data, num_colors_used,
          image_width, image_height}.

    palette_data 為 list[dict]，每筆 {template_id, master_id, rgb, hex, pixels, percent}。
    """
    import cv2  # noqa: PLC0415  — 重型依賴只在實際呼叫時 import
    import numpy as np
    from pbn_gen import PbnGen  # noqa: PLC0415  — 動態加進來的引擎

    os.makedirs(output_dir, exist_ok=True)

    # 1. 讀圖（cv2.imread 不支援中文路徑 → 用 imdecode）
    img_bgr = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"無法讀取圖片：{image_path}")

    # 2. 裁切成符合畫布比例（沿用 run.py:89 crop_to_canvas_ratio）
    img_bgr = _crop_to_canvas_ratio(img_bgr, canvas_w_cm, canvas_h_cm)
    img_h, img_w = img_bgr.shape[:2]

    # 3. PbnGen 主流程：KMeans 分色 → 高斯雙邊模糊 + prune
    pbn = PbnGen(
        img_bgr,
        num_colors=num_colors,
        pruningThreshold=pruning_threshold,
        fixed_palette=None,  # standard 模式不固定色盤
    )
    pbn.set_final_pbn(
        blur_ksize=blur_ksize,
        blur_sigma_color=blur_sigma_color,
        blur_sigma_space=blur_sigma_space,
        prune_iterations=prune_iterations,
    )

    # 4. 小色塊合併：幾何門檻（最大內切圓半徑） × 難易度倍數
    min_radius_px = (
        _calc_min_radius_px(canvas_w_cm, img_w, min_brush_diam_cm) * min_ratio_multiplier
    )
    pbn.merge_tiny_colors(min_radius_px=min_radius_px, exclude_mask=None)

    # 5. 輸出 SVG + palette JSON（output_to_svg 內部會建 _snapped_rgb 屬性）
    svg_path = os.path.join(output_dir, "template.svg")
    palette_json_path = os.path.join(output_dir, "palette.json")
    palette_raw = pbn.output_to_svg(
        svg_path,
        palette_json_path,
        min_radius_px=min_radius_px,
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
    )

    # 6. 輸出 filled 預覽圖
    filled_path = os.path.join(output_dir, "filled_template.png")
    pbn.output_filled_from_template(filled_path)

    # 7. 額外存 snapped_rgb.png（後處理會沿用，避免重跑 KMeans）
    snapped_rgb_path = os.path.join(output_dir, "snapped_rgb.png")
    snapped = pbn._snapped_rgb  # output_to_svg 內部已產
    cv2.imwrite(snapped_rgb_path, cv2.cvtColor(snapped, cv2.COLOR_RGB2BGR))

    # 8. 整理 palette_data：補上 hex / pixels / percent（規格 schema.md palette_json 格式）
    palette_data = _build_palette_data(palette_raw, snapped, img_w, img_h)

    return {
        "svg_path": svg_path,
        "filled_path": filled_path,
        "snapped_rgb_path": snapped_rgb_path,
        "palette_data": palette_data,
        "num_colors_used": len(palette_data),
        "image_width": img_w,
        "image_height": img_h,
        "min_radius_px": round(min_radius_px, 3),
    }


def apply_color_replacement(
    snapped_rgb_path: str,
    output_dir: str,
    *,
    src_rgb: tuple[int, int, int],
    tgt_rgb: tuple[int, int, int],
    canvas_w_cm: float,
    canvas_h_cm: float,
    min_brush_diam_cm: float,
    min_ratio_multiplier: float = 1.0,
) -> dict[str, Any]:
    """post-process A/B 共用：把 src_rgb 像素全 replace 成 tgt_rgb，重跑 SVG/filled。

    沿用 admin_production.md §1.6：
    - A 格子合併 / B 消除邊界 都是 pixel replacement
    - 改後重跑 PbnGen.output_to_svg + output_filled_from_template
    - **重要**：output_to_svg 會依面積大小重編號 template_id，回傳的 palette_data 是新編號

    本路徑**不**呼叫 KMeans（cluster_colors）— output_to_svg 直接從 self.image 用
    `getUniqueColorsMasks()` 推 unique colors。所以 PbnGen 的 num_colors 參數對輸出
    無影響（且若 < min_num_colors=10 會被 constructor 加 +10，更不可信）。傳一個
    任意非 None 值跳過 knee 偵測即可。

    回傳 {svg_path, filled_path, snapped_rgb_path, palette_data, num_colors_used,
          image_width, image_height, min_radius_px}
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from pbn_gen import PbnGen  # noqa: PLC0415

    os.makedirs(output_dir, exist_ok=True)

    # 1. 讀 snapped_rgb.png（之前我們存時是 BGR 格式，這裡讀回 BGR 後轉 RGB）
    img_bgr = cv2.imdecode(np.fromfile(snapped_rgb_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"無法讀取 snapped_rgb 圖片：{snapped_rgb_path}")

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_h, img_w = img_rgb.shape[:2]

    # 2. pixel replacement：mask = src_rgb 的所有像素 → tgt_rgb
    src_arr = np.array(src_rgb, dtype=np.uint8)
    tgt_arr = np.array(tgt_rgb, dtype=np.uint8)
    mask = np.all(img_rgb == src_arr, axis=2)
    img_rgb[mask] = tgt_arr

    # 3. 構造 PbnGen，餵改完的圖（BGR 格式，constructor 內部會轉 RGB）
    # num_colors 必須非 None 才能 skip knee detection；具體值不影響 output_to_svg。
    img_bgr_modified = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    pbn = PbnGen(
        img_bgr_modified,
        num_colors=1,  # placeholder — output_to_svg 從 self.image 推 unique colors
        pruningThreshold=1e-4,
        fixed_palette=None,
    )

    # 4. 算 min_radius_px（與 generate_standard 一致）
    min_radius_px = (
        _calc_min_radius_px(canvas_w_cm, img_w, min_brush_diam_cm) * min_ratio_multiplier
    )

    # 5. 跑 output_to_svg → 新 SVG（會重編號 template_id）
    svg_path = os.path.join(output_dir, "template.svg")
    palette_json_path = os.path.join(output_dir, "palette.json")
    palette_raw = pbn.output_to_svg(
        svg_path,
        palette_json_path,
        min_radius_px=min_radius_px,
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
    )

    # 6. 輸出新 filled
    filled_path = os.path.join(output_dir, "filled_template.png")
    pbn.output_filled_from_template(filled_path)

    # 7. 額外存新 snapped_rgb（output_to_svg 跑完內部 _smooth_quantized 後產生的版本）
    snapped_out_path = os.path.join(output_dir, "snapped_rgb.png")
    snapped = pbn._snapped_rgb
    cv2.imwrite(snapped_out_path, cv2.cvtColor(snapped, cv2.COLOR_RGB2BGR))

    # 8. 補 hex/pixels/percent
    palette_data = _build_palette_data(palette_raw, snapped, img_w, img_h)

    return {
        "svg_path": svg_path,
        "filled_path": filled_path,
        "snapped_rgb_path": snapped_out_path,
        "palette_data": palette_data,
        "num_colors_used": len(palette_data),
        "image_width": img_w,
        "image_height": img_h,
        "min_radius_px": round(min_radius_px, 3),
    }


def _crop_to_canvas_ratio(img_bgr, canvas_w_cm: float, canvas_h_cm: float):
    """中央裁切成符合畫布比例（沿用 run.py:89 crop_to_canvas_ratio，不含 mask 路徑）。"""
    ih, iw = img_bgr.shape[:2]
    target_ratio = canvas_w_cm / canvas_h_cm
    img_ratio = iw / ih
    if abs(img_ratio - target_ratio) < 0.01:
        return img_bgr
    if img_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        x0 = (iw - new_w) // 2
        return img_bgr[:, x0:x0 + new_w]
    new_h = int(iw / target_ratio)
    y0 = (ih - new_h) // 2
    return img_bgr[y0:y0 + new_h, :]


def _build_palette_data(palette_raw, snapped_rgb, img_w: int, img_h: int) -> list[dict]:
    """把 output_to_svg 回傳的 palette_map 補上 hex / pixels / percent。

    schema.md 規定 palette_json 格式：
      [{template_id, master_id, rgb, hex, pixels, percent, shapes?}]
    """
    import numpy as np  # noqa: PLC0415

    total_px = img_w * img_h
    pixels_flat = snapped_rgb.reshape(-1, 3)

    enriched = []
    for item in palette_raw:
        rgb = item["rgb"]
        match = np.all(pixels_flat == list(rgb), axis=1)
        pixels = int(match.sum())
        enriched.append({
            "template_id": item["template_id"],
            "master_id": item.get("master_id", "N/A"),
            "rgb": rgb,
            "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
            "pixels": pixels,
            "percent": round(pixels / total_px * 100, 2) if total_px > 0 else 0.0,
        })
    enriched.sort(key=lambda x: x["template_id"])
    return enriched


# ── Difficulty / detail presets（沿用 run.py 預設值，確保引擎一致）────────────────

DETAIL_PRESETS = {
    "粗糙": {
        "blur_ksize": 31, "blur_sigma_color": 51, "blur_sigma_space": 51,
        "prune_iterations": 10, "bg_extra_blur": 21, "min_ratio_multiplier": 2.0,
    },
    "標準": {
        "blur_ksize": 21, "blur_sigma_color": 21, "blur_sigma_space": 14,
        "prune_iterations": 6, "bg_extra_blur": 21, "min_ratio_multiplier": 1.0,
    },
    "細緻": {
        "blur_ksize": 13, "blur_sigma_color": 13, "blur_sigma_space": 9,
        "prune_iterations": 3, "bg_extra_blur": 9, "min_ratio_multiplier": 0.6,
    },
    "高級": {
        "blur_ksize": 7, "blur_sigma_color": 7, "blur_sigma_space": 5,
        "prune_iterations": 1, "bg_extra_blur": 0, "min_ratio_multiplier": 0.3,
    },
}

# difficulty 對應引擎內部色數與 pruning 門檻（與 run.py:213 DIFFICULTY_LEVELS 一致）
DIFFICULTY_LEVELS = {
    "beginner":     {"num_colors": 18, "pruning_threshold": 8e-4,    "refine_extra_colors": 8},
    "elementary":   {"num_colors": 24, "pruning_threshold": 2e-4,    "refine_extra_colors": 12},
    "intermediate": {"num_colors": 35, "pruning_threshold": 6.25e-5, "refine_extra_colors": 18},
    "advanced":     {"num_colors": 50, "pruning_threshold": 1.5e-5,  "refine_extra_colors": 25},
}


def resolve_engine_params(job: Any) -> dict[str, Any]:
    """從 ProductionJob 物件解出引擎參數。

    優先使用 job 上的覆蓋值（admin 可能在建任務時調整）；缺失時用 difficulty + detail="標準" 預設。
    """
    difficulty = str(job.difficulty)
    if difficulty not in DIFFICULTY_LEVELS:
        raise ValueError(f"未支援的難易度：{difficulty}")
    diff_preset = DIFFICULTY_LEVELS[difficulty]
    detail_preset = DETAIL_PRESETS["標準"]  # admin 後台目前只暴露 difficulty，detail 用標準

    def _pick(field: str, default: Any) -> Any:
        v = getattr(job, field, None)
        return v if v is not None else default

    return {
        "num_colors": _pick("num_colors", diff_preset["num_colors"]),
        "pruning_threshold": float(_pick("pruning_threshold", diff_preset["pruning_threshold"])),
        "blur_ksize": _pick("blur_ksize", detail_preset["blur_ksize"]),
        "blur_sigma_color": float(_pick("blur_sigma_color", detail_preset["blur_sigma_color"])),
        "blur_sigma_space": float(_pick("blur_sigma_space", detail_preset["blur_sigma_space"])),
        "prune_iterations": _pick("prune_iterations", detail_preset["prune_iterations"]),
        "canvas_w_cm": float(job.canvas_w_cm),
        "canvas_h_cm": float(job.canvas_h_cm),
        "min_brush_diam_cm": float(_pick("min_brush_diam_cm", 1.0)),
        "min_ratio_multiplier": float(
            _pick("min_ratio_multiplier", detail_preset["min_ratio_multiplier"]),
        ),
    }


__all__ = [
    "DETAIL_PRESETS",
    "DIFFICULTY_LEVELS",
    "apply_color_replacement",
    "generate_standard",
    "resolve_engine_params",
]


def _smoke_test():
    """快速本機驗證：用 paint-by-number/images/Mom.jpg 跑入門難度 standard。"""
    sample = _PBN_SRC.parent / "images" / "Mom.jpg"
    if not sample.exists():
        print(f"sample not found: {sample}")
        return
    out = Path(__file__).resolve().parent.parent / "_engine_smoke_out"
    result = generate_standard(
        str(sample),
        str(out),
        num_colors=18,
        pruning_threshold=8e-4,
        blur_ksize=21,
        blur_sigma_color=21,
        blur_sigma_space=14,
        prune_iterations=6,
        canvas_w_cm=30,
        canvas_h_cm=40,
        min_brush_diam_cm=1.0,
        min_ratio_multiplier=1.0,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "palette_data"}, indent=2))
    print(f"palette: {len(result['palette_data'])} colors")


if __name__ == "__main__":
    _smoke_test()
