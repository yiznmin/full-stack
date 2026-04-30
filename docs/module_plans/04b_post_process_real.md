# Module 04-B — Post-Process 真實實作（A 格子合併 + B 消除邊界）

> 取代 `production/tasks.py:_run_post_process_async` 的 stub。

## 範圍

- ✅ 操作 A 格子合併：admin 選任意兩色（src + tgt）→ pixel replace → 重產 SVG / filled
- ✅ 操作 B 消除邊界：admin 選相鄰兩色（absorbed + surviving）→ pixel replace → 重產 SVG / filled
- ❌ 操作 C 輪廓平滑：上一階段已下架
- ❌ SAM 模式（不在本模組）

## 不修改的檔案

- `paint-by-number/src/*` — 用既有 PbnGen 的 constructor + `output_to_svg` + `output_filled_from_template` 三個方法即可，不擴展引擎

## 要建立 / 修改的檔案

| 檔案 | 動作 |
|------|------|
| `backend/production/engine.py` | 加 `apply_color_replacement(snapped_rgb_path, src_rgb, tgt_rgb, output_dir, **engine_params) → dict` |
| `backend/production/tasks.py` | 重寫 `_run_post_process_async`：讀 job → 解析 op type → 跑 engine → 上傳 → 更新 palette + mappings → 寫 DB |
| `backend/tests/production/test_post_process.py` | 新建測試檔（暫時放新檔案，避免拆 test_tasks 的成本） |

## 業務流程（Critical：template_id 重編號副作用）

**重要陷阱**：`PbnGen.output_to_svg` 會依面積大小**重新編號 template_id**（pbn_gen.py:1402-1413：`color_to_seq[key] = len(color_to_seq) + 1`）。
合併後不只「被合併的色號從 palette 移除」，**其他色號的 template_id 也會位移**。

例：原 palette `[1=A(100), 2=B(50), 3=C(30), 4=D(20), 5=E(10)]`
合併 C → A 後，新 palette 應為 `[1=A(130), 2=B(50), 3=D(20), 4=E(10)]`（不是 `[1=A, 2=B, 4=D, 5=E]`）。

所以 `palette_color_mappings` 表的 row 不能只「刪掉被合併色號的 row」，還必須**用 `algorithm_rgb` 重新匹配新 palette 找到新的 template_id 並 UPDATE**。

### 主流程

```
1. _load_job 取 job（service.post_process 已把 status=processing, approved=false）
2. 解析 op type：
   - {source_template_id, target_template_id} → A
   - {absorbed_template_id, surviving_template_id} → B
   - 其他形狀 → ValueError → status=failed
3. 從 palette_json 找 src_rgb 與 tgt_rgb（用 src_template_id / tgt_template_id 對照）
   - 任一查無 → status=failed, notes 含「找不到 template_id=X」
4. 從 Firebase 下載 snapped_rgb_url 到 temp dir
5. 跑 engine.apply_color_replacement：
   a. cv2.imdecode 讀 snapped_rgb.png → BGR
   b. cv2.cvtColor → RGB
   c. mask = np.all(rgb == src_rgb, axis=2)
   d. rgb[mask] = tgt_rgb
   e. 構造 PbnGen(BGR(modified_rgb), num_colors=len(palette)-1)
      - PbnGen 接受 ndarray 直接傳；num_colors 給定就 skip knee detection
   f. pbn.output_to_svg(svg_path, palette_path, min_radius_px=從 job 解出, canvas_w_cm, canvas_h_cm)
      - 回傳 palette_data：list[{template_id (重編號), master_id, rgb, shapes}]
   g. pbn.output_filled_from_template(filled_path)
   h. 把 RGB 圖（modified）存成 snapped_rgb.png（給下次 post-process）
   i. 用我們既有的 _build_palette_data 補 hex/pixels/percent
   j. return {svg_path, filled_path, snapped_rgb_path, palette_data}
6. 上傳新 svg / filled / snapped 到 Firebase（新 token，避免覆蓋舊版本）
   - 失敗 → 反向刪已上傳 + status=failed
7. 重建 palette_color_mappings：
   a. 取舊 mappings（production_job_id=job.id）
   b. 對每筆，用 algorithm_rgb 在新 palette_data 中找 template_id：
      - 找到 → UPDATE mapping.template_id = new_id（rgb 不變）
      - 找不到 → DELETE mapping（這就是被合併色號的 row）
   注意：不能直接 DELETE WHERE template_id=src_template_id（舊 id 已位移）；必須用 algorithm_rgb 比對
8. 更新 production_jobs：
   - svg_url, filled_template_url, snapped_rgb_url（新 gs:// URL）
   - palette_json = 新 palette_data
   - num_colors_used = len(new palette)
   - status = completed
   - approved = false（規格 §1.6，service.post_process 已設）
   - notes：清掉舊的 [Phase 2-B] 標記（如果有）
9. final commit 失敗 → 同 run_production_job 的 fallback：刪 blob、用獨立 engine 標 failed
10. 清理 temp dir

A 與 B 共用步驟 1-10。差別僅在步驟 2 的 op type 解析（屬於 dispatch 層）。
```

## EVENT_MATRIX 對照

E31「管理員進行後處理」：
- DB 寫入：UPDATE production_jobs.palette_json、UPDATE/DELETE palette_color_mappings、Firebase 覆寫
- 狀態變更：approved: true → false（service.post_process 已處理）
- 副作用無 Email / 通知（admin polling）

✅ 規格已涵蓋。

## 測試覆蓋

### test_post_process.py（新建）

**Engine layer（pure function）**：
1. `test_apply_color_replacement_replaces_pixels` — 80×80 圖含 A/B 兩色 → replace A→B → assert 全圖只剩 B
2. `test_apply_color_replacement_invalid_palette` — src_rgb 不在圖中 → 還是會跑（mask=空），不 raise
3. `test_apply_color_replacement_produces_files` — assert svg/filled/snapped 三檔產出 + palette_data 結構正確

**Task layer（mock Firebase）**：
4. `test_run_post_process_merge_color_success` — DB 從 processing → completed、palette_json 少 1 色、3 個 url 更新、num_colors_used 減 1
5. `test_run_post_process_eliminate_border_success` — 同 4 但用 absorbed/surviving naming
6. `test_run_post_process_palette_mappings_remapped` — 前置 seed 5 個 mappings → 合併後驗 4 個 mappings 仍存在但 template_id 已重新匹配；被合併色號的 mapping row 被刪
7. `test_run_post_process_template_id_not_in_palette` — params 帶不存在的 template_id → status=failed、notes 含「找不到 template_id」
8. `test_run_post_process_engine_error` — engine raise → status=failed、無 orphan blob
9. `test_run_post_process_upload_error_rolls_back` — 第 2 個檔上傳失敗 → 第 1 個被刪、status=failed
10. `test_run_post_process_unknown_op_shape` — params 無 src/tgt 也無 absorbed/surviving → status=failed
11. `test_run_post_process_clears_phase2b_note` — job 之前因 stub 留下 [Phase 2-B] notes → 真實成功後 notes 清空

## 規格依據（已查過、不猜）

- `paint-by-number/src/pbn_gen.py:1326-1491` `output_to_svg` — 使用 self.image 的 unique colors 自動分群、重編號
- `paint-by-number/src/pbn_gen.py:1493+` `output_filled_from_template` — 從 _template_contours 等私有屬性產 PNG，必須先 call output_to_svg
- `paint-by-number/src/pbn_gen.py:19-52` PbnGen constructor 接受 ndarray + 顯式 num_colors
- `docs/requirements/admin_production.md §1.6` — A/B/C 操作行為（C 已下架）
- `docs/EVENT_MATRIX.md E31` — DB 副作用清單
- `backend/palette/models.py:24-42` — PaletteColorMapping 表結構（uniq production_job_id + template_id；algorithm_rgb 是 JSONB snapshot）

## 待確認事項

1. **min_radius_px 來源**：output_to_svg 需要 min_radius_px 參數，原來 generate_standard 用 `_calc_min_radius_px(canvas_w_cm, img_w, min_brush_diam_cm) * min_ratio_multiplier`。本次 post-process 的 canvas_w_cm 從 job 取、img_w 從 snapped_rgb 解析，min_brush_diam_cm 也從 job 取。沒問題。

2. **失敗時的 _windows_compat**：tasks.py 已有 `import core._windows_compat`（celery_app 啟動時就 load 了）。沒問題。

3. **output_to_svg 內部會跑 _smooth_quantized 再次平滑**：合併後的圖經過 output_to_svg 的內部平滑會略修色塊邊緣，這符合規格 §1.6「重跑 output_to_svg」的描述，是預期行為。
