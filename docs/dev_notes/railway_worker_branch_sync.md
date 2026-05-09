# Railway Worker 分支同步流程

> 用途：當 backend 改了 production / custom / upload 等 worker 會讀的 code，
> 但 admin / store 操作後 production job 失敗、Celery 立刻 0.x 秒結束，
> 一定要先檢查這條清單。
>
> 紀錄日期：2026-05-09。下次對話遇到「task 0.x 秒 succeeded 但 job status=failed」直接照這個流程。

---

## 為什麼會踩到這個雷

Railway 上有兩個 service 共用同一份 Docker image，但**綁不同 git 分支**：

| Service | 分支 | 用途 |
|---|---|---|
| `paint-web` | `master` | FastAPI web，admin / store / customer endpoint |
| `paint-worker` | `deploy/worker` | Celery worker，跑 production job |

**deploy/worker 是 master 砍掉前端 + 加 railway.toml 的歷史快照。**
deploy/worker 不會自動 sync master — 必須手動把 backend 改動同步進去，否則 worker 永遠跑分支建立當時的 backend code。

歷史上 deploy/worker 從建立後沒同步過任何 backend 改動 — 落後 master 7901 行。
這次的 production/tasks.py worker fix（commit `d8b2557`）push 到 master 後 web 立刻部署生效，但 worker 完全沒拿到。

---

## 怎麼快速確認是這個問題

**症狀**：
- admin 端從客製申請點「前往製作」→ 建 job 成功（DB 有記錄）
- worker log 顯示 task received → **0.x 秒 succeeded（None return）**
- job status=failed，notes 訊息對不上你最近寫的 code（因為跑的是舊版）
- web 改動一切正常（customer 端 API 行為符合最新 code）

**驗證**：
```bash
# 1. 看 web 是否有最新 code（用一個 master 上新加的 endpoint）
curl https://paint-web-production.up.railway.app/openapi.json | grep "新加的路徑"

# 2. 看 Railway dashboard：paint-worker 服務 → Deployments → 最新 deploy 的 commit hash
#    若不是 master HEAD 而是某個 deploy/worker 上的舊 commit → 確認踩雷
```

也可以直接觸發一次新 job 看 notes 是否符合最新 code 的 message：

```python
# backend/scripts/_probe_worker_version.py 風格
import asyncio, re, httpx
async def main():
    async with httpx.AsyncClient(base_url='https://paint-web-production.up.railway.app') as c:
        r = await c.post('/api/v1/admin/auth/login', json={'email': '...', 'password': '...'})
        cookie = {'Cookie': f'access_token={...}'}
        # 拿一個 photo 已上傳的 custom_request id
        # POST /admin/production/jobs (custom_request_id, jobs:[...])
        # GET /admin/production/jobs/{new_id} → 看 notes
        # 若 notes 內容不是最新 code 的 _mark_failed_with_notification 訊息 → worker 跑舊 code
```

---

## 修復流程（4 步）

### 步驟 1：切到 deploy/worker

```powershell
git fetch --all
git checkout deploy/worker
```

### 步驟 2：用 master 的 backend + paint-by-number 覆蓋

```powershell
git checkout master -- backend/ paint-by-number/
git status --short  # 確認沒有不該帶的東西（store/, admin/ 不應該出現）
```

**為什麼用 `git checkout master --` 而不是 `git merge master`**：
- merge 會把 master 砍掉的 store/, admin/ 整批帶回來，破壞 deploy/worker「只有後端」的設計
- checkout 路徑只覆蓋指定資料夾，乾淨

### 步驟 3：commit + push 兩個 remote

```powershell
git commit -m "sync(deploy/worker): backend + paint-by-number 從 master 完整同步"
git push origin deploy/worker
git push yizhen-lili deploy/worker
```

memory `project_git_remotes.md` 提過 repo 有兩個 remote — 都要 push（Railway 可能連任一個）。

### 步驟 4：等 Railway worker rebuild

Image 含 torch (~800MB) + SAM model (~375MB)，第一次 cold build ~15 分鐘；增量 build（只動 backend layer）約 2-3 分鐘。

驗證 worker 是否吃到新 code：
- Railway dashboard → paint-worker → Deployments → 最新 deploy commit = 你剛才 push 的 hash ✓
- trigger 一個新 job → poll 看 notes 是否變最新訊息 ✓

---

## 預防：master 改完 backend 該怎麼做

**短期（手動）**：每次改 backend 完並 push master 後，立即跑步驟 1-3 把 deploy/worker 同步。

**長期（建議重構）**：取消 deploy/worker 分支，讓 paint-worker service 也綁 master，靠 railway.toml 或 service 的 `Start Command` 區分 web / worker（同一份 code 兩種啟動命令）。這樣就不會有兩條分支不一致的問題。

或者：寫一個 GitHub Action，master push 時自動把 backend / paint-by-number 同步到 deploy/worker。

---

## 完整反例：這次踩雷的時間軸

```
T+0    push master commit d8b2557 (worker fix)
       → paint-web 自動 rebuild + deploy ✓
       → paint-worker 不動（綁 deploy/worker）✗

T+5    user 從 admin 點「前往製作」→ task 0.2s 結束 → job failed
       (notes: 舊版「缺少 image_id」訊息)

T+10   user dashboard 點 Redeploy paint-worker → restart same image
       (還是舊 code，notes 不變)

T+15   git checkout deploy/worker
       git checkout master -- backend/ paint-by-number/
       commit + push deploy/worker
       → Railway 自動 rebuild paint-worker (~3 分鐘)
       → worker 跑新 code ✓
```

---

## 相關 memory

- `project_git_remotes.md` — repo 兩個 remote（origin / yizhen-lili），push 要兩個都推
- `feedback_test_before_handoff.md` — 寫完 code 必須自己跑完所有測試，包括 production worker 端到端流程
