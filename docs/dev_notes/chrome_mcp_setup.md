# Chrome DevTools MCP 開啟流程（Windows）

> 用途：讓 Claude Code 能透過 Chrome DevTools MCP 驅動真實瀏覽器，做 e2e 測試
> （點擊、上傳、查 DOM、看 Network、看 Console）。
>
> 紀錄日期：2026-05-09。每次新對話需要 Chrome MCP 時可以直接照這個流程。

---

## 為什麼需要這流程

Claude Code 的 `mcp__chrome-devtools__*` 工具假設 Chrome 已經啟動且開啟 CDP（Chrome
DevTools Protocol）port 9222。**如果 Chrome 沒開或沒開 CDP，所有 MCP 呼叫會回**：

```
Could not connect to Chrome. Check if Chrome is running.
Cause: Failed to fetch browser webSocket URL from http://127.0.0.1:9222/json/version
```

這時要做兩件事：(1) 啟動 Chrome 帶 `--remote-debugging-port=9222` (2) 開啟想測的網址。

---

## 完整開啟流程（4 步）

### 步驟 1：啟動 Chrome 帶 CDP

PowerShell：

```powershell
Start-Process "chrome.exe" -ArgumentList @(
  "--remote-debugging-port=9222",
  "--user-data-dir=$env:TEMP\chrome-cdp-admin-test",
  "https://yiimui-admin.vercel.app/admin/content?tab=cases"
)
```

**重點**：
- `--remote-debugging-port=9222` 必填，這是 MCP 連的 port
- `--user-data-dir=$env:TEMP\<隨意名>` 必填 — Chrome 已經有開的視窗會卡 CDP，
  指定一個全新 user-data-dir 確保是獨立 instance
- 最後一個參數是要直接打開的 URL

### 步驟 2：等待 CDP 就緒

```bash
until curl -sf http://localhost:9222/json/version >/dev/null; do sleep 0.5; done
echo READY
```

通常 1-3 秒。

### 步驟 3：確認 MCP 看得到 page

```python
mcp__chrome-devtools__list_pages
```

如果回 "No page selected" 或空 list，表示 MCP 沒抓到頁。可能是 Chrome 啟動時開的
網址不在 MCP 的 page list（例如 Chrome welcome / Google sign-in 蓋在前面）。
這時用 CDP REST 強制開新 tab：

```bash
curl -s -X PUT 'http://localhost:9222/json/new?<目標URL>' | python -m json.tool
```

例如：

```bash
curl -s -X PUT 'http://localhost:9222/json/new?https://yiimui-admin.vercel.app/admin/content?tab=cases'
```

成功後 MCP 立刻看得到。

### 步驟 4：選擇 page 開始操作

```python
mcp__chrome-devtools__list_pages
# 看哪個是目標 URL，記下 pageId

mcp__chrome-devtools__select_page(pageId=N)
```

之後 `take_snapshot` / `click` / `fill` / `upload_file` / `evaluate_script` /
`list_network_requests` / `list_console_messages` 都可用。

---

## 常用驗證流程（admin 案例上傳為例）

```python
# 1. 拍 a11y 快照拿 uid
mcp__chrome-devtools__take_snapshot

# 2. 點按鈕（用 uid）
mcp__chrome-devtools__click(uid="N_M")

# 3. 上傳檔案到 file input（用 uid）
mcp__chrome-devtools__upload_file(uid="N_M", filePath="d:/path/to/file.jpg")

# 4. 看 fetch / xhr 是否打到對的 endpoint
mcp__chrome-devtools__list_network_requests(resourceTypes=["fetch", "xhr"])

# 5. 看是否有 console error
mcp__chrome-devtools__list_console_messages(types=["error", "warn"])

# 6. 跑 JS 看 Vue state / DOM details
mcp__chrome-devtools__evaluate_script(function="() => { return document.querySelector('[role=\"dialog\"]')?.innerHTML }")
```

---

## 踩過的雷 / 注意事項

### 雷 1：`upload_file` 工具有時候會 fail with "did not trigger a file chooser"

CDP 的檔案上傳機制需要對應 `<input type="file">` 接受檔案。如果 MCP 拿到的是
`<button>` 元素而非 `<input>`，且 button click 不能觸發 file chooser（例如
display:none 的 input、或 button + JS .click() 模式在某些環境失效），
upload_file 會 fail。

**對策**：
- 改用 `<label>` 直接包 `<input type="file">`（HTML 標準 label/input 連動）
- input 用 sr-only 模式（absolute + opacity:0 + clip rect）而非 `display:none`
- 把 file input 本身的 uid（不是按鈕的 uid）傳給 upload_file

### 雷 2：MCP `select_page(pageId)` 看不到目標 tab

可能 Chrome 啟動時打開了多個 tab（例如歡迎頁 / sync 頁），目標頁不在 list。
用 CDP REST 開新 tab（步驟 3 的 fallback）。

### 雷 3：CDP 連到 Chrome 後 MCP 仍顯示 "No page selected"

`select_page(pageId=0)` 也回錯。原因是 MCP client 自己的內部 state 沒同步。
解法：用 `list_pages` 先掃一次 → `select_page(pageId=正確的數字)`。如果還不行，
關掉所有 MCP 連線並從步驟 1 再來一次（Chrome 進程不需要重啟）。

### 雷 4：JS-injected file 跟真實 click 行為不同

`input.dispatchEvent(new Event('change'))` 會觸發 onChange 但 **不算 user gesture**。
某些 API（如 `requestFileSystem`、`navigator.clipboard.write`）需要 user gesture
才會生效。要驗證真實使用體驗請用 `mcp__chrome-devtools__click(uid)` 模擬真實 click。

### 雷 5：Vercel deploy 後 MCP page 還在舊版

需要 reload：

```python
mcp__chrome-devtools__navigate_page(type="reload", ignoreCache=True)
```

`ignoreCache=True` 強制繞過 disk cache。

---

## 退出 / 清理

開發完關掉 Chrome：

```powershell
# 找到該 user-data-dir 的 chrome 進程關掉
Get-Process -Name chrome | Where-Object {
  (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -like "*chrome-cdp-admin-test*"
} | Stop-Process -Force
```

或直接關 Chrome 視窗。

`$env:TEMP\chrome-cdp-admin-test\` 會留下 user data，下次再用 MCP 時繼承
cookies / 登入狀態（很方便）。要全清就刪整個資料夾。

---

## 一次性快速啟動 script

```powershell
# scripts/start-admin-mcp-chrome.ps1
$URL = if ($args[0]) { $args[0] } else { "https://yiimui-admin.vercel.app" }
$DataDir = "$env:TEMP\chrome-cdp-admin-test"

if (-not (Test-Path $DataDir)) { New-Item -ItemType Directory -Path $DataDir | Out-Null }

Start-Process "chrome.exe" -ArgumentList @(
  "--remote-debugging-port=9222",
  "--user-data-dir=$DataDir",
  $URL
)

# 等 CDP 就緒
$timeout = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $timeout) {
  try {
    Invoke-WebRequest -Uri "http://localhost:9222/json/version" -UseBasicParsing -TimeoutSec 1 | Out-Null
    Write-Host "Chrome CDP ready at http://localhost:9222"
    break
  } catch { Start-Sleep -Milliseconds 500 }
}
```

呼叫：`pwsh scripts/start-admin-mcp-chrome.ps1` 或加上 URL。

---

## 環境需求

- Windows 10/11
- Chrome 已安裝（路徑通常 `C:\Program Files\Google\Chrome\Application\chrome.exe`）
- PowerShell 5+ 或 7
- curl（Windows 10+ 內建）

如果 `chrome.exe` 不在 PATH，用完整路徑：

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 ...
```
