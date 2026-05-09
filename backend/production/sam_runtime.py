"""SAM (Segment Anything) 推論 runtime — 與 FastAPI 同進程懶載入單例。

依規格 [admin_production.md §1.3]：
- 服務啟動時不載入模型；第一次呼叫才載入並常駐記憶體
- 第一次冷啟動 ~5-10 秒；後續推論 1-3 秒
- 使用 vit_b checkpoint（375MB）；模型路徑由 settings.sam_model_path 提供

設計：
- `get_sam_predictor()` 模組級單例（threading.Lock 保護初始化）
- `predict_mask(predictor, image_bgr, sam_points)` 同步推論；
  caller 用 asyncio.to_thread 包裹避免 block event loop
"""
from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import numpy as np

# 模組級單例 + 初始化 lock（thread-safe lazy load）
_PREDICTOR: Any = None
_LOAD_LOCK = threading.Lock()

# image embedding cache：set_image() 是 SAM 推論中最慢的部分（CPU vit_b 10-30s），
# 但 predict() 在 cache 存在時只需 < 0.5s。同一張圖被連續點選時不該重做 set_image。
# 用 image_key（caller 傳入，通常是 image_url 或 image_id）識別目前已 cache 的圖。
# 對應問題：用戶從 paint-by-number/src/sam_select.py 經驗中認知「點一下立刻看到 mask」
# — 因為本機版只跑一次 set_image。Web 版要呈現同樣即時感必須跳過 redundant set_image。
_LAST_IMAGE_KEY: str | None = None
_PREDICT_LOCK = threading.Lock()  # 序列化 set_image / predict（SamPredictor 非 thread-safe）


def is_image_cached(image_key: str) -> bool:
    """判斷此 image_key 是否已 set_image 過（caller 可省略下載 + 解碼）。"""
    return image_key is not None and image_key == _LAST_IMAGE_KEY


def get_sam_predictor() -> Any:
    """懶載入 SAM predictor 單例。

    第一次呼叫：
      1. 取 settings.sam_model_path（缺失 → ValueError）
      2. 確認檔案存在（不在 → FileNotFoundError）
      3. 載入 sam_model_registry["vit_b"](checkpoint=...) + to("cpu")
      4. 包成 SamPredictor 並快取於模組級變數

    後續呼叫：直接返回快取。

    raise:
      ValueError — settings.sam_model_path 未設定
      FileNotFoundError — 模型檔不存在
      ImportError — segment_anything 未安裝
    """
    global _PREDICTOR

    if _PREDICTOR is not None:
        return _PREDICTOR

    with _LOAD_LOCK:
        # double-check：可能其他 thread 已載入完成
        if _PREDICTOR is not None:
            return _PREDICTOR

        from core.config import settings  # noqa: PLC0415

        model_path = settings.sam_model_path
        if not model_path:
            raise ValueError(
                "settings.sam_model_path 未設定（環境變數 SAM_MODEL_PATH）"
            )
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"SAM 模型檔不存在：{model_path}")

        try:
            import torch  # noqa: PLC0415
            from segment_anything import (  # noqa: PLC0415
                SamPredictor,
                sam_model_registry,
            )
        except ImportError as e:
            raise ImportError(
                "segment-anything 未安裝（pip install segment-anything）"
            ) from e

        logger.info("Loading SAM vit_b model from %s ...", model_path)
        # segment_anything 1.0 build_sam.py 內部用 `torch.load(file_object)`
        # 在 torch 2.5 + Windows 上會 segfault（無論 weights_only=True/False）。
        # 唯一穩定路徑是 `torch.load(path_string, weights_only=True)`。
        # 因此繞開 segment_anything 的 checkpoint 載入：先建空模型、再自己 load state_dict。
        # weights_only=True 同時防 pickle 反序列化 RCE（部署到 Linux 後仍保留此防護）。
        sam = sam_model_registry["vit_b"](checkpoint=None)
        state_dict = torch.load(model_path, weights_only=True, map_location="cpu")
        sam.load_state_dict(state_dict)
        # 顯式 eval mode（避免依賴 segment_anything 內部 _build_sam 順序的隱含契約）
        sam.eval()
        sam.to("cpu")
        _PREDICTOR = SamPredictor(sam)
        logger.info("SAM predictor ready")

    return _PREDICTOR


def predict_mask(
    predictor: Any,
    image_bgr: "np.ndarray | None",
    sam_points: list[dict],
    *,
    image_key: str | None = None,
) -> np.ndarray:
    """同步呼叫 SAM 推論 → 回傳 bool 遮罩（True = 選取區）。

    sam_points 格式：[{x: float, y: float, label: int (1=foreground/0=background)}]

    image_key 用來判斷是否要重做 set_image（SAM 推論瓶頸）：
    - 提供且與上次相同 → 跳過 set_image，predict 直接用 cached embedding（< 0.5s）
    - 為 None 或與上次不同 → 重新 set_image（10-30s）+ predict
    - caller 應傳穩定的字串（image_url / image_id），同 admin session 連點 SAM
      只在第一次慢，後續即時。

    image_bgr 可為 None — 但僅當 image_key 與既有快取一致時（caller 已用
    is_image_cached(key) 確認過、可省去下載+解碼）。否則 cache miss 必須提供。

    raise:
      ValueError — sam_points 為空（caller 應先驗證）
                 — cache miss 但 image_bgr=None（資料不足無法 set_image）
    """
    global _LAST_IMAGE_KEY
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    if not sam_points:
        raise ValueError("sam_points 不能為空")

    points = np.array([[float(p["x"]), float(p["y"])] for p in sam_points], dtype=np.float32)
    labels = np.array([int(p["label"]) for p in sam_points], dtype=np.int32)

    # SamPredictor 內部 state（features tensor 等）非 thread-safe；序列化 set_image+predict
    with _PREDICT_LOCK:
        if image_key is None or image_key != _LAST_IMAGE_KEY:
            # 沒 key 或 key 不同 → 重新 embedding
            if image_bgr is None:
                raise ValueError(
                    "cache miss（image_key 不一致）但未提供 image_bgr，無法 set_image"
                )
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            predictor.set_image(image_rgb)
            _LAST_IMAGE_KEY = image_key
            logger.info("SAM set_image done for key=%s", image_key)
        # else: predictor 已快取此圖 embedding，直接 predict（不讀 image_bgr）

        masks, scores, _ = predictor.predict(
            point_coords=points,
            point_labels=labels,
            multimask_output=True,
        )
    # 多 mask 取分數最高那一張（mirror paint-by-number/src/sam_select.py:predict_mask_sam）
    return masks[int(np.argmax(scores))]


def reset_predictor_for_test() -> None:
    """測試專用：清掉單例 + image cache（讓下個測試重新走載入路徑）。"""
    global _PREDICTOR, _LAST_IMAGE_KEY
    _PREDICTOR = None
    _LAST_IMAGE_KEY = None
