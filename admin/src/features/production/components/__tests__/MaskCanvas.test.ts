/**
 * MaskCanvas 單元測試 — 對應 04c_production_sam.md §C.5。
 *
 * 因 happy-dom 不會自動算 layout，getBoundingClientRect 會回 0,0,0,0；
 * 我們覆寫 Element.prototype.getBoundingClientRect 讓座標換算可正常 work。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import MaskCanvas from '../MaskCanvas.vue'

const W = 1000   // natural width
const H = 800    // natural height

const baseProps = {
  imageUrl: 'data:image/png;base64,iVBORw0KGgo=',
  imageWidth: W,
  imageHeight: H,
  tool: 'sam' as const,
  samPoints: [],
  polygons: [],
  currentPolygon: [],
  maskUrl: null,
  isLocked: false,
}

beforeEach(() => {
  // 讓所有元素的 rect 都對應到一個 1000x800 的虛擬畫布（從 (0,0) 開始）
  // 這樣 e.clientX = X 直接映射到 natural X（縮放比 1:1）
  const fakeRect = (): DOMRect => ({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: W,
    bottom: H,
    width: W,
    height: H,
    toJSON: () => ({}),
  })
  Element.prototype.getBoundingClientRect = vi.fn(fakeRect) as unknown as () => DOMRect
})

describe('MaskCanvas', () => {
  it('test_canvas_left_click_foreground — 左鍵在 SAM 模式下 emit add-sam-point label=1', async () => {
    const wrapper = mount(MaskCanvas, { props: baseProps, attachTo: document.body })
    // 拿外層容器（有 @click handler）
    const container = wrapper.find('div.relative.w-full')
    expect(container.exists()).toBe(true)

    // 在 (300, 400) 觸發 click — 因 rect 1:1，natural 座標也是 (300, 400)
    await container.trigger('click', { clientX: 300, clientY: 400, button: 0 })

    const events = wrapper.emitted('add-sam-point')
    expect(events).toBeTruthy()
    expect(events!.length).toBe(1)
    expect(events![0][0]).toEqual({ x: 300, y: 400, label: 1 })

    wrapper.unmount()
  })

  it('test_canvas_right_click_background — 右鍵在 SAM 模式下 emit add-sam-point label=0', async () => {
    const wrapper = mount(MaskCanvas, { props: baseProps, attachTo: document.body })
    const container = wrapper.find('div.relative.w-full')

    await container.trigger('contextmenu', { clientX: 200, clientY: 250, button: 2 })

    const events = wrapper.emitted('add-sam-point')
    expect(events).toBeTruthy()
    expect(events!.length).toBe(1)
    expect(events![0][0]).toEqual({ x: 200, y: 250, label: 0 })

    wrapper.unmount()
  })

  it('test_polygon_close_requires_3_points — 多邊形模式下 currentPolygon < 3 點時右鍵不 emit close-polygon', async () => {
    // currentPolygon 只有 2 點 → 右鍵不該觸發閉合
    const wrapper = mount(MaskCanvas, {
      props: { ...baseProps, tool: 'polygon', currentPolygon: [[10, 10], [20, 20]] },
      attachTo: document.body,
    })
    const container = wrapper.find('div.relative.w-full')

    await container.trigger('contextmenu', { clientX: 100, clientY: 100, button: 2 })

    expect(wrapper.emitted('close-polygon')).toBeFalsy()

    // 再加一點到 3 點 → 右鍵才該觸發閉合
    await wrapper.setProps({ currentPolygon: [[10, 10], [20, 20], [30, 30]] })
    await container.trigger('contextmenu', { clientX: 100, clientY: 100, button: 2 })

    expect(wrapper.emitted('close-polygon')).toBeTruthy()
    expect(wrapper.emitted('close-polygon')!.length).toBe(1)

    wrapper.unmount()
  })
})
