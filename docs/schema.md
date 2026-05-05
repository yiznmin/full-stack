# PaintLearn 資料庫 Schema

所有欄位名稱、型別、限制均依各需求文件中「資料庫欄位」章節為準。

---

## 模組一：使用者系統

來源：`auth_users.md`

### users

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| name | VARCHAR | NOT NULL, min 4 UTF-8 chars | 顯示名稱 |
| email | VARCHAR | NOT NULL, UNIQUE | 登入帳號 |
| password_hash | VARCHAR | NOT NULL | bcrypt 雜湊，不存明文 |
| gender | ENUM('female','male','other') | nullable | 性別 |
| birthday | DATE | nullable | 生日 |
| role | ENUM('admin','customer') | NOT NULL, DEFAULT 'customer' | 角色（自行註冊固定 customer） |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 停用旗標（停用後 JWT 仍回 401） |
| is_email_verified | BOOLEAN | NOT NULL, DEFAULT false | Email 驗證狀態 |
| pending_email | VARCHAR | nullable | 申請更換的新 email（驗證完成後寫入 email，驗證前舊 email 仍可登入） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後更新時間 |

> 密碼格式：最少 10 碼，需同時包含英文字母與數字。
> 管理員無法停用自己的帳號（後端驗證 operator_id ≠ target_id）。

---

### shipping_profiles

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| user_id | UUID | NOT NULL, FK → users.id | 所屬用戶 |
| shipping_type | ENUM('home','seven_eleven','family_mart') | NOT NULL | 取貨方式 |
| recipient_name | VARCHAR | NOT NULL | 收件人姓名 |
| phone | VARCHAR | NOT NULL | 聯絡電話 |
| email | VARCHAR | nullable | 物流通知 email（未填則用帳號 email） |
| city | VARCHAR | nullable | 縣市（宅配時填寫，下拉選單） |
| district | VARCHAR | nullable | 鄉鎮市區（宅配時填寫，依縣市連動下拉） |
| address_detail | VARCHAR | nullable | 詳細地址：路街號樓（宅配時填寫，自由文字） |
| store_id | VARCHAR | nullable | 門市代號（超商時填寫） |
| store_name | VARCHAR | nullable | 門市名稱（超商時填寫） |
| is_default | BOOLEAN | NOT NULL, DEFAULT false | 是否為預設收件資料 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> 同一用戶只能有一筆 is_default=true，設定新預設時自動取消舊的。

---

### email_verification_tokens

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| user_id | UUID | NOT NULL, FK → users.id | 所屬用戶 |
| token | VARCHAR | NOT NULL | 隨機安全 token（hashed） |
| token_type | ENUM('signup','email_change') | NOT NULL | 驗證類型 |
| expires_at | TIMESTAMP | NOT NULL | 有效期限（產生後 24 小時） |
| used_at | TIMESTAMP | nullable | 使用時間（驗證後填入，token 作廢） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> `signup` 驗證成功 → is_email_verified=true，觸發 new_user 歡迎券。
> `email_change` 驗證成功 → pending_email 寫入 email，不觸發歡迎券。

---

### password_reset_tokens

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| user_id | UUID | NOT NULL, FK → users.id | 所屬用戶 |
| token | VARCHAR | NOT NULL | 隨機安全 token（hashed） |
| expires_at | TIMESTAMP | NOT NULL | 有效期限（產生後 1 小時） |
| used_at | TIMESTAMP | nullable | 使用時間（使用後填入） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> 用戶重新申請時，自動將該用戶所有 used_at IS NULL 的舊 token 標記已用。

---

## 模組二：商品系統

來源：`admin_product.md 3.11`、`store_browse.md`

### themes

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| name | VARCHAR(50) | NOT NULL UNIQUE | 主題名稱（例：萌寵、風景）|
| description | TEXT | nullable | 主題說明 |
| cover_image_url | VARCHAR | nullable | 主題封面（store 首頁區塊用；Firebase URL）|
| sort_order | INTEGER | NOT NULL DEFAULT 0 CHECK >= 0 | 顯示排序，數字小越靠前 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() onupdate now() | 最後更新時間 |

> 主題之上不再分層；主題下可有 0 ~ N 個系列。
> 刪除主題時其下系列的 `theme_id` 自動 SET NULL（系列保留，僅變未分類）。
> Index：`(sort_order ASC, created_at DESC)` 用於列表預設排序。

---

### product_series

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| name | VARCHAR | NOT NULL | 系列名稱 |
| description | TEXT | nullable | 系列描述 |
| theme_id | UUID | nullable, FK → themes.id ON DELETE SET NULL | 所屬主題 |
| is_featured | BOOLEAN | NOT NULL, DEFAULT false | 是否為精選系列（store 端「精選系列」nav 用）|
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> 系列下仍有商品時禁止刪除，需先將所有商品移出系列。
> theme_id 為 nullable：未歸屬主題的系列允許存在。
> is_featured 由 admin 後台勾選；store 端 GET /series?featured=true 過濾精選系列。

---

### products

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| title | VARCHAR | NOT NULL | 商品標題 |
| description | TEXT | nullable | 商品描述 |
| cover_image_url | VARCHAR | NOT NULL | 封面圖（Firebase Storage，公開） |
| series_id | UUID | nullable, FK → product_series.id | 所屬系列 |
| series_order | INTEGER | nullable | 系列內排序 |
| status | ENUM('draft','on_sale','off_sale') | NOT NULL, DEFAULT 'draft' | 商品狀態；不支援硬刪除，下架以 off_sale 標記 |
| is_featured | BOOLEAN | NOT NULL, DEFAULT false | 是否為精選商品（store 端「精選商品」入口、SeriesDetailPage 右側 Pick 區塊用）|
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後更新時間 |

> **series_order 規則**：若 `series_id IS NOT NULL` 則 `series_order` 必填（後端驗證，資料庫層允許 nullable 以支援 series_id 為 null 的情境）。
> **is_featured 規則**：admin 後台勾選；store 端 `GET /products?featured=true` 過濾精選商品。

---

### product_images

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| product_id | UUID | NOT NULL, FK → products.id | 所屬商品 |
| image_url | VARCHAR | NOT NULL | Firebase Storage 路徑（公開） |
| sort_order | INTEGER | NOT NULL, DEFAULT 0 | 排列順序（可拖曳排序） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

---

### product_variants

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| product_id | UUID | NOT NULL, FK → products.id | 所屬商品 |
| production_job_id | UUID | NOT NULL, FK → production_jobs.id | 對應製作結果（difficulty/detail/canvas 從此讀取） |
| price | NUMERIC(10,2) | NOT NULL | 售價（管理員設定，參考公式建議） |
| price_formula_base | NUMERIC(10,2) | NOT NULL | 公式計算的建議定價（記錄用） |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否開放選購 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> difficulty、detail、canvas_w_cm、canvas_h_cm 等資訊從 production_job 讀取，不重複儲存。
> 同一個 production_job_id 可出現在多筆 product_variants（跨不同商品）。
> 變體庫存狀態由 production_job → palette_color_mappings → physical_colors.stock_ml 自動計算，不另存欄位。
> UNIQUE(product_id, production_job_id)：同一商品不能掛兩次相同 production_job；重新建立時覆蓋舊記錄（ON CONFLICT UPDATE price, price_formula_base, is_active）。

---

### tags

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| name | VARCHAR | NOT NULL, UNIQUE | 標籤名稱 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

---

### product_tags

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| product_id | UUID | NOT NULL, FK → products.id | 商品 |
| tag_id | UUID | NOT NULL, FK → tags.id ON DELETE CASCADE | 標籤（刪除標籤時自動移除關聯） |

> PRIMARY KEY (product_id, tag_id)

---

## 模組三：製作系統

來源：`admin_production.md 1.10`、`admin_color.md 2.8`

### images

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| uploader_id | UUID | NOT NULL, FK → users.id | 上傳的管理員 |
| original_url | VARCHAR | NOT NULL | Firebase Storage 原始圖片路徑（**私有**，後端以簽名 URL 提供存取） |
| filename | VARCHAR | NOT NULL | 原始檔名 |
| width | INTEGER | NOT NULL | 圖片寬度（px） |
| height | INTEGER | NOT NULL | 圖片高度（px） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 上傳時間 |

> 同一張圖片可對應多筆 production_jobs（不同參數跑多次）。
> 注意：客製照片（custom_requests.photo_url）不存於此表，直接存於 custom_requests。

---

### production_jobs

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| image_id | UUID | nullable, FK → images.id | 管理員手動上傳時填入；從客製申請帶入照片時為 null |
| custom_request_id | UUID | nullable, FK → custom_requests.id | 從客製申請帶入時關聯 |
| status | ENUM('pending','processing','completed','failed','cancelled') | NOT NULL, DEFAULT 'pending' | 處理狀態 |
| approved | BOOLEAN | NOT NULL, DEFAULT false | 管理員審核通過（completed + approved=true 才可進入顏色對應） |
| detail | ENUM('rough','standard','detailed','premium') | NOT NULL | 細緻度 |
| difficulty | ENUM('beginner','elementary','intermediate','advanced') | NOT NULL | 難易度 |
| mode | ENUM('standard','sam_refine','sam_weighted') | NOT NULL, DEFAULT 'standard' | 處理模式 |
| canvas_w_cm | NUMERIC(6,1) | NOT NULL | 畫布寬度（cm） |
| canvas_h_cm | NUMERIC(6,1) | NOT NULL | 畫布高度（cm） |
| num_colors | INTEGER | nullable | 覆蓋色數上限 |
| blur_ksize | INTEGER | nullable | 覆蓋值 |
| blur_sigma_color | NUMERIC(6,2) | nullable | 覆蓋值 |
| blur_sigma_space | NUMERIC(6,2) | nullable | 覆蓋值 |
| prune_iterations | INTEGER | nullable | 覆蓋值 |
| pruning_threshold | NUMERIC(10,8) | nullable | 覆蓋值 |
| min_ratio_multiplier | NUMERIC(6,2) | nullable | 覆蓋值 |
| bg_extra_blur | INTEGER | nullable | 覆蓋值 |
| min_brush_diam_cm | NUMERIC(4,2) | NOT NULL, DEFAULT 1.0 | 最小筆觸直徑（cm） |
| extra_colors | INTEGER | nullable | sam_refine 額外色數 |
| weight_ratio | NUMERIC(4,2) | nullable, DEFAULT 0.65（僅 sam_weighted 模式使用）| sam_weighted 比重（0.5~0.8），未填時使用預設 0.65 |
| sam_points | JSONB | nullable | SAM 前景/背景點 [{x,y,label}] |
| polygons | JSONB | nullable | 多邊形頂點 [[[x,y],...]] |
| mask_url | VARCHAR | nullable | Firebase Storage 遮罩 PNG 路徑（私有） |
| mask_coverage | NUMERIC(6,2) | nullable | 遮罩佔圖片面積比例 0~1（例如 0.42 表 42%；純 sam_points 等 worker 推論時為 null） |
| svg_url | VARCHAR | nullable | Firebase Storage 模板 SVG 路徑（私有） |
| filled_template_url | VARCHAR | nullable | Firebase Storage 完成示意圖路徑（公開） |
| snapped_rgb_url | VARCHAR | nullable | Firebase Storage 色彩快照路徑（私有，後處理用） |
| palette_json | JSONB | nullable | 調色盤（純演算法 RGB）[{template_id, rgb, hex, pixels, percent}] |
| num_colors_used | INTEGER | nullable | 實際使用色數 |
| notes | TEXT | nullable | 管理者備註 |
| batch_id | UUID | nullable | 批次識別碼（同批送出的 job 共用；單筆為 null） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| approved_at | TIMESTAMP | nullable | 審核通過時間 |

> 批次 job 依序進入 Celery 佇列，一次只執行一個（避免 SAM 模型記憶體衝突）。
> 失敗時 on_failure 回呼自動刪除已上傳至 Firebase 的所有中間檔案。

---

### physical_colors

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| code | VARCHAR | NOT NULL, UNIQUE | 色號（如 `201`、`601`） |
| name | VARCHAR | NOT NULL | 顏色名稱（如 `SKIN TONE`） |
| color_family | VARCHAR | nullable | 色系（如紅系、膚色系，供篩選） |
| brand | VARCHAR | nullable | 品牌 / 來源（之後補充） |
| rgb | JSONB | NOT NULL | RGB 近似值，格式為陣列 `[R, G, B]`，例如 `[255, 165, 0]`（用於 LAB 距離自動對應） |
| stock_ml | NUMERIC(10,2) | NOT NULL, DEFAULT 0 | 庫存量（單位：ml） |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否啟用（停用後視同庫存為 0） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後更新時間 |

---

### physical_color_rgb_history

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| physical_color_id | UUID | NOT NULL, FK → physical_colors.id ON DELETE CASCADE | 所屬實體色 |
| rgb | JSONB | NOT NULL | 該版本的 RGB snapshot `[R, G, B]` |
| changed_by_user_id | UUID | nullable, FK → users.id ON DELETE SET NULL | 變更者（系統建色時可空） |
| note | VARCHAR | nullable | `initial` / `manual` / `revert from <history_id>` |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 變動時間 |

> 每次 `create_color`、`update_rgb`、`revert_rgb` 都寫入一筆。INDEX `(physical_color_id, created_at DESC)` 加速歷史查詢。

---

### palette_color_mappings

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| production_job_id | UUID | NOT NULL, FK → production_jobs.id | 關聯的製作記錄 |
| template_id | INTEGER | NOT NULL | 調色盤色號（1, 2, 3...，對應 palette_json 中的 template_id） |
| algorithm_rgb | JSONB | NOT NULL | 演算法產出的 RGB，陣列格式 `[R, G, B]`，與 production_jobs.palette_json 裡各 color 的 rgb 格式一致 |
| physical_color_id | UUID | NOT NULL, FK → physical_colors.id | 對應的實體色 |
| required_ml | NUMERIC(8,4) | nullable | 此規格每套所需顏料量（對應完成後計算儲存） |
| mapped_by | ENUM('system','manual') | NOT NULL, DEFAULT 'system' | 人工指定 / 系統預設 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後修改時間 |

> required_ml = max(畫布面積×該色佔比×paint_ml_per_cm2×paint_buffer_ratio, paint_min_ml)
> 計算係數存於 system_settings（paint_ml_per_cm2、paint_min_ml、paint_buffer_ratio）。

---

## 模組四：訂單系統

來源：`admin_orders.md 5.10`

### cart_items

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| user_id | UUID | NOT NULL, FK → users.id | 所屬用戶（需登入才能使用） |
| product_variant_id | UUID | NOT NULL, FK → product_variants.id | 商品變體 |
| quantity | INTEGER | NOT NULL, DEFAULT 1 | 數量 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 加入購物車時間 |

> 購物車不儲存價格快照，結帳時以當下 product_variants.price 為準。
> 結帳前後端驗證 is_active，已下架變體拒絕結帳並在前端標記灰色。

---

### orders

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| order_number | VARCHAR | NOT NULL, UNIQUE | 訂單編號（`PL-YYYYMMDD-XXXXXX`，PostgreSQL SEQUENCE 全域遞增）；**超過 999999 時自動擴展為 7 位**（`PL-YYYYMMDD-XXXXXXX`），前端 parser 不 hardcode 位數 |
| user_id | UUID | NOT NULL, FK → users.id | 下單用戶 |
| status | ENUM('pending_payment','payment_expired','paid','processing','shipped','completed','cancelled','refund_processing','refunded','partially_refunded') | NOT NULL, DEFAULT 'pending_payment' | 訂單狀態 |
| subtotal | NUMERIC(10,2) | NOT NULL | 商品總價 |
| discount_amount | NUMERIC(10,2) | NOT NULL, DEFAULT 0 | 折扣總額（折扣券或 auto_checkout，擇優） |
| discount_source | ENUM('coupon','auto_checkout') | nullable | 實際套用的折扣來源 |
| auto_checkout_config_id | UUID | nullable, FK → coupon_configs.id | discount_source='auto_checkout' 時記錄來源活動 |
| shipping_fee | NUMERIC(10,2) | NOT NULL, DEFAULT 0 | 運費 |
| total | NUMERIC(10,2) | NOT NULL | 實付金額（subtotal - discount_amount + shipping_fee） |
| user_coupon_id | UUID | nullable, FK → user_coupons.id | 使用的折扣券 |
| shipping_type | ENUM('home','seven_eleven','family_mart') | NOT NULL | 取貨方式 |
| shipping_preference | ENUM('together','separate') | nullable | 含預購項目時的出貨偏好 |
| shipping_snapshot | JSONB | NOT NULL | 收件資料快照，結構：`{"recipient_name","phone","notify_email","city","district","address_detail","store_id","store_name"}`（宅配時 city/district/address_detail 有值，store_id/store_name 為 null；超商反之。notify_email 為 null 時出貨改用 users.email）|
| payment_deadline | TIMESTAMP | nullable | 付款期限。初始值 created_at + 24h；flag 時重設為 MIN(now()+24h, created_at + payment_absolute_deadline_hours)；絕對上限不可延超過 created_at + 48h（預設值，可在 system_settings 調整）|
| paid_at | TIMESTAMP | nullable | 付款確認時間 |
| completed_at | TIMESTAMP | nullable | 訂單完成時間 |
| cancel_reason_code | ENUM('payment_expired','customer_cancelled','admin_cancelled') | nullable | 取消原因分類；僅 status='cancelled' 時有值 |
| cancel_reason_note | TEXT | nullable | 取消原因自由說明（管理員取消時建議填寫，逾期或客戶取消通常為 null）|
| refund_amount | NUMERIC(10,2) | nullable | 退款金額（退款時填入，支援部分退款） |
| refunded_at | TIMESTAMP | nullable | 退款完成時間 |
| refund_confirmed_at | TIMESTAMP | nullable | 客戶確認已收到退款的時間(管理員按退款後,客戶需手動確認;僅紀錄用,不影響訂單狀態流程)|
| customer_notes | TEXT | nullable | 客戶備注 |
| admin_notes | TEXT | nullable | 管理者備注（客戶不可見） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 下單時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後更新時間 |

> 訂單編號格式：日期為建立當天，流水號不跨日歸零，永遠遞增（例如當日第一筆可能為 PL-20260418-000312）。
> 客製訂單透過 custom_requests 流程建立，不走購物車；由 order_items.custom_request_id 非 null 識別。
> **庫存扣減**：訂單建立（pending_payment）時立即以 SELECT FOR UPDATE 扣減 stock_ml；付款確認（paid）不再扣；payment_expired / cancelled / refunded 時回補。
> **Coupon 回補**：
> - `refund_processing` 期間 coupon 維持「已使用」，不回補
> - 訂單達到 `refunded`（全額退款）→ coupon 完整回補（is_used=false）、public_code 的 total_used -1
> - 訂單達到 `partially_refunded`（部分退款）→ coupon **不回補**（訂單仍有部分成立）
> - 回饋券（source_order_id）撤銷邏輯依「剩餘金額是否仍達發券門檻」判斷，見 admin_discount.md §4.8

---

### shipments

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| order_id | UUID | NOT NULL, FK → orders.id | 所屬訂單 |
| shipment_type | ENUM('fulfilled','preorder') | NOT NULL | 批次類型（現貨出貨 / 預購出貨） |
| status | ENUM('pending','shipped','delivered') | NOT NULL, DEFAULT 'pending' | 出貨狀態 |
| tracking_number | VARCHAR | nullable | ECpay 物流追蹤號 |
| ecpay_logistics_id | VARCHAR | nullable | ECpay 物流訂單 ID |
| shipped_at | TIMESTAMP | nullable | 出貨時間（ECpay API 成功回傳追蹤號時自動填入） |
| delivered_at | TIMESTAMP | nullable | 取貨 / 投遞確認時間（ECpay Webhook 或客戶確認） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> 合併出貨只有一筆記錄；選「分開出貨」時現貨與預購各建一筆。
> **order.status 聚合規則（動作導向，見 admin_orders.md §5.10 詳表）：**
> - 訂單底下至少一筆 shipments.status ∈ {shipped, delivered} → order.status = shipped
> - 訂單底下所有 shipments.status = delivered → order.status = completed

---

### order_items

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| order_id | UUID | NOT NULL, FK → orders.id | 所屬訂單 |
| product_variant_id | UUID | nullable, FK → product_variants.id | 商品變體（客製訂單為 null） |
| custom_request_id | UUID | nullable, FK → custom_requests.id | 客製申請（一般目錄商品為 null） |
| production_job_id | UUID | nullable, FK → production_jobs.id | 對應的製作任務（客製訂單在 quote_confirmed 建立 order_items 時從 custom_request 反查寫入；目錄訂單為 null） |
| product_title_snapshot | VARCHAR | NOT NULL | 下單時商品名稱快照 |
| variant_spec_snapshot | JSONB | NOT NULL | 下單時規格快照（尺寸、難易度、細緻度等） |
| unit_price | NUMERIC(10,2) | NOT NULL | 下單時單價快照 |
| quantity | INTEGER | NOT NULL | 購買總數量 |
| fulfilled_qty | INTEGER | NOT NULL, DEFAULT 0 | 現貨數量（下單時庫存足夠的部分） |
| preorder_qty | INTEGER | NOT NULL, DEFAULT 0 | 預購數量（庫存不足需等待的部分） |
| is_returned | BOOLEAN | NOT NULL, DEFAULT false | 此項目是否退回（僅部分退款時使用）|

> 客製訂單：fulfilled_qty=0、preorder_qty=1，全部算預購。

---

### production_progress

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| order_item_id | UUID | NOT NULL, FK → order_items.id | 所屬訂單明細 |
| status | ENUM('pending','in_production','manufacturing','packaging','ready_to_ship','shipped') | NOT NULL, DEFAULT 'pending' | 生產狀態 |
| notes | TEXT | nullable | 備注（管理員填寫，客戶可見） |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 狀態更新時間 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> 建立時機：訂單狀態變為 paid 時，系統自動為每筆 order_item 建立一筆，初始狀態 pending。
> 一般目錄商品跳過 in_production，從 pending 直接進 manufacturing。
> 客製訂單需經過 in_production（跑 production_job），之後同樣走 manufacturing → packaging → ready_to_ship → shipped。
> 管理員出貨後系統自動將所有關聯 production_progress 推進至 shipped。
> 各狀態變更自動發 email 通知客戶（pending 和 packaging 除外）。

---

### custom_requests

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| user_id | UUID | NOT NULL, FK → users.id | 申請用戶 |
| request_type | ENUM('custom_photo','custom_spec') | NOT NULL | 申請類型 |
| status | ENUM('quote_pending','negotiating','quote_sent','draft_revision','quote_confirmed','quote_rejected','quote_expired') | NOT NULL, DEFAULT 'quote_pending' | 申請狀態 |
| photo_url | VARCHAR | nullable | 客戶上傳照片（Firebase Storage，私有；custom_photo 用） |
| ref_product_id | UUID | nullable, FK → products.id | 參考商品；**custom_spec 時必填**，custom_photo 時為 null |
| canvas_w_cm | INTEGER | nullable | 畫布寬度偏好（custom_photo 選填） |
| canvas_h_cm | INTEGER | nullable | 畫布高度偏好（custom_photo 選填） |
| difficulty | ENUM('beginner','elementary','intermediate','advanced') | nullable | 難易度偏好（null=讓管理員建議） |
| detail | ENUM('rough','standard','detailed','premium') | nullable | 細緻度偏好。custom_spec 必填、custom_photo 不開放客戶填（由管理員於報價階段決定）；custom_spec 可選「讓管理員建議」時存 null |
| customer_notes | TEXT | nullable | 客戶備注 |
| quoted_price | NUMERIC(10,2) | nullable | 管理員填入的報價金額 |
| quote_token | VARCHAR | nullable, UNIQUE | 報價確認信安全 token（hashed，用於 /custom/quote/:token 連結驗證） |
| quote_expires_at | TIMESTAMP | nullable | 報價有效期限（送出後 +1 天） |
| is_extended | BOOLEAN | NOT NULL, DEFAULT false | 客戶是否已使用延長一次 |
| revision_count | INTEGER | NOT NULL, DEFAULT 0 | 客戶已要求修改的次數，上限 3 |
| parent_request_id | UUID | nullable, FK → custom_requests.id | 重新申請時指向原始申請 |
| order_id | UUID | nullable, FK → orders.id | 客戶確認報價後建立的訂單 |
| admin_notes | TEXT | nullable | 管理員內部備注 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 申請時間 |
| quoted_at | TIMESTAMP | nullable | 報價時間 |

> 客製照片私有存取：後端用 Firebase Admin SDK 產生簽名 URL（15分鐘 TTL），前端憑此 URL 存取。
> 客戶更換照片時，舊照片立即從 Firebase 刪除，系統覆蓋 photo_url 欄位。
> 被拒絕/逾期的申請照片不自動刪除，保留供查閱。

---

### custom_request_messages

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| request_id | UUID | NOT NULL, FK → custom_requests.id | 所屬申請 |
| sender_type | ENUM('admin','customer') | NOT NULL | 發送者角色 |
| message | TEXT | NOT NULL | 訊息內容（純文字） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 發送時間 |

> 申請建立時系統自動發送歡迎訊息（第一則，sender_type=admin）。
> 管理員送出報價時，報價金額+備注同步進入訊息。

---

### payment_submissions

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| order_id | UUID | NOT NULL, FK → orders.id | 所屬訂單 |
| is_flagged | BOOLEAN | NOT NULL, DEFAULT false | 管理員標記有誤 |
| transfer_amount | NUMERIC(10,2) | NOT NULL | 轉帳金額（客戶填寫） |
| transfer_date | DATE | NOT NULL | 轉帳日期（客戶填寫） |
| transfer_time | TIME | NOT NULL | 轉帳時間（客戶填寫） |
| account_last5 | VARCHAR(5) | NOT NULL | 轉帳帳號末五碼 |
| notes | TEXT | nullable | 備注 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 填寫時間 |

> 客戶可多次填寫（填錯可重填）；管理員以最新一筆為準對照銀行帳款。

---

## 模組五：折扣系統

來源：`admin_discount.md 4.6`

### coupon_configs

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| coupon_type | ENUM('new_user','spend_reward','returning_loyal','manual','auto_checkout') | NOT NULL | 折扣券類型 |
| discount_type | ENUM('percentage','fixed') | NOT NULL | 折扣方式 |
| discount_value | NUMERIC(10,2) | NOT NULL | 折扣值 |
| min_purchase | NUMERIC(10,2) | nullable | 最低消費門檻 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否啟用 |
| params | JSONB | NOT NULL, DEFAULT '{}' | 類型專屬參數（見下方說明） |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後修改時間 |

**各類型 params 內容**
```json
// new_user
{ "valid_days": 30 }

// spend_reward
{ "trigger_threshold": 1000, "valid_days": 30 }

// returning_loyal
{ "trigger_threshold": 1000, "valid_days": 30 }

// manual
{}

// auto_checkout
{ "trigger_threshold": 1000, "start_at": "2026-05-01", "end_at": "2026-05-31" }
```

> public_code 類型獨立存於 promo_codes 表，不在此表。
> params 結構由後端按 coupon_type 負責驗證，不依賴資料庫層級約束。
> **部分唯一索引**：`new_user / spend_reward / returning_loyal / manual` 各只能有一筆（`UNIQUE INDEX ON coupon_configs (coupon_type) WHERE coupon_type != 'auto_checkout'`）；`auto_checkout` 可有多筆以支援同時多個活動並存，系統擇優套用折扣金額最高者。

---

### promo_codes

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| code | VARCHAR | NOT NULL, UNIQUE | 促銷碼（唯一，如 SALE2026） |
| discount_type | ENUM('percentage','fixed') | NOT NULL | 折扣方式 |
| discount_value | NUMERIC(10,2) | NOT NULL | 折扣值 |
| min_purchase | NUMERIC(10,2) | nullable | 最低消費門檻 |
| start_at | TIMESTAMP | nullable | 活動開始時間 |
| end_at | TIMESTAMP | nullable | 活動結束時間 |
| max_total_uses | INTEGER | nullable | 總使用上限（null=無限） |
| max_per_user | INTEGER | NOT NULL, DEFAULT 1 | 每人使用上限 |
| total_used | INTEGER | NOT NULL, DEFAULT 0 | 已使用次數（原子遞增） |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否啟用 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後修改時間 |

> 並發保護：UPDATE promo_codes SET total_used = total_used + 1 WHERE id = ? AND total_used < max_total_uses
> 更新影響列數為 0 時回傳「促銷碼已達使用上限」。

---

### user_coupons

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| user_id | UUID | NOT NULL, FK → users.id | 所屬用戶 |
| coupon_config_id | UUID | nullable, FK → coupon_configs.id | 對應折扣設定（public_code 使用時為 null） |
| promo_code_id | UUID | nullable, FK → promo_codes.id | 對應促銷碼（非 public_code 為 null） |

> CHECK: `coupon_config_id IS NOT NULL OR promo_code_id IS NOT NULL`（兩者至少一個有值，防止無效券）

| discount_type | ENUM('percentage','fixed') | NOT NULL | 折扣方式快照（發放當時） |
| discount_value | NUMERIC(10,2) | NOT NULL | 折扣值快照 |
| min_purchase | NUMERIC(10,2) | nullable | 最低消費門檻快照 |
| expires_at | TIMESTAMP | nullable | 到期時間 |
| is_used | BOOLEAN | NOT NULL, DEFAULT false | 是否已使用 |
| used_at | TIMESTAMP | nullable | 使用時間 |
| used_in_order_id | UUID | nullable, FK → orders.id | 使用於哪筆訂單（退款/取消時依此找回） |
| source_order_id | UUID | nullable, FK → orders.id | 來源訂單（spend_reward/returning_loyal 記錄觸發訂單，退款時據此撤銷未使用的券） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 發放時間 |

> 快照欄位確保即使管理員修改 coupon_configs 參數，已發放的券仍按當時條件計算。
> 訂單取消/退款 → used_in_order_id 對應此訂單的券：is_used→false、used_at/used_in_order_id 清空。
> public_code 退款還需 promo_codes.total_used 原子遞減。
> spend_reward/returning_loyal：source_order_id 對應退款訂單的未使用券 → 將 expires_at 設為當下使其作廢。
> 結帳擇優：max(user_coupon 折扣, best_auto_checkout 折扣)；客戶手動輸入 public_code 則尊重其選擇。

---

## 模組六：通知系統

來源：`admin_notifications.md`

### admin_notifications

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| type | VARCHAR | NOT NULL | 通知類型（見下方） |
| requires_action | BOOLEAN | NOT NULL | 是否需要手動處理 |
| status | ENUM('unhandled','in_progress','completed') | NOT NULL, DEFAULT 'unhandled' | 處理狀態 |
| reference_type | VARCHAR | nullable | 關聯資源類型（'order' / 'custom_request' / 'physical_color'） |
| reference_id | UUID | nullable | 關聯資源 ID |
| message | TEXT | NOT NULL | 通知摘要文字 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 狀態更新時間 |

**通知類型（type 值）**

| type | requires_action | 觸發時機 |
|------|----------------|---------|
| `quote_pending` | true | 客戶提交客製申請 |
| `custom_order_paid` | true | 客製訂單狀態變為 paid |
| `draft_revision_requested` | true | 客戶要求修改初稿 |
| `new_message` | true | 客戶傳訊息（管理員不在頁面） |
| `payment_submitted` | true | 客戶填寫付款核對表單 |
| `payment_resubmitted` | true | 客戶重新填寫付款表單 |
| `shipment_overdue` | true | 出貨後 14 天無取貨確認 |
| `stock_shortage` | true | 進貨後仍有預購訂單庫存不足 |
| `order_cancelled` | false | 客戶取消訂單 |
| `quote_confirmed` | false | 客戶確認報價 |
| `quote_rejected` | false | 客戶拒絕報價 |
| `ecpay_status` | false | ECpay Webhook 物流狀態更新 |
| `production_failed` | true | production_job 失敗 |
| `batch_completed` | true | production 批次全部處理完畢 |
| `order_completed_by_customer` | false | 客戶主動點確認收貨 |
| `preorder_upgraded` | false | 進貨後預購訂單自動升單成功（per-order）|

> 新通知即時推送至所有有活躍 SSE 連線的 admin（Railway heartbeat 每 30 秒）。
> payment_resubmitted 建立時，自動將同訂單的 payment_submitted 通知標記為 completed。
> preorder_upgraded 由 E34 觸發，每升單一張訂單建立一筆通知。

---

## 模組七：內容管理

來源：`admin_content.md 6.6`、`store_custom.md`

### static_pages

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| slug | VARCHAR | NOT NULL, UNIQUE | 頁面識別碼（size_guide / shipping / custom_process / pricing_reference / refund_policy） |
| title | VARCHAR | NOT NULL | 頁面標題 |
| content | TEXT | NOT NULL | 頁面內容（Markdown） |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後更新時間 |

---

### system_settings

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| key | VARCHAR | PK | 設定項目識別碼 |
| value | TEXT | NOT NULL | 設定值 |
| updated_at | TIMESTAMP | NOT NULL, DEFAULT now() | 最後更新時間 |

**常用 key 列表**

| key | 說明 |
|-----|------|
| bank_account_number | 匯款帳號 |
| bank_name | 匯款銀行名稱 |
| bank_account_name | 匯款戶名 |
| quote_reply_days | 客製申請預計回覆工作天 |
| product_info_tools | 商品頁說明：畫具內容物（Markdown） |
| product_info_material | 商品頁說明：畫布材質 |
| product_info_tips | 商品頁說明：使用建議 |
| product_info_notes | 商品頁說明：注意事項 |
| paint_ml_per_cm2 | 每 cm² 所需顏料 ml（預設 0.05） |
| paint_min_ml | 每色最低配給 ml（預設 3） |
| paint_buffer_ratio | 顏料緩衝倍數（預設 1.3） |
| custom_photo_price_multiplier | 客製照片服務費率，預設 2.0 |
| payment_absolute_deadline_hours | 訂單付款絕對期限（小時），預設 48 |

---

### custom_photo_prices

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| canvas_w | INTEGER | NOT NULL | 畫布寬（cm） |
| canvas_h | INTEGER | NOT NULL | 畫布高（cm） |
| difficulty | ENUM('beginner','elementary','intermediate','advanced') | NOT NULL | 難易度 |
| price | NUMERIC(10,2) | NOT NULL | 基礎定價 |

> UNIQUE(canvas_w, canvas_h, difficulty)

---

### custom_photo_surcharges

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| category | VARCHAR | NOT NULL | 加費類別（如「照片類型」、「人物數量」） |
| label | VARCHAR | NOT NULL | 顯示名稱（如「2人」、「寵物」、「複雜背景」） |
| amount | NUMERIC(10,2) | NOT NULL | 加費金額 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否在報價時顯示 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

---

### canvas_sizes

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| canvas_w_cm | INTEGER | NOT NULL | 畫布寬度（cm） |
| canvas_h_cm | INTEGER | NOT NULL | 畫布高度（cm） |
| display_name | VARCHAR | NOT NULL | 顯示名稱（例如「30×40 cm」） |
| sort_order | INTEGER | NOT NULL, DEFAULT 0 | 排列順序 |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | 是否開放選用 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> UNIQUE(canvas_w_cm, canvas_h_cm)
> **初始資料**：依 pricing_formula.md 的 17 種標準尺寸（20×20 / 30×30 / 30×40 / 40×30 / 30×50 / 40×40 / 50×30 / 30×60 / 40×50 / 50×40 / 40×60 / 60×40 / 50×50 / 50×60 / 60×50 / 60×60 等共 17 筆）
> **停用**：is_active=false 後該尺寸不在新商品/客製表單中出現，但不影響已建立的 production_jobs 和 orders

---

### case_categories

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| name | VARCHAR | NOT NULL, UNIQUE | 類型名稱（如「人像」、「寵物」） |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

> 刪除分類時，custom_cases.category_id 自動設為 null（ON DELETE SET NULL），前台顯示為「未分類」。

---

### custom_cases

| 欄位 | 型別 | 限制 | 說明 |
|------|------|------|------|
| id | UUID | PK | 主鍵 |
| image_url | VARCHAR | NOT NULL | 成品圖（Firebase Storage） |
| title | VARCHAR | NOT NULL | 案例標題 |
| description | TEXT | nullable | 說明文字 |
| category_id | UUID | nullable, FK → case_categories.id ON DELETE SET NULL | 案例類型 |
| canvas_w_cm | INTEGER | nullable | 尺寸寬（cm） |
| canvas_h_cm | INTEGER | nullable | 尺寸高（cm） |
| difficulty | ENUM('beginner','elementary','intermediate','advanced') | nullable | 難易度 |
| is_published | BOOLEAN | NOT NULL, DEFAULT false | 是否公開顯示 |
| created_at | TIMESTAMP | NOT NULL, DEFAULT now() | 建立時間 |

---

## 索引建議

| 資料表 | 索引欄位 | 原因 |
|--------|----------|------|
| users | email | 登入查詢 |
| products | status | 商品列表篩選 |
| product_variants | product_id, is_active | 商品詳情變體查詢 |
| product_variants | production_job_id | 反查變體 |
| cart_items | user_id | 購物車查詢 |
| orders | user_id, status | 用戶訂單列表 |
| orders | order_number | 訂單編號查詢 |
| orders | payment_deadline | Celery Beat 逾期掃描 |
| order_items | order_id | 訂單明細查詢 |
| production_progress | order_item_id | 製作進度查詢 |
| production_jobs | batch_id | 批次分組查詢 |
| production_jobs | status, approved | 可用變體池查詢 |
| palette_color_mappings | production_job_id | 顏色對應查詢 |
| palette_color_mappings | physical_color_id | 庫存計算反查 |
| custom_requests | user_id, status | 客製申請列表 |
| custom_requests | quote_token | 報價確認連結查詢 |
| user_coupons | user_id, is_used | 可用券查詢 |
| user_coupons | source_order_id | 退款撤銷回饋券 |
| user_coupons | used_in_order_id | 退款回補已用券 |
| admin_notifications | status, created_at | 未處理通知查詢 |
