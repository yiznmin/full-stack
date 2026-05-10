# yiimui.com 網域串接手冊

> **目標**：把 `yiimui.com` 串到現有 Vercel + Railway + Resend 部署，讓客戶看到漂亮網址、收得到 email。
>
> **時間**：30–60 分鐘（DNS 傳遞最慢）
>
> **前置**：已在 Cloudflare 購買 yiimui.com ✅

---

## 規劃的 URL 結構

| URL | 指向 | 用途 |
|---|---|---|
| `yiimui.com` | Vercel store project | 客戶商店首頁 |
| `www.yiimui.com` | Vercel store project | 別名（→ 自動 redirect 到 root） |
| `admin.yiimui.com` | Vercel admin project | 後台管理 |
| `api.yiimui.com` | Railway backend | FastAPI（也可選擇不開，繼續走 Vercel rewrite） |
| `noreply@yiimui.com` | Resend | 系統通知信寄件人 |
| `service@yiimui.com` | Cloudflare Email Routing → 你 Gmail | 客服信箱（轉寄到 Gmail） |

---

## 步驟 1：在 Cloudflare 加 DNS Records（5 分鐘）

進入 Cloudflare → 你的 yiimui.com → **DNS** → **Records**

### 1.1 store 前端（root + www）

點「Add record」：

| 欄位 | 值 |
|---|---|
| Type | `CNAME` |
| Name | `@`（代表 root，即 yiimui.com） |
| Target | `cname.vercel-dns.com` |
| Proxy status | **DNS only**（灰色雲、不要橘色） ⚠️ |
| TTL | Auto |

再加一條 www：

| 欄位 | 值 |
|---|---|
| Type | `CNAME` |
| Name | `www` |
| Target | `cname.vercel-dns.com` |
| Proxy status | **DNS only**（灰色雲）⚠️ |

> ⚠️ **Proxy 一定要關（灰色雲）**：Vercel 自己有 SSL + CDN，Cloudflare 的橘色雲會跟它打架。

### 1.2 admin 後台

| 欄位 | 值 |
|---|---|
| Type | `CNAME` |
| Name | `admin` |
| Target | `cname.vercel-dns.com` |
| Proxy status | DNS only |

### 1.3 api 後端（連 Railway）

| 欄位 | 值 |
|---|---|
| Type | `CNAME` |
| Name | `api` |
| Target | `paint-web-production.up.railway.app` |
| Proxy status | DNS only |

### 1.4 完成後 DNS 列表應該長這樣

```
A     @       <Vercel IP，自動>          DNS only
CNAME www     cname.vercel-dns.com       DNS only
CNAME admin   cname.vercel-dns.com       DNS only
CNAME api     paint-web-production.up.railway.app  DNS only
```

---

## 步驟 2：Vercel 加 Custom Domain（5 分鐘）

### 2.1 store project

進入 Vercel → **store project** → **Settings** → **Domains** → Add：

1. 輸入 `yiimui.com` → Add → Vercel 會檢查 DNS（剛剛設好的）→ 綠色 valid ✓
2. 再 Add 一條 `www.yiimui.com` → Vercel 自動設成 redirect to apex

如果 Vercel 跳出說「請設 A record 指 76.76.21.21」就照做（替代 CNAME 方案）。

### 2.2 admin project

Vercel → **admin project** → **Settings** → **Domains** → Add `admin.yiimui.com`

---

## 步驟 3：Railway 加 Custom Domain（5 分鐘）

進入 Railway → **backend service**（FastAPI）→ **Settings** → **Networking** → **Custom Domain**

1. 輸入 `api.yiimui.com` → Add
2. Railway 顯示「請設 CNAME 指向 xxx.up.railway.app」→ 你已經設好（步驟 1.3） → 等綠燈

---

## 步驟 4：Resend 驗證 yiimui.com（5 分鐘 + DNS 傳遞 1–10 分鐘）

進入 [resend.com/domains](https://resend.com/domains) → **Add Domain**

1. 輸入 `yiimui.com` → Add
2. Region 選 **Asia Pacific (Tokyo)**（亞洲速度最快）
3. Resend 吐出 4–6 條 DNS records，類似：

```
TYPE     NAME                  VALUE
TXT      send                  "v=spf1 include:amazonses.com ~all"
TXT      _dmarc                "v=DMARC1; p=none;"
CNAME    resend._domainkey     resend.domainkey.xxx.amazonses.com
TXT      send                  ...DKIM 公鑰...
```

4. 把這些 records **一條一條複製到 Cloudflare DNS**（步驟 1 同樣介面）：
   - Type: 對應的 TYPE
   - Name: 對應的 NAME（**不要加 .yiimui.com，Cloudflare 會自動補**）
   - Content / Target: 對應的 VALUE
   - Proxy status: **DNS only**（灰色雲）⚠️
5. 全部加完 → 回 Resend 點 **Verify Domain** → 通常 1–5 分鐘綠燈

---

## 步驟 5：Cloudflare Email Routing（5 分鐘，免費）

> 用途：讓 `service@yiimui.com` 收到的信自動轉寄到你 yizn.min@gmail.com，你還是用 Gmail 收 / 回信。

進入 Cloudflare → yiimui.com → **Email** → **Email Routing** → **Get started**

1. Cloudflare 會自動加幾條 MX records 到你的 DNS（接受）
2. **Routes** → Add → Custom address
3. 加幾條轉寄規則：

| Custom address | Action | Destination |
|---|---|---|
| `service@yiimui.com` | Send to | yizn.min@gmail.com |
| `contact@yiimui.com` | Send to | yizn.min@gmail.com |
| `hello@yiimui.com` | Send to | yizn.min@gmail.com |

每加一個，Cloudflare 會寄驗證信給你 Gmail，點連結確認後生效。

> 💡 想再進一步「也能從 yourname@yiimui.com 寄信」要設 Gmail Send-As + SMTP，這個之後可選做。

---

## 步驟 6：更新 Railway env（我會提示你改哪些）

進入 Railway → **backend service** → **Variables** → 改下列項目：

| Variable | 改成 |
|---|---|
| `RESEND_FROM_EMAIL` | `易木 YIIMUI <noreply@yiimui.com>` |
| `FRONTEND_URL` | `https://yiimui.com` |
| `ADMIN_URL` | `https://admin.yiimui.com` |

改完 Railway 會自動 redeploy（約 1–2 分鐘）。

---

## 步驟 7：驗證全部串通了

依序測試：

1. **網站開得起來**
   - 瀏覽器打 `https://yiimui.com` → 看到 store 首頁 ✓
   - `https://admin.yiimui.com` → 看到 admin 登入頁 ✓
   - `https://api.yiimui.com/health` → 看到 `{"status": "ok"}` ✓

2. **Email 寄得出去**（最關鍵）
   - 用一個跟 yizn.min 不同的 Gmail（朋友的、第二個帳號都行）
   - 註冊 yiimui.com 上的會員
   - 收件夾應該收到「易木 YIIMUI」寄來的驗證信 ✓
   - 之前不行：寄件人 `onboarding@resend.dev` + 只能寄到 yizn.min
   - 現在應該：寄件人 `noreply@yiimui.com` + 寄到任何 email

3. **客服信能轉寄**
   - 用任何 Gmail 寄信到 `service@yiimui.com`
   - 你 yizn.min 的 Gmail 收件夾應該收到 ✓

---

## 檢查清單

- [ ] Cloudflare DNS 加了 3 條（@、admin、api）+ Resend 給的 4–6 條
- [ ] Vercel store project 加了 yiimui.com 與 www.yiimui.com（綠燈）
- [ ] Vercel admin project 加了 admin.yiimui.com（綠燈）
- [ ] Railway backend 加了 api.yiimui.com（綠燈）
- [ ] Resend yiimui.com Verified（綠燈）
- [ ] Cloudflare Email Routing service@yiimui.com 設定 + Gmail 確認
- [ ] Railway env 改了 RESEND_FROM_EMAIL / FRONTEND_URL / ADMIN_URL
- [ ] Redeploy 完成
- [ ] 測試 email 真的寄到非 yizn.min 的 Gmail

---

## Troubleshooting

### 「Vercel 顯示 Invalid Configuration」
- 通常是 Cloudflare proxy 沒關。確認那條 record 是**灰色雲不是橘色雲**。

### 「Resend Verify 一直紅燈」
- DNS 傳遞要時間，平均 5 分鐘但偶爾 30 分鐘以上
- 確認 Cloudflare Records 那邊 Name 沒加錯（不要寫 `send.yiimui.com`，只寫 `send`）

### 「Email 寄出去但客戶說沒收到」
- 看 Resend Dashboard → Emails → 找該封看 status
- `delivered` ✓ → 可能進客戶垃圾信
- `bounced` → 對方信箱不存在或拒收
- `failed` → 我方 SPF/DKIM 沒設好，回頭驗證

### 「DNS 設好了但網站打不開」
- 等 5–30 分鐘 DNS 傳遞
- 可以用 [whatsmydns.net](https://whatsmydns.net) 查全球 DNS 是否更新到

---

## 之後想要的 polish（之後再說）

- `api.yiimui.com` 接好後，把 `vercel.json` 的 rewrite destination 從 `paint-web-production.up.railway.app` 改成 `api.yiimui.com`（更清晰、Railway 換產品時不用改 code）
- DMARC 進階設 `p=quarantine` / `p=reject`（提高 anti-spoofing）
- Cloudflare WAF 規則（基礎防 DDoS）
