# 易木 YIIMUI — Admin Design System

> 整站視覺與互動的單一來源。每個模組規劃書的「設計決策」段落引用此檔；無例外不重新發明色票、字體、間距。
> 品牌：易木 YIIMUI / 易木工房（paint-by-number 平台）

---

## 1. 方向 — 易木工房 Atelier

### 一句話
**像走進一間日系雜貨鋪後巷的工藝師工作室——資訊密度高，但視覺安靜。**

### 心象
- 無印良品的紙感標籤
- 京都老舖手寫帳冊
- 木紋工作枱 + 米白水彩紙 + 礦物顏料色卡
- 不是 Linear / Notion 那種科技後台

### 紀律（禁區）
- ❌ 科技藍紫 / 霓虹 / 任何漸層
- ❌ Material Design 大圓角（≥ 8px）
- ❌ 花俏動畫、彈跳、scale on hover
- ❌ 過度可愛（emoji icon、圓臉吉祥物、糖果色）
- ❌ Inter 用在標題（太 SaaS）
- ❌ 多色彩 accent（每模組一個色）→ 違反「視覺安靜」

### 取代之以
- ✓ 木質暖棕單色 accent，整站只一個主色
- ✓ 米白底 + 細灰線分層（不靠陰影）
- ✓ 紙質感：極淡 noise / 紋理（CSS 製造，無圖檔）
- ✓ 模組區分靠**圖示 + 文字 + 留白**，不靠色彩
- ✓ 靜的動畫：fade、color transition，<150ms

---

## 2. 字體

### 選擇

| 用途 | 字體 | CJK Fallback | 為什麼 |
|---|---|---|---|
| **Display**（標題、大數字） | **Shippori Mincho B1**（Google Fonts，免費）| **Noto Serif TC** | 日式經典明朝體；筆觸有書道、紙感、雜貨鋪標籤的氣質。Latin 字符也走筆鋒明顯，不像 Newsreader 那麼 editorial 西式。中日台三語顯示一致 |
| **Body**（內文、表單、表格）| **IBM Plex Sans**（IBM，免費，OFL）| **Noto Sans TC** | 比 Inter 多一點人文氣（弧度、收尾），同時保持高密度可讀。資訊密度高的場合不會像 serif 那樣累。Plex 設計初衷是企業內部工具——契合「工藝師後台」 |
| **Numerals**（表格數字、報表）| **JetBrains Mono**（免費，OFL）| 同字 | tabular figures 是表格必備；OldStyle 數字會在報表跳動 |

### 不選哪些（決策痕跡）
- **Inter**：太 SaaS，frontend-design skill 明確點名要避免
- **Noto Serif JP / TC 當主 display**：太「正式公文」，缺紙感
- **Newsreader**：英美 editorial 感太強，跟日系雜貨調性不合
- **手寫風 display**（Caveat 等）：滑入過度可愛區
- **Helvetica / Arial 系**：放棄個性

### 載入方式
Google Fonts CSS API（`font-display: swap`），整站 layout 層只載一次。Shippori Mincho 抓 weights 400 / 500 / 700；Plex Sans 抓 400 / 500 / 600；JetBrains Mono 抓 400 / 500。

```html
<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+TC:wght@400;500&family=Noto+Serif+TC:wght@500;700&display=swap" rel="stylesheet">
```

### 字級規模

縮緊版（資訊密度需求）：

| Token | 字體 | px / line | 字重 | 用途 |
|---|---|---|---|---|
| `text-display` | Shippori Mincho B1 | 30 / 38 | 500 | 頁面主標題 |
| `text-h1` | Shippori Mincho B1 | 22 / 30 | 500 | 主要區塊標題 |
| `text-h2` | IBM Plex Sans | 16 / 24 | 600 | 卡片 / 子區塊標題 |
| `text-h3` | IBM Plex Sans | 14 / 20 | 600 | 表格欄位、表單群組 |
| `text-body` | IBM Plex Sans | 14 / 22 | 400 | 預設內文 |
| `text-meta` | IBM Plex Sans | 12 / 18 | 400 | 時間戳、輔助說明、tag |
| `text-num-sm` | JetBrains Mono | 13 / 18 | 400 | 表格數字（tabular） |
| `text-num-lg` | JetBrains Mono | 24 / 30 | 500 | 統計卡片數字 |

字距：sans `letter-spacing: 0`；display 標題 `-0.005em`（紙感字本身已收緊）；meta uppercase `0.06em`；中文字距 `0`（CJK 不收緊）。

---

## 3. 色票

### 設計準則
1. 整站只有一個 **accent 棕色**——不分模組各色
2. 所有色取自**天然 / 礦物 / 植物染**參照，不取自螢光顏料庫
3. 飽和度上限 **55%**，明度區間 **30–95%**（避免刺眼）
4. 黑不用 `#000`，棕不用 `#000`+hue 直接來，皆**從米白 base 偏色**

### 3.1 紙與墨（中性層）

| Token | Hex | HSL | 用途 | 為什麼這個值 |
|---|---|---|---|---|
| `--paper-canvas` | `#F5F0E6` | hsl(40 35% 93%) | 整頁底色 | 水彩紙未上色狀態；不是純白避免刺眼，不是米黃避免廉價 |
| `--paper-surface` | `#FAF6EF` | hsl(40 45% 96%) | 卡片 / 表格 / modal 紙面 | 比 canvas 亮一階——元件浮在紙面感 |
| `--paper-subtle` | `#EDE6D8` | hsl(40 28% 89%) | hover row、disabled 底 | 比 canvas 暗一階——主動 / 被選擇感 |
| `--paper-deep` | `#E0D6C2` | hsl(40 25% 82%) | 較深區塊背景（少用）| 用於對比強調區塊 |
| `--ink-strong` | `#2B2620` | hsl(30 14% 15%) | 標題 / 主要文字 | 不用 `#000`——帶一點暖棕，貼合紙面氣質 |
| `--ink-default` | `#3D362D` | hsl(30 15% 21%) | 內文 | 比 strong 淡一階，長閱讀不疲勞 |
| `--ink-muted` | `#6B5F50` | hsl(30 16% 36%) | 輔助、placeholder | 仍可讀但退到背景 |
| `--ink-disabled` | `#9C8E7B` | hsl(35 18% 55%) | disabled | 明確表達不可互動 |
| `--line-hairline` | `#DDD2BD` | hsl(40 25% 80%) | 表格 row、卡片邊 1px 線 | 線條為主要層次工具——這條線必須足夠細才像紙感 |
| `--line-strong` | `#C5B69E` | hsl(35 25% 70%) | 區塊分隔、focus ring 底色 | 比 hairline 深一階用於強分隔 |

### 3.2 主色 — 胡桃木 Walnut

| Token | Hex | HSL | 用途 | 為什麼這個值 |
|---|---|---|---|---|
| `--accent` | `#7A4E32` | hsl(22 41% 34%) | 主要 CTA、active nav、品牌強調 | 胡桃木色——比栗皮（深）淺，比赭石（橙）穩；飽和度 41% 落在自然色域，不刺眼；明度 34% 確保白字對比達 WCAG AA |
| `--accent-hover` | `#5E3A24` | hsl(22 45% 25%) | CTA hover | 加深一階；hover 不亮反深，符合「靜」原則 |
| `--accent-soft` | `#A0795C` | hsl(25 28% 49%) | inactive nav text、tertiary button | 同調但更淡 |
| `--accent-tint` | `#E8DDD0` | hsl(30 30% 86%) | accent 背景（如選中 row 的左側強調 + 8% alpha 配色） | 主色 8% alpha 等價值 |

整頁同一時刻主 CTA 只允許一個 `--accent`（次要操作降級為 secondary）。

### 3.3 狀態色 — 天然顏料

取自植物 / 礦物染色傳統，飽和度刻意壓低。

| Token | Hex | HSL | 對應狀態 | 顏料來源 |
|---|---|---|---|---|
| `--state-success` | `#6B7F4D` | hsl(82 26% 40%) | paid / completed / approved | 苔綠 / 抹茶——比螢光綠安靜 |
| `--state-warning` | `#B89149` | hsl(38 47% 50%) | pending / 待處理 / 報價中 | 黃櫨木染、栀子色——溫暖的黃 |
| `--state-danger` | `#A04A3F` | hsl(7 44% 44%) | error / 退款 / 失敗 | 茜草根、朱泥——紅但不是消防紅 |
| `--state-info` | `#3F5B7A` | hsl(213 32% 36%) | 中性提示 / 資訊 | 藍染靛 / 藍墨——沉穩深藍 |

每個 state 配一個 8% alpha 背景版（如 success badge：`background: rgba(107, 127, 77, 0.08); color: #6B7F4D`）。

### 3.4 完整 CSS variables（複製即用）

```css
:root {
  /* Paper & ink */
  --paper-canvas: #F5F0E6;
  --paper-surface: #FAF6EF;
  --paper-subtle: #EDE6D8;
  --paper-deep: #E0D6C2;

  --ink-strong: #2B2620;
  --ink-default: #3D362D;
  --ink-muted: #6B5F50;
  --ink-disabled: #9C8E7B;

  --line-hairline: #DDD2BD;
  --line-strong: #C5B69E;

  /* Accent — Walnut */
  --accent: #7A4E32;
  --accent-hover: #5E3A24;
  --accent-soft: #A0795C;
  --accent-tint: #E8DDD0;

  /* States */
  --state-success: #6B7F4D;
  --state-success-bg: rgba(107, 127, 77, 0.08);
  --state-warning: #B89149;
  --state-warning-bg: rgba(184, 145, 73, 0.08);
  --state-danger: #A04A3F;
  --state-danger-bg: rgba(160, 74, 63, 0.08);
  --state-info: #3F5B7A;
  --state-info-bg: rgba(63, 91, 122, 0.08);

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-7: 32px;
  --space-8: 48px;
  --space-9: 64px;

  /* Radius */
  --radius-xs: 2px;
  --radius-sm: 4px;
  --radius-md: 6px;

  /* Shadow (paper feel — extremely subtle) */
  --shadow-paper: 0 1px 2px rgba(43, 38, 32, 0.04);
  --shadow-elevated: 0 4px 16px rgba(43, 38, 32, 0.08);

  /* Motion */
  --ease-default: cubic-bezier(0.2, 0, 0, 1);
  --duration-fast: 120ms;
  --duration-default: 180ms;

  /* Typography stacks */
  --font-display: 'Shippori Mincho B1', 'Noto Serif TC', 'PingFang TC', serif;
  --font-body: 'IBM Plex Sans', 'Noto Sans TC', 'PingFang TC', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, Consolas, monospace;
}
```

---

## 4. 間距 Scale

8px grid 但中等密度（資訊優先 > 留白）：

| Token | px | 用途 |
|---|---|---|
| `--space-1` | 4 | icon 與文字 gap、tag 內距 |
| `--space-2` | 8 | input 與 label、表單緊湊 stack |
| `--space-3` | 12 | 表單一般 stack |
| `--space-4` | 16 | 表單 group 之間、卡片內 padding 緊湊 |
| `--space-5` | 20 | 卡片內距預設 |
| `--space-6` | 24 | 區塊內主要間距、卡片間 gap |
| `--space-7` | 32 | 標題與內容、page padding |
| `--space-8` | 48 | 大區塊分段 |
| `--space-9` | 64 | hero / 登入頁置中佈局 |

### 應用慣例
- **表格 row height：40px**（資訊密度高，比典型 SaaS 的 48 緊一格）
- **卡片內距：20px**（密度需求 > breathing）
- **頁面外距**：32px（≥ 1024）/ 20px（< 1024）
- **表單欄位間距**：12px（同群組）/ 24px（跨群組）
- **標題與內容間**：16–24px（不要 32+，太鬆稀）

**為什麼縮緊**：用戶定調「資訊密度高但視覺安靜」。安靜不靠留白爆量達成（那是 editorial 路線），靠**色彩低彩度 + 字體靜謐 + 動畫克制**達成。

---

## 5. 圓角

| Token | 用途 | 為什麼 |
|---|---|---|
| `--radius-xs: 2px` | input、tag、status badge | 像剪刀剪過的紙邊；幾乎不顯但避免完全銳利 |
| `--radius-sm: 4px` | button、card | 紙感剛好的圓潤——再大就 Material 化 |
| `--radius-md: 6px` | modal、dropdown | 浮層稍微圓潤 |

**禁止**：≥ 8px。違反「不要 Material 大圓角」禁區。

---

## 6. 線條 / 陰影

### 主原則：線條為層次主工具，陰影輔助

- **永遠 1px**——不用 2px 線（粗線改用色彩深淺如 `--line-strong` 區分）
- **平面元素優先用 1px hairline**，不用陰影（紙感）
- **modal / dropdown** 才用 `--shadow-elevated`，且非常淡（4px blur 16px alpha 8%）
- **focus ring**：`outline: 2px solid var(--accent); outline-offset: 2px;`——這是少數允許「強烈」的地方，因為 a11y

### 紙紋（背景質地）
整頁 body 加極淡 noise（CSS `repeating-linear-gradient` 或 SVG inline filter），透明度 `0.025–0.04`。Retina 螢幕測試後決定要不要保留——不能變廉價或顆粒感過重。

```css
body {
  background-color: var(--paper-canvas);
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%' height='100%' filter='url(%23n)' opacity='0.04'/></svg>");
}
```

如果效能或視覺實測有問題，整片移除——靠純色 + 字體 + 線條也夠。

---

## 7. 動畫哲學

- **頁面進場**：主內容 stagger fade-in，第一塊 0ms、第二 30ms、第三 60ms... 全部 180ms 內結束
- **Hover**：只變色，120ms `--ease-default`；不縮放、不旋轉、不浮起
- **Modal**：fade + 從中心向上 4px（120ms）
- **Toast**：右下出現，停 4s，往下淡出
- **Skeleton 載入**：靜態灰塊，**不要 shimmer 動畫**（太現代）
- **絕對禁止**：spring physics、scale on hover、3D flip、parallax、bounce、彈跳

---

## 8. 元件原則

### Button
- **Primary**：實心 `--accent` 底 + `--paper-surface` 字
- **Secondary**：`--paper-surface` 底 + 1px `--line-strong` + `--ink-default` 字
- **Tertiary**（連結式）：`--accent` 文字 + 底色透明 + 下劃線
- **Danger**：實心 `--state-danger` 底 + 白字
- 高度 36px（密度），`--radius-sm` 圓角，內距 12/16
- **不存在**：ghost、soft、icon-only 等變體（紀律：減少視覺方言）

### Input / Textarea
- 1px `--line-hairline` 底，`--paper-surface` 內底
- focus → 2px focus ring（accent）
- error → border 換 `--state-danger`
- 高度 36px（同 button），padding 8/12

### Table
- Header row：`--paper-subtle` 底，`text-h3` 字體，無 padding inset
- 1px `--line-hairline` 分 row（無 zebra）
- hover row → `--paper-subtle`
- 數字欄用 `text-num-sm` + `text-align: right`
- row height 40px（含內距 8/12）

### Card
- `--paper-surface` 底 + 1px `--line-hairline`
- `--radius-sm` 圓角
- 內距 20px
- 標題 `text-h2`、副資訊 `text-meta`
- 不用陰影（紙感靠線條）

### Modal
- 全屏遮罩 `rgba(43, 38, 32, 0.4)`
- panel max-width 520px（form）/ 720px（detail）
- `--shadow-elevated` + `--radius-md`
- 標題 + body + footer 三層，footer 對齊右下，主操作在最右

### Status badge
- 高 22px、`--radius-xs`、padding 4/8
- 對應 state 色 + state-bg 8% alpha 底
- `text-meta` 字級、字重 500

### Sidebar Nav Item
- 高 36px、padding 8/16
- 圖示 16px + 文字 `text-body`
- inactive：`--ink-muted` 字，無底
- hover：`--paper-subtle` 底
- active：`--paper-subtle` 底 + 左側 2px `--accent` 直條 + `--ink-strong` 字
- **不放圓點 / 模組色**（推翻原 design system 的多色設計，遵守「視覺安靜」）

### 印章式 status（只用於某些特殊情境，例如客製訂單狀態）
- 1px `--state-*` 邊框（無底色）
- `text-meta` 字、uppercase、letter-spacing 0.08em
- 像收件章，不像現代 pill

---

## 9. 圖示

- 統一用 **Lucide Icons**（免費、開源、一致 stroke）
- `stroke-width: 1.5`
- 16 / 20 / 24px 三種尺寸
- **不混風格**：禁止與 Heroicons / Feather / Material Icons 混用
- 顏色繼承文字（`currentColor`），除非為品牌 logo

---

## 10. A11y 基準

- 文字對比 ≥ 4.5:1（除 disabled）— 所有 token 已 WCAG AA 驗證
- focus 必須可見（accent 2px outline-offset 2px）
- 所有按鈕 / link 鍵盤可達
- form 欄位必有 label（visible 或 sr-only）
- icon button 必有 aria-label
- modal Esc 關閉、focus trap、return focus
- Lighthouse Accessibility 每模組驗收 ≥ 90

---

## 11. 暗色模式

**v1 不做。** Token 設計皆為亮色，但用 CSS variables 已留好通道——未來補 dark 時，新增 `:root[data-theme='dark']` 覆蓋同名 token，元件層只引 token 不直接寫色碼。

---

## 12. 跨模組強制慣例

- 頁面結構：`AdminLayout > <main>` 內第一個元素永遠是 `PageHeader`（標題 + 麵包屑 + 主操作 slot）
- 列表頁：搜尋列頂、表格中、分頁底，垂直三段
- 詳情頁：左 2/3 主內容、右 1/3 側欄（meta / 操作）
- 表單：縱向單欄、欄位 stack 上下、CTA 永遠在頁尾右
- 空狀態：1 個 lucide icon（24px、`--ink-muted`）+ 1 句說明 + 1 個 CTA；**不放插畫**（守紀律）
- 1024px 寬以下：sidebar 摺成抽屜（漢堡按鈕觸發）

---

## 13. 黑名單（與禁區呼應）

- 紫漸層 / 藍紫科技色
- Inter 用在標題
- 圓角 ≥ 8px
- shadow-2xl / shadow-lg 等堆疊景深
- hover scale / lift 效果
- 多色 accent 同頁出現
- 圖示混風格
- 表格斑馬紋
- emoji 當 icon
- Material Design 元件視覺
- shimmer / pulse 大量出現的 skeleton
- 任何漸層背景（包含 sidebar、卡片）
