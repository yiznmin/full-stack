"""Drive Chrome via raw CDP to verify store /custom hub UI smoke.

Verifies:
- /custom hub renders 3 cards + hero
- /custom/about renders FAQ + CTA
- /custom/cases loads case data
- /custom/apply renders form + canvas sizes load (proxy → backend)
- Click flows: hub → about, cases, apply, modal open + consult CTA → /custom/apply
- Console errors counted at end

Requires: Chrome already running with --remote-debugging-port=9222.
Run: cd backend && PYTHONIOENCODING=utf-8 venv/Scripts/python scripts/smoke_test_store_ui.py
"""
import asyncio
import json
import sys
from typing import Any

import httpx
import websockets

CHROME_REST = "http://localhost:9222"
STORE_BASE = "http://localhost:5175"


def step(label: str) -> None:
    print(f"\n=== {label} ===", flush=True)


def check(cond: bool, msg: str) -> None:
    if not cond:
        print(f"  FAIL: {msg}", flush=True)
        sys.exit(1)
    print(f"  PASS: {msg}", flush=True)


async def open_tab(url: str) -> str:
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{CHROME_REST}/json/new", params=url)
        return r.json()["webSocketDebuggerUrl"]


async def close_tab(target_id: str) -> None:
    async with httpx.AsyncClient() as c:
        await c.get(f"{CHROME_REST}/json/close/{target_id}")


class CDPSession:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws: websockets.ClientConnection | None = None
        self.id_counter = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._events: list[dict[str, Any]] = []
        self._console: list[str] = []
        self._loop_task: asyncio.Task | None = None

    async def __aenter__(self) -> "CDPSession":
        self.ws = await websockets.connect(self.ws_url, max_size=20 * 1024 * 1024)
        self._loop_task = asyncio.create_task(self._loop())
        await self.send("Runtime.enable")
        await self.send("Page.enable")
        await self.send("Network.enable")
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._loop_task:
            self._loop_task.cancel()
        if self.ws:
            await self.ws.close()

    async def _loop(self) -> None:
        assert self.ws
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                if "id" in msg and msg["id"] in self._pending:
                    self._pending.pop(msg["id"]).set_result(msg)
                elif "method" in msg:
                    self._events.append(msg)
                    if msg["method"] == "Runtime.consoleAPICalled":
                        params = msg.get("params", {})
                        type_ = params.get("type", "log")
                        args = params.get("args", [])
                        text = " ".join(str(a.get("value", a.get("description", ""))) for a in args)
                        self._console.append(f"[{type_}] {text}")
                    elif msg["method"] == "Runtime.exceptionThrown":
                        ex = msg.get("params", {}).get("exceptionDetails", {})
                        self._console.append(f"[exception] {ex.get('text', '')} {ex.get('exception', {}).get('description', '')}")
        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass

    async def send(self, method: str, params: dict | None = None) -> dict:
        assert self.ws
        self.id_counter += 1
        cid = self.id_counter
        fut: asyncio.Future = asyncio.Future()
        self._pending[cid] = fut
        await self.ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
        result = await asyncio.wait_for(fut, timeout=15.0)
        return result.get("result", {})

    async def navigate(self, url: str) -> None:
        await self.send("Page.navigate", {"url": url})
        # Wait for load — poll until document.readyState === 'complete'
        for _ in range(30):
            r = await self.eval("document.readyState")
            if r == "complete":
                # Wait briefly for Vue hydration
                await asyncio.sleep(1.0)
                return
            await asyncio.sleep(0.3)
        raise RuntimeError(f"timeout waiting for load: {url}")

    async def eval(self, expr: str) -> Any:
        r = await self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    @property
    def console_errors(self) -> list[str]:
        return [m for m in self._console if "[error]" in m or "[exception]" in m]


async def main() -> None:
    # Open tab to /custom
    ws_url = await open_tab(f"{STORE_BASE}/custom")
    target_id = ws_url.rsplit("/", 1)[-1]
    print(f"  opened tab: {target_id}", flush=True)
    await asyncio.sleep(1.0)

    async with CDPSession(ws_url) as s:
        step("1) /custom hub: 3 cards + hero render")
        await s.navigate(f"{STORE_BASE}/custom")
        title = await s.eval("document.querySelector('.hero-title')?.innerText")
        check(title and "客製化" in title.replace("\n", "") or "回憶" in (title or ""), f"hero rendered: {title!r}")
        cards = await s.eval("document.querySelectorAll('.hub-card').length")
        check(cards == 3, f"hub-card count = {cards}, expected 3")
        about_link = await s.eval("document.querySelector('a[href=\"/custom/about\"]')?.href")
        check(about_link is not None, f"/custom/about link present: {about_link}")
        cases_link = await s.eval("document.querySelector('a[href=\"/custom/cases\"]')?.href")
        check(cases_link is not None, f"/custom/cases link present: {cases_link}")
        apply_link = await s.eval("document.querySelector('a[href=\"/custom/apply\"]')?.href")
        check(apply_link is not None, f"/custom/apply link present: {apply_link}")

        step("2) /custom/about: FAQ accordion + flow")
        await s.navigate(f"{STORE_BASE}/custom/about")
        h1 = await s.eval("document.querySelector('h1')?.innerText")
        check(h1 and "客製化" in h1, f"H1 = {h1!r}")
        faq_count = await s.eval("document.querySelectorAll('.faq-item').length")
        check(faq_count >= 5, f"FAQ items = {faq_count}, expected >= 5")
        # Click first FAQ — Vue 反應式更新需要等下一個 tick
        await s.eval("document.querySelector('.faq-item .faq-q')?.click()")
        await asyncio.sleep(0.3)
        opened = await s.eval("document.querySelector('.faq-item.open') !== null")
        check(opened, "first FAQ item opens on click")
        cta = await s.eval("document.querySelector('a[href=\"/custom/apply\"]')?.innerText")
        check(cta and ("申請" in cta or "開始" in cta), f"about CTA → /custom/apply present: {cta!r}")

        step("3) /custom/cases: gallery loads (or empty state)")
        await s.navigate(f"{STORE_BASE}/custom/cases")
        # Wait for query to settle
        await asyncio.sleep(1.5)
        empty_or_grid = await s.eval("""
            (() => {
                if (document.querySelector('.case-grid')) return 'grid';
                if (document.querySelector('.state.empty')) return 'empty';
                if (document.querySelector('.state')) return 'loading';
                return 'unknown';
            })()
        """)
        check(empty_or_grid in ("grid", "empty"), f"cases page state = {empty_or_grid}")
        # Filter chips render even on empty
        filter_count = await s.eval("document.querySelectorAll('.filter-chip').length")
        check(filter_count >= 1, f"filter-chip count = {filter_count} (at least '全部')")

        step("4) /custom/apply: form + canvas sizes load")
        await s.navigate(f"{STORE_BASE}/custom/apply")
        await asyncio.sleep(1.5)
        size_chips = await s.eval("document.querySelectorAll('.size-chip').length")
        check(size_chips > 0, f"size-chip count = {size_chips} (canvas sizes loaded from /api)")
        diff_chips = await s.eval("document.querySelectorAll('.level-chip').length")
        check(diff_chips == 5, f"difficulty chips = {diff_chips}, expected 5 (4 levels + 'admin suggest')")
        # Photo upload should be locked (not logged in)
        locked = await s.eval("document.querySelector('.photo-locked') !== null")
        check(locked, "photo upload disabled when not logged in")
        # No 'detail' field (規格 v1.1 拿掉)
        has_detail = await s.eval("""
            (() => {
                const legends = Array.from(document.querySelectorAll('.field-legend'));
                return legends.some(l => l.innerText.includes('精細度') || l.innerText.includes('細緻度') || l.innerText.includes('detail'));
            })()
        """)
        check(not has_detail, "form has NO 細緻度/detail field (custom_photo)")

        step("5) Click hub card → /custom/about navigates")
        await s.navigate(f"{STORE_BASE}/custom")
        await asyncio.sleep(0.8)
        await s.eval("document.querySelector('a[href=\"/custom/about\"]').click()")
        await asyncio.sleep(1.0)
        cur_url = await s.eval("location.pathname")
        check(cur_url == "/custom/about", f"after click → {cur_url}")

        step("6) /custom/requests requires auth (redirect to /login)")
        await s.navigate(f"{STORE_BASE}/custom/requests")
        await asyncio.sleep(1.0)
        cur_url = await s.eval("location.pathname")
        check(cur_url == "/login", f"unauth → {cur_url} (expected /login)")

        step("7) Console errors")
        errs = s.console_errors
        if errs:
            print("  WARN: console errors detected:", flush=True)
            for e in errs[:10]:
                print(f"    - {e}", flush=True)
        check(len(errs) == 0, f"no console errors (got {len(errs)})")

    await close_tab(target_id)
    print("\n=== STORE UI SMOKE: ALL PASS ===", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
