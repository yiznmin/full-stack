/**
 * useMaskActions — MaskEditPage 編輯狀態 + actionStack reducer。
 *
 * 提供 sam_points / polygons / currentPolygon 三個狀態與 add / undo / clear 動作。
 * 抽離出來主要是讓 actionStack 邏輯可被單元測試（vitest），原本嵌在
 * MaskEditPage setup() 內無法 isolated 測試。
 *
 * onChange callback：每次有效操作觸發（用於 MaskEditPage debounced trigger SAM mask）。
 */
import { computed, ref } from 'vue'

import type { SamPoint } from '../api'

export type MaskAction =
  | { type: 'sam'; point: SamPoint }
  | { type: 'poly_vertex'; vertex: [number, number] }
  | { type: 'poly_close'; polygon: number[][] }
  | { type: 'sam_delete'; point: SamPoint; index: number }
  | { type: 'poly_delete'; polygon: number[][]; index: number }
  | {
      type: 'clear'
      samPoints: SamPoint[]
      polygons: number[][][]
      currentPolygon: number[][]
    }

export interface MaskActionsOptions {
  /** 任何 add / close / delete / undo / clear 完成後觸發 — 給 caller debounce 送 SAM mask 用 */
  onChange?: () => void
}

export function useMaskActions(opts: MaskActionsOptions = {}) {
  const samPoints = ref<SamPoint[]>([])
  const polygons = ref<number[][][]>([])
  const currentPolygon = ref<number[][]>([])
  const actionStack = ref<MaskAction[]>([])

  const canUndo = computed(() => actionStack.value.length > 0)

  function addSamPoint(point: SamPoint) {
    samPoints.value.push(point)
    actionStack.value.push({ type: 'sam', point })
    opts.onChange?.()
  }

  function addPolygonVertex(vertex: [number, number]) {
    currentPolygon.value.push(vertex)
    actionStack.value.push({ type: 'poly_vertex', vertex })
    // 進行中 polygon 沒形成有效 mask，不觸發 onChange
  }

  function closePolygon() {
    if (currentPolygon.value.length < 3) return
    const closed = [...currentPolygon.value]
    polygons.value.push(closed)
    actionStack.value.push({ type: 'poly_close', polygon: closed })
    currentPolygon.value = []
    opts.onChange?.()
  }

  function deleteSamPoint(idx: number) {
    if (idx < 0 || idx >= samPoints.value.length) return
    const removed = samPoints.value.splice(idx, 1)[0]
    actionStack.value.push({ type: 'sam_delete', point: removed, index: idx })
    opts.onChange?.()
  }

  function deletePolygon(idx: number) {
    if (idx < 0 || idx >= polygons.value.length) return
    const removed = polygons.value.splice(idx, 1)[0]
    actionStack.value.push({ type: 'poly_delete', polygon: removed, index: idx })
    opts.onChange?.()
  }

  function undo() {
    const last = actionStack.value.pop()
    if (!last) return
    if (last.type === 'sam') {
      samPoints.value.pop()
    } else if (last.type === 'poly_vertex') {
      currentPolygon.value.pop()
    } else if (last.type === 'poly_close') {
      polygons.value.pop()
      currentPolygon.value = last.polygon
    } else if (last.type === 'sam_delete') {
      samPoints.value.splice(last.index, 0, last.point)
    } else if (last.type === 'poly_delete') {
      polygons.value.splice(last.index, 0, last.polygon)
    } else if (last.type === 'clear') {
      samPoints.value = last.samPoints
      polygons.value = last.polygons
      currentPolygon.value = last.currentPolygon
    }
    opts.onChange?.()
  }

  function clearAll() {
    actionStack.value.push({
      type: 'clear',
      samPoints: [...samPoints.value],
      polygons: polygons.value.map((p) => [...p]),
      currentPolygon: [...currentPolygon.value],
    })
    samPoints.value = []
    polygons.value = []
    currentPolygon.value = []
  }

  function cancelCurrentPolygon() {
    if (currentPolygon.value.length === 0) return
    // pop 屬於進行中 polygon 的連續 poly_vertex
    const n = currentPolygon.value.length
    let popped = 0
    while (popped < n && actionStack.value.length > 0) {
      const top = actionStack.value[actionStack.value.length - 1]
      if (top.type === 'poly_vertex') {
        actionStack.value.pop()
        popped++
      } else {
        break
      }
    }
    currentPolygon.value = []
  }

  /** 從 server hydrate 既有狀態（純設值，不入 actionStack）— caller 自行控制只跑一次。 */
  function hydrate(state: {
    samPoints?: SamPoint[]
    polygons?: number[][][]
  }): void {
    if (state.samPoints) samPoints.value = [...state.samPoints]
    if (state.polygons) polygons.value = state.polygons.map((p) => [...p])
  }

  return {
    samPoints,
    polygons,
    currentPolygon,
    actionStack,
    canUndo,
    addSamPoint,
    addPolygonVertex,
    closePolygon,
    deleteSamPoint,
    deletePolygon,
    undo,
    clearAll,
    cancelCurrentPolygon,
    hydrate,
  }
}
