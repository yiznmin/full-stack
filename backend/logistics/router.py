"""ECpay 物流 router：CVS Map（超商選店）。

兩個 endpoint：
  - GET  /logistics/cvs-map?type=UNIMARTC2C
      → 回 HTML（auto-submit form 跳轉到 ECpay map page）
  - POST /logistics/cvs-callback
      → 接 ECpay 回傳，驗章後 postMessage 給 opener，close 自己
"""
import asyncio
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from core.config import settings
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


@router.get("/probe-subtypes")
async def probe_subtypes(request: Request) -> dict:
    """⚠️ 暫時 diagnostic — 用當前 env 的 MerchantID/HashKey 對 ECpay 試各 SubType，回報哪些已開通。

    對 ECpay map endpoint 各送一筆 fake POST，依回應內容判斷：
    - 「找不到加密金鑰」→ 未開通
    - 真實 map redirect HTML → 已開通

    僅供 user 確認自己 ECpay 帳號開通了哪些物流方式。正式上線前要刪除此 endpoint。
    """
    if not settings.ecpay_merchant_id:
        return {"error": "ECPAY_MERCHANT_ID 未設定"}

    server_reply_url = _resolve_server_reply_url(request)
    sub_types = ["UNIMART", "UNIMARTFREEZE", "FAMI", "HILIFE", "UNIMARTC2C", "FAMIC2C", "HILIFEC2C", "OKMARTC2C"]

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_probe_one_subtype(client, st, server_reply_url) for st in sub_types]
        )

    activated = [r["sub_type"] for r in results if r["supported"] is True]
    return {
        "merchant_id": settings.ecpay_merchant_id,
        "env": settings.ecpay_env,
        "activated_subtypes": activated,
        "category_hint": (
            "B2C" if any(s in activated for s in ["UNIMART", "FAMI", "HILIFE"])
            else "C2C" if any(s in activated for s in ["UNIMARTC2C", "FAMIC2C", "HILIFEC2C", "OKMARTC2C"])
            else "未知"
        ),
        "details": results,
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
        "computed_endpoint": service.map_endpoint_url(),
        "computed_callback_url": _resolve_server_reply_url(request),
    }


@router.get("/cvs-map", response_class=HTMLResponse)
async def cvs_map_redirect(
    request: Request,
    type: str = Query(..., description="LogisticsSubType, e.g. UNIMARTC2C / FAMIC2C"),
    extra: str = Query("", description="ExtraData，用來把 user 識別資訊帶回"),
) -> HTMLResponse:
    """產出 auto-submit form HTML，瀏覽器一打開就 POST 到 ECpay map 頁面。"""
    if not service.is_supported_sub_type(type):
        raise HTTPException(status_code=400, detail=f"不支援的物流類型：{type}")

    if not settings.ecpay_merchant_id:
        raise HTTPException(status_code=503, detail="ECPAY_MERCHANT_ID 未設定")

    server_reply_url = _resolve_server_reply_url(request)
    params = service.build_cvs_map_form(
        logistics_sub_type=type,
        server_reply_url=server_reply_url,
        extra_data=extra,
    )
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
async def cvs_map_callback(
    request: Request,
    MerchantID: str = Form(...),
    MerchantTradeNo: str = Form(...),
    LogisticsSubType: str = Form(...),
    CVSStoreID: str = Form(""),
    CVSStoreName: str = Form(""),
    CVSAddress: str = Form(""),
    CVSTelephone: str = Form(""),
    CVSOutSide: str = Form(""),  # '0' = 本島, '1' = 離島；UNIMART/UNIMARTC2C/FAMI/FAMIC2C 才有
    ExtraData: str = Form(""),
    CheckMacValue: str = Form(""),
) -> HTMLResponse:
    """接 ECpay 選店結果，驗章後用 postMessage 把資料傳給 opener window，並 close 自己。

    來源：https://developers.ecpay.com.tw/8795/ ServerReplyURL 回傳參數規格
    """
    params = {
        "MerchantID": MerchantID,
        "MerchantTradeNo": MerchantTradeNo,
        "LogisticsSubType": LogisticsSubType,
        "CVSStoreID": CVSStoreID,
        "CVSStoreName": CVSStoreName,
        "CVSAddress": CVSAddress,
        "CVSTelephone": CVSTelephone,
        "CVSOutSide": CVSOutSide,
        "ExtraData": ExtraData,
        "CheckMacValue": CheckMacValue,
    }
    # 簽章驗證時排除 CheckMacValue 自身與空值欄位
    params_for_check = {k: v for k, v in params.items() if k != "CheckMacValue" and v != ""}
    valid = service.verify_check_mac_value({**params_for_check, "CheckMacValue": CheckMacValue})

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
