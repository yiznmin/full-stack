"""更新 5 個資訊頁的內容（針對 production 寫好的精緻版）。

設計：
- 預設 dry-run：只比對差異不寫入
- --apply 才真的 PUT；會覆蓋現有內容（即使 user 已手改）
- --skip-modified：若內容跟 seed_content.py 預設值不同（表示 user 改過），skip
  這個組合 = 「只更新沒人手改過的」最安全

用法：
    cd backend
    venv/Scripts/python scripts/update_info_pages.py            # dry-run（看 diff）
    venv/Scripts/python scripts/update_info_pages.py --apply    # 強制覆蓋
    venv/Scripts/python scripts/update_info_pages.py --apply --skip-modified
"""
import argparse
import asyncio
import os
import re
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))
from seed_content import PAGES as SEED_DEFAULT_PAGES  # noqa: E402

BACKEND_URL = "https://paint-web-production.up.railway.app"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "yizn.min@gmail.com")
ADMIN_PWD = os.environ.get("ADMIN_PWD", "aa0965721667")


# ── 5 個更完整的內容（取代 seed_content.py 的最小版本）──────────────────────────


SIZE_GUIDE_CONTENT = """## 該選多大？跟著畫面感覺走

從 20×20 的書桌小品，到 60×60 的客廳主視覺，找到適合你空間的那一幅。

---

## 首波 4 個尺寸

我們最常被選的 4 個尺寸 — 對應日常空間，從桌上小品到沙發牆都有。

### 20×20 cm — 桌上小品

- ≈ 一張 CD 大小
- 📍 書桌、床頭櫃、層架小角
- 🎨 迷你花卉、寵物大頭照
- 🕒 半天 ~ 一天可完成

### 30×30 cm — 一本雜誌大小

- ≈ 一本雜誌大小
- 📍 書桌、玄關、茶几
- 🎨 單一花朵、單一動物
- 🕒 1 ~ 2 天

### 30×40 cm — A3 直幅

- ≈ A3 紙
- 📍 沙發牆、臥室掛畫
- 🎨 風景、人物半身、寵物全身
- 🕒 1 週左右

### 40×50 cm — 螢幕大小

- ≈ 筆電打開的螢幕
- 📍 客廳主視覺、玄關大牆
- 🎨 完整風景、家庭合照、紀念場景
- 🕒 2-3 週

---

## 想做更大？這幾個尺寸最適合客製

### 40×40 cm — 客製入門款

正方形構圖，適合單一寵物、單一人像。

### 50×50 cm — 客製主流款

最受歡迎的客製尺寸，適合情侶、寵物全身、家庭照。

### 50×60 cm — 客製旗艦款

橫幅大尺寸，適合家庭橫照、情侶橫照、紀念場景。

---

## 完整尺寸與參考售價

| 尺寸 | 參考售價 | 超商取貨 |
|------|---------|---------|
| 20×20 | NT$ 205–296 | ✅ 可 |
| 30×30 | NT$ 309–416 | ✅ 可 |
| 30×40 / 40×30 | NT$ 397–518 | ✅ 可 |
| 30×50 / 40×40 / 50×30 | NT$ 413–537 | ✅ 可 |
| 30×60 / 40×50 / 50×40 | NT$ 501–638 | ✅ 可 |
| 40×60 / 60×40 / 50×50 | NT$ 517–657 | ⚠️ 建議宅配 |
| 50×60 / 60×50 | NT$ 605–759 | ⚠️ 建議宅配 |
| 60×60 | NT$ 693–860 | ⚠️ 建議宅配 |

> 任一邊長超過 40 cm 的尺寸建議改選宅配，以避免超商包裹尺寸限制。售價會依難易度與細緻度加乘，實際售價以商品頁標示為準。

---

## 框架規格

- **畫布材質**：加厚棉麻織布裱於 1.5 cm MDF 板上
- **表面**：已上 acrylic primer 底劑，可直接上色
- **完成後**：自帶背框，無需額外裱框，可直接掛牆
"""


SHIPPING_CONTENT = """## 下單前，你會想知道的幾件事

下面是付款、製作、出貨、運費的所有規則 — 寫得有點直白，但希望省下你來回詢問的時間。

---

## 付款方式

> **銀行轉帳**

下單後 24 小時內完成轉帳並回填末五碼，即可進入製作流程。

> 為什麼是銀行轉帳？
> 易木 YIIMUI 是一個小型獨立品牌，把信用卡手續費省下來，
> 換成更好的顏料、更紮實的畫布、更友善的減塑包裝。
> 一筆轉帳的時間，是我們之間第一個共同完成的小儀式。

---

## 製作天數

| 商品類型 | 天數 |
|---------|------|
| 現成款 | 5 – 10 個工作天 |
| 客製款 | 轉檔 1–2 天 + 確認後印製 5–10 天 |

> **節慶提醒**
> 母親節、情人節、聖誕節等節日前下單的客人，
> 建議至少預留 14 天緩衝。
> 我們是手工為你準備每一份 kit，趕件可能會犧牲品質。

---

## 出貨方式

| 方式 | 費用 |
|------|------|
| 超商取貨 | NT$ 60 |
| 宅配 | NT$ 120 |

> 任一邊長超過 40 cm 的尺寸建議改選宅配，以避免超商包裹尺寸限制。

---

## 運費規則

- **現成款**：滿 **NT$ 1,000** 免運
- **客製款**：依實際運送方式收取

> 客製款是為你獨立準備的作品，從照片轉檔到顏料配色都是專屬製作。因此客製款的運費獨立計算，不參與滿額活動。

---

## 訂單流程

1. **付款確認**：管理員核對您提供的轉帳資訊（24 小時內）
2. **進入製作**：現貨商品立即備貨；客製商品安排 5–10 天製作期
3. **打包出貨**：以物流寄出，發送出貨通知 email + 站內通知
4. **追蹤狀態**：可在「我的訂單」查詢即時物流進度
5. **完成收貨**：物流送達後請確認收貨，協助我們關單
"""


CUSTOM_PROCESS_CONTENT = """## 有些照片，值得花一點時間慢慢畫

你不用會畫畫。把那張對你有意義的照片交給我們，把它變成可以親手完成的畫。

---

## 四個步驟，把照片變成畫

### 01　選尺寸 + 上傳照片

選擇你想要的畫布尺寸，上傳一張對你有意義的照片。

### 02　我們幫你轉成線稿

1–2 個工作天內，我們會把照片轉成可以畫的線稿並完成報價。

### 03　你確認、可微調

你會看到線稿與報價，可以微調最多 **3 次**，直到你滿意。

### 04　印製寄出

你按下「確認製作」，我們開始印製、配料、寄出。

> ※ 按下「確認製作」後即進入印製階段，**不可退換**。
> 確認前若有疑問，可以無限次討論。

---

## 怎麼選一張適合的照片？

### ✓ 適合

- **主體清楚** — 人 / 寵物 / 物件佔畫面 1/2 以上
- **光線充足** — 自然光最好
- **解析度夠** — 手機原檔即可
- **背景單純** — 純色牆、單色布料最佳

### ✗ 不適合

- **逆光、背光** — 看不清主體
- **過度模糊或晃動**
- **低解析度截圖、社群縮圖**
- **過度複雜的背景**

不適合的照片我們會在報價前主動說明並建議調整方向。

---

## 智慧財產權說明

- ✅ **你自己的照片**：寵物、家人、朋友、自己 — 都歡迎
- ❌ **公眾人物肖像**：明星、偶像、卡通角色、品牌商標 — 不接受
- ❌ **他人攝影作品**：未取得授權的網路圖片 — 不接受

---

## 隱私承諾

您上傳的照片會儲存在私密路徑，**僅您與管理員可看見**。完成的作品如要展示在公開「客製案例」中，會主動徵詢您的同意。

> 客人可隨時要求刪除照片，刪除後本服務無法繼續。
"""


PRICING_REFERENCE_CONTENT = """## 客製大概多少錢？

客製照片的售價依**畫布尺寸**、**難易度**、以及照片實際內容調整。以下是各尺寸 × 難度的參考區間。

---

## 各尺寸參考售價（單位：NT$）

| 尺寸 | 入門 | 初級 | 中級 | 進階 |
|------|------|------|------|------|
| 20×20 | 240 | 290 | 360 | 440 |
| 30×30 | 380 | 460 | 580 | 700 |
| 30×40 | 480 | 580 | 680 | 880 |
| 40×40 | 530 | 640 | 800 | 990 |
| 40×50 | 600 | 720 | 900 | 1,110 |
| 50×60 | 800 | 960 | 1,200 | 1,480 |
| 60×60 | 920 | 1,100 | 1,380 | 1,700 |

> 完整 17 種尺寸 × 4 難易度的報價請於申請後由我們報出。

---

## 常見加費項目

| 項目 | 加費 |
|------|------|
| 人物 2 人 | +200 |
| 人物 3 人以上 | +400 |
| 寵物毛髮細節 | +250 |
| 複雜背景 | +300 |
| 限時加急（5 工作天內完成） | +500 |

---

## 試算範例

> **範例 1：** 30×40 cm 中級、單人物、無加急
> 基礎 NT$ 680，總計 **NT$ 680**

> **範例 2：** 40×50 cm 進階、家庭照（3 人）、複雜背景
> 基礎 NT$ 1,110 + 人物加費 400 + 背景加費 300 = **NT$ 1,810**

---

## 重要說明

- 上方為**參考區間**，**實際金額以管理員報價為準**
- 報價有效期 24 小時，可延長一次（再 +24h）
- 加入購物車後可與一般商品合併結帳
- 客製商品**不計入免運門檻**（除非使用免運券）
"""


REFUND_POLICY_CONTENT = """## 收到後，如果有狀況

為了讓每一份 kit 都能順利送達，退換貨的規則寫得有點清楚 — 但我相信你會理解。

---

## 現成款 退換貨

- ✓ **未拆封 7 天內可退貨**（運費自負）
- ✓ **瑕疵品 7 天內反映可換貨**（運費由易木負擔）
- ✗ **已拆封不可退** — 顏料、畫布拆封後無法復原
- ✗ **「畫起來不像」不適用退換貨**

---

## 客製款 退換貨

- ✓ **按下「確認製作」之前** — 可全額退款
- ✓ **線稿不滿意** — 最多可修改 **3 次**
- ✓ **瑕疵品 7 天內反映** — 可重新印製
- ✗ **按下「確認製作」之後不可退換**
- ✗ **「畫起來不像」不適用退換貨**
- ✗ **客人提供照片不適合導致的不滿不適用退換**

> **「確認製作」按鈕是客製流程的分水嶺。**
> 按下之前，所有討論都可以重來；按下之後，印製就會開始。
> 我希望你按下那一刻，是真的滿意了。

---

## 退款流程

1. 客戶申請退款（聯絡客服 / 站內訊息）
2. 管理員審核並標記「退款處理中」
3. 退款於 **5 個工作天**內匯回您的銀行帳戶
4. 客戶收到款項 → 在訂單頁點「我已收到退款」確認

退款處理中可在「我的訂單 → 退款」分頁追蹤狀態。

---

## 怎麼聯絡我們

瑕疵品、退換貨請透過以下方式聯絡：

- 訂單詳情頁的**站內訊息**（最快回覆）
- **Email**：service@yiimui.com
- **IG 私訊**：@yiimui

我們會在 **24 小時**內回覆你。
"""


PAGES_CONTENT = {
    "size_guide": ("尺寸指南", SIZE_GUIDE_CONTENT.strip()),
    "shipping": ("出貨流程", SHIPPING_CONTENT.strip()),
    "custom_process": ("訂製流程", CUSTOM_PROCESS_CONTENT.strip()),
    "pricing_reference": ("報價參考", PRICING_REFERENCE_CONTENT.strip()),
    "refund_policy": ("退款退貨政策", REFUND_POLICY_CONTENT.strip()),
}


# ── 主流程 ─────────────────────────────────────────────────────────────────────


def is_seed_default(slug: str, current_content: str) -> bool:
    """判斷 production 內容是否與 seed_content.py 預設值一致（user 沒手改）。"""
    for s, _t, c in SEED_DEFAULT_PAGES:
        if s == slug and c.strip() == current_content.strip():
            return True
    return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="實際寫入（否則 dry-run 只看 diff）")
    parser.add_argument(
        "--skip-modified",
        action="store_true",
        help="若 production 內容已被 user 編輯（與 seed 預設不同），skip 不覆蓋",
    )
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=30, base_url=BACKEND_URL) as c:
        r = await c.post(
            "/api/v1/admin/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
        )
        m = re.search(r"access_token=([^;]+)", r.headers.get("set-cookie", ""))
        if not m:
            print("login failed")
            return
        cookie = {"Cookie": f"access_token={m.group(1)}"}

        updated = 0
        skipped = 0
        unchanged = 0

        for slug, (title, new_content) in PAGES_CONTENT.items():
            r = await c.get(f"/api/v1/pages/{slug}")
            if r.status_code != 200:
                print(f"  ! {slug}: GET status {r.status_code}, skip")
                continue
            current = r.json()
            current_content = current.get("content", "")

            if current_content.strip() == new_content.strip():
                print(f"  = {slug:24s} unchanged ({len(current_content)} chars)")
                unchanged += 1
                continue

            if args.skip_modified and not is_seed_default(slug, current_content):
                print(f"  ~ {slug:24s} user-edited, skip")
                skipped += 1
                continue

            old_len = len(current_content)
            new_len = len(new_content)
            arrow = "+" if new_len > old_len else "-"
            print(f"  {arrow} {slug:24s} {old_len} -> {new_len} chars")

            if args.apply:
                r = await c.put(
                    f"/api/v1/admin/pages/{slug}",
                    headers=cookie,
                    json={"title": title, "content": new_content},
                )
                if r.status_code == 200:
                    updated += 1
                else:
                    print(f"    ! PUT failed {r.status_code} {r.text[:100]}")

        if args.apply:
            print(f"\n{updated} updated, {skipped} skipped, {unchanged} unchanged")
        else:
            print(f"\n[DRY RUN] {len(PAGES_CONTENT) - unchanged - skipped} would update, "
                  f"{skipped} would skip, {unchanged} unchanged")
            print("加 --apply 才會實際寫入；加 --skip-modified 保留 user 已編輯的")


if __name__ == "__main__":
    asyncio.run(main())
