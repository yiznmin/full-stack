/**
 * 製作任務「批次組合」表單驗證 — 對應 docs/api.md POST /admin/production/jobs 的 mode 必填欄位規則：
 *   sam_refine → extra_colors > 0
 *   sam_weighted → 0.5 ≤ weight_ratio ≤ 0.8
 *   standard → 無額外驗證
 *
 * 抽到 utility 主因：原本嵌在 ProductionNewPage setup() 內無法被 vitest 測，且
 * 同一 rule 將來可能在批次 wizard 流程重用。
 */
import type { Detail, Difficulty, Mode } from '../api'

export interface ComboItem {
  canvas_size: string         // "30x40" 等
  difficulty: Difficulty
  detail: Detail
  mode: Mode
  /** sam_refine 必填 > 0；其他 mode 可為 0/undefined */
  extra_colors?: number
  /** sam_weighted 必填 0.5–0.8；其他 mode 可為任意 */
  weight_ratio?: number
}

/**
 * 驗證所有 combo 是否合法。
 * @returns null = 全部 OK；非 null = 第一個錯誤訊息（含組合 index）
 */
export function validateCombos(combos: ComboItem[]): string | null {
  for (let i = 0; i < combos.length; i++) {
    const c = combos[i]
    if (c.mode === 'sam_refine') {
      if (!c.extra_colors || c.extra_colors <= 0) {
        return `組合 #${i + 1}（SAM 細化）的 extra_colors 必須 > 0`
      }
    }
    if (c.mode === 'sam_weighted') {
      const r = c.weight_ratio ?? 0
      if (r < 0.5 || r > 0.8) {
        return `組合 #${i + 1}（SAM 加權）的 weight_ratio 必須在 0.5–0.8 之間`
      }
    }
  }
  return null
}
