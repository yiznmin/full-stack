/**
 * validateCombos 單元測試 — 對應 04c_production_sam.md §C.5「ProductionNewPage 選 sam_refine 沒填 extra_colors」case。
 * 該驗證為「提交按鈕 disabled」的 source of truth：canSubmit = !validateCombos(combos)。
 */
import { describe, it, expect } from 'vitest'

import { validateCombos, type ComboItem } from '../validateCombos'

const baseStandard: ComboItem = {
  canvas_size: '30x40',
  difficulty: 'intermediate',
  detail: 'standard',
  mode: 'standard',
}
const baseSamRefine: ComboItem = {
  ...baseStandard,
  mode: 'sam_refine',
  extra_colors: 3,
}
const baseSamWeighted: ComboItem = {
  ...baseStandard,
  mode: 'sam_weighted',
  weight_ratio: 0.65,
}

describe('validateCombos', () => {
  it('test_new_page_sam_refine_validation — sam_refine 沒填 extra_colors → 回錯誤訊息（提交按鈕 disabled）', () => {
    const result = validateCombos([{ ...baseSamRefine, extra_colors: 0 }])
    expect(result).not.toBeNull()
    expect(result).toContain('SAM 細化')
    expect(result).toContain('extra_colors')
  })

  it('sam_refine extra_colors=undefined → 視同沒填 → 錯誤', () => {
    const result = validateCombos([{ ...baseSamRefine, extra_colors: undefined }])
    expect(result).not.toBeNull()
  })

  it('sam_refine extra_colors > 0 → null（valid）', () => {
    expect(validateCombos([baseSamRefine])).toBeNull()
  })

  it('sam_weighted weight_ratio 超出 0.5–0.8 → 錯誤', () => {
    expect(validateCombos([{ ...baseSamWeighted, weight_ratio: 0.4 }])).not.toBeNull()
    expect(validateCombos([{ ...baseSamWeighted, weight_ratio: 0.9 }])).not.toBeNull()
  })

  it('sam_weighted weight_ratio 邊界 0.5 / 0.8 → 都接受', () => {
    expect(validateCombos([{ ...baseSamWeighted, weight_ratio: 0.5 }])).toBeNull()
    expect(validateCombos([{ ...baseSamWeighted, weight_ratio: 0.8 }])).toBeNull()
  })

  it('多組 combo 第一個錯就回該錯誤（含組合 index）', () => {
    const result = validateCombos([
      baseStandard,
      { ...baseSamRefine, extra_colors: 0 },  // 第 2 個壞
      baseSamWeighted,
    ])
    expect(result).not.toBeNull()
    expect(result).toContain('組合 #2')
  })

  it('standard mode 無額外驗證 → 無論 extra_colors / weight_ratio 都 valid', () => {
    expect(validateCombos([{ ...baseStandard, extra_colors: 0, weight_ratio: 999 }])).toBeNull()
  })

  it('空陣列 → null（caller 自行檢查長度）', () => {
    expect(validateCombos([])).toBeNull()
  })
})
