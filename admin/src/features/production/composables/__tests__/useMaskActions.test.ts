/**
 * useMaskActions 單元測試 — 對應 04c_production_sam.md §C.5「撤銷 SAM 點」case。
 * 同時涵蓋 close / delete / clear / cancelCurrentPolygon 等 action 的還原行為。
 */
import { describe, it, expect, vi } from 'vitest'

import { useMaskActions } from '../useMaskActions'

describe('useMaskActions — undo & state transitions', () => {
  it('test_undo_pops_last_action — addSamPoint 後 undo 讓 samPoints 長度 -1', () => {
    const onChange = vi.fn()
    const a = useMaskActions({ onChange })

    expect(a.samPoints.value.length).toBe(0)
    expect(a.canUndo.value).toBe(false)

    a.addSamPoint({ x: 100, y: 200, label: 1 })
    expect(a.samPoints.value.length).toBe(1)
    expect(a.canUndo.value).toBe(true)
    expect(onChange).toHaveBeenCalledTimes(1)

    a.undo()
    expect(a.samPoints.value.length).toBe(0)   // ← 規格驗收：長度 -1
    expect(a.actionStack.value.length).toBe(0)
    expect(a.canUndo.value).toBe(false)
    expect(onChange).toHaveBeenCalledTimes(2)  // undo 也算 onChange
  })

  it('addPolygonVertex < 3 點時 closePolygon no-op', () => {
    const a = useMaskActions()
    a.addPolygonVertex([10, 10])
    a.addPolygonVertex([20, 20])
    a.closePolygon()
    expect(a.polygons.value.length).toBe(0)             // 沒閉合
    expect(a.currentPolygon.value.length).toBe(2)       // 還在進行中
  })

  it('closePolygon ≥ 3 點 → 推進 polygons + 清空 currentPolygon', () => {
    const a = useMaskActions()
    a.addPolygonVertex([10, 10])
    a.addPolygonVertex([20, 20])
    a.addPolygonVertex([30, 30])
    a.closePolygon()
    expect(a.polygons.value.length).toBe(1)
    expect(a.currentPolygon.value.length).toBe(0)

    a.undo()
    // undo poly_close → polygon 回 currentPolygon
    expect(a.polygons.value.length).toBe(0)
    expect(a.currentPolygon.value.length).toBe(3)
  })

  it('deleteSamPoint 後 undo 還原該點到原 index', () => {
    const a = useMaskActions()
    a.addSamPoint({ x: 1, y: 1, label: 1 })
    a.addSamPoint({ x: 2, y: 2, label: 1 })
    a.addSamPoint({ x: 3, y: 3, label: 0 })

    a.deleteSamPoint(1)  // 刪中間那個
    expect(a.samPoints.value.length).toBe(2)
    expect(a.samPoints.value[1]).toEqual({ x: 3, y: 3, label: 0 })

    a.undo()
    expect(a.samPoints.value.length).toBe(3)
    expect(a.samPoints.value[1]).toEqual({ x: 2, y: 2, label: 1 })  // 回到 index 1
  })

  it('clearAll 後 undo 還原所有 state', () => {
    const a = useMaskActions()
    a.addSamPoint({ x: 1, y: 1, label: 1 })
    a.addPolygonVertex([5, 5])
    a.addPolygonVertex([6, 6])
    a.addPolygonVertex([7, 7])
    a.closePolygon()

    a.clearAll()
    expect(a.samPoints.value.length).toBe(0)
    expect(a.polygons.value.length).toBe(0)

    a.undo()
    expect(a.samPoints.value.length).toBe(1)
    expect(a.polygons.value.length).toBe(1)
  })

  it('cancelCurrentPolygon 只清進行中頂點 — pop 連續 poly_vertex 不動其他 action', () => {
    const a = useMaskActions()
    a.addSamPoint({ x: 1, y: 1, label: 1 })
    a.addPolygonVertex([5, 5])
    a.addPolygonVertex([6, 6])

    a.cancelCurrentPolygon()
    expect(a.currentPolygon.value.length).toBe(0)
    expect(a.samPoints.value.length).toBe(1)              // SAM 點不動
    expect(a.actionStack.value.length).toBe(1)            // 只剩 SAM 那筆
    expect(a.actionStack.value[0].type).toBe('sam')
  })

  it('hydrate 不入 actionStack — 從 server 載入後 canUndo=false', () => {
    const a = useMaskActions()
    a.hydrate({
      samPoints: [{ x: 10, y: 20, label: 1 }],
      polygons: [[[1, 1], [2, 2], [3, 3]]],
    })
    expect(a.samPoints.value.length).toBe(1)
    expect(a.polygons.value.length).toBe(1)
    expect(a.canUndo.value).toBe(false)  // hydrate 不算操作，沒得 undo
  })
})
