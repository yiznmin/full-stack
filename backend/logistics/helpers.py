"""ECpay 建單 helpers — name padding / sanitize / zipcode 推導。

來源規格：docs/integration_specs/ecpay_create_shipment.md §7
"""
import json
import re
from pathlib import Path

# ── 台灣郵遞區號資料 ────────────────────────────────────────────────────────
# 來源：twzipcode-data 套件，跟 store 前端用同一份。
# 載入時機：模組第一次被 import 時讀檔（lazy）。

_ZIPCODE_DATA: dict[str, dict[str, str]] | None = None


def _load_zipcode_data() -> dict[str, dict[str, str]]:
    global _ZIPCODE_DATA
    if _ZIPCODE_DATA is None:
        path = Path(__file__).parent / "taiwan_zipcode.json"
        with open(path, encoding="utf-8") as f:
            _ZIPCODE_DATA = json.load(f)
    return _ZIPCODE_DATA


def _normalize_county(county: str) -> str:
    """套件用「臺」，但用戶輸入習慣可能是「台」 — 雙向相容。"""
    if not county:
        return ""
    data = _load_zipcode_data()
    if county in data:
        return county
    # 台 → 臺
    t = county.replace("台", "臺", 1)
    if t in data:
        return t
    # 臺 → 台
    n = county.replace("臺", "台", 1)
    if n in data:
        return n
    return county


def derive_zipcode(city: str | None, district: str | None) -> str | None:
    """從 city + district 查 3 碼郵遞區號。找不到回 None。

    用於 ECpay /7414/ 宅配建單的 ReceiverZipCode 必填欄位。
    """
    if not city or not district:
        return None
    data = _load_zipcode_data()
    normalized_city = _normalize_county(city)
    return data.get(normalized_city, {}).get(district)


# ── 寄／收件人姓名 padding ──────────────────────────────────────────────────
# ECpay 規範：4-10 字元、禁數字/特殊符號/emoji
# 多數台灣本名 2-3 字 → 自動加後綴湊到 4 字以上

_NAME_FORBIDDEN_CHARS = re.compile(r"[\d\W_]+", re.UNICODE)


def _strip_forbidden_name_chars(name: str) -> str:
    """移除數字、特殊符號（保留中英字母）。"""
    # \W 在 re.UNICODE 模式下會排除 letters/digits/_，反向想留 letters → 自己手動
    # 用較精準的：只保留 unicode letter
    return "".join(c for c in name if c.isalpha())


def pad_name_to_ecpay_limit(name: str) -> str:
    """把姓名 pad / truncate 到 ECpay 規範的 4-10 字元。

    Rules:
    - 先 strip 數字/特殊符號（保留 letters）
    - len ≥ 4: 截到 10 字（>10 截斷）
    - len = 3: 後加「客戶」(5 字)
    - len = 2: 後加「客戶您好」(6 字)
    - len ≤ 1: ValueError
    """
    if not name:
        raise ValueError("姓名不可空白")
    cleaned = _strip_forbidden_name_chars(name.strip())
    if not cleaned:
        raise ValueError("姓名移除特殊符號後為空")
    n = len(cleaned)
    if n >= 10:
        return cleaned[:10]
    if n >= 4:
        return cleaned
    if n == 3:
        return cleaned + "客戶"
    if n == 2:
        return cleaned + "客戶您好"
    # n == 1
    raise ValueError("姓名至少需 2 字元")


# ── 商品名 sanitize ────────────────────────────────────────────────────────
# ECpay 禁用：^'`!@#%&*+"<>|_[]
# 我們再加幾個 ECpay 沒禁但 form data 容易出問題的：=, &, /

_GOODSNAME_FORBIDDEN_CHARS = re.compile(r"[\^'`!@#%&*+\"<>|_\[\]\\=\/]+")


def sanitize_goods_name(raw: str, max_len: int = 50) -> str:
    """清掉 ECpay 禁用的特殊符號，截到 max_len。多空白合併成單一空格。"""
    if not raw:
        return ""
    cleaned = _GOODSNAME_FORBIDDEN_CHARS.sub(" ", raw)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_len]


def concat_goods_names(titles: list[str], max_len: int = 50) -> str:
    """多個商品標題串成一個 GoodsName。

    用「、」串接，總長 > 50 時截斷並加「…等」。
    """
    if not titles:
        return ""
    sanitized = [sanitize_goods_name(t, max_len=20) for t in titles if t]
    sanitized = [s for s in sanitized if s]
    if not sanitized:
        return ""
    full = "、".join(sanitized)
    if len(full) <= max_len:
        return full
    # 截斷加「…等」
    return full[: max_len - 2] + "…等"
