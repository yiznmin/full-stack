"""透過 Chrome DevTools Protocol 注入 JS，模擬真實 browser 從 admin page 跑完整 upload 流程。

需要：Chrome 啟動時帶 --remote-debugging-port=9222
此 script 找到 yiimui-admin 那個 page，注入 JS 跑 upload，回報結果。
"""
import json
import urllib.request
from websocket import create_connection


def main():
    # 1. 找到 yiimui-admin page
    PORT = 9223
    pages = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json").read())
    admin_page = None
    for p in pages:
        if "yiimui-admin.vercel.app" in p.get("url", ""):
            admin_page = p
            break
    if not admin_page:
        print("❌ 沒找到 yiimui-admin page。請先打開 https://yiimui-admin.vercel.app/")
        return

    print(f"✓ Found page: {admin_page['url']}")
    ws_url = admin_page["webSocketDebuggerUrl"]

    # 2. 連 CDP websocket
    ws = create_connection(ws_url)

    # 3. 注入 JS：完整 upload 流程
    js_code = """
(async () => {
  const log = [];
  const push = (k, v) => log.push({ step: k, ...v });

  // Step 1: Login (idempotent)
  push('login_start', { ts: Date.now() });
  const loginRes = await fetch('/api/v1/admin/auth/login', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: 'yizn.min@gmail.com', password: 'aa0965721667' }),
  });
  push('login_done', { status: loginRes.status });

  // Step 2: Get signed upload URL
  const tinyPng = new Uint8Array([
    0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,0x00,0x00,0x00,0x0d,0x49,0x48,0x44,0x52,
    0x00,0x00,0x00,0x01,0x00,0x00,0x00,0x01,0x08,0x04,0x00,0x00,0x00,0xb5,0x1c,0x0c,
    0x02,0x00,0x00,0x00,0x0b,0x49,0x44,0x41,0x54,0x78,0x9c,0x63,0x00,0x01,0x00,0x00,
    0x05,0x00,0x01,0x0d,0x0a,0x2d,0xb4,0x00,0x00,0x00,0x00,0x49,0x45,0x4e,0x44,0xae,
    0x42,0x60,0x82,
  ]);
  const blob = new Blob([tinyPng], { type: 'image/png' });

  const signRes = await fetch('/api/v1/upload/product-image', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: 'browser-test.png',
      content_type: 'image/png',
      size: tinyPng.length,
    }),
  });
  push('sign_done', { status: signRes.status });
  const signed = await signRes.json();
  push('sign_url', { url: signed.upload_url ? signed.upload_url.slice(0, 100) + '...' : 'NONE' });

  // Step 3: PUT to Firebase signed URL
  push('put_start', { ts: Date.now() });
  let putErr = null;
  let putStatus = 0;
  try {
    const putRes = await fetch(signed.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': 'image/png' },
      body: blob,
    });
    putStatus = putRes.status;
  } catch (e) {
    putErr = e.message;
  }
  push('put_done', { status: putStatus, error: putErr });

  // Step 4: GET public_url to verify
  let getStatus = 0;
  let getErr = null;
  try {
    const getRes = await fetch(signed.public_url, { method: 'HEAD' });
    getStatus = getRes.status;
  } catch (e) {
    getErr = e.message;
  }
  push('get_done', { status: getStatus, error: getErr });

  return log;
})()
"""

    msg = {
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {
            "expression": js_code,
            "awaitPromise": True,
            "returnByValue": True,
        },
    }
    ws.send(json.dumps(msg))
    while True:
        resp = json.loads(ws.recv())
        if resp.get("id") == 1:
            break

    if "error" in resp:
        print(f"❌ CDP error: {resp['error']}")
    else:
        result = resp["result"]["result"]
        if result.get("type") == "object" and "value" in result:
            for step in result["value"]:
                print(f"  {step}")
        elif result.get("subtype") == "error":
            print(f"❌ JS exception: {result.get('description')}")
        else:
            print(f"Response: {json.dumps(result, indent=2)[:500]}")

    ws.close()


if __name__ == "__main__":
    main()
