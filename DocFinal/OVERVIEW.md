# PaintLearn 系統總覽(OVERVIEW)

> 本文件是整個專案的**入口文件**與**系統地圖**。
> 任何人(包括未來回來的你自己)應該能在 15 分鐘內讀完,掌握系統全貌,並知道要去哪份詳細文件查細節。
> 細節**不寫在這裡**——本文件只負責「骨架、主幹流程、文件索引、跨模組連動」。

---

## 一、系統一句話

**PaintLearn 是一套自建的數字油畫(Paint-by-Numbers)電商平台,整合了「照片轉 PBN 模板」的自動化生產流水線與現貨/客製/預購三路併行的銷售流程,讓創業者可在單一系統內完成「生產 → 配色 → 上架 → 銷售 → 出貨」的完整閉環。**

---

## 二、專案定位

| 項目 | 說明 |
|---|---|
| 性質 | 個人創業,自建系統(不仰賴第三方電商平台) |
| 核心差異化 | 自有 Python PBN 生成引擎(支援 standard / sam_refine / sam_weighted 三種模式) |
| 業務類型 | B2C 電商,主打「客製化照片數字油畫」+「現貨目錄商品」雙軌 |
| 規模預期 | 初期單人經營,系統需支援未來加入一般管理員協作 |

---

## 三、技術棧(定案)

| 層 | 技術 | 部署 |
|---|---|---|
| 核心處理引擎 | Python(既有 `paint-by-number/src/pbn_gen.py`) | Railway Worker |
| 後端 API | FastAPI + PostgreSQL | Railway |
| 任務佇列 | Celery + Redis | Railway |
| 定時任務 | Celery Beat(付款逾期、報價逾期、出貨逾期提醒) | Railway |
| 圖片儲存 | Firebase Storage(公開 / 私有 + 簽名 URL 雙軌) | Firebase |
| Email | Resend(Python SDK,免費額度 3,000 封/月) | — |
| 金流 | 銀行轉帳(24 小時內付款,人工核對) | — |
| 物流 | ECpay(綠界)— 宅配黑貓 / 7-11 / 全家 | — |
| 前端(管理)| Vue 3 | Vercel |
| 前端(商店)| Vue 3 | Vercel |
| 會員系統 | JWT 自建(httpOnly cookie)| — |
| SAM 部署 | 與 FastAPI 同進程、懶載入、常駐記憶體 | Railway |

---

## 四、三大使用者角色

| 角色 | 身份 | 主要能力 |
|---|---|---|
| **管理員** (`role=admin`) | 創業者本人;初期僅 1 人,未來可新增 | 全站後台所有操作;但**不可停用自己**;現階段所有 admin 權限相同 |
| **會員** (`role=customer`) | 註冊完成且已驗證 email 的用戶 | 下單、客製化申請、站內訊息、優惠券、歷史訂單、收件資料管理 |
| **訪客** | 未註冊或未登入 | 僅限商品瀏覽、資訊頁閱讀;**無法下單、無法客製化申請** |

> 第一個管理員帳號以後端 CLI 指令 `scripts/create_admin.py` 建立,不走前台註冊。後續 admin 由已存在的 admin 於後台升級 customer 為 admin。

---

## 五、核心業務流程(六條主幹)

以下為系統內所有動作最終都會匯入的六條主幹流程。每條流程的**狀態機、API、欄位**詳見對應模組文件。

### 流程 A|目錄商品從製作到上架

```
管理員上傳圖片(或從客製申請帶入)
    ↓
選參數:細緻度 / 難易度 / 模式 / 畫布尺寸(可批次組合多筆)
    ↓
(若 sam_refine / sam_weighted)繪製 SAM 遮罩
    ↓
Celery Worker 依序執行(不並發,避免 SAM 模型搶記憶體)
    ↓
產出 template.svg / filled_template.png / palette_json
    ↓
管理員後處理(格子合併 / 消邊界 / 輪廓平滑)→ approved=true
    ↓
進入「填色色號對應」模組,palette 中每個 RGB 配對實體色(physical_colors)
    ↓
全部對應完成 → 進入商品建立模組
    ↓
設定規格變體(尺寸×細緻度×難易度)、定價(公式自動帶入,可覆寫)、標籤、上架
```

**相關文件**:`admin_production.md` → `admin_color.md` → `admin_product.md` → `pricing_formula.md`

---

### 流程 B|目錄商品下單到完成

```
客戶加入購物車 → 結帳
    ↓
[庫存拆單] 若下單量 > 現有庫存,同一 order_item 自動拆為
  fulfilled_qty(現貨)+ preorder_qty(預購)
    ↓
order 建立於 pending_payment(24 小時倒數)
    ↓
客戶 24 小時內完成銀行轉帳 + 填寫付款核對表單(payment_submissions)
    ↓ 逾期未付 → Celery Beat 每 5 分鐘掃描 → payment_expired(自動取消)
    ↓ 已付款
管理員後台確認付款(或標記付款資訊有誤退回客戶)
    ↓
paid → processing(備貨)
    ↓ [若含預購] 預購部分停滯等補料;可選分開出貨或合併出貨
    ↓
管理員點「出貨」→ ECpay API 建立物流訂單 → 拿到 tracking_number
    ↓
shipped(寄出貨 email 通知客戶)
    ↓ 三軌完成判定
  (1) ECpay Webhook 回報 delivered → 所有 shipment 都 delivered 則 completed
  (2) 客戶主動點「確認收貨」→ 立即 completed
  (3) 出貨 14 天後仍無取貨 → email 提醒管理員(不自動變更狀態)
    ↓
completed(發放回饋券、判斷忠誠券)
```

**相關文件**:`admin_orders.md` → `store_browse.md` / `store_orders.md`

---

### 流程 C|客製照片申請(custom_photo)

```
客戶(必須登入)於客製頁上傳照片 + 填寫規格
    ↓
建立 custom_requests(status=quote_pending)
    ↓ 系統自動發歡迎訊息;通知 admin_notifications
管理員與客戶於站內訊息來回溝通(可手動切 negotiating)
    ↓
管理員於製作模組「從客製申請帶入照片」→ 產生 production_job(關聯 custom_request_id)
    ↓
後處理完成 + 配色完成
    ↓
管理員於客製申請詳情頁計算報價(基礎定價 + 勾選加費項目) → 手動覆寫或送出
    ↓
status=quote_sent;寄 email 給客戶(含限時確認連結 /custom/quote/:token)
    ↓ 逾期未回應 → Celery Beat 掃描 → quote_expired
    ↓ 客戶拒絕 → quote_rejected(可重新申請,parent_request_id 關聯)
    ↓ 客戶確認
quote_confirmed → **建立 orders 記錄**(pending_payment,24 小時倒數)
    ↓
往後走「流程 B」的付款 → 出貨 → completed
```

**相關文件**:`store_custom.md` → `admin_orders.md`(§5.9) → `admin_production.md`(§1.1 從客製申請帶入)

---

### 流程 D|客製規格申請(custom_spec)

```
客戶從某個現有商品點「客製此規格」(例如尺寸不在目錄內)
    ↓
建立 custom_requests(type=custom_spec, status=quote_pending)
    ↓
無須繪製(使用該商品既有模板),但可能需要重新做畫布尺寸的 production_job
    ↓
後續流程與流程 C 相同(報價確認 → 付款 → 出貨)
```

**相關文件**:`store_custom.md` → `admin_orders.md`(§5.9)

---

### 流程 E|預購補料自動備貨

```
管理員於色庫管理頁更新某色 stock_ml(進貨)
    ↓
系統自動掃描所有使用此顏色、仍有 preorder_qty > 0 的待出貨訂單
依訂單建立時間排序
    ↓
逐一判斷庫存是否足夠(能備就備,跳過不足者)
    ↓ 足夠者(全自動):
  扣減 stock_ml(required_ml × preorder_qty)
  fulfilled_qty += preorder_qty,preorder_qty = 0
  若該 order 所有 item 均歸零 → 自動建立出貨任務、發 email 通知客戶
  觸發 admin_notifications(告知有預購自動升單)
```

**相關文件**:`admin_color.md`(§2.1 進貨操作流程) → `admin_orders.md`(§5.3 庫存拆單)

---

### 流程 F|退款處理

```
客戶在 paid 狀態「之前」可自行取消(→ cancelled)
    ↓
paid 之後,客戶無法自行取消,必須聯繫管理員
    ↓
管理員不可直接改為 cancelled,必須走退款流程
    ↓
管理員標記 refund_processing + 填寫原因(客戶退貨 / 管理員主動)
    ↓
實際退款完成後填入 refund_amount
  全額 → refunded
  部分 → partially_refunded
    ↓
相關優惠券處理:依退款類型決定是否回補(詳見 admin_discount.md §4.8)
```

**相關文件**:`admin_orders.md`(§5.1, §5.7) → `admin_discount.md`(§4.8)

---

## 六、模組地圖與依賴關係

### 後端模組結構(依 implementation_plan.md)

```
Module 1  Auth(使用者/驗證/密碼重設)
Module 2  User Profile + Shipping Profiles
Module 3  Products(公開瀏覽)
Module 4  Products Management(Admin)
Module 5  Production System(Admin)
Module 6  Color Management + Palette Mapping(Admin)
Module 7  Cart
Module 8  Orders(Customer)
Module 9  Orders Management(Admin)
Module 10 Custom Requests(Customer + Admin)
Module 11 Discount System
Module 12 Notifications(SSE)
Module 13 Content Management
Module 14 Upload
Module 15 Webhooks(ECpay)
Module 16 Sales Reports
```

### 上架依賴鏈(單向)

```
Module 5(製作) → Module 6(配色) → Module 4(商品建立) → Module 3(公開)
```

### 下單依賴鏈(單向)

```
Module 3(瀏覽) → Module 7(購物車) → Module 8(結帳下單)
  → Module 9(管理員確認付款)→ Module 15(ECpay 出貨)
  → Module 12(通知)
```

### 客製申請依賴鏈

```
Module 10(申請+訊息) → Module 5(製作)→ Module 6(配色)
  → Module 10(報價) → Module 8(建立訂單) → 同下單鏈
```

### 橫向通用模組(所有業務都會用到)

- **Module 1 Auth**:所有登入/權限的根
- **Module 11 Discount**:結帳時介入;亦依訂單完成事件自動發券
- **Module 12 Notifications**:所有重要狀態變更都會產生通知
- **Module 13 Content Management**:所有前台靜態頁的內容來源
- **Module 14 Upload**:圖片相關模組都依賴

---

## 七、文件地圖|問題該去哪裡查

### 「我想了解整個系統...」

| 想知道 | 讀哪份 |
|---|---|
| 系統全貌、入口、主幹流程 | **本文件(OVERVIEW.md)** |
| 資料夾結構、部署架構 | `architecture.md` |
| 所有模組的索引清單 | `requirements.md` |
| 資料庫所有表與欄位 | `schema.md` |
| 所有 API endpoint | `api.md` |
| 施工順序(16 個 Module) | `implementation_plan.md` |
| 尚未決定的問題 | `implementation_questions.md` |
| 後端編碼規範 | `backend_conventions.md` |

### 「我要做後台功能,找...」

| 功能 | 讀哪份 |
|---|---|
| 路由結構 | `admin_routes.md` |
| 上傳圖片、生成 PBN 模板、後處理 | `admin_production.md` |
| 實體色庫、palette 對應、庫存進貨 | `admin_color.md` |
| 商品建立、規格變體、標籤 | `admin_product.md` |
| 折扣券的 6 種類型、觸發、發放 | `admin_discount.md` |
| 訂單生命週期、付款、出貨、退款 | `admin_orders.md` |
| 通知中心(需處理 vs 純資訊) | `admin_notifications.md` |
| 靜態頁、系統設定、客製定價、案例 | `admin_content.md` |

### 「我要做前台功能,找...」

| 功能 | 讀哪份 |
|---|---|
| 路由結構 | `store_routes.md` |
| 首頁、商品列表、詳情、購物車、結帳 | `store_browse.md` |
| 客製化商品頁、申請表單、案例展示 | `store_custom.md` |
| 訂單列表、詳情、客製申請列表、生產進度 | `store_orders.md` |
| 尺寸指南、出貨流程、報價參考、退款政策 | `store_info.md` |
| 註冊、登入、收件資料、折扣券錢包 | `store_auth.md` |

### 「我要查規則性的設定...」

| 規則 | 讀哪份 |
|---|---|
| 定價公式(目錄)、客製報價邏輯 | `pricing_formula.md` |
| 密碼 / 名稱格式、JWT 過期、角色權限 | `auth_users.md` |

---

## 八、跨文件連動|常被忽略的耦合點

以下為**多份文件共同觸及**的邏輯,修改時需**同步檢查所有列出的檔案**。

### 1. 訂單狀態 ↔ 通知 ↔ 優惠券

| 事件 | 改 | 也影響 |
|---|---|---|
| `paid` | `admin_orders.md` §5.1 | `admin_orders.md` §5.8(email)、`admin_notifications.md` |
| `completed` | `admin_orders.md` §5.4 | `admin_discount.md` §4.4(發券觸發)、`admin_orders.md` §5.8(email) |
| `refunded` / `partially_refunded` | `admin_orders.md` §5.7 | `admin_discount.md` §4.8(券回補) |

### 2. 客製申請 ↔ 訂單 ↔ 製作

- `custom_requests.status` 與 `orders.status` 是**兩組獨立狀態機**,不要混淆(見 `admin_orders.md` §5.2 的紅字提醒)。
- `quote_confirmed` 是**唯一**由 custom_request 建立 order 的時間點。
- `production_job.custom_request_id` 連接兩者;製作模組可從客製申請「帶入照片」(見 `admin_production.md` §1.1)。

### 3. 實體色庫存 ↔ 訂單拆單 ↔ 商品上架狀態

- 色庫 `stock_ml` 下降 → 可能導致商品變「預購」(見 `admin_product.md` §3.5)
- 色庫 `stock_ml` 上升(進貨)→ 觸發**流程 E** 的自動備貨
- 實體色停用 → 對應商品自動顯示預購

### 4. Firebase Storage 的公開 / 私有

| 檔案類型 | 權限 |
|---|---|
| `filled_template.png` | **公開**(商品預覽要顯示) |
| `template.svg` | **私有**(需 Firebase Admin SDK 簽名 URL,15 分鐘有效) |
| `snapped_rgb` | **私有** |
| `custom_requests.photo_url` | **私有** |

存取方式見 `admin_production.md` §1.8「Firebase Storage 存取控制」。

### 5. Celery 任務失敗清理

製作任務若失敗,`on_failure` 會自動刪除該任務期間上傳至 Firebase 的檔案(見 `admin_production.md` §1.4),避免孤兒檔案。未來其他上傳型任務(例如 PDF、報表)應沿用同一套 pattern。

---

## 九、目前尚未解決的關鍵議題

> 完整清單見 `implementation_questions.md`(24KB,16 大類)。以下僅列出**影響多個模組、必須優先拍板**的議題。

| # | 議題 | 影響模組 |
|---|---|---|
| 1 | 客製照片的基礎定價表金額 | `pricing_formula.md`、`admin_content.md`、`store_custom.md` |
| 2 | 客製照片的加費項目金額 | 同上 |
| 3 | 實體色庫的初始清單(品牌、色號、RGB、每色消耗公式) | `admin_color.md`、`admin_product.md`(庫存連動) |
| 4 | 「一件商品消耗多少 ml 顏料」的計算公式(目前 schema 有 `required_ml` 但計算方式待定) | `schema.md`、`admin_color.md`、`流程 E` |
| 5 | 優惠券結帳時的取優邏輯細節(`discount` 欄位「折扣券 或 auto_checkout 取最優惠」的並列情境) | `admin_orders.md` §5.6、`admin_discount.md` |
| 6 | ECpay 測試商店與正式商店帳號申請狀態 | Module 15 整個 |
| 7 | Firebase 專案建立與 Service Account 金鑰配置 | Module 5 / 6 / 14 整個 |
| 8 | Resend 網域驗證與寄件地址 | 所有會發信的模組 |

---

## 十、施工建議的優先順序

若規劃與實作要同步推進,建議依以下順序,每完成一組才開下一組:

| 階段 | 完成項目 | 為何先做 |
|---|---|---|
| **0. 基礎建設** | Railway / Vercel / Firebase / Resend 帳號與環境變數 | 所有開發的前提 |
| **1. 認證根基** | Module 1(Auth)、Module 2(Profile / Shipping)| 所有模組都依賴 |
| **2. 生產引擎** | Module 14(Upload)、Module 5(Production)、Module 6(Color) | 這是系統的核心差異化,也是最難的部分 |
| **3. 商品上架** | Module 4(Products Admin)、Module 3(Products Public) | 有模板才能建商品 |
| **4. 下單閉環** | Module 7(Cart)、Module 8(Orders Customer)、Module 9(Orders Admin)、Module 15(ECpay Webhook) | 驗證一條可賣的主幹 |
| **5. 客製擴充** | Module 10(Custom Requests) | 有主幹後再加分支 |
| **6. 營運輔助** | Module 11(Discount)、Module 12(Notifications)、Module 13(Content)、Module 16(Reports) | 錦上添花,不影響交易 |

---

## 十一、本文件的維護原則

- **OVERVIEW 只寫骨架,不寫細節**。細節放在各模組文件,本文件用連結指過去。
- **OVERVIEW 出現矛盾 → 以模組文件為準**,然後回頭修 OVERVIEW。
- **模組文件改了跨模組耦合的行為 → 必須回頭檢查本文件第八節**。
- **「目前尚未解決的關鍵議題」解掉一個就劃掉一個**,連帶更新 `implementation_questions.md`。

---

## 附錄|專有名詞速查

| 術語 | 說明 |
|---|---|
| PBN | Paint By Numbers,數字油畫 |
| SAM | Segment Anything Model(Meta 開源影像分割模型),用於客製精細化遮罩 |
| standard | 製作模式:全圖直接轉換,不用遮罩 |
| sam_refine | 製作模式:遮罩區額外加色(細化主體) |
| sam_weighted | 製作模式:遮罩區佔色數比重較高 |
| production_job | 一次製作任務的資料列(同一張圖可有多筆不同參數的 job) |
| palette | 調色盤(演算法產出的 RGB 清單) |
| physical_color | 實體顏料(有色號、RGB 近似、庫存) |
| palette_color_mapping | 調色盤 RGB 與實體色的對應表 |
| custom_request | 客製化申請(分 custom_photo 與 custom_spec 兩型) |
| order | 正式訂單(客製要 quote_confirmed 才建立) |
| order_item | 訂單明細,含 fulfilled_qty(現貨)+ preorder_qty(預購)拆單 |
| shipping_profile | 客戶收件資料(一人可存多筆,指定一筆為預設) |
| admin_notification | 後台通知中心的通知項(分需處理 / 純資訊) |
| batch_id | 批次製作時,同一批 job 共用的 UUID |

---

**最後更新**:2026-04
**本文件版本**:v0.1(初稿)
**適用專案**:PaintLearn
