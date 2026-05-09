"""一次性：對 remote backend 透過 admin login + PUT /admin/pages/{slug} 塞 5 個資訊頁。

冪等：每個 slug 先 GET /pages/{slug}，若已存在則跳過（保留 admin 後台修改）。

用法：
    cd backend && venv/Scripts/python scripts/seed_pages_remote.py [--prod]

預設打 https://paint-web-production.up.railway.app；--prod 也是同樣 URL（保留語意）。
帳密從 env 變數 ADMIN_EMAIL / ADMIN_PWD 讀，否則用 dev 預設。
"""
import asyncio
import os
import re
import sys

import httpx

# 從 seed_content.py 同步：避免 dup 維護成本，直接 import
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
from seed_content import PAGES  # noqa: E402

BACKEND_URL = "https://paint-web-production.up.railway.app"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "yizn.min@gmail.com")
ADMIN_PWD = os.environ.get("ADMIN_PWD", "aa0965721667")


async def main():
    async with httpx.AsyncClient(timeout=30, base_url=BACKEND_URL) as c:
        # 1. login
        r = await c.post(
            "/api/v1/admin/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
        )
        r.raise_for_status()
        m = re.search(r"access_token=([^;]+)", r.headers.get("set-cookie", ""))
        if not m:
            print("login failed: no access_token cookie")
            return
        cookie = {"Cookie": f"access_token={m.group(1)}"}

        added = 0
        skipped = 0
        for slug, title, content in PAGES:
            # 已存在 → 跳過
            r = await c.get(f"/api/v1/pages/{slug}")
            if r.status_code == 200:
                print(f"  - {slug:24s} exists, skip")
                skipped += 1
                continue
            if r.status_code != 404:
                print(f"  ! {slug:24s} unexpected GET status {r.status_code}")
                continue

            # 404 → PUT 塞入
            r = await c.put(
                f"/api/v1/admin/pages/{slug}",
                headers=cookie,
                json={"title": title, "content": content},
            )
            if r.status_code == 200:
                print(f"  + {slug:24s} created ({len(content)} chars)")
                added += 1
            else:
                print(f"  ! {slug:24s} PUT failed: {r.status_code} {r.text[:100]}")

        print(f"\n+{added} added, {skipped} skipped (already exist)")


if __name__ == "__main__":
    asyncio.run(main())
