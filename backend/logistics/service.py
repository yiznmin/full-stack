"""ECpay 物流（CVS Map / 超商選店）service。

流程：
  1. 前端開新視窗 → GET /logistics/cvs-map?type=UNIMARTC2C → 我們回 auto-submit form HTML
  2. Form auto-submit POST 到 ECpay map page → 用戶選店
  3. ECpay 把選店結果 POST 回 ServerReplyURL（即 /logistics/cvs-callback）
  4. callback 驗 CheckMacValue → 回 HTML 用 postMessage 把資料丟給 opener window → close()

CheckMacValue 演算法（ECpay 物流 規範，採 MD5 — 非金流的 SHA256）：
  1. 參數依 key 字典序排序（A→Z）
  2. 串成 HashKey=xxx&Key1=Val1&...&HashIV=yyy
  3. URL encode（.NET style：空格 → +；保留不編碼 -_.!*()）
  4. 全部轉小寫
  5. MD5
  6. 轉大寫

來源：https://developers.ecpay.com.tw/7424/  及  https://developers.ecpay.com.tw/8795/
"""
import hashlib
import secrets
from datetime import datetime
from urllib.parse import quote_plus

from core.config import settings


# ── 環境 endpoint ─────────────────────────────────────────────────────────────

def _ecpay_base_url() -> str:
    if settings.ecpay_env == "production":
        return "https://logistics.ecpay.com.tw"
    return "https://logistics-stage.ecpay.com.tw"


# ── 支援的物流子類型 ──────────────────────────────────────────────────────────

# C2C (個人寄件，多數新商家先用這個)
LOGISTICS_SUB_TYPES = {
    "UNIMARTC2C": "7-Eleven 交貨便",
    "FAMIC2C": "全家 店到店",
    "HILIFEC2C": "萊爾富 來來貨運",
    "OKMARTC2C": "OK 超商",
}


def is_supported_sub_type(sub_type: str) -> bool:
    return sub_type in LOGISTICS_SUB_TYPES


# ── CheckMacValue ─────────────────────────────────────────────────────────────

def _ecpay_url_encode(s: str) -> str:
    """ECpay 的 .NET style URL encode：與 Python urllib.parse.quote_plus 大致一致，
    但需保留 '-', '_', '.', '!', '*', '(', ')' 不編碼，且最後轉小寫。"""
    # quote_plus 預設會編碼 -, _, ., 但實際上 RFC 不要求；ECpay 需保留它們
    encoded = quote_plus(s, safe="-_.!*()")
    return encoded.lower()


def calculate_check_mac_value(params: dict[str, str]) -> str:
    """產生 ECpay CheckMacValue (物流：MD5 大寫)."""
    # 1. 依 key 字典序升冪排序（ECpay key 都 PascalCase，case-insensitive 結果相同）
    sorted_keys = sorted(params.keys(), key=lambda k: k.lower())

    # 2. 串成 raw string
    pairs = [f"{k}={params[k]}" for k in sorted_keys]
    raw = (
        f"HashKey={settings.ecpay_hash_key}"
        + "&"
        + "&".join(pairs)
        + f"&HashIV={settings.ecpay_hash_iv}"
    )

    # 3. URL encode + lowercase
    encoded = _ecpay_url_encode(raw)

    # 4. MD5 + uppercase（物流 API 用 MD5，非金流的 SHA256）
    return hashlib.md5(encoded.encode("utf-8")).hexdigest().upper()


def verify_check_mac_value(params: dict[str, str]) -> bool:
    """驗證 ECpay 回傳的 CheckMacValue。"""
    received = params.get("CheckMacValue", "")
    if not received:
        return False
    rest = {k: v for k, v in params.items() if k != "CheckMacValue"}
    expected = calculate_check_mac_value(rest)
    return received.upper() == expected


# ── Map URL 產生 ──────────────────────────────────────────────────────────────

def _generate_merchant_trade_no() -> str:
    """產生 20 字元內、唯一的 MerchantTradeNo，僅用於 CVS Map 互動，不對應實際物流單。"""
    # 格式：CVS + yyyyMMddHHmmss + 4 hex random = 21 字元 → 砍掉前綴
    ts = datetime.now().strftime("%y%m%d%H%M%S")  # 12 字元
    rand = secrets.token_hex(3).upper()  # 6 字元
    return f"CVS{ts}{rand}"  # 3 + 12 + 6 = 21 → ECpay 限制 20，砍 1 個 random
    # 實際 21 字元時 ECpay 仍多半接受，但保險起見回到 20：


def generate_merchant_trade_no() -> str:
    """20 字元內 MerchantTradeNo（CVS Map 一次性用，無需保存）."""
    ts = datetime.now().strftime("%y%m%d%H%M%S")  # 12
    rand = secrets.token_hex(2).upper()            # 4
    return f"CVS{ts}{rand}"  # 19 字元，安全


def build_cvs_map_form(
    logistics_sub_type: str,
    server_reply_url: str,
    extra_data: str = "",
) -> dict[str, str]:
    """產出送到 ECpay /Express/map 的所有參數（含 CheckMacValue）."""
    if not is_supported_sub_type(logistics_sub_type):
        raise ValueError(f"Unsupported LogisticsSubType: {logistics_sub_type}")

    params = {
        "MerchantID": settings.ecpay_merchant_id,
        "MerchantTradeNo": generate_merchant_trade_no(),
        "LogisticsType": "CVS",
        "LogisticsSubType": logistics_sub_type,
        "IsCollection": "N",
        "ServerReplyURL": server_reply_url,
        "Device": "0",  # 0 = PC
    }
    if extra_data:
        params["ExtraData"] = extra_data

    params["CheckMacValue"] = calculate_check_mac_value(params)
    return params


def map_endpoint_url() -> str:
    return f"{_ecpay_base_url()}/Express/map"
