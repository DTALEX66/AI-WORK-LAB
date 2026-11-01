/** W02 / task #32 — the canvas's pointer lifecycle and geometry, measured rather than assumed.
 *
 * The audit found this component had ZERO test consumers on this line, and three measured defects:
 * dragging from the + handle never added an edge, clicking the handle threw "No active pointer", the
 * full-size overlay swallowed background panning, and 适应画布 reset only zoom. This file is the
 * population that can convict all four — geometry (rect-based mapping at several widths, a real
 * hit-test) and pointer lifecycle (down → move → up).
 *
 * Why a model-space hit-test is asserted instead of `document.elementFromPoint`: the drop target has to
 * be resolved from the same coordinates the drag itself used. Layout hit-testing depends on a laid-out
 * DOM (jsdom has none) and on `offsetLeft`, which is relative to the offset parent rather than the
 * viewport — the old code mixed both and resolved against a point it had computed differently.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, fireEvent } from '@testing-library/react'

import { WorkflowCanvas, type FlowEdge, type FlowNode } from '@/components/graph/workflow-canvas'

afterEach(cleanup)

const NODE_W = 150
const NODE_H = 64

function mkNodes(): FlowNode[] {
  return [
    { id: 'n1', kind: 'Trigger', label: '触发器', x: 40, y: 60 },
    { id: 'n2', kind: 'Validate', label: '校验', x: 400, y: 60 },
    { id: 'n3', kind: 'Output', label: '产出', x: 400, y: 320 },
  ]
}

/** `.at(-1)` is ES2022 and this project's tsconfig lib is older; take the last call explicitly. */
function last<T>(calls: T[][]): T[] | undefined {
  return calls.length ? calls[calls.length - 1] : undefined
}

/** jsdom has no layout, so the rect the component reads is supplied explicitly. */
function stubRect(canvas: HTMLElement, left: number, top: number, width: number, height: number) {
  canvas.getBoundingClientRect = () =>
    ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top,
       toJSON: () => ({}) }) as DOMRect
}

function mount(opts: { nodes?: FlowNode[]; edges?: FlowEdge[]; width?: number; left?: number } = {}) {
  const nodes = opts.nodes ?? mkNodes()
  const edges = opts.edges ?? []
  const onNodesChange = vi.fn()
  const onEdgesChange = vi.fn()
  const view = render(
    <WorkflowCanvas
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      selectedId={null}
      onSelect={vi.fn()}
    />,
  )
  const canvas = view.container.querySelector('.canvas') as HTMLElement
  stubRect(canvas, opts.left ?? 0, 0, opts.width ?? 1280, 520)
  return { ...view, canvas, onNodesChange, onEdgesChange }
}

function handle(view: ReturnType<typeof mount>, id: string): HTMLElement {
  return view.container.querySelector(`[data-node-id="${id}"] button[aria-label^="从"]`) as HTMLElement
}

/**
 * jsdom has no PointerEvent constructor, and testing-library's fallback drops clientX/clientY — which is
 * exactly the coordinate this file exists to measure. A MouseEvent dispatched under a pointer type keeps
 * the coordinates and still reaches React's onPointerDown/Move/Up handlers.
 */
function pointer(el: Element, type: 'pointerDown' | 'pointerMove' | 'pointerUp', clientX: number, clientY: number) {
  const ev = new MouseEvent(type.toLowerCase(), { bubbles: true, cancelable: true, clientX, clientY })
  Object.defineProperty(ev, 'pointerId', { value: 1 })
  fireEvent(el as unknown as HTMLElement, ev)
}

function node(view: ReturnType<typeof mount>, id: string): HTMLElement {
  return view.container.querySelector(`[data-node-id="${id}"]`) as HTMLElement
}

function transform(view: ReturnType<typeof mount>): string {
  const layer = view.canvas.querySelector('.absolute.inset-0') as HTMLElement
  return layer.style.transform
}

describe('canvas · connecting two nodes', () => {
  it('pointer down on the handle, move to a node, up: an edge is added exactly once', () => {
    const view = mount({ edges: [{ id: 'e0', from: 'n1', to: 'n3' }] })
    const h = handle(view, 'n1')
    expect(h, 'the + handle is the documented way to start a connection').toBeTruthy()

    // Start on the handle with a REAL pointer (the old code called setPointerCapture from a click
    // event, whose pointerId is undefined -> "No active pointer with the given id").
    expect(() => pointer(h, 'pointerDown', 190, 92)).not.toThrow()
    // Move to the centre of n2 (400,60) + half a node.
    pointer(h, 'pointerMove', 400 + NODE_W / 2, 60 + NODE_H / 2)
    pointer(h, 'pointerUp', 400 + NODE_W / 2, 60 + NODE_H / 2)

    expect(view.onEdgesChange).toHaveBeenCalledTimes(1)
    const next = view.onEdgesChange.mock.calls[0][0] as FlowEdge[]
    expect(next).toHaveLength(2)
    expect(next[1]).toMatchObject({ from: 'n1', to: 'n2' })
  })

  it('dropping on empty canvas adds nothing', () => {
    const view = mount()
    const h = handle(view, 'n1')
    pointer(h, 'pointerDown', 190, 92)
    pointer(h, 'pointerMove', 900, 480)
    pointer(h, 'pointerUp', 900, 480)
    const calls = view.onEdgesChange.mock.calls
    const added = calls.filter((c) => (c[0] as FlowEdge[]).length > 0)
    expect(added).toEqual([])
  })

  it('a node cannot connect to itself', () => {
    const view = mount()
    const h = handle(view, 'n1')
    pointer(h, 'pointerDown', 190, 92)
    pointer(h, 'pointerMove', 40 + NODE_W / 2, 60 + NODE_H / 2)
    pointer(h, 'pointerUp', 40 + NODE_W / 2, 60 + NODE_H / 2)
    const added = view.onEdgesChange.mock.calls.filter((c) => (c[0] as FlowEdge[]).length > 0)
    expect(added).toEqual([])
  })

  it.each([1280, 1440, 1920, 2560])('width %i: the drop point maps through the rect, not the origin', (width) => {
    // The canvas starts at a non-zero left offset, so any math that ignores rect.left (or mixes in
    // offsetLeft) misses by exactly that offset at every width.
    const left = width === 1280 ? 240 : 64
    const view = mount({ width, left })
    const h = handle(view, 'n1')
    pointer(h, 'pointerDown', left + 190, 92)
    pointer(h, 'pointerMove', left + 400 + NODE_W / 2, 60 + NODE_H / 2)
    pointer(h, 'pointerUp', left + 400 + NODE_W / 2, 60 + NODE_H / 2)
    const next = last(view.onEdgesChange.mock.calls)?.[0] as FlowEdge[] | undefined
    expect(next?.[0]).toMatchObject({ from: 'n1', to: 'n2' })
  })
})

describe('canvas · pointer lifecycle', () => {
  it('dragging a node moves it by the pointer delta divided by zoom', () => {
    const view = mount()
    const n = node(view, 'n1')
    pointer(n, 'pointerDown', 100, 80)
    pointer(n, 'pointerMove', 260, 150)
    const moved = last(view.onNodesChange.mock.calls)?.[0] as FlowNode[] | undefined
    const n1 = moved?.find((x) => x.id === 'n1')
    // rect.left = 0, zoom = 1: model x = 260 - NODE_W/2, model y = 150 - NODE_H/2
    expect(n1).toMatchObject({ x: 260 - NODE_W / 2, y: 150 - NODE_H / 2 })
    pointer(n, 'pointerUp', 260, 150)
  })

  it('a drag releases: a later move with no button held does not keep moving the node', () => {
    const view = mount()
    const n = node(view, 'n1')
    pointer(n, 'pointerDown', 100, 80)
    pointer(n, 'pointerUp', 100, 80)
    const before = view.onNodesChange.mock.calls.length
    pointer(n, 'pointerMove', 500, 400)
    expect(view.onNodesChange.mock.calls.length).toBe(before)
  })

  it('the background pans even though a full-size overlay sits over the canvas', () => {
    const view = mount()
    const overlay = view.canvas.querySelector('.absolute.inset-0') as HTMLElement
    expect(overlay, 'the canvas content layer covers it; panning must not depend on hitting the canvas itself')
      .toBeTruthy()
    pointer(overlay, 'pointerDown', 300, 200)
    pointer(overlay, 'pointerMove', 380, 260)
    expect(transform(view)).toContain('translate(80px, 60px)')
    pointer(overlay, 'pointerUp', 380, 260)
  })

  it('a node drag is not also a background pan', () => {
    const view = mount()
    const n = node(view, 'n1')
    pointer(n, 'pointerDown', 100, 80)
    pointer(n, 'pointerMove', 200, 180)
    expect(transform(view)).toContain('translate(0px, 0px)')
  })
})

describe('canvas · fit', () => {
  it.each([1280, 1920])('width %i: 适应画布 resets zoom AND pan, not zoom alone', (width) => {
    const view = mount({ width })
    const overlay = view.canvas.querySelector('.absolute.inset-0') as HTMLElement
    // zoom in twice, then pan away
    fireEvent.click(view.container.querySelector('[aria-label="放大"]') as HTMLElement)
    fireEvent.click(view.container.querySelector('[aria-label="放大"]') as HTMLElement)
    pointer(overlay, 'pointerDown', 100, 100)
    pointer(overlay, 'pointerMove', 260, 220)
    pointer(overlay, 'pointerUp', 260, 220)
    expect(transform(view)).not.toContain('translate(0px, 0px)')

    fireEvent.click(view.container.querySelector('[aria-label="适应画布"]') as HTMLElement)
    expect(transform(view)).toContain('translate(0px, 0px)')
    expect(transform(view)).toContain('scale(1)')
  })
})
