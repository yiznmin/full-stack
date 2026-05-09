"""sam_runtime — 懶載入 + 單例 + predict_mask 行為測試（mock segment_anything）。

測試環境不真載 SAM 模型（vit_b 375MB）；只驗封裝層邏輯。
真實 inference 走 Phase B.5 本地 smoke test。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def _reset_predictor():
    """每個 test 前後清掉 sam_runtime 的單例，避免 test 互相污染。"""
    from production import sam_runtime
    sam_runtime.reset_predictor_for_test()
    yield
    sam_runtime.reset_predictor_for_test()


def test_get_sam_predictor_missing_model_path():
    """settings.sam_model_path=None → ValueError。"""
    from production import sam_runtime
    with patch("core.config.settings.sam_model_path", None):
        with pytest.raises(ValueError, match="sam_model_path"):
            sam_runtime.get_sam_predictor()


def test_get_sam_predictor_missing_model_file(tmp_path):
    """模型路徑指向不存在檔 → FileNotFoundError。"""
    from production import sam_runtime
    fake_path = str(tmp_path / "no_such_model.pth")
    with patch("core.config.settings.sam_model_path", fake_path):
        with pytest.raises(FileNotFoundError, match="不存在"):
            sam_runtime.get_sam_predictor()


def test_get_sam_predictor_loads_once(tmp_path):
    """快取命中後不重複建構：兩次呼叫 _PREDICTOR 早 return，registry 只 call 一次。

    註：本測試只驗「快取命中」路徑（line 41-42 early return）；不驗 threading.Lock
    double-check 的 race-free 行為（單 process 環境難測；理想需多 thread concurrent
    模擬，但 sam_runtime 僅在初始化呼叫 lock，之後 early return 跟 lock 無關）。
    """
    from production import sam_runtime

    fake_path = str(tmp_path / "fake_model.pth")
    open(fake_path, "wb").close()

    fake_sam = MagicMock()
    fake_predictor = MagicMock(name="SamPredictor instance")
    fake_registry = {"vit_b": MagicMock(return_value=fake_sam)}

    with patch("core.config.settings.sam_model_path", fake_path), \
         patch("torch.load", return_value={"fake_state": "dict"}), \
         patch.dict(
             "sys.modules",
             {"segment_anything": MagicMock(
                 sam_model_registry=fake_registry,
                 SamPredictor=MagicMock(return_value=fake_predictor),
             )},
         ):
        # 第一次呼叫：走完整載入路徑（取 lock + import + build + load_state_dict + eval）
        p1 = sam_runtime.get_sam_predictor()
        # 第二次呼叫：快取命中，line 41-42 early return（不取 lock）
        p2 = sam_runtime.get_sam_predictor()

    assert p1 is fake_predictor
    assert p2 is fake_predictor
    assert fake_registry["vit_b"].call_count == 1
    assert fake_sam.load_state_dict.call_count == 1
    # eval() 顯式呼叫驗證（M1 修法）
    assert fake_sam.eval.call_count == 1


def test_get_sam_predictor_reloads_after_reset(tmp_path):
    """reset_predictor_for_test 後重新呼叫應重新走載入路徑。

    補完 test_get_sam_predictor_loads_once 漏的「重新載入」路徑：
    驗證 lock-protected 區塊在 _PREDICTOR=None 時真的會重跑。
    """
    from production import sam_runtime

    fake_path = str(tmp_path / "fake_model.pth")
    open(fake_path, "wb").close()

    fake_sam = MagicMock()
    fake_predictor = MagicMock()
    fake_registry = {"vit_b": MagicMock(return_value=fake_sam)}

    with patch("core.config.settings.sam_model_path", fake_path), \
         patch("torch.load", return_value={"fake": "state"}), \
         patch.dict(
             "sys.modules",
             {"segment_anything": MagicMock(
                 sam_model_registry=fake_registry,
                 SamPredictor=MagicMock(return_value=fake_predictor),
             )},
         ):
        sam_runtime.get_sam_predictor()
        sam_runtime.reset_predictor_for_test()
        sam_runtime.get_sam_predictor()

    # 第 1 次 + reset + 第 2 次 → registry 被 call 2 次
    assert fake_registry["vit_b"].call_count == 2


def test_get_sam_predictor_missing_segment_anything(tmp_path):
    """segment_anything import 失敗 → ImportError。"""
    from production import sam_runtime

    fake_path = str(tmp_path / "fake_model.pth")
    open(fake_path, "wb").close()

    # 用 builtins.__import__ patch 模擬 import 失敗
    real_import = __import__

    def _fake_import(name, *args, **kwargs):
        if name == "segment_anything":
            raise ImportError("segment_anything not available")
        return real_import(name, *args, **kwargs)

    with patch("core.config.settings.sam_model_path", fake_path), \
         patch("builtins.__import__", side_effect=_fake_import):
        with pytest.raises(ImportError, match="segment-anything"):
            sam_runtime.get_sam_predictor()


def test_predict_mask_calls_predictor_correctly():
    """predict_mask：cv2 BGR→RGB、predictor.predict 拿到正確 points/labels、回最高分 mask。"""
    from production import sam_runtime

    image_bgr = np.zeros((50, 50, 3), dtype=np.uint8)

    # 假 predictor：回三張 mask + 三個 score；應取分數最高那張
    mask0 = np.zeros((50, 50), dtype=bool)
    mask1 = np.ones((50, 50), dtype=bool)
    mask2 = np.zeros((50, 50), dtype=bool)
    fake_masks = np.array([mask0, mask1, mask2])
    fake_scores = np.array([0.3, 0.9, 0.5])

    fake_predictor = MagicMock()
    fake_predictor.predict.return_value = (fake_masks, fake_scores, None)

    sam_points = [
        {"x": 10.0, "y": 20.0, "label": 1},
        {"x": 30.0, "y": 40.0, "label": 0},
    ]
    result = sam_runtime.predict_mask(fake_predictor, image_bgr, sam_points)

    # set_image 被呼叫（RGB image）
    assert fake_predictor.set_image.call_count == 1
    # predict 被呼叫並傳對 points / labels
    pred_kwargs = fake_predictor.predict.call_args.kwargs
    np.testing.assert_array_equal(
        pred_kwargs["point_coords"],
        np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32),
    )
    np.testing.assert_array_equal(
        pred_kwargs["point_labels"], np.array([1, 0], dtype=np.int32),
    )
    assert pred_kwargs["multimask_output"] is True
    # 回傳的是 mask1（score 最高 0.9）
    np.testing.assert_array_equal(result, mask1)


def test_predict_mask_empty_points_raises():
    """sam_points 為空 → ValueError。"""
    from production import sam_runtime

    image_bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    fake_predictor = MagicMock()
    with pytest.raises(ValueError, match="sam_points"):
        sam_runtime.predict_mask(fake_predictor, image_bgr, [])


def test_predict_mask_skips_set_image_when_key_matches():
    """同 image_key 連續呼叫 → set_image 只執行一次（cache 命中），predict 每次跑。"""
    from production import sam_runtime

    image_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    fake_masks = np.array([np.ones((20, 20), dtype=bool)])
    fake_scores = np.array([0.9])
    fake_predictor = MagicMock()
    fake_predictor.predict.return_value = (fake_masks, fake_scores, None)

    points = [{"x": 1.0, "y": 1.0, "label": 1}]
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-A")
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-A")
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-A")

    # set_image 只跑一次（後兩次命中 cache）
    assert fake_predictor.set_image.call_count == 1
    # predict 三次都要跑（每次點選都要重算 mask）
    assert fake_predictor.predict.call_count == 3


def test_predict_mask_resets_cache_when_key_changes():
    """切到不同 image_key → 必須重做 set_image（不同圖 embedding 不同）。"""
    from production import sam_runtime

    image_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    fake_masks = np.array([np.ones((20, 20), dtype=bool)])
    fake_scores = np.array([0.9])
    fake_predictor = MagicMock()
    fake_predictor.predict.return_value = (fake_masks, fake_scores, None)

    points = [{"x": 1.0, "y": 1.0, "label": 1}]
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-A")
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-B")
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-A")

    # 三次 image_key 變化（A → B → A）每次都要重算 embedding
    assert fake_predictor.set_image.call_count == 3


def test_predict_mask_cache_hit_accepts_none_image():
    """同 image_key 已 cache → image_bgr=None 時也能正常 predict（不需要原圖）。"""
    from production import sam_runtime

    image_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    fake_masks = np.array([np.ones((20, 20), dtype=bool)])
    fake_scores = np.array([0.9])
    fake_predictor = MagicMock()
    fake_predictor.predict.return_value = (fake_masks, fake_scores, None)

    points = [{"x": 1.0, "y": 1.0, "label": 1}]
    # 第一次：提供 image_bgr，set_image
    sam_runtime.predict_mask(fake_predictor, image_bgr, points, image_key="img-X")
    # 第二次：image_bgr=None — cache 命中所以不需要
    sam_runtime.predict_mask(fake_predictor, None, points, image_key="img-X")

    assert fake_predictor.set_image.call_count == 1
    assert fake_predictor.predict.call_count == 2


def test_predict_mask_cache_miss_with_none_image_raises():
    """cache miss 但 image_bgr=None → ValueError（無法 set_image）。"""
    from production import sam_runtime

    fake_predictor = MagicMock()
    points = [{"x": 1.0, "y": 1.0, "label": 1}]
    with pytest.raises(ValueError, match="image_bgr"):
        sam_runtime.predict_mask(fake_predictor, None, points, image_key="img-Y")


def test_is_image_cached_reflects_state():
    """is_image_cached 對應 set_image 後的狀態。"""
    from production import sam_runtime

    assert sam_runtime.is_image_cached("img-A") is False  # 初始空

    image_bgr = np.zeros((10, 10, 3), dtype=np.uint8)
    fake_masks = np.array([np.ones((10, 10), dtype=bool)])
    fake_predictor = MagicMock()
    fake_predictor.predict.return_value = (fake_masks, np.array([0.9]), None)
    sam_runtime.predict_mask(fake_predictor, image_bgr, [{"x": 1, "y": 1, "label": 1}], image_key="img-A")

    assert sam_runtime.is_image_cached("img-A") is True
    assert sam_runtime.is_image_cached("img-B") is False
    assert sam_runtime.is_image_cached(None) is False  # type: ignore[arg-type]


def test_predict_mask_no_key_always_set_image():
    """image_key=None（預設）→ 每次都重做 set_image（保守 fallback）。"""
    from production import sam_runtime

    image_bgr = np.zeros((20, 20, 3), dtype=np.uint8)
    fake_masks = np.array([np.ones((20, 20), dtype=bool)])
    fake_scores = np.array([0.9])
    fake_predictor = MagicMock()
    fake_predictor.predict.return_value = (fake_masks, fake_scores, None)

    points = [{"x": 1.0, "y": 1.0, "label": 1}]
    sam_runtime.predict_mask(fake_predictor, image_bgr, points)
    sam_runtime.predict_mask(fake_predictor, image_bgr, points)

    # 沒 key → 每次都 set_image
    assert fake_predictor.set_image.call_count == 2
