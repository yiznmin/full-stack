@echo off
REM 啟動專用於 Yiimui admin 開發的 Chrome（帶 remote debugging port）
REM 雙擊執行，Claude 的 chrome-devtools MCP 會 attach 到這個 Chrome
REM 用獨立 user-data-dir 避免影響你日常瀏覽器

set DEV_PROFILE=%USERPROFILE%\.yiimui-dev-chrome
set CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe

if not exist "%CHROME_EXE%" (
  echo Chrome 找不到，請確認路徑：%CHROME_EXE%
  pause
  exit /b 1
)

start "" "%CHROME_EXE%" ^
  --remote-debugging-port=9222 ^
  --user-data-dir="%DEV_PROFILE%" ^
  --no-first-run ^
  --no-default-browser-check ^
  http://localhost:5173/admin/dashboard

echo Chrome 已啟動，debug port 9222
echo 第一次開會像新瀏覽器（沒書籤、沒登入），那是正常的
echo 之後 Claude 會自動 attach
exit /b 0
