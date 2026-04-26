# 商店端路由結構

---

| 路由 | 頁面 | 說明 |
|------|------|------|
| `/` | 首頁 | 最新上架、熱門商品、分類入口 |
| `/products` | 商品列表 | 全部商品，支援篩選排序 |
| `/products/:id` | 商品詳情 | 規格選擇、加入購物車、客製此規格 |
| `/search` | 搜尋結果 | `?q=關鍵字`，支援同列表篩選條件 |
| `/cart` | 購物車 | 需登入 |
| `/checkout` | 結帳頁 | 需登入 |
| `/checkout/complete` | 訂單建立完成 | 顯示付款帳號與期限 |
| `/orders` | 訂單列表 | 需登入 |
| `/orders/:id` | 訂單詳情 | 需登入 |
| `/custom` | 客製化服務頁 | 案例展示 + 申請表單入口 |
| `/custom/requests` | 客製申請列表 | 需登入 |
| `/custom/requests/:id` | 客製申請詳情 | 訊息對話、報價確認 |
| `/custom/quote/:token` | 報價確認頁 | **不需登入**（token 本身為認證憑證）；token 過期後改為強制登入並導向 `/custom/requests/:id` |
| `/profile` | 個人資料 | 需登入 |
| `/profile/shipping` | 收件資料管理 | 需登入 |
| `/profile/coupons` | 折扣券錢包 | 需登入 |
| `/register` | 註冊頁 | |
| `/login` | 登入頁 | |
| `/forgot-password` | 忘記密碼 | |
| `/reset-password/:token` | 重設密碼 | |
| `/verify-email/:token` | Email 驗證 | |
| `/size-guide` | 尺寸指南 | 靜態頁 |
| `/shipping-info` | 出貨流程 | 靜態頁 |
| `/custom-process` | 訂製流程 | 靜態頁 |
| `/pricing` | 報價參考 | 靜態頁 |
| `/refund-policy` | 退款退貨政策 | 靜態頁 |
