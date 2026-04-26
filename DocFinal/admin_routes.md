# 管理員後台路由結構

---

| 路由 | 頁面 | 說明 |
|------|------|------|
| `/admin/login` | 登入頁 | 公開，其餘路由需登入 |
| `/admin` | 儀表板 | 跳轉至 `/admin/orders` |
| `/admin/orders` | 訂單管理 | 訂單列表 + 統計 |
| `/admin/orders/:id` | 訂單詳情 | 含生產進度操作 |
| `/admin/custom-requests` | 客製申請管理 | 列表 + 篩選 |
| `/admin/custom-requests/:id` | 客製申請詳情 | 含訊息對話、報價操作 |
| `/admin/products` | 商品管理 | 商品列表 |
| `/admin/products/new` | 新增商品 | |
| `/admin/products/:id` | 編輯商品 | |
| `/admin/production` | 製作模組 | 上傳圖片、設定參數、送出 |
| `/admin/production/:jobId` | 製作結果 | 預覽、後處理、確認儲存 |
| `/admin/colors` | 實體色管理 | 色庫列表 + 預購缺貨儀表板 |
| `/admin/colors/mapping/:jobId` | 顏色對應工作台 | |
| `/admin/discounts` | 折扣券管理 | 券類型設定、手動發放 |
| `/admin/users` | 用戶管理 | 用戶列表 + 操作 |
| `/admin/notifications` | 通知中心 | 三頁籤：未處理/處理中/已完成 |
| `/admin/reports` | 銷售報表 | 基本統計（初期簡易版）|
| `/admin/content` | 內容管理 | 靜態頁面、系統設定、報價設定、案例管理 |
