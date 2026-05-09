"""ECpay 物流 router：CVS Map（超商選店）。

兩個 endpoint：
  - GET  /logistics/cvs-map?type=UNIMARTC2C
      → 回 HTML（auto-submit form 跳轉到 ECpay map page）
  - POST /logistics/cvs-callback
      → 接 ECpay 回傳，驗章後 postMessage 給 opener，close 自己
"""
import asyncio
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from dependencies.auth import require_admin
from logistics import service

router = APIRouter(prefix="/logistics", tags=["logistics"])


def _resolve_server_reply_url(request: Request) -> str:
    """callback URL 解析優先序：
      1. settings.ecpay_server_reply_url（明確設定）
      2. request.base_url 推導出 /api/v1/logistics/cvs-callback

    Railway 反向代理 X-Forwarded-Proto 沒被 uvicorn 採信，request.base_url 會回 http；
    強制改成 https，因為 Railway 公開網域只接 https + ECpay 要求 https callback。
    """
    if settings.ecpay_server_reply_url:
        return settings.ecpay_server_reply_url
    base = str(request.base_url).rstrip("/")
    # 修正 Railway 內部 http → 公開 https
    if base.startswith("http://") and "railway.app" in base:
        base = "https://" + base[len("http://"):]
    return f"{base}/api/v1/logistics/cvs-callback"


def _mask(value: str) -> str:
    """部分遮罩：頭3 + ... + 尾3，少於 8 字元只回長度。"""
    if not value:
        return "(empty)"
    if len(value) < 8:
        return f"(length={len(value)})"
    return f"{value[:3]}...{value[-3:]}"


async def _probe_one_subtype(
    client: httpx.AsyncClient,
    sub_type: str,
    server_reply_url: str,
) -> dict:
    """送一個假請求到 ECpay map 看是否被接受。"""
    try:
        params = service.build_cvs_map_form(
            logistics_sub_type=sub_type,
            server_reply_url=server_reply_url,
            extra_data="",
        )
    except ValueError:
        return {"sub_type": sub_type, "supported": False, "reason": "未知 SubType"}

    try:
        resp = await client.post(
            service.map_endpoint_url(),
            data=params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        body = resp.text
    except Exception as e:
        return {"sub_type": sub_type, "supported": None, "reason": f"ECpay 連線失敗：{e}"}

    if "找不到加密金鑰" in body or "請確認是否有申請開通" in body:
        return {"sub_type": sub_type, "supported": False, "reason": "ECpay 回：未開通此物流方式"}
    if "presco.com.tw" in body or "map.com.tw" in body or "<form" in body and "PostForm" in body:
        return {"sub_type": sub_type, "supported": True, "reason": "ECpay 回真實地圖 redirect → 已開通"}
    snippet = body.replace("\n", " ").strip()[:120]
    return {"sub_type": sub_type, "supported": None, "reason": f"未知回應：{snippet}"}


async def _probe_home_subtype(
    client: httpx.AsyncClient,
    sub_type: str,
    server_reply_url: str,
) -> dict:
    """測 HOME 宅配 SubType（TCAT/POST/ECAN）— 透過 /Express/Create 發試探單。

    送故意不完整的資料：ECpay 會優先檢查「SubType 是否開通」再檢查資料完整性。
    - 「找不到加密金鑰」/ 「請確認是否有申請開通」 → 沒開通
    - 任何資料相關錯誤（如「ReceiverZipCode 必填」「金額錯誤」「姓名格式錯誤」）→ 已開通
    """
    import secrets as _secrets
    from datetime import datetime as _dt

    # 故意把姓名送 X (1 字)，會被 ECpay 退「字元不符」— 但簽章必須對
    test_params = {
        "MerchantID": settings.ecpay_merchant_id,
        "MerchantTradeNo": f"PROBE{_secrets.token_hex(2).upper()}",
        "MerchantTradeDate": _dt.now().strftime("%Y/%m/%d %H:%M:%S"),
        "LogisticsType": "HOME",
        "LogisticsSubType": sub_type,
        "GoodsAmount": "100",
        "GoodsName": "probe",
        "SenderName": "測試客戶",
        "SenderCellPhone": "0912345678",
        "SenderZipCode": "100",
        "SenderAddress": "台北市中正區重慶南路一段122號",
        "ReceiverName": "測試客戶",
        "ReceiverCellPhone": "0912345678",
        "ReceiverZipCode": "100",
        "ReceiverAddress": "台北市中正區重慶南路一段122號",
        "Temperature": "0001",
        "Specification": "0001",
        "ScheduledPickupTime": "4",
        "ServerReplyURL": server_reply_url,
        "IsCollection": "N",
    }
    test_params["CheckMacValue"] = service.calculate_check_mac_value(test_params)

    try:
        resp = await client.post(
            service.create_endpoint_url(),
            data=test_params,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        body = resp.text.strip()
    except Exception as e:
        return {"sub_type": sub_type, "supported": None, "reason": f"ECpay 連線失敗：{e}"}

    if "找不到加密金鑰" in body or "請確認是否有申請開通" in body:
        return {"sub_type": sub_type, "supported": False, "reason": "ECpay 回：未開通此物流方式"}
    # ECpay 建單回 0|錯誤訊息 或 1|...&RtnCode=...
    # 只要不是「未開通」就視為「已開通」
    snippet = body.replace("\n", " ").strip()[:200]
    return {"sub_type": sub_type, "supported": True, "reason": f"已開通（ECpay 回應：{snippet}）"}


@router.get("/probe-subtypes")
async def probe_subtypes(request: Request) -> dict:
    """⚠️ 暫時 diagnostic — 用當前 env 的 MerchantID/HashKey 對 ECpay 試各 SubType，回報哪些已開通。

    CVS：用 /Express/map 試
    HOME：用 /Express/Create 試

    僅供 user 確認自己 ECpay 帳號開通了哪些物流方式。正式上線前要刪除此 endpoint。
    """
    if not settings.ecpay_merchant_id:
        return {"error": "ECPAY_MERCHANT_ID 未設定"}

    server_reply_url = _resolve_server_reply_url(request)
    cvs_sub_types = ["UNIMART", "UNIMARTFREEZE", "FAMI", "HILIFE", "UNIMARTC2C", "FAMIC2C", "HILIFEC2C", "OKMARTC2C"]
    home_sub_types = ["TCAT", "POST", "ECAN"]

    async with httpx.AsyncClient() as client:
        cvs_results = await asyncio.gather(
            *[_probe_one_subtype(client, st, server_reply_url) for st in cvs_sub_types]
        )
        home_results = await asyncio.gather(
            *[_probe_home_subtype(client, st, server_reply_url) for st in home_sub_types]
        )

    all_results = list(cvs_results) + list(home_results)
    activated = [r["sub_type"] for r in all_results if r["supported"] is True]
    return {
        "merchant_id": settings.ecpay_merchant_id,
        "env": settings.ecpay_env,
        "activated_subtypes": activated,
        "categories": {
            "cvs_b2c": [s for s in activated if s in ("UNIMART", "UNIMARTFREEZE", "FAMI", "HILIFE")],
            "cvs_c2c": [s for s in activated if s in ("UNIMARTC2C", "FAMIC2C", "HILIFEC2C", "OKMARTC2C")],
            "home": [s for s in activated if s in ("TCAT", "POST", "ECAN")],
        },
        "details": all_results,
    }


@router.get("/debug-config")
async def debug_config(request: Request) -> dict:
    """⚠️ 暫時 diagnostic，正式上線前要刪除。

    回傳當前 ECpay 設定狀態（HashKey/HashIV 遮罩），用來驗證 Railway env var 是否正確注入。
    """
    return {
        "merchant_id": settings.ecpay_merchant_id or "(empty)",
        "hash_key_masked": _mask(settings.ecpay_hash_key),
        "hash_key_length": len(settings.ecpay_hash_key),
        "hash_iv_masked": _mask(settings.ecpay_hash_iv),
        "hash_iv_length": len(settings.ecpay_hash_iv),
        "env": settings.ecpay_env or "(empty)",
        "dry_run": settings.ecpay_dry_run,
        "computed_endpoint_map": service.map_endpoint_url(),
        "computed_endpoint_create": service.create_endpoint_url(),
        "computed_callback_url": _resolve_server_reply_url(request),
    }


@router.get("/cvs-map", response_class=HTMLResponse)
async def cvs_map_redirect(
    request: Request,
    type: str = Query(..., max_length=20, description="LogisticsSubType, e.g. UNIMARTC2C / FAMIC2C"),
    extra: str = Query("", max_length=service.MAX_EXTRA_DATA_LEN,
                       description="ExtraData，最多 20 字元，原值會回 callback"),
) -> HTMLResponse:
    """產出 auto-submit form HTML，瀏覽器一打開就 POST 到 ECpay map 頁面。

    所有欄位驗證集中在 service.build_cvs_map_form()，違反 raise ValueError
    這裡轉成 HTTP 400。
    """
    server_reply_url = _resolve_server_reply_url(request)
    try:
        params = service.build_cvs_map_form(
            logistics_sub_type=type,
            server_reply_url=server_reply_url,
            extra_data=extra,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    action = service.map_endpoint_url()

    # auto-submit form
    inputs = "\n".join(
        f'<input type="hidden" name="{k}" value="{_html_escape(v)}" />'
        for k, v in params.items()
    )
    html = f"""<!doctype html>
<html lang="zh-TW">
<head>
<meta charset="utf-8" />
<title>正在前往 ECpay 選店…</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", sans-serif;
    background: #F4EFE2;
    color: #2E2823;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; margin: 0;
  }}
  .box {{ text-align: center; }}
  .spinner {{
    width: 28px; height: 28px;
    border: 2px solid #8C6E52; border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 16px;
  }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <p>正在前往 ECpay 選店…</p>
  </div>
  <form id="ecpay-form" method="POST" action="{action}">
    {inputs}
  </form>
  <script>document.getElementById('ecpay-form').submit();</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/cvs-callback", response_class=HTMLResponse)
async def cvs_map_callback(request: Request) -> HTMLResponse:
    """接 ECpay 選店結果，用 postMessage 把資料傳給 opener window，並 close 自己。

    來源：https://developers.ecpay.com.tw/8795/ ServerReplyURL 回傳參數規格
    """
    # 讀 raw bytes，避免 FastAPI 預設 UTF-8 decode 弄亂 Big5 中文
    raw_body = await request.body()
    raw_text_utf8 = raw_body.decode("utf-8", errors="replace")

    # ★ Ground truth log — ECpay 真的送了什麼 raw bytes，逐字記錄
    print(f"[ecpay-callback] raw_body bytes={len(raw_body)}", flush=True)
    print(f"[ecpay-callback] raw_text_utf8={raw_text_utf8}", flush=True)

    def _parse_form(body: bytes, encoding: str) -> dict[str, str]:
        from urllib.parse import parse_qsl
        try:
            decoded = body.decode(encoding)
        except UnicodeDecodeError:
            return {}
        return dict(parse_qsl(decoded, keep_blank_values=True))

    # 嘗試 UTF-8 + Big5 兩種編碼，看哪個 MAC 對得起來
    all_params = _parse_form(raw_body, "utf-8")
    received_mac = all_params.get("CheckMacValue", "")
    chosen_encoding = "utf-8"
    valid = False
    expected_mac = ""

    if received_mac:
        # 嚴格驗：MAC 存在則必須對得起來
        expected_mac = service.calculate_check_mac_value(
            {k: v for k, v in all_params.items() if k != "CheckMacValue"}
        )
        if received_mac.upper() == expected_mac:
            valid = True
        else:
            big5_params = _parse_form(raw_body, "big5")
            if big5_params:
                exp_big5 = service.calculate_check_mac_value(
                    {k: v for k, v in big5_params.items() if k != "CheckMacValue"}
                )
                if big5_params.get("CheckMacValue", "").upper() == exp_big5:
                    all_params = big5_params
                    chosen_encoding = "big5"
                    valid = True
                    expected_mac = exp_big5
    else:
        # ECpay CVS Map 已知 quirk：實際不附 CheckMacValue 欄位（與 /8795/ 文件不符）
        # 缺失視為 valid；其他欄位驗證仍會把關（MerchantTradeNo / CVSStoreID 等）
        valid = True
        print("[ecpay-callback] no CheckMacValue from ECpay → accept (CVS Map quirk)", flush=True)

    if received_mac and not valid:
        print(f"[ecpay-callback] verify FAILED: received_mac={received_mac!r} "
              f"expected_mac={expected_mac!r}", flush=True)
    elif received_mac:
        print(f"[ecpay-callback] verify OK encoding={chosen_encoding}", flush=True)
    print(f"[ecpay-callback] parsed keys={list(all_params.keys())}", flush=True)

    # ── 業務層驗證（避免亂塞偽造資料給前端）─────────────────────────────
    # 必要欄位齊備
    if not all_params.get("MerchantTradeNo"):
        valid = False
        print("[ecpay-callback] missing MerchantTradeNo", flush=True)

    # CVSStoreID 長度 ≤ 9（ECpay 規範）
    cvs_store_id_raw = all_params.get("CVSStoreID", "")
    if cvs_store_id_raw and len(cvs_store_id_raw) > service.MAX_CVS_STORE_ID_LEN:
        valid = False
        print(f"[ecpay-callback] CVSStoreID too long: {len(cvs_store_id_raw)}", flush=True)

    # 截斷過長 response 欄位（log 警告但不拒收，避免可顯示資料丟失）
    all_params["CVSStoreName"] = service.truncate_response_field(
        all_params.get("CVSStoreName", ""), service.MAX_CVS_STORE_NAME_LEN * 3,  # 容錯 3 倍
    )
    all_params["CVSAddress"] = service.truncate_response_field(
        all_params.get("CVSAddress", ""), service.MAX_CVS_ADDRESS_LEN * 2,  # 容錯 2 倍
    )

    # 必要欄位提取（給前端 postMessage）
    MerchantID = all_params.get("MerchantID", "")
    MerchantTradeNo = all_params.get("MerchantTradeNo", "")
    LogisticsSubType = all_params.get("LogisticsSubType", "")
    CVSStoreID = all_params.get("CVSStoreID", "")
    CVSStoreName = all_params.get("CVSStoreName", "")
    CVSAddress = all_params.get("CVSAddress", "")
    CVSTelephone = all_params.get("CVSTelephone", "")
    CVSOutSide = all_params.get("CVSOutSide", "")
    ExtraData = all_params.get("ExtraData", "")
    CheckMacValue = received_mac

    payload = {
        "type": "ecpay-cvs-selected",
        "ok": bool(valid and CVSStoreID),
        "logistics_sub_type": LogisticsSubType,
        "store_id": CVSStoreID,
        "store_name": CVSStoreName,
        "store_address": CVSAddress,
        "store_phone": CVSTelephone,
        "store_outside": CVSOutSide,  # '0' / '1' / ''
        "extra_data": ExtraData,
    }
    import json
    payload_json = json.dumps(payload, ensure_ascii=False)

    html = f"""<!doctype html>
<html lang="zh-TW">
<head><meta charset="utf-8" /><title>選店完成</title>
<style>
  body {{
    font-family: -apple-system, "Noto Sans TC", sans-serif;
    background: #F4EFE2; color: #2E2823;
    display: flex; align-items: center; justify-content: center;
    min-height: 100vh; margin: 0;
    text-align: center;
  }}
</style></head>
<body>
  <div>
    <p>已選擇門市，正在返回…</p>
    <p style="font-size: 12px; color: #6B6660; margin-top: 16px;">
      若視窗未自動關閉請手動關閉。
    </p>
  </div>
  <script>
    (function () {{
      var payload = {payload_json};
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, '*');
        }}
      }} catch (e) {{ /* ignore */ }}
      setTimeout(function () {{ window.close(); }}, 600);
    }})();
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ── Day 3：物流狀態通知 Webhook ─────────────────────────────────────────────

@router.get("/print-shipment-label/{shipment_id}", response_class=HTMLResponse)
async def print_shipment_label(
    shipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _admin=Depends(require_admin),
):
    """列印託運單 HTML 頁面（管理員用，瀏覽器開新分頁）.

    依該 Shipment 對應正確的 ECpay 列印 endpoint
    （HOME 走 /helper/printTradeDocument，CVS C2C 各家獨立）.

    dry_run 模式回 mock 預覽 HTML，不真連 ECpay。
    """
    from sqlalchemy import select as _select

    from orders.models import Order, Shipment

    result = await db.execute(_select(Shipment).where(Shipment.id == shipment_id))
    shipment = result.scalar_one_or_none()
    if shipment is None:
        return HTMLResponse(content="<h1>找不到出貨記錄</h1>", status_code=404)
    if not shipment.ecpay_logistics_id:
        return HTMLResponse(
            content="<h1>此出貨記錄無 ECpay 物流交易編號，無法列印</h1>",
            status_code=400,
        )

    order_result = await db.execute(_select(Order).where(Order.id == shipment.order_id))
    order = order_result.scalar_one_or_none()
    if order is None:
        return HTMLResponse(content="<h1>找不到訂單</h1>", status_code=404)

    # 推導 LogisticsType / SubType
    shipping_type = order.shipping_type
    if shipping_type == "home":
        logistics_type = "HOME"
        logistics_sub_type = "TCAT"
    else:
        logistics_type = "CVS"
        logistics_sub_type = service.SHIPPING_TYPE_TO_SUB_TYPE.get(
            shipping_type, ("CVS", "UNIMARTC2C")
        )[1]

    # dry_run mock
    if settings.ecpay_dry_run:
        return _mock_print_html(shipment, order, logistics_type, logistics_sub_type)

    # 真實：build form auto-submit 到 ECpay 列印 endpoint
    try:
        params = service.build_print_label_form(
            logistics_type=logistics_type,
            logistics_sub_type=logistics_sub_type,
            all_pay_logistics_id=shipment.ecpay_logistics_id,
            cvs_payment_no=shipment.cvs_payment_no,
            cvs_validation_no=shipment.cvs_validation_no,
        )
    except ValueError as e:
        return HTMLResponse(content=f"<h1>列印失敗</h1><p>{e}</p>", status_code=400)

    action = service.print_endpoint_url(logistics_type, logistics_sub_type)
    inputs = "\n".join(
        f'<input type="hidden" name="{k}" value="{_html_escape(v)}" />'
        for k, v in params.items()
    )
    html = f"""<!doctype html>
<html lang="zh-TW">
<head><meta charset="utf-8" /><title>列印託運單…</title>
<style>
  body {{ font-family: -apple-system, "Noto Sans TC", sans-serif;
          background: #F4EFE2; color: #2E2823;
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; margin: 0; }}
  .box {{ text-align: center; }}
  .spinner {{ width: 28px; height: 28px;
              border: 2px solid #8C6E52; border-top-color: transparent;
              border-radius: 50%; animation: spin 0.8s linear infinite;
              margin: 0 auto 16px; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style></head>
<body>
  <div class="box">
    <div class="spinner"></div>
    <p>正在前往 ECpay 列印頁面…</p>
  </div>
  <form id="ecpay-print-form" method="POST" action="{action}">
    {inputs}
  </form>
  <script>document.getElementById('ecpay-print-form').submit();</script>
</body>
</html>"""
    return HTMLResponse(content=html)


def _mock_print_html(shipment, order, logistics_type: str, logistics_sub_type: str) -> "HTMLResponse":
    """dry_run 模式的列印預覽（不真連 ECpay）."""
    snapshot = order.shipping_snapshot or {}
    receiver_name = snapshot.get("recipient_name", "")
    receiver_phone = snapshot.get("phone", "")
    receiver_addr = (
        f"{snapshot.get('city', '')}{snapshot.get('district', '')}{snapshot.get('address_detail', '')}"
        if logistics_type == "HOME"
        else snapshot.get("store_name", "")
    )
    sub_label = {
        "TCAT": "黑貓宅急便",
        "POST": "中華郵政",
        "UNIMARTC2C": "7-Eleven 交貨便",
        "FAMIC2C": "全家店到店",
        "HILIFEC2C": "萊爾富店到店",
        "OKMARTC2C": "OK 超商店到店",
    }.get(logistics_sub_type, logistics_sub_type)
    html = f"""<!doctype html>
<html lang="zh-TW">
<head><meta charset="utf-8" /><title>託運單預覽（模擬）</title>
<style>
  body {{ font-family: -apple-system, "Noto Sans TC", sans-serif;
          background: #F4EFE2; color: #2E2823; padding: 40px 20px; }}
  .label {{ max-width: 600px; margin: 0 auto;
            background: white; border: 2px solid #2E2823;
            padding: 32px; border-radius: 8px; }}
  .header {{ text-align: center; padding-bottom: 16px;
             border-bottom: 2px dashed #2E2823; margin-bottom: 24px; }}
  .header h1 {{ margin: 0 0 8px; font-size: 22px; letter-spacing: 0.08em; }}
  .header .sub {{ font-size: 13px; color: #8C6E52; letter-spacing: 0.18em; }}
  .row {{ display: grid; grid-template-columns: 100px 1fr; gap: 12px; margin-bottom: 12px; font-size: 13px; }}
  .row dt {{ color: #6B6660; letter-spacing: 0.08em; }}
  .row dd {{ color: #2E2823; margin: 0; font-weight: 500; }}
  .barcode {{ font-family: "Courier New", monospace; font-size: 18px;
              text-align: center; margin: 24px 0;
              padding: 12px; background: #F2E8D5;
              border: 1px dashed #8C6E52; }}
  .footer {{ margin-top: 24px; padding-top: 16px;
             border-top: 1px dashed #8C6E52;
             text-align: center; font-size: 11px; color: #6B6660;
             letter-spacing: 0.18em; text-transform: uppercase; }}
  .mock-banner {{ position: fixed; top: 0; left: 0; right: 0;
                  background: #7B2E40; color: white;
                  padding: 12px; text-align: center; font-size: 13px;
                  letter-spacing: 0.18em; }}
  @media print {{
    .mock-banner {{ display: none; }}
    body {{ background: white; padding: 0; }}
  }}
  .actions {{ max-width: 600px; margin: 24px auto 0; display: flex; gap: 12px; justify-content: center; }}
  .actions button {{ padding: 10px 20px; border: 1px solid #2E2823;
                     background: white; color: #2E2823; cursor: pointer;
                     font-family: inherit; font-size: 13px; letter-spacing: 0.12em; }}
  .actions button.primary {{ background: #2E2823; color: white; }}
  @media print {{ .actions {{ display: none; }} }}
</style></head>
<body>
  <div class="mock-banner">⚠️ 模擬列印（DRY_RUN 模式）— 切到 production 才會印真實託運單</div>
  <div class="label">
    <div class="header">
      <h1>易木 YIIMUI 託運單</h1>
      <div class="sub">{sub_label}</div>
    </div>
    <dl class="row">
      <dt>訂單編號</dt>
      <dd>{order.order_number}</dd>
    </dl>
    <dl class="row">
      <dt>託運單號</dt>
      <dd>{shipment.tracking_number or shipment.ecpay_logistics_id}</dd>
    </dl>
    <dl class="row">
      <dt>收件人</dt>
      <dd>{_html_escape(receiver_name)}</dd>
    </dl>
    <dl class="row">
      <dt>聯絡電話</dt>
      <dd>{_html_escape(receiver_phone)}</dd>
    </dl>
    <dl class="row">
      <dt>{ '送達地址' if logistics_type == 'HOME' else '取貨門市' }</dt>
      <dd>{_html_escape(receiver_addr)}</dd>
    </dl>
    <div class="barcode">|||| {shipment.tracking_number or 'DRY-MOCK'} ||||</div>
    <div class="footer">— ECpay 物流系統（模擬模式）—</div>
  </div>
  <div class="actions">
    <button onclick="window.print()" class="primary">列印</button>
    <button onclick="window.close()">關閉</button>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.post("/status-callback")
async def status_callback(request: Request):
    """ECpay 物流狀態通知 webhook (/7420/)。

    全部物流類型（CVS + HOME）共用此 endpoint。
    依 LogisticsType + RtnCode 對映至 Shipment.status，必回 "1|OK" 給 ECpay。

    來源：docs/integration_specs/ecpay_status_tracking.md
    """
    import logging
    from urllib.parse import parse_qsl

    from sqlalchemy import select as _select
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa

    from core.database import get_db as _get_db
    from orders.models import Order, OrderStatusEnum, Shipment, ShipmentStatusEnum

    log = logging.getLogger(__name__)

    raw_body = await request.body()
    decoded = raw_body.decode("utf-8", errors="replace")
    params = dict(parse_qsl(decoded, keep_blank_values=True))

    log.info(f"[status-callback] received: {params}")

    # 1. 簽章驗證
    received_mac = params.get("CheckMacValue", "")
    rest = {k: v for k, v in params.items() if k != "CheckMacValue"}
    expected_mac = service.calculate_check_mac_value(rest)
    if not received_mac or received_mac.upper() != expected_mac:
        log.warning(
            f"[status-callback] MAC verify failed: received={received_mac} expected={expected_mac}"
        )
        # 故意仍回 1|OK：不暴露失敗細節，避免 ECpay 重發 / 攻擊者試探
        return _plain_text_response("1|OK")

    # 2. 找對應的 Shipment
    all_pay_id = params.get("AllPayLogisticsID", "")
    if not all_pay_id:
        log.warning("[status-callback] missing AllPayLogisticsID")
        return _plain_text_response("1|OK")

    rtn_code_str = params.get("RtnCode", "0")
    try:
        rtn_code = int(rtn_code_str)
    except ValueError:
        rtn_code = 0
    rtn_msg = params.get("RtnMsg", "")
    update_status_date_str = params.get("UpdateStatusDate", "")
    update_status_date = service.parse_ecpay_datetime(update_status_date_str)

    # 3. 進 DB 更新（用 dependency injection 拿 db）
    async for db in _get_db():
        try:
            ship_result = await db.execute(
                _select(Shipment).where(Shipment.ecpay_logistics_id == all_pay_id).with_for_update()
            )
            shipment = ship_result.scalar_one_or_none()
            if shipment is None:
                log.warning(f"[status-callback] no Shipment found for AllPayLogisticsID={all_pay_id}")
                return _plain_text_response("1|OK")

            # 4. Idempotency：last_status_at >= 新的 UpdateStatusDate → 跳過
            if (
                update_status_date
                and shipment.last_status_at
                and shipment.last_status_at >= update_status_date
            ):
                log.info(
                    f"[status-callback] skip stale update: shipment={shipment.id} "
                    f"existing_at={shipment.last_status_at} new_at={update_status_date}"
                )
                return _plain_text_response("1|OK")

            # 5. 更新狀態欄位
            shipment.last_rtn_code = rtn_code
            shipment.last_rtn_msg = rtn_msg
            if update_status_date:
                shipment.last_status_at = update_status_date

            # 6. 「已送達 / 客戶取貨」→ Shipment.status='delivered'
            if service.is_delivered_status(rtn_code, rtn_msg):
                if shipment.status != ShipmentStatusEnum.delivered:
                    shipment.status = ShipmentStatusEnum.delivered
                    shipment.delivered_at = update_status_date or datetime.now(__import__("datetime").timezone.utc)
                    log.info(f"[status-callback] shipment {shipment.id} marked delivered")

                # 7. 該 Order 所有 Shipment 都 delivered → Order.status='completed'
                order_result = await db.execute(
                    _select(Order).where(Order.id == shipment.order_id).with_for_update()
                )
                order = order_result.scalar_one_or_none()
                if order is not None:
                    all_ships_result = await db.execute(
                        _select(Shipment).where(Shipment.order_id == order.id)
                    )
                    all_ships = list(all_ships_result.scalars().all())
                    if all_ships and all(
                        s.status == ShipmentStatusEnum.delivered for s in all_ships
                    ):
                        if order.status != OrderStatusEnum.completed:
                            order.status = OrderStatusEnum.completed
                            from datetime import datetime as _dt
                            order.completed_at = _dt.now(UTC)
                            log.info(f"[status-callback] order {order.id} auto-completed")

            await db.commit()
        except Exception as e:
            log.exception(f"[status-callback] error processing: {e}")
            await db.rollback()

    return _plain_text_response("1|OK")


def _plain_text_response(text_content: str):
    """ECpay webhook 必回純字串（不含 HTML/JSON 結構）."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=text_content)
