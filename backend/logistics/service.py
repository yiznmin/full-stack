"""ECpay 物流 service — CVS Map (Day 1) + 訂單建立 (Day 2)。

CheckMacValue 演算法（ECpay 物流 規範，採 MD5）：
  1. 參數依 key 字典序排序（A→Z）
  2. 串成 HashKey=xxx&Key1=Val1&...&HashIV=yyy
  3. URL encode（.NET style：空格 → +；保留不編碼 -_.!*()）
  4. 全部轉小寫
  5. MD5
  6. 轉大寫

文件：
  /7424/ CheckMacValue 規則
  /8795/ CVS Map 電子地圖
  /8809/ 門市訂單建立（CVS）
  /7414/ 物流訂單建立Ⅱ（HOME 黑貓 + 中華郵政）

規格檔：
  docs/integration_specs/ecpay_cvs_map.md
  docs/integration_specs/ecpay_create_shipment.md
"""
import hashlib
import logging
import secrets
from datetime import datetime
from urllib.parse import quote_plus

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from logistics import helpers

logger = logging.getLogger(__name__)


# ── 環境 endpoint ─────────────────────────────────────────────────────────────

def _ecpay_base_url() -> str:
    if settings.ecpay_env == "production":
        return "https://logistics.ecpay.com.tw"
    return "https://logistics-stage.ecpay.com.tw"


# ── 支援的物流子類型 ──────────────────────────────────────────────────────────

# 支援的 LogisticsSubType（B2C + C2C 全列）
# 帳號實際開了哪幾項要看 ECpay 後台「物流選單」
LOGISTICS_SUB_TYPES = {
    # B2C（大宗寄倉，月結合約）
    "UNIMART": "7-Eleven 大宗寄倉",
    "UNIMARTFREEZE": "7-Eleven 冷凍店取",
    "FAMI": "全家 大宗寄倉",
    "HILIFE": "萊爾富 大宗寄倉",
    # C2C（店到店，個人寄件）
    "UNIMARTC2C": "7-Eleven 交貨便",
    "FAMIC2C": "全家 店到店",
    "HILIFEC2C": "萊爾富 來來貨運",
    "OKMARTC2C": "OK 超商",
}


def is_supported_sub_type(sub_type: str) -> bool:
    return sub_type in LOGISTICS_SUB_TYPES


# ── 欄位長度限制（ECpay /8795/ 規範）─────────────────────────────────────────
# 來源：docs/integration_specs/ecpay_cvs_map.md §11

MAX_MERCHANT_ID_LEN = 10
MAX_MERCHANT_TRADE_NO_LEN = 20
MAX_SERVER_REPLY_URL_LEN = 200
MAX_EXTRA_DATA_LEN = 20

# Response 欄位長度上限（驗 ECpay 回傳資料完整性用）
MAX_CVS_STORE_ID_LEN = 9
MAX_CVS_STORE_NAME_LEN = 10
MAX_CVS_ADDRESS_LEN = 60
MAX_CVS_TELEPHONE_LEN = 20


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

def generate_merchant_trade_no() -> str:
    """產生 ECpay 規範內、唯一的 MerchantTradeNo（最多 20 字元、英數）。

    格式：CVS + yyMMddHHmmss(12) + 4 hex = 19 字元，安全在 20 字元限制內。
    CVS Map 一次性用、不對應實際物流訂單，無需保存。
    """
    ts = datetime.now().strftime("%y%m%d%H%M%S")  # 12
    rand = secrets.token_hex(2).upper()            # 4
    no = f"CVS{ts}{rand}"  # 19 字元
    assert len(no) <= MAX_MERCHANT_TRADE_NO_LEN, "MerchantTradeNo length out of spec"
    return no


def build_cvs_map_form(
    logistics_sub_type: str,
    server_reply_url: str,
    extra_data: str = "",
) -> dict[str, str]:
    """產出送到 ECpay /Express/map 的所有參數（含 CheckMacValue）。

    驗證規則（依 docs/integration_specs/ecpay_cvs_map.md §3）：
    - LogisticsSubType 必須在 LOGISTICS_SUB_TYPES 列表內
    - MerchantID 必須有設定且 ≤ 10 字元
    - ServerReplyURL 必須以 https 開頭、≤ 200 字元
    - ExtraData ≤ 20 字元
    違反任何一條 raise ValueError，由 caller 轉成 HTTP 400 回傳。
    """
    if not is_supported_sub_type(logistics_sub_type):
        raise ValueError(f"不支援的物流類型：{logistics_sub_type}")

    if not settings.ecpay_merchant_id:
        raise ValueError("ECPAY_MERCHANT_ID 未設定")
    if len(settings.ecpay_merchant_id) > MAX_MERCHANT_ID_LEN:
        raise ValueError(f"ECPAY_MERCHANT_ID 過長（規範 ≤ {MAX_MERCHANT_ID_LEN}）")

    if not server_reply_url:
        raise ValueError("ServerReplyURL 不可空白")
    if not server_reply_url.startswith("https://"):
        raise ValueError("ServerReplyURL 必須以 https:// 開頭（ECpay 要求）")
    if len(server_reply_url) > MAX_SERVER_REPLY_URL_LEN:
        raise ValueError(f"ServerReplyURL 超過 {MAX_SERVER_REPLY_URL_LEN} 字元限制")

    if extra_data and len(extra_data) > MAX_EXTRA_DATA_LEN:
        raise ValueError(f"ExtraData 超過 {MAX_EXTRA_DATA_LEN} 字元限制")

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


def truncate_response_field(value: str, max_len: int) -> str:
    """ECpay 回傳欄位若超過規範長度（少數狀況），截斷並 log。
    不直接 raise — response 已收到，截斷比拒絕資料完整性更友善。"""
    if value and len(value) > max_len:
        return value[:max_len]
    return value


# ── 物流狀態代碼映射（Day 3 webhook）────────────────────────────────────────
# 來源：docs/integration_specs/ecpay_status_tracking.md §2.5
# 「客戶取貨 / 已送達」是我們系統決定 Shipment.status='delivered' 的關鍵狀態。

# 確定的「已送達 / 已取貨」狀態碼
DELIVERED_RTN_CODES: set[int] = {
    2067,   # 7-Eleven B2C/C2C 消費者成功取件
    3022,   # 全家 / 萊爾富 / OK C2C 消費者成功取件
    3003,   # 黑貓宅配 已送達（部分 HOME 狀態與物流中心代碼共用）
}

# 7 天未取件代碼（包裹要退回賣家）
EXPIRED_PICKUP_RTN_CODES: set[int] = {
    2074, 3020,
}

# RtnMsg 含這些關鍵字 → 視為已送達。
# 注意：不可包含「已送達」(too broad — 「商品已送達門市」是待取階段、非 delivered)
DELIVERED_MSG_KEYWORDS = (
    "成功取件",      # 超商：消費者成功取件
    "客戶取件",
    "已取件",
    "妥投",          # 黑貓：順利妥投 = 收件人已收
    "已配達",        # 黑貓：配達收件人
    "已送達收件人",   # HOME 明確區分「送達門市」vs「送達收件人」
    "已送達客戶",
    "成功投遞",
)


def is_delivered_status(rtn_code: int, rtn_msg: str) -> bool:
    """判斷 ECpay 狀態是否代表「已送達 / 客戶取貨」.

    區分「商品送達門市」(待取階段) vs「客戶取走 / 妥投」(真正完成)。
    """
    if rtn_code in DELIVERED_RTN_CODES:
        return True
    if rtn_msg:
        for kw in DELIVERED_MSG_KEYWORDS:
            if kw in rtn_msg:
                return True
    return False


def is_expired_pickup_status(rtn_code: int) -> bool:
    """7 天未取件需 admin 處理（包裹會退回）."""
    return rtn_code in EXPIRED_PICKUP_RTN_CODES


# ── 查詢物流訂單 (/7418/) ──────────────────────────────────────────────────

def query_endpoint_url() -> str:
    return f"{_ecpay_base_url()}/Helper/QueryLogisticsTradeInfo/V5"


# ── 列印託運單 endpoints (Day 4) ─────────────────────────────────────────────
# 依物流類型不同 endpoint：
#   HOME (TCAT/POST) + B2C 通用：/helper/printTradeDocument
#   CVS C2C 各家獨立 endpoint，且需要 CVSPaymentNo + CVSValidationNo
# 文件來源：
#   /8875/ HOME B2C 列印
#   /7406/ 7-Eleven C2C 列印
#   /8848/ 全家 C2C 列印（同模式不同 path）

PRINT_ENDPOINTS = {
    # HOME（黑貓 / 中華郵政）+ B2C 通用
    "_home_b2c": "/helper/printTradeDocument",
    # CVS C2C 列印 endpoint（單筆 + 需驗證碼）
    "UNIMARTC2C": "/Express/PrintUniMartC2COrderInfo",
    "FAMIC2C": "/Express/PrintFAMIC2COrderInfo",
    "HILIFEC2C": "/Express/PrintHILIFEC2COrderInfo",
    "OKMARTC2C": "/Express/PrintOKMARTC2COrderInfo",
}


def print_endpoint_url(logistics_type: str, logistics_sub_type: str) -> str:
    """依物流類型回對應的列印 endpoint."""
    base = _ecpay_base_url()
    # CVS C2C 各家獨立 endpoint
    if logistics_sub_type in PRINT_ENDPOINTS:
        return f"{base}{PRINT_ENDPOINTS[logistics_sub_type]}"
    # HOME 或其他 → 共用 B2C endpoint
    return f"{base}{PRINT_ENDPOINTS['_home_b2c']}"


def build_print_label_form(
    *,
    logistics_type: str,
    logistics_sub_type: str,
    all_pay_logistics_id: str,
    cvs_payment_no: str | None = None,
    cvs_validation_no: str | None = None,
    print_mode: int = 1,  # 1=A4, 2=A6 熱感應
) -> dict[str, str]:
    """組列印託運單需要的 form 參數（含 CheckMacValue）.

    HOME / B2C 只需 MerchantID + AllPayLogisticsID + CheckMacValue
    CVS C2C 還需 CVSPaymentNo + CVSValidationNo（看各家規範略有差異）
    """
    if not settings.ecpay_merchant_id:
        raise ValueError("ECPAY_MERCHANT_ID 未設定")
    if not all_pay_logistics_id:
        raise ValueError("AllPayLogisticsID 必填")

    params: dict[str, str] = {
        "MerchantID": settings.ecpay_merchant_id,
        "AllPayLogisticsID": all_pay_logistics_id,
    }

    is_cvs_c2c = logistics_sub_type in (
        "UNIMARTC2C", "FAMIC2C", "HILIFEC2C", "OKMARTC2C",
    )
    if is_cvs_c2c:
        if not cvs_payment_no or not cvs_validation_no:
            raise ValueError("CVS C2C 列印必須提供 CVSPaymentNo 與 CVSValidationNo")
        params["CVSPaymentNo"] = cvs_payment_no
        params["CVSValidationNo"] = cvs_validation_no
    else:
        # HOME / B2C：可選擇 PrintMode
        params["PrintMode"] = str(print_mode)

    params["CheckMacValue"] = calculate_check_mac_value(params)
    return params


def build_query_form(
    *,
    all_pay_logistics_id: str | None = None,
    merchant_trade_no: str | None = None,
) -> dict[str, str]:
    """組查詢物流訂單的 request 參數。AllPayLogisticsID 與 MerchantTradeNo 二擇一."""
    if not all_pay_logistics_id and not merchant_trade_no:
        raise ValueError("AllPayLogisticsID / MerchantTradeNo 至少需提供一個")

    import time
    params: dict[str, str] = {
        "MerchantID": settings.ecpay_merchant_id,
        "TimeStamp": str(int(time.time())),
    }
    if all_pay_logistics_id:
        params["AllPayLogisticsID"] = all_pay_logistics_id
    if merchant_trade_no:
        params["MerchantTradeNo"] = merchant_trade_no

    params["CheckMacValue"] = calculate_check_mac_value(params)
    return params


async def query_logistics_trade(
    *,
    all_pay_logistics_id: str | None = None,
    merchant_trade_no: str | None = None,
) -> dict[str, str]:
    """查詢物流訂單最新狀態（/7418/）。

    回傳 ECpay 給的 dict（含 LogisticsStatus, BookingNote, CVSPaymentNo 等）。
    dry_run 模式：回 mock 資料、不真連 ECpay。
    """
    if settings.ecpay_dry_run:
        # mock 回應 — 模擬「客戶已取貨」
        import secrets as _secrets
        mock_id = all_pay_logistics_id or f"MOCK{_secrets.token_hex(6).upper()}"
        return {
            "AllPayLogisticsID": mock_id,
            "MerchantTradeNo": merchant_trade_no or "DRY-MERCHANT",
            "LogisticsStatus": "2067",
            "LogisticsType": "CVS",
            "RtnCode": "2067",
            "RtnMsg": "[模擬] 消費者成功取件",
            "UpdateStatusDate": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
            "_dry_run": "true",
        }

    params = build_query_form(
        all_pay_logistics_id=all_pay_logistics_id,
        merchant_trade_no=merchant_trade_no,
    )
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                query_endpoint_url(),
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as e:
            logger.error(f"[query-logistics] ECpay HTTP error: {e}")
            raise ConnectionError(f"ECpay 連線失敗：{e}") from e

    body = resp.text.strip()
    # /7418/ response 是 key=value&key=value 格式，沒有 1|/ 0| prefix
    from urllib.parse import parse_qsl
    raw = dict(parse_qsl(body, keep_blank_values=True))
    if not raw:
        raise ConnectionError(f"ECpay 查詢回應格式異常：{body[:200]}")
    return raw


# ── ECpay UpdateStatusDate 解析 ────────────────────────────────────────────

def parse_ecpay_datetime(s: str) -> datetime | None:
    """解析 ECpay 'yyyy/MM/dd HH:mm:ss' 為 datetime（UTC+0 naive，視為台灣時間 +8 → UTC）."""
    from datetime import timedelta, timezone
    if not s:
        return None
    try:
        # ECpay 時間是台灣時間（UTC+8），轉成 UTC 存
        tw_tz = timezone(timedelta(hours=8))
        return datetime.strptime(s, "%Y/%m/%d %H:%M:%S").replace(tzinfo=tw_tz)
    except ValueError:
        try:
            tw_tz = timezone(timedelta(hours=8))
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tw_tz)
        except ValueError:
            return None


def map_endpoint_url() -> str:
    return f"{_ecpay_base_url()}/Express/map"


def create_endpoint_url() -> str:
    """ECpay 物流訂單建立 endpoint（CVS + HOME 共用，靠 LogisticsType 區分）."""
    return f"{_ecpay_base_url()}/Express/Create"


# ── 建單 form 組裝 ──────────────────────────────────────────────────────────
# 規格：docs/integration_specs/ecpay_create_shipment.md

# CVS C2C 對應的 LogisticsSubType（依用戶選的配送方式）
SHIPPING_TYPE_TO_SUB_TYPE: dict[str, tuple[str, str]] = {
    # shipping_type → (LogisticsType, LogisticsSubType)
    # yiimui 用戶帳號 = C2C；要切 B2C 把這裡的 C2C 後綴去掉
    "seven_eleven": ("CVS", "UNIMARTC2C"),
    "family_mart": ("CVS", "FAMIC2C"),
    "home": ("HOME", "TCAT"),  # 預設黑貓；POST 中華郵政另外開選項
}


def build_create_shipment_form(
    *,
    merchant_trade_no: str,
    merchant_trade_date: str,            # 'yyyy/MM/dd HH:mm:ss'
    shipping_type: str,                   # 'seven_eleven' | 'family_mart' | 'home'
    goods_amount: int,
    goods_name: str,
    sender_name: str,
    sender_cell_phone: str,
    sender_zip_code: str,
    sender_address: str,
    receiver_name: str,
    receiver_cell_phone: str,
    receiver_email: str | None,
    server_reply_url: str,
    # CVS only
    receiver_store_id: str | None = None,
    # HOME only
    receiver_zip_code: str | None = None,
    receiver_address: str | None = None,
    # HOME options
    temperature: str = "0001",            # 0001 常溫
    specification: str = "0001",          # 0001 60cm
    scheduled_pickup_time: str = "4",     # 不限時
    scheduled_delivery_time: str = "4",   # 不限時
    is_collection: str = "N",
    trade_desc: str = "",
    remark: str = "",
) -> dict[str, str]:
    """組合建單參數（含 CheckMacValue）。

    驗證規則：
    - shipping_type 在 SHIPPING_TYPE_TO_SUB_TYPE 內
    - merchant_trade_no ≤ 20 字
    - goods_amount 1 ~ 20000
    - goods_name ≤ 50 字（不另 sanitize，呼叫端要先 sanitize_goods_name）
    - sender/receiver_name 4-10 字（不另 pad，呼叫端要先 pad_name_to_ecpay_limit）
    - cell_phone 必須 09xxxxxxxx
    - server_reply_url https
    - CVS：receiver_store_id 必填、≤ 6 字
    - HOME：receiver_zip_code 3 碼、receiver_address > 6 字

    違反 raise ValueError，由 caller 轉 HTTP 400。
    """
    if shipping_type not in SHIPPING_TYPE_TO_SUB_TYPE:
        raise ValueError(f"不支援的配送方式：{shipping_type}")
    logistics_type, logistics_sub_type = SHIPPING_TYPE_TO_SUB_TYPE[shipping_type]

    if not merchant_trade_no or len(merchant_trade_no) > MAX_MERCHANT_TRADE_NO_LEN:
        raise ValueError(f"MerchantTradeNo 必填且 ≤ {MAX_MERCHANT_TRADE_NO_LEN} 字")

    if goods_amount < 1 or goods_amount > 20000:
        raise ValueError("商品金額需 1 ~ 20,000 元（ECpay 規範）")

    if not goods_name or len(goods_name) > 50:
        raise ValueError("商品名稱必填且 ≤ 50 字")

    for label, val in [("寄件人姓名", sender_name), ("收件人姓名", receiver_name)]:
        if not (4 <= len(val) <= 10):
            raise ValueError(f"{label}長度需為 4-10 字（已自動 padding 仍未達標）")

    import re as _re
    for label, val in [("寄件人手機", sender_cell_phone), ("收件人手機", receiver_cell_phone)]:
        if not _re.fullmatch(r"09\d{8}", val):
            raise ValueError(f"{label}格式錯誤（需為 09xxxxxxxx）")

    # https 強制：dry-run + 明確 testserver / localhost 才放行，避免「prod 漏設
    # ECPAY_DRY_RUN=False 但 server_reply_url 仍是 http」的 silent insecure 路徑。
    is_safe_test_url = (
        "testserver" in server_reply_url or "localhost" in server_reply_url
    )
    if not server_reply_url.startswith("https://"):
        if not (settings.ecpay_dry_run and is_safe_test_url):
            raise ValueError("ServerReplyURL 需為 https")
    if len(server_reply_url) > MAX_SERVER_REPLY_URL_LEN:
        raise ValueError("ServerReplyURL ≤ 200 字")

    if logistics_type == "CVS":
        if not receiver_store_id:
            raise ValueError("超商取貨必填收件門市代碼")
        if len(receiver_store_id) > 9:  # /8809/ 寫 6，但 Map 給 9 → 取寬鬆
            raise ValueError("門市代碼過長")
    else:  # HOME
        if not receiver_zip_code or not _re.fullmatch(r"\d{3,6}", receiver_zip_code):
            raise ValueError("宅配必填 3-6 碼郵遞區號")
        if not receiver_address or len(receiver_address) <= 6:
            raise ValueError("宅配地址必填且需 > 6 字")
        if temperature not in ("0001", "0002", "0003"):
            raise ValueError("Temperature 需為 0001/0002/0003")
        if specification not in ("0001", "0002", "0003", "0004"):
            raise ValueError("Specification 需為 0001/0002/0003/0004")

    params: dict[str, str] = {
        "MerchantID": settings.ecpay_merchant_id,
        "MerchantTradeNo": merchant_trade_no,
        "MerchantTradeDate": merchant_trade_date,
        "LogisticsType": logistics_type,
        "LogisticsSubType": logistics_sub_type,
        "GoodsAmount": str(goods_amount),
        "GoodsName": goods_name,
        "SenderName": sender_name,
        "SenderCellPhone": sender_cell_phone,
        "ReceiverName": receiver_name,
        "ReceiverCellPhone": receiver_cell_phone,
        "ServerReplyURL": server_reply_url,
        "IsCollection": is_collection,
    }

    if receiver_email:
        params["ReceiverEmail"] = receiver_email
    if trade_desc:
        params["TradeDesc"] = trade_desc[:200]
    if remark:
        params["Remark"] = remark[:200]

    if logistics_type == "CVS":
        # /8809/ 規範說 6，但 Map 給的是 9，先取前 9 由 ECpay 自己驗
        params["ReceiverStoreID"] = (receiver_store_id or "")[:9]
    else:  # HOME
        params["SenderZipCode"] = sender_zip_code
        params["SenderAddress"] = sender_address
        params["ReceiverZipCode"] = receiver_zip_code or ""
        params["ReceiverAddress"] = (receiver_address or "")[:60]
        params["Temperature"] = temperature
        params["Specification"] = specification
        params["ScheduledPickupTime"] = scheduled_pickup_time
        params["ScheduledDeliveryTime"] = scheduled_delivery_time

    params["CheckMacValue"] = calculate_check_mac_value(params)
    return params


# ── ECpay 建單 response parser ──────────────────────────────────────────────

def parse_create_shipment_response(body: str) -> dict[str, str | bool | int]:
    """解析 ECpay /Express/Create 的 response。

    格式：
      成功 → "1|MerchantID=XXX&MerchantTradeNo=XXX&RtnCode=300&...&CheckMacValue=XXX"
      失敗 → "0|錯誤訊息"

    回傳：
      {ok: bool, rtn_code: int|None, rtn_msg: str|None, raw: dict|None}
      解析成功且 RtnCode=300 → ok=True
      其他 → ok=False
    """
    body = (body or "").strip()
    if not body:
        return {"ok": False, "rtn_msg": "ECpay 回傳空 body", "raw": None}

    if "|" not in body:
        return {"ok": False, "rtn_msg": f"ECpay 回傳格式異常：{body[:200]}", "raw": None}

    head, payload = body.split("|", 1)
    if head == "0":
        return {"ok": False, "rtn_msg": payload, "raw": None}

    if head != "1":
        return {"ok": False, "rtn_msg": f"未知 ECpay 回應 prefix={head}", "raw": None}

    # head == "1" → 解析 key=val&key=val...
    from urllib.parse import parse_qsl
    raw = dict(parse_qsl(payload, keep_blank_values=True))
    rtn_code = int(raw.get("RtnCode", "0") or "0")
    rtn_msg = raw.get("RtnMsg", "")

    return {
        "ok": rtn_code == 300,
        "rtn_code": rtn_code,
        "rtn_msg": rtn_msg,
        "raw": raw,
    }


def verify_response_mac(raw: dict[str, str]) -> bool:
    """驗證 /Express/Create response 的 CheckMacValue。

    /8795/ Map callback 沒送 MAC（quirk），但 /8809/ /7414/ 建單 response 必送，必須驗。
    """
    received = raw.get("CheckMacValue", "")
    if not received:
        return False
    rest = {k: v for k, v in raw.items() if k != "CheckMacValue"}
    expected = calculate_check_mac_value(rest)
    return received.upper() == expected


# ── 寄件人資訊（從 system_settings 取）─────────────────────────────────────

# 對應 system_settings 的 key
SENDER_KEYS = {
    "name": "ecpay_sender_name",
    "phone": "ecpay_sender_phone",
    "zip_code": "ecpay_sender_zip_code",
    "address": "ecpay_sender_address",
}


async def get_sender_info(db: AsyncSession) -> dict[str, str]:
    """從 system_settings 表撈寄件人資訊（admin 在後台設）。

    缺欄位 → raise ValueError（admin 必須先到後台設）。
    """
    # SystemSetting 模型實際定義在 color.models（歷史包袱，跨模組共用該表）
    from color.models import SystemSetting

    info: dict[str, str] = {}
    for field, key in SENDER_KEYS.items():
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        info[field] = (row.value if row else "") or ""

    missing = [f for f in info if not info[f]]
    if missing:
        raise ValueError(
            f"寄件人資訊未設定（{', '.join(SENDER_KEYS[f] for f in missing)}），"
            f"請至 admin 後台「系統設定 → 寄件人資料」填寫"
        )
    return info


# ── 端到端建單（單筆）─────────────────────────────────────────────────────

async def execute_create_shipment(
    db: AsyncSession,
    *,
    order_number: str,
    order_created_at: datetime,
    total_amount: float,
    goods_titles: list[str],
    shipping_snapshot: dict,
    server_reply_url: str,
) -> dict:
    """端到端：取 sender info → pad/sanitize → build form → POST ECpay → parse response。

    Args:
        order_number: 我們的訂單編號（會當作 MerchantTradeNo，須 ≤ 20 字）
        order_created_at: 訂單建立時間（會 format 成 yyyy/MM/dd HH:mm:ss）
        total_amount: 訂單總金額（必須 1-20000，否則 ValueError）
        goods_titles: 訂單裡所有商品的標題 list
        shipping_snapshot: order.shipping_snapshot dict，含
            type / recipient_name / phone / notify_email / city / district /
            address_detail / store_id / store_name
        server_reply_url: ECpay 推狀態通知用（Day 3）

    Returns:
        {
          ok: bool,
          rtn_code: int,
          rtn_msg: str,
          tracking_number: str,         # CVS: CVSPaymentNo / HOME: BookingNote
          ecpay_logistics_id: str,
          validation_no: str | None,    # CVS 7-Eleven 才有
          mac_verified: bool,
        }
    """
    # 1. Sender info
    sender = await get_sender_info(db)

    # 2. 從 shipping_snapshot 取資料
    shipping_type = shipping_snapshot.get("type") or ""
    recipient_name = shipping_snapshot.get("recipient_name", "")
    phone = shipping_snapshot.get("phone", "")
    email = shipping_snapshot.get("notify_email", "")
    city = shipping_snapshot.get("city", "")
    district = shipping_snapshot.get("district", "")
    address_detail = shipping_snapshot.get("address_detail", "")
    store_id = shipping_snapshot.get("store_id", "")

    # 3. Pad/sanitize names + goods
    padded_sender_name = helpers.pad_name_to_ecpay_limit(sender["name"])
    padded_receiver_name = helpers.pad_name_to_ecpay_limit(recipient_name)
    sanitized_goods_name = helpers.concat_goods_names(goods_titles)
    if not sanitized_goods_name:
        sanitized_goods_name = "商品"  # fallback

    # 4. 金額檢查
    goods_amount = int(total_amount)
    if goods_amount > 20000:
        raise ValueError(f"訂單金額 NT${goods_amount} 超過 ECpay 上限 NT$20,000，無法建單")
    if goods_amount < 1:
        raise ValueError("訂單金額需 ≥ 1 元")

    # 5. HOME 專屬：地址、郵遞區號
    receiver_zip_code = None
    receiver_address = None
    if shipping_type == "home":
        receiver_zip_code = helpers.derive_zipcode(city, district)
        if not receiver_zip_code:
            raise ValueError(f"找不到 {city} {district} 的郵遞區號")
        # ECpay 需「縣市+行政區+地址」完整字串
        receiver_address = f"{city}{district}{address_detail}".strip()
        if len(receiver_address) <= 6:
            raise ValueError("收件地址過短（< 7 字）")

    # 6. 組 form（同時驗證所有欄位 — 即便 dry-run 也跑這步確保資料正確）
    params = build_create_shipment_form(
        merchant_trade_no=order_number[:MAX_MERCHANT_TRADE_NO_LEN],
        merchant_trade_date=order_created_at.strftime("%Y/%m/%d %H:%M:%S"),
        shipping_type=shipping_type,
        goods_amount=goods_amount,
        goods_name=sanitized_goods_name,
        sender_name=padded_sender_name,
        sender_cell_phone=sender["phone"],
        sender_zip_code=sender["zip_code"],
        sender_address=sender["address"],
        receiver_name=padded_receiver_name,
        receiver_cell_phone=phone,
        receiver_email=email or None,
        server_reply_url=server_reply_url,
        receiver_store_id=store_id or None,
        receiver_zip_code=receiver_zip_code,
        receiver_address=receiver_address,
    )

    # 6.5 dry-run 模式：跳過真實 ECpay 呼叫，回 mock 資料
    if settings.ecpay_dry_run:
        import secrets as _secrets
        # 模擬 ECpay 真實格式長度
        mock_logistics_id = f"MOCK{_secrets.token_hex(6).upper()}"               # 16 字元
        # CVSPaymentNo 真實是 11-13 字元純數字，mock 用 DRY+10 hex
        mock_payment_no = f"DRY{_secrets.token_hex(5).upper()}"                  # 13 字元
        # CVSValidationNo 只 7-Eleven 有、4 字純數字
        mock_validation_no = (
            f"{_secrets.randbelow(10000):04d}"                                    # 0000-9999
            if shipping_type == "seven_eleven" else None
        )
        logger.warning(
            f"[create-shipment][DRY-RUN] order={order_number} "
            f"mock_payment_no={mock_payment_no} mock_validation={mock_validation_no} "
            f"would POST to ECpay with params={params}"
        )
        return {
            "ok": True,
            "rtn_code": 300,
            "rtn_msg": "[模擬] 訂單建立成功（未實際送 ECpay）",
            "tracking_number": mock_payment_no,             # CVSPaymentNo 也是 tracking_number
            "ecpay_logistics_id": mock_logistics_id,
            "cvs_payment_no": mock_payment_no,
            "cvs_validation_no": mock_validation_no,
            "mac_verified": True,
            "dry_run": True,
        }

    # 7. POST 到 ECpay
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                create_endpoint_url(),
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as e:
            logger.error(f"[create-shipment] ECpay HTTP error: {e}")
            raise ConnectionError(f"ECpay 連線失敗：{e}") from e

    # 8. Parse response
    parsed = parse_create_shipment_response(resp.text)
    logger.info(
        f"[create-shipment] order={order_number} status={resp.status_code} "
        f"ok={parsed.get('ok')} rtn_code={parsed.get('rtn_code')} "
        f"rtn_msg={parsed.get('rtn_msg')}"
    )

    if not parsed["ok"]:
        return {
            "ok": False,
            "rtn_code": parsed.get("rtn_code") or 0,
            "rtn_msg": parsed.get("rtn_msg") or "未知錯誤",
            "tracking_number": "",
            "ecpay_logistics_id": "",
            "cvs_payment_no": None,
            "cvs_validation_no": None,
            "mac_verified": False,
        }

    raw = parsed["raw"] or {}
    mac_verified = verify_response_mac(raw)
    if not mac_verified:
        # 不 raise，但 log 警告 — admin 介面要顯示這個訂單需人工核對
        logger.warning(
            f"[create-shipment] order={order_number} MAC verify failed but RtnCode=300; "
            f"recording shipment but flagging for manual review"
        )

    # CVS: tracking_number 用 CVSPaymentNo；HOME: 用 BookingNote
    cvs_payment_no = raw.get("CVSPaymentNo") or None
    tracking_number = cvs_payment_no or raw.get("BookingNote") or ""

    return {
        "ok": True,
        "rtn_code": parsed["rtn_code"],
        "rtn_msg": parsed["rtn_msg"],
        "tracking_number": tracking_number,
        "ecpay_logistics_id": raw.get("AllPayLogisticsID", ""),
        "cvs_payment_no": cvs_payment_no,
        "cvs_validation_no": raw.get("CVSValidationNo") or None,
        "mac_verified": mac_verified,
    }
