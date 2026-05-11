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

# 把 paint-by-number/src 加到 import path（CLAUDE.md 規範：不複製、只 import）。
# 嘗試多個路徑，容錯本地 dev 與 Docker 部署的 layout 差異：
#   - 本地：<repo>/backend/production/engine.py → ../.. = <repo>，<repo>/paint-by-number/src
#   - Docker：/app/production/engine.py（backend 平鋪到 /app）+ /app/paint-by-number/src
_HERE = Path(__file__).resolve()
_PBN_CANDIDATES = [
    _HERE.parents[2] / "paint-by-number" / "src",  # 本地 dev: backend/production → repo root
    _HERE.parents[1] / "paint-by-number" / "src",  # Docker: /app/production → /app
    Path("/app/paint-by-number/src"),               # Docker absolute fallback
]
for _candidate in _PBN_CANDIDATES:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))
        break


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
    use_saliency: bool = True,
    saliency_radius_px: int = 15,
    saliency_weight_alpha: float = 3.0,
    saliency_threshold_pct: float = 80.0,
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
        use_saliency=use_saliency,
        saliency_radius_px=saliency_radius_px,
        saliency_weight_alpha=saliency_weight_alpha,
        saliency_threshold_pct=saliency_threshold_pct,
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


def _load_mask_grayscale(mask_path: str, target_size: tuple[int, int]):
    """讀 mask PNG → 灰階 + resize 至圖片尺寸（INTER_NEAREST 保留 0/255 二值）。

    target_size 為 (width, height)，與 cv2.resize 慣例一致。

    若 mask 與圖片尺寸不符會 INTER_NEAREST resize 並 log warning（admin 編 mask
    時前端應已對準圖片尺寸；尺寸不符表示資料異常或前後端尺寸假設不一致）。
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    mask = cv2.imdecode(np.fromfile(mask_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError(f"無法讀取 mask：{mask_path}")
    target_w, target_h = target_size
    if (mask.shape[1], mask.shape[0]) != (target_w, target_h):
        logger.warning(
            "mask 尺寸不符圖片，自動 INTER_NEAREST resize："
            "mask=%dx%d, image=%dx%d",
            mask.shape[1], mask.shape[0], target_w, target_h,
        )
        mask = cv2.resize(mask, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
    return mask


def generate_sam_refine(
    image_path: str,
    output_dir: str,
    *,
    mask_path: str,
    num_colors: int,
    pruning_threshold: float,
    blur_ksize: int,
    blur_sigma_color: float,
    blur_sigma_space: float,
    prune_iterations: int,
    canvas_w_cm: float,
    canvas_h_cm: float,
    min_brush_diam_cm: float,
    extra_colors: int,
    min_ratio_multiplier: float = 1.0,
    use_saliency: bool = True,
    saliency_radius_px: int = 15,
    saliency_weight_alpha: float = 3.0,
    saliency_threshold_pct: float = 80.0,
) -> dict[str, Any]:
    """sam_refine 模式：set_final_pbn 後對遮罩區域加做細化 K-Means。

    與 generate_standard 差異：
      1. 圖片裁切時 mask 同步裁切（同偏移）
      2. set_final_pbn 之後呼叫 pbn.refine_region(mask, extra_colors)
      3. merge_tiny_colors 帶 exclude_mask=mask（避免細化區小色塊被合併）

    回傳格式與 generate_standard 完全相同。
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from pbn_gen import PbnGen  # noqa: PLC0415

    if extra_colors <= 0:
        raise ValueError(f"sam_refine 需 extra_colors > 0（收到 {extra_colors}）")

    os.makedirs(output_dir, exist_ok=True)

    img_bgr = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"無法讀取圖片：{image_path}")

    mask_full = _load_mask_grayscale(mask_path, (img_bgr.shape[1], img_bgr.shape[0]))
    img_bgr, mask_cropped = _crop_to_canvas_ratio_with_mask(
        img_bgr, mask_full, canvas_w_cm, canvas_h_cm,
    )
    img_h, img_w = img_bgr.shape[:2]

    if not (mask_cropped > 127).any():
        raise ValueError("mask 裁切後為空（遮罩全部落在裁切外）")

    pbn = PbnGen(
        img_bgr,
        num_colors=num_colors,
        pruningThreshold=pruning_threshold,
        fixed_palette=None,
    )
    pbn.set_final_pbn(
        blur_ksize=blur_ksize,
        blur_sigma_color=blur_sigma_color,
        blur_sigma_space=blur_sigma_space,
        prune_iterations=prune_iterations,
        use_saliency=use_saliency,
        saliency_radius_px=saliency_radius_px,
        saliency_weight_alpha=saliency_weight_alpha,
        saliency_threshold_pct=saliency_threshold_pct,
    )
    pbn.refine_region(mask_cropped, extra_colors=extra_colors)

    min_radius_px = (
        _calc_min_radius_px(canvas_w_cm, img_w, min_brush_diam_cm) * min_ratio_multiplier
    )
    pbn.merge_tiny_colors(min_radius_px=min_radius_px, exclude_mask=mask_cropped)

    svg_path = os.path.join(output_dir, "template.svg")
    palette_json_path = os.path.join(output_dir, "palette.json")
    palette_raw = pbn.output_to_svg(
        svg_path,
        palette_json_path,
        min_radius_px=min_radius_px,
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
    )

    filled_path = os.path.join(output_dir, "filled_template.png")
    pbn.output_filled_from_template(filled_path)

    snapped_rgb_path = os.path.join(output_dir, "snapped_rgb.png")
    snapped = pbn._snapped_rgb
    cv2.imwrite(snapped_rgb_path, cv2.cvtColor(snapped, cv2.COLOR_RGB2BGR))

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


def generate_sam_weighted(
    image_path: str,
    output_dir: str,
    *,
    mask_path: str,
    num_colors: int,
    pruning_threshold: float,
    prune_iterations: int,
    canvas_w_cm: float,
    canvas_h_cm: float,
    min_brush_diam_cm: float,
    weight_ratio: float = 0.65,
    bg_extra_blur: int = 0,
    min_ratio_multiplier: float = 1.0,
) -> dict[str, Any]:
    """sam_weighted 模式：色數預算按 weight_ratio 拆分到選取區 / 非選取區。

    與 generate_standard 差異：
      1. 不走 set_final_pbn（會把整圖重新量化、覆蓋 weighted 結果）
      2. 改走 pbn.apply_weighted_region 直接量化兩區
      3. 加 pruneClustersSimple + 黑色邊框（mirror run.py:run_single_level）

    blur_ksize / blur_sigma_* 在此模式無作用，故簽名不收。
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from pbn_gen import PbnGen  # noqa: PLC0415

    if not (0.5 <= weight_ratio <= 0.8):
        raise ValueError(f"weight_ratio 必須在 0.5~0.8（收到 {weight_ratio}）")

    os.makedirs(output_dir, exist_ok=True)

    img_bgr = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"無法讀取圖片：{image_path}")

    mask_full = _load_mask_grayscale(mask_path, (img_bgr.shape[1], img_bgr.shape[0]))
    img_bgr, mask_cropped = _crop_to_canvas_ratio_with_mask(
        img_bgr, mask_full, canvas_w_cm, canvas_h_cm,
    )
    img_h, img_w = img_bgr.shape[:2]

    if not (mask_cropped > 127).any():
        raise ValueError("mask 裁切後為空（遮罩全部落在裁切外）")

    pbn = PbnGen(
        img_bgr,
        num_colors=num_colors,
        pruningThreshold=pruning_threshold,
        fixed_palette=None,
    )
    pbn.apply_weighted_region(
        mask=mask_cropped,
        total_colors=num_colors,
        weight_ratio=weight_ratio,
        bg_extra_blur=bg_extra_blur,
    )
    pbn.pruneClustersSimple(iterations=prune_iterations)

    # 黑色邊框（mirror run.py:run_single_level）
    img = pbn.getImage()
    img = cv2.rectangle(img, (0, 0), (img.shape[1], img.shape[0]), (0, 0, 0), 10)
    pbn.setImage(img)

    min_radius_px = (
        _calc_min_radius_px(canvas_w_cm, img_w, min_brush_diam_cm) * min_ratio_multiplier
    )
    pbn.merge_tiny_colors(min_radius_px=min_radius_px, exclude_mask=None)

    svg_path = os.path.join(output_dir, "template.svg")
    palette_json_path = os.path.join(output_dir, "palette.json")
    palette_raw = pbn.output_to_svg(
        svg_path,
        palette_json_path,
        min_radius_px=min_radius_px,
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
    )

    filled_path = os.path.join(output_dir, "filled_template.png")
    pbn.output_filled_from_template(filled_path)

    snapped_rgb_path = os.path.join(output_dir, "snapped_rgb.png")
    snapped = pbn._snapped_rgb
    cv2.imwrite(snapped_rgb_path, cv2.cvtColor(snapped, cv2.COLOR_RGB2BGR))

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


def _extract_polygon_points(svg_path: str, polygon_id: str) -> list[tuple[float, float]]:
    """從 template.svg 解出指定 polygon 的頂點座標列表。

    SVG 中 polygon 由 pbn_gen.py:1443 加上 id="rN"，points 屬性格式為 "x,y x,y ..."。
    """
    import xml.etree.ElementTree as ET  # noqa: PLC0415  # nosec B405

    # SVG 由我們自己引擎產出（trusted source），無 XXE 風險
    tree = ET.parse(svg_path)  # noqa: S314  # nosec B314
    root = tree.getroot()
    ns = {"svg": "http://www.w3.org/2000/svg"}
    for poly in root.iter("{http://www.w3.org/2000/svg}polygon"):
        if poly.get("id") == polygon_id:
            pts_str = poly.get("points", "")
            pts: list[tuple[float, float]] = []
            for tok in pts_str.split():
                if "," in tok:
                    x, y = tok.split(",", 1)
                    pts.append((float(x), float(y)))
            if len(pts) < 3:
                raise ValueError(f"polygon {polygon_id} 頂點數 {len(pts)} < 3")
            return pts
    _ = ns
    raise ValueError(f"找不到 polygon id={polygon_id}（SVG 內無此 region）")


def _polygon_to_mask(points: list[tuple[float, float]], img_w: int, img_h: int):
    """把 polygon 頂點 list 畫成布林 mask（True = polygon 內部像素）。

    **erode 1px 補償 dilation**：pbn_gen.py:1385 在輸出 SVG 前對每個 region 做 dilate 1 px
    讓相鄰 polygon 重疊以消除縫隙；如果直接 fillPoly 還原會吃到鄰格 1 px。erode 1 px
    把 dilated 邊界縮回原始色塊範圍，避免：
    - 合併操作污染鄰格 1 px 邊（出現第三色縫）
    - get_polygon_rgb 採樣到鄰格色
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    raw = np.zeros((img_h, img_w), dtype=np.uint8)
    pts_array = np.array([[round(x), round(y)] for x, y in points], dtype=np.int32)
    cv2.fillPoly(raw, [pts_array], 255)
    # erode 1 px 抵銷 SVG polygon 的 dilation
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    eroded = cv2.erode(raw, kernel, iterations=1)
    return eroded > 0


def get_polygon_rgb(snapped_rgb_path: str, svg_path: str, polygon_id: str) -> tuple[int, int, int]:
    """取得指定 polygon 在 snapped_rgb 中的實際 RGB（用於 eliminate-border 找 surviving 色）。

    sample mask 內第一個 True 像素的 RGB；若 mask 空（不該發生）→ ValueError。
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    img_bgr = cv2.imdecode(np.fromfile(snapped_rgb_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"無法讀取 snapped_rgb：{snapped_rgb_path}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_h, img_w = img_rgb.shape[:2]

    points = _extract_polygon_points(svg_path, polygon_id)
    mask = _polygon_to_mask(points, img_w, img_h)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        raise ValueError(f"polygon {polygon_id} 對應 mask 為空（SVG 解析或畫布尺寸問題）")
    pixel = img_rgb[ys[0], xs[0]]
    return (int(pixel[0]), int(pixel[1]), int(pixel[2]))


def apply_region_replacements(
    snapped_rgb_path: str,
    svg_path: str,
    output_dir: str,
    *,
    ops: list[dict],
    canvas_w_cm: float,
    canvas_h_cm: float,
    min_brush_diam_cm: float,
    min_ratio_multiplier: float = 1.0,
) -> dict[str, Any]:
    """批次區域 replace：按順序套用 ops（每筆 {polygon_ids, tgt_rgb}）→ 一次重跑 SVG/filled。

    每個 op 都用**原始** SVG 的 polygon mask（不會因前面 op 改色而連動），按順序在
    snapped_rgb buffer 上覆蓋。最後 output_to_svg 會自動依新像素分布重編號並縮減 palette。

    ops 例：
      [
        {"polygon_ids": ["r5"], "tgt_rgb": (0, 255, 0)},      # A 合併
        {"polygon_ids": ["r12"], "tgt_rgb": (40, 50, 60)},     # B 消邊界（surviving 取自的 RGB）
      ]
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415
    from pbn_gen import PbnGen  # noqa: PLC0415

    if not ops:
        raise ValueError("ops 不能為空")

    os.makedirs(output_dir, exist_ok=True)

    # 1. 讀 snapped_rgb 為單一 buffer（所有 op 都改它）
    img_bgr = cv2.imdecode(np.fromfile(snapped_rgb_path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"無法讀取 snapped_rgb：{snapped_rgb_path}")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_h, img_w = img_rgb.shape[:2]

    # 2. 按順序套用每個 op
    for idx, op in enumerate(ops):
        polygon_ids = op["polygon_ids"]
        tgt_rgb = op["tgt_rgb"]
        union_mask = np.zeros((img_h, img_w), dtype=bool)
        for pid in polygon_ids:
            pts = _extract_polygon_points(svg_path, pid)
            union_mask = union_mask | _polygon_to_mask(pts, img_w, img_h)
        if not union_mask.any():
            raise ValueError(
                f"op #{idx} polygon mask 為空（polygon_ids={polygon_ids}）"
            )
        img_rgb[union_mask] = np.array(tgt_rgb, dtype=np.uint8)

    # 3. 構造 PbnGen，餵改完的圖
    img_bgr_modified = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    pbn = PbnGen(
        img_bgr_modified,
        num_colors=1,
        pruningThreshold=1e-4,
        fixed_palette=None,
    )

    min_radius_px = (
        _calc_min_radius_px(canvas_w_cm, img_w, min_brush_diam_cm) * min_ratio_multiplier
    )

    new_svg_path = os.path.join(output_dir, "template.svg")
    palette_json_path = os.path.join(output_dir, "palette.json")
    palette_raw = pbn.output_to_svg(
        new_svg_path,
        palette_json_path,
        min_radius_px=min_radius_px,
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
    )

    filled_path = os.path.join(output_dir, "filled_template.png")
    pbn.output_filled_from_template(filled_path)

    snapped_out_path = os.path.join(output_dir, "snapped_rgb.png")
    snapped = pbn._snapped_rgb
    cv2.imwrite(snapped_out_path, cv2.cvtColor(snapped, cv2.COLOR_RGB2BGR))

    palette_data = _build_palette_data(palette_raw, snapped, img_w, img_h)

    return {
        "svg_path": new_svg_path,
        "filled_path": filled_path,
        "snapped_rgb_path": snapped_out_path,
        "palette_data": palette_data,
        "num_colors_used": len(palette_data),
        "image_width": img_w,
        "image_height": img_h,
        "min_radius_px": round(min_radius_px, 3),
    }


def apply_region_replacement(
    snapped_rgb_path: str,
    svg_path: str,
    output_dir: str,
    *,
    polygon_ids: list[str],
    tgt_rgb: tuple[int, int, int],
    canvas_w_cm: float,
    canvas_h_cm: float,
    min_brush_diam_cm: float,
    min_ratio_multiplier: float = 1.0,
) -> dict[str, Any]:
    """單一 op 包裝層；內部走 apply_region_replacements 共用實作。"""
    return apply_region_replacements(
        snapped_rgb_path, svg_path, output_dir,
        ops=[{"polygon_ids": polygon_ids, "tgt_rgb": tgt_rgb}],
        canvas_w_cm=canvas_w_cm,
        canvas_h_cm=canvas_h_cm,
        min_brush_diam_cm=min_brush_diam_cm,
        min_ratio_multiplier=min_ratio_multiplier,
    )


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


def _crop_to_canvas_ratio_with_mask(img_bgr, mask, canvas_w_cm: float, canvas_h_cm: float):
    """中央裁切圖片＋mask 同時用同樣偏移（mirror run.py:89 crop_to_canvas_ratio）。

    mask 必須與 img_bgr 同尺寸（H×W），灰階 uint8。回傳 (cropped_bgr, cropped_mask)。
    """
    ih, iw = img_bgr.shape[:2]
    mh, mw = mask.shape[:2]
    if (ih, iw) != (mh, mw):
        raise ValueError(
            f"mask 尺寸與圖片不符（image={iw}x{ih}, mask={mw}x{mh}）"
        )
    target_ratio = canvas_w_cm / canvas_h_cm
    img_ratio = iw / ih
    if abs(img_ratio - target_ratio) < 0.01:
        return img_bgr, mask
    if img_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        x0 = (iw - new_w) // 2
        return img_bgr[:, x0:x0 + new_w], mask[:, x0:x0 + new_w]
    new_h = int(iw / target_ratio)
    y0 = (ih - new_h) // 2
    return img_bgr[y0:y0 + new_h, :], mask[y0:y0 + new_h, :]


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
    "apply_region_replacement",
    "apply_region_replacements",
    "generate_sam_refine",
    "generate_sam_weighted",
    "generate_standard",
    "get_polygon_rgb",
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
