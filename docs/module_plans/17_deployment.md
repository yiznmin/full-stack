# 17. Railway 部署計畫書

> 用戶 Railway Pro Plan（24 GB RAM / 24 vCPU / 100 GB Shared Disk）。
>
> 部署觸發脈絡：Phase B SAM 推論 runtime 完成，但本地 Windows 跑 ViT image encoder forward
> 必 segfault（PyTorch + Windows 已知不穩）。Linux 容器內無此問題，部署到 Railway 後可
> 完整驗證 SAM e2e。Phase C（前端 Mask UI）等部署完再做，避免本地開發體驗卡住。

---

## 一、現況盤點

### 既有資產

| 項目 | 狀態 |
|---|---|
| backend FastAPI + Celery + Alembic | ✅ 完整（645 tests pass） |
| paint-by-number 引擎（mode=standard / sam_refine / sam_weighted） | ✅ |
| backend/.env（11 個 keys） | ✅ 本地可用 |
| backend Alembic migrations | ✅ |
| admin (Vite + Vue 3 + Pinia + TanStack Query) | ✅ 可 build |
| store frontend | ❌ 不存在（前台尚未建立，本次不部署） |

### 待解阻擋

| 阻擋 | 說明 |
|---|---|
| ❌ 沒 Dockerfile | backend 部署用 |
| ❌ 沒 railway.toml / nixpacks | Railway 部署配置 |
| ❌ Inkscape 寫死 Windows 路徑 | `paint-by-number/src/export_pdf.py:19` 寫死 `D:\Inkscape\bin\inkscape.exe` |
| ❌ 沒 .env.example | 11 個 env keys 沒列清單 |
| ❌ Firebase service account 注入策略 | JSON file mount vs base64 env var 未決 |
| ❌ Celery worker 服務拆分策略 | 跟 web 同 service 還是分開 service 未決 |
| ❌ admin 前端部署位置 | Vercel vs Railway static service vs 跟 backend 同 image |

---

## 二、架構決策（待確認）

### 決策 #1：paint-by-number/src/export_pdf.py Inkscape 路徑

**衝突**：CLAUDE.md + 記憶體 `feedback_pbn_gen_lock.md` 規定 `paint-by-number/src/*` 鎖定，但部署到 Linux 必須改 Inkscape 路徑。

**選項 A**：申請例外，把 `export_pdf.py` 內 `INKSCAPE` 改成讀環境變數 `INKSCAPE_PATH`，預設 `/usr/bin/inkscape`
- 優：最直接、單檔改動小、Linux/Windows 通吃
- 缺：違反鎖定規則（需用戶明確授權）

**選項 B**：backend wrapper 在 import 時 monkey-patch `paint_by_number.src.export_pdf.INKSCAPE`
- 優：不改 paint-by-number/src/
- 缺：monkey-patch fragile、未來維護困難、其他人 import 看不出來

**選項 C**：複製 export_pdf.py 邏輯到 backend/production/，徹底脫鈎
- 優：完全不依賴 paint-by-number/src/export_pdf.py
- 缺：邏輯重複（duplicate code），未來引擎升級時兩邊不同步

**建議：A**（用戶授權的單次例外）

**[已決議 2026-05-01：選項 A]** — 用戶授權單次例外。`export_pdf.py:19` 改成 `INKSCAPE = os.environ.get("INKSCAPE_PATH", r"D:\Inkscape\bin\inkscape.exe")`，本地 Windows 預設仍可跑，Linux 部署設 `INKSCAPE_PATH=/usr/bin/inkscape`。

### 決策 #2：Celery worker 服務拆分

**選項 A**：web + worker 同 service（一個 image，啟動腳本 fork web + worker）
- 優：Railway 計費單一 service、部署簡單
- 缺：擴容只能整體擴；worker 跑 SAM 時 RAM/CPU 競爭影響 web 回應

**選項 B**：web + worker 分兩個 Railway service（同一 image，不同 entrypoint）
- 優：獨立擴容、worker 跑重活不影響 web；Pro Plan 不在意多 service 計費
- 缺：兩個 service 要分別配 env vars（用 Shared Variables 解）

**建議：B**（Pro Plan 已付費，獨立擴容更穩）

**[已決議 2026-05-01：選項 B]** — backend-web 與 backend-worker 拆兩個 Railway service，共用同一個 Docker image，差別僅在 startCommand。理由：SAM ViT-B forward 吃 ~1-2GB RAM，跟 web 同容器會干擾 admin UI 體感；獨立擴容讓 worker 流量增長不影響 web。

### 決策 #3：Firebase service account 注入

**選項 A**：base64-encoded JSON 塞 env var `FIREBASE_CREDENTIALS_BASE64`，runtime 解碼存到 `/tmp/firebase.json` 再讓 firebase-admin 讀
- 優：整個 service account 在 Railway env var；不用 volume
- 缺：env var 字串很長（service account JSON 解 base64 後約 2KB）

**選項 B**：把 JSON 內容直接放 env var `FIREBASE_CREDENTIALS_JSON`（不 base64），runtime parse json
- 優：不用解碼步驟
- 缺：JSON 字串內含換行、特殊字元，Railway env var UI 處理可能踩雷

**選項 C**：用 Railway 的 file volume 上傳 firebase.json
- 優：直觀
- 缺：Pro Plan 雖支援 volume，但會跟 web/worker 兩個 service 都要 mount，配置複雜

**建議：A**（base64 是最穩定的字串注入方式）

**[已決議 2026-05-01：選項 A]** — base64-encoded JSON 塞 env var `FIREBASE_CREDENTIALS_BASE64`，runtime 解碼到 `/tmp/firebase.json` 後讓 firebase-admin 讀。

### 決策 #4：SAM 模型檔（375MB）放哪

memory `deployment_notes.md` 已決議：**Docker image 內含**（Dockerfile RUN curl 下載）。本計畫書沿用。

### 決策 #5：admin 前端部署位置

**選項 A**：Vercel（前端專業 host）
- 優：CDN、global edge、免費 tier 夠用、deploy preview
- 缺：跟 backend 在不同雲服務、CORS 設定要明確（已 admin_url env var 控制）

**選項 B**：Railway 同帳號 static service（serve dist/）
- 優：單一帳號管理、internal network 跟 backend 通訊
- 缺：Railway static service 沒 CDN（速度比 Vercel 慢一截）

**建議：A**（Vercel 對 Vue/Vite 體驗最好；CORS 已用 ADMIN_URL env var 配置）

**[已決議 2026-05-01：選項 A]** — admin 部署 Vercel，CDN + global edge；CORS 透過 backend `ADMIN_URL` env var 設定為 admin Vercel URL。

### 決策 #6：DB / Redis 用 Railway plugin？

Railway 提供官方 PostgreSQL + Redis plugin，自動注入 `DATABASE_URL` / `REDIS_URL` env var。
- **建議：是**。本地 dev 用本地 Postgres（既有 yiimui DB）+ Redis；正式環境用 Railway plugin。

**[已決議 2026-05-01：選項是]** — 用 Railway 官方 Postgres + Redis plugin，env var 自動注入。本地 dev 仍用本機既有 yiimui DB + 本機 Redis。

---

## 三、部署架構

確認 #1A + #2B + #3A + #4 image 內含 + #5A Vercel + #6 Railway plugins 後：

```
┌─────────────────────────────────────────────────────────────────┐
│                          Railway 專案                             │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │  backend-web │  │backend-worker│  │  PostgreSQL  │           │
│  │  (FastAPI)   │  │  (Celery)    │  │   plugin     │           │
│  │              │  │              │  │              │           │
│  │  same image  │  │  same image  │  │  Railway     │           │
│  │  uvicorn ..  │  │  celery -A.. │  │  internal    │           │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘           │
│         │                 │                                      │
│         │  shared env     │                                      │
│         │  vars           │                                      │
│         │                 │           ┌──────────────┐           │
│         │                 │           │    Redis     │           │
│         │                 │           │   plugin     │           │
│         │                 │           └──────────────┘           │
└─────────┼─────────────────┼───────────────────────────────────────┘
          │                 │
          ▼                 ▼
       ┌──────────────────────────┐
       │  Firebase Storage        │
       │  (圖片 / SAM mask)       │
       └──────────────────────────┘
          ▲
          │ CORS allowed
          │
   ┌──────┴───────┐
   │   Vercel     │
   │  admin       │
   │  (Vue/Vite)  │
   └──────────────┘
```

---

## 四、要建立 / 修改的檔案

| 動作 | 檔案 | 說明 |
|---|---|---|
| 新增 | `backend/Dockerfile` | python 3.12-slim + apt install inkscape + curl SAM model + uv/pip install requirements + COPY backend/ |
| 新增 | `backend/.dockerignore` | 排除 venv / __pycache__ / tests / .pytest_cache |
| 新增 | `backend/.env.example` | 11 個 keys 列表（無 secret 值） |
| 新增 | `backend/scripts/start_web.sh` | uvicorn entrypoint（讀 PORT env var） |
| 新增 | `backend/scripts/start_worker.sh` | celery worker entrypoint |
| 新增 | `backend/scripts/load_firebase_credentials.py` | base64 decode FIREBASE_CREDENTIALS_BASE64 → /tmp/firebase.json |
| 修改 | `backend/core/firebase.py` | 啟動時若 `FIREBASE_CREDENTIALS_BASE64` 存在，先呼叫 load_firebase_credentials |
| 修改（**例外開放**） | `paint-by-number/src/export_pdf.py` | INKSCAPE 改讀 env var `INKSCAPE_PATH`（fallback Windows 預設） |
| 新增 | `railway.toml` | services 定義（web + worker） |
| 新增 | `admin/vercel.json` | vue-router SPA fallback 設定 |
| 修改 | `admin/.env.production` 或 build env | VITE_API_URL → 指向 backend-web Railway URL |
| 新增 | `docs/deployment_runbook.md` | 部署、回滾、debug 步驟（給未來自己 / 維運人員看） |

---

## 五、Dockerfile 設計

```dockerfile
FROM python:3.12-slim

# 系統依賴
RUN apt-get update && apt-get install -y \
    inkscape \
    curl \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \   # cairosvg / svglib 需要
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps（先複製 requirements.txt 利用 layer cache）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# SAM model（375MB）— layer cache 命中後不重下
RUN mkdir -p /app/models \
 && curl -L https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth \
    -o /app/models/sam_vit_b.pth

ENV SAM_MODEL_PATH=/app/models/sam_vit_b.pth
ENV INKSCAPE_PATH=/usr/bin/inkscape
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 把 paint-by-number/src 也複製進來（engine.py 用 sys.path.insert 載入）
COPY paint-by-number/src /app/paint-by-number/src

# backend code 在最後（變更最頻繁、layer cache 早失效）
COPY backend /app

# Railway 給 PORT env var；start_web.sh 讀
EXPOSE 8000
CMD ["bash", "scripts/start_web.sh"]
```

worker 的 image 用同一份 Dockerfile，CMD 在 railway.toml 內 override 為 `bash scripts/start_worker.sh`。

---

## 六、railway.toml 設計

```toml
[build]
builder = "dockerfile"
dockerfilePath = "backend/Dockerfile"

[[services]]
name = "backend-web"
[services.deploy]
startCommand = "bash scripts/start_web.sh"

[[services]]
name = "backend-worker"
[services.deploy]
startCommand = "bash scripts/start_worker.sh"
```

---

## 七、env vars 清單

### 共用（Railway shared variables）
- `DATABASE_URL` — Postgres plugin 自動注入
- `REDIS_URL` — Redis plugin 自動注入
- `JWT_SECRET` — 手動填（256-bit random）
- `JWT_ALGORITHM` — `HS256`
- `RESEND_API_KEY` — 手動填
- `RESEND_FROM_EMAIL` — `noreply@<domain>`（待用戶提供 domain）
- `FRONTEND_URL` — store 還沒部署，先填空字串或 placeholder
- `ADMIN_URL` — Vercel admin 部署網址
- `FIREBASE_CREDENTIALS_BASE64` — service account JSON base64 編碼
- `FIREBASE_STORAGE_BUCKET` — `paint-by-number-d9fa3.firebasestorage.app`
- `SAM_MODEL_PATH` — `/app/models/sam_vit_b.pth`（也由 Dockerfile ENV 設）
- `INKSCAPE_PATH` — `/usr/bin/inkscape`

### 限 backend-web
（無）

### 限 backend-worker
（無）

### 不需注入（image 自帶）
- `PYTHONPATH`、`PYTHONUNBUFFERED` 由 Dockerfile ENV 提供

---

## 八、Alembic migrations

**首次部署**：在 Railway shell 內手動執行
```bash
cd /app && alembic upgrade head
```

**未來自動化選項**：
- A. 每次 deploy 自動跑 `alembic upgrade head`（在 start_web.sh 開頭加），優：自動化；缺：併發部署兩個 service 可能 race
- B. 維持手動，每次 release 走 release branch + 手動跑 migration

**[已決議 2026-05-01：選項 A，但只在 backend-web 跑]** — `start_web.sh` 開頭執行 `alembic upgrade head` 後再啟動 uvicorn；`start_worker.sh` **不**跑 migration（避免兩個 service 同時 alembic upgrade race）。實務上 Railway 的兩個 service 啟動有先後，但 alembic 內部 advisory lock 保證安全。

---

## 九、EVENT_MATRIX 對照

部署本身不觸發 EVENT_MATRIX 任何 Event；屬基礎設施工作。但**部署完後**所有現有 Events 才能在生產環境真實運作（之前都是本地 dev 環境）。

---

## 十、測試與驗收

### 部署驗收清單

依重要性排序，逐項手動驗收：

| 驗收項 | 預期 | 失敗影響 |
|---|---|---|
| Web service `GET /` | 200 | 服務沒起來 |
| Web service `GET /docs`（FastAPI Swagger） | 200 | 服務沒起來 |
| `POST /api/v1/auth/register` + login | 200 | DB 連線壞 / JWT 壞 |
| Resend email 寄出（驗證信） | 信箱收得到 | Resend API 壞 |
| Firebase upload signed URL | 可拿到 + 上傳成功 | Firebase 認證壞 |
| `POST /admin/production/jobs` mode=standard | 200 + Celery enqueue + worker run + DB 寫回 status=completed | Celery / Redis / paint-by-number 引擎壞 |
| `POST /admin/production/jobs/{id}/sam-mask` mode=sam_refine | 200 + mask_url 寫入 + mask_coverage > 0 | **SAM 終於真實能跑（Phase B 主要驗收）** |
| `GET /admin/production/jobs/{id}/export-pdf` | 200 + 下載 PDF | Inkscape 路徑壞 |

### 預期問題與排查

| 症狀 | 可能原因 | 排查 |
|---|---|---|
| service 啟動 30 秒就被 Railway kill | 健康檢查 fail | 檢查 `start_web.sh` log；FastAPI 可能 import 失敗（缺 dep） |
| SAM 推論 OOM | Pro Plan 24GB 應夠，但若 worker + web 同 service 競爭 | 確認 #2B 已分服務；觀察 worker memory 用量 |
| Firebase 401 | service account JSON 解碼錯 | 確認 base64 編碼正確；test runtime 印出 client_email |

---

## 十一、待確認事項

### 技術決策（已全數釘定 2026-05-01）

| # | 議題 | 決議 |
|---|---|---|
| 1 | export_pdf.py Inkscape 路徑 | **A** 例外開放，env var `INKSCAPE_PATH` |
| 2 | backend web/worker 拆分 | **B** 分兩個 Railway service |
| 3 | Firebase 注入 | **A** base64 env var |
| 4 | SAM model 部署 | image 內含（既有 memory 決議） |
| 5 | admin 部署位置 | **A** Vercel |
| 6 | DB/Redis | Railway plugin |
| 7 | Alembic auto migrate | **A** start_web.sh 跑（worker 不跑） |

### 用戶資訊（已釘定 2026-05-01）

- **Resend domain**：暫未設定 → 先用 `onboarding@resend.dev`（限制：只能寄 `yizn.min@gmail.com`）。Phase 17.4 買到 domain 後再 verify + 切 from。
- **Domain**：暫未購買 → 先用 Railway / Vercel 預設網址。Phase 17.4 推遲。
- **Railway 帳號**：已有，但跟 PaintLearn GitHub repo 不同 GitHub 帳號
- **Railway 觸發方式**：**X — GitHub App 授權到 repo**（push 自動 redeploy）
- **Railway 專案名**：**yiimui**
- **admin domain**：**A — Vercel 預設**（`xxx.vercel.app`）
- **admin/api 自訂 domain**：Phase 17.4 再做

### Phase 17 階段拆分（domain 推遲）

| Phase | 範圍 | 依賴 domain |
|---|---|---|
| **17.1** | Dockerfile + scripts + export_pdf.py + .env.example + .dockerignore + railway.toml + admin/vercel.json | ❌ |
| **17.2** | Railway 部署 backend（`*.up.railway.app`）+ Postgres/Redis plugin + alembic + 驗收前 5 項 | ❌ |
| **17.3** | Vercel 部署 admin（`*.vercel.app`）+ 驗收後 3 項（含 SAM e2e） | ❌ |
| **17.4**（domain 買到再做） | Cloudflare DNS + 綁 admin/api 自訂 domain + Resend verify | ✅ |

---

## 十二、執行節奏（Definition of Done）

依 CLAUDE.md「分段節奏」拆三階段：

1. **17.1**：Dockerfile + .dockerignore + .env.example + start scripts + 修 export_pdf.py + 本地 Docker build 驗證 image 起得來、容器內 SAM 能跑（Linux Docker on Windows 證實 segfault 真的是 Windows 主機特有）
2. **17.2**：railway.toml + 推 Railway + 接 Postgres / Redis plugin + alembic + 走部署驗收清單前 5 項
3. **17.3**：admin 部署 Vercel + 配 ADMIN_URL CORS + 走部署驗收清單後 3 項（含 SAM e2e 真實驗收）

每階段結束 commit 一次。
