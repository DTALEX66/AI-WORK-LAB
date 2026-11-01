// L10 (2026-09-27) · L10b: B10 workflow editor canvas — an INTERACTIVE node
// surface (NOT a static flow diagram). Drag nodes, select, connect, delete,
// zoom, with the verbatim B10 look:
//
//   <div class="canvas">
//     <svg class="flow-svg"><path d="M … C …"/></svg>
//     <div class="node" style="left:…px;top:…px">
//       <div class="title">触发器</div><div class="meta">cron · 每日 02:00</div>
//     </div> × N
//   </div>
//
// `.canvas` (30px grid + primary radial wash, 18px radius) / `.flow-svg path`
// (3px primary stroke, dashed, dashMove animation, glow) / `.node` (16px radius,
// primary border, grab cursor, hover lift) / `.node .title` / `.node .meta` are
// B10-verbatim in src/skins/b10.css. Position stays inline (real node
// coordinates from the caller's model).
//
// Honest boundary: this canvas is a LOCAL editing model. "发布 / 运行" is the
// caller's contract — until a real workflow-schema backend is wired the view
// renders those actions disabled + explanatory (no fake success), while the
// canvas interaction is fully real.
import * as React from 'react'
import { ZoomIn, ZoomOut, Maximize, Plus, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'

const HINT_ID = 'workflow-canvas-contract-hint'

export type NodeKind =
  | 'Trigger' | 'Validate' | 'Agent' | 'Tool' | 'Approval'
  | 'Condition' | 'Deploy' | 'Output'

export interface FlowNode {
  id: string
  kind: NodeKind
  label: string
  meta?: string
  x: number
  y: number
}

export interface FlowEdge {
  id: string
  from: string
  to: string
}

export const NODE_KINDS: NodeKind[] = [
  'Trigger', 'Validate', 'Agent', 'Tool', 'Approval', 'Condition', 'Deploy', 'Output',
]

const NODE_W = 150
const NODE_H = 64
const KIND_COLOR: Record<NodeKind, string> = {
  Trigger: 'rgb(var(--secondary-rgb))',
  Validate: 'rgb(var(--primary-rgb))',
  Agent: 'rgb(var(--primary-rgb))',
  Tool: 'rgb(var(--secondary-rgb))',
  Approval: 'rgb(var(--warning-rgb))',
  Condition: 'rgb(var(--info-rgb))',
  Deploy: 'rgb(var(--success-rgb))',
  Output: 'rgb(var(--secondary-rgb))',
}

export interface WorkflowCanvasProps {
  nodes: FlowNode[]
  edges: FlowEdge[]
  onNodesChange: (n: FlowNode[]) => void
  onEdgesChange: (e: FlowEdge[]) => void
  /** add a node of a given kind at a fresh position */
  onAddNode?: (kind: NodeKind) => void
  onPublish?: () => void
  onRun?: () => void
  publishDisabled?: boolean
  runDisabled?: boolean
  publishHint?: string
  runHint?: string
  /** selected node id drives the property panel */
  selectedId?: string | null
  onSelect?: (id: string | null) => void
}

export function WorkflowCanvas({
  nodes, edges, onNodesChange, onEdgesChange,
  onAddNode, onPublish, onRun,
  publishDisabled, runDisabled, publishHint, runHint,
  selectedId, onSelect,
}: WorkflowCanvasProps) {
  const [zoom, setZoom] = React.useState(1)
  const [pan, setPan] = React.useState({ x: 0, y: 0 })
  const [dragId, setDragId] = React.useState<string | null>(null)
  const [connecting, setConnecting] = React.useState<{ from: string; x: number; y: number } | null>(null)
  // W02: the live gesture, mirrored in a ref. `onPointerUp` is attached to the handle, to the node and to
  // the canvas, so one release bubbles through all three; with state alone the gesture was still "open" at
  // the second and third handler (React batches the clear), and one drag produced three identical edges.
  // The ref is read and cleared synchronously, so a gesture resolves exactly once.
  const connectingRef = React.useRef<{ from: string; x: number; y: number } | null>(null)
  const canvasRef = React.useRef<HTMLDivElement>(null)
  const [canvasSize, setCanvasSize] = React.useState({ w: 800, h: 520 })
  void canvasSize

  // measure the canvas for edge geometry
  React.useEffect(() => {
    const el = canvasRef.current
    if (!el) return
    const ro = new ResizeObserver(() => setCanvasSize({ w: el.clientWidth, h: el.clientHeight }))
    ro.observe(el)
    setCanvasSize({ w: el.clientWidth, h: el.clientHeight })
    return () => ro.disconnect()
  }, [])

  const nodeById = React.useMemo(() => {
    const m = new Map<string, FlowNode>()
    for (const n of nodes) m.set(n.id, n)
    return m
  }, [nodes])

  /**
   * W02: client pixel -> model coordinate. The old expression dropped `pan`, so every drag and every
   * connection was resolved against a canvas origin that was only correct while pan was {0,0} — drag a
   * node, press 适应画布, drag again and the node jumps. Both the rect origin and the pan are subtracted
   * before the zoom division, and this is the ONLY place that conversion is written.
   */
  const toModel = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current
    if (!canvas) return null
    const rect = canvas.getBoundingClientRect()
    return { x: (clientX - rect.left - pan.x) / zoom, y: (clientY - rect.top - pan.y) / zoom }
  }

  /**
   * W02: the drop target is resolved in model space, not by `document.elementFromPoint`.
   * The screen point the old code handed to elementFromPoint was built from `offsetLeft/offsetTop`
   * (offset-parent relative) while the drag coordinates came from `getBoundingClientRect`
   * (viewport relative), so the two never agreed; it also needs a laid-out DOM, which a jsdom
   * measurement has none of. The node rects are the model, so ask the model.
   */
  const nodeAt = (x: number, y: number): FlowNode | undefined => {
    for (let i = nodes.length - 1; i >= 0; i--) {
      const n = nodes[i]
      if (x >= n.x && x <= n.x + NODE_W && y >= n.y && y <= n.y + NODE_H) return n
    }
    return undefined
  }

  // ---- node dragging (pointer) ----
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragId && !connecting) return
    const point = toModel(e.clientX, e.clientY)
    if (!point) return
    const px = point.x
    const py = point.y
    if (dragId) {
      onNodesChange(nodes.map((n) => (n.id === dragId ? { ...n, x: px - NODE_W / 2, y: py - NODE_H / 2 } : n)))
    } else if (connecting) {
      const next = { ...connecting, x: px, y: py }
      connectingRef.current = next
      setConnecting(next)
    }
  }

  const onPointerUp = () => {
    // Read-and-clear before anything else: this handler runs once per bubbling level.
    const active = connectingRef.current
    connectingRef.current = null
    if (active) {
      // drop on a node completes a connection (model-space hit test — see nodeAt)
      const target = nodeAt(active.x, active.y)
      if (target && target.id !== active.from) {
        onEdgesChange([...edges, { id: `e-${active.from}-${target.id}`, from: active.from, to: target.id }])
      }
      setConnecting(null)
    }
    setDragId(null)
  }

  /**
   * W02: `setPointerCapture` is an optimisation (it keeps moves coming to the element that started the
   * gesture), not a precondition. Calling it with an id the browser does not consider active throws
   * NotFoundError — "No active pointer with the given id" — which was the audit's measured symptom, and
   * an unguarded throw here aborts the whole gesture before any state is set. A failed capture must
   * never break the drag.
   */
  const capturePointer = (e: React.PointerEvent) => {
    try {
      (e.currentTarget as Element).setPointerCapture?.(e.pointerId)
    } catch {
      /* no active pointer to capture: the gesture still works through bubbling */
    }
  }

  const startDrag = (e: React.PointerEvent, id: string) => {
    e.stopPropagation()
    capturePointer(e)
    setDragId(id)
    onSelect?.(id)
  }

  /**
   * W02: this used to be wired to `onClick` and cast to a PointerEvent. A click carries no pointerId, so
   * `setPointerCapture(undefined)` threw "No active pointer with the given id" and — worse — the click
   * fires only AFTER the press is released, so there was never a pointer *session* to drag inside.
   * Connecting now starts on pointerdown, where a real pointer id exists.
   */
  const startConnect = (e: React.PointerEvent, from: string) => {
    e.stopPropagation()
    capturePointer(e)
    const point = toModel(e.clientX, e.clientY)
    if (!point) return
    const next = { from, x: point.x, y: point.y }
    connectingRef.current = next
    setConnecting(next)
  }

  // ---- pan (background drag) ----
  const panStart = React.useRef<{ x: number; y: number; panX: number; panY: number } | null>(null)
  const onBgPointerDown = (e: React.PointerEvent) => {
    // W02: the old guard was `e.target !== canvasRef.current`, but a full-size content layer
    // (.absolute.inset-0) sits over the canvas, so the background was never the event target and
    // panning could never start. Background is now "anything that is not a node".
    if ((e.target as Element)?.closest?.('[data-node-id]')) return
    capturePointer(e)
    panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y }
  }
  const onBgPointerMove = (e: React.PointerEvent) => {
    if (!panStart.current) return
    setPan({ x: panStart.current.panX + (e.clientX - panStart.current.x), y: panStart.current.panY + (e.clientY - panStart.current.y) })
  }
  const onBgPointerUp = () => { panStart.current = null }

  const deleteSelected = () => {
    if (!selectedId) return
    onNodesChange(nodes.filter((n) => n.id !== selectedId))
    onEdgesChange(edges.filter((e) => e.from !== selectedId && e.to !== selectedId))
    onSelect?.(null)
  }

  const nodeCenter = (n: FlowNode) => ({ x: n.x + NODE_W / 2, y: n.y + NODE_H / 2 })
  const edgePath = (a: FlowNode, b: FlowNode) => {
    const p = nodeCenter(a), q = nodeCenter(b)
    const mx = (p.x + q.x) / 2
    return `M ${p.x} ${p.y} C ${mx} ${p.y}, ${mx} ${q.y}, ${q.x} ${q.y}`
  }

  return (
    <div className="flex flex-col gap-3">
      {/* toolbar — B10 `.toolbar` + `.seg` (node kinds) + `.ghost-btn` (view) */}
      <div className="toolbar">
        <div className="seg" role="group" aria-label="节点类型">
          {NODE_KINDS.map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => onAddNode?.(k)}
              title={`添加 ${k} 节点`}
              aria-label={`添加 ${k} 节点`}
              className="flex items-center gap-1.5"
            >
              <span className="h-2 w-2 rounded-full" style={{ background: KIND_COLOR[k] }} aria-hidden />
              {k}
            </button>
          ))}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" className="ghost-btn" onClick={() => setZoom((z) => Math.max(0.4, z - 0.1))} aria-label="缩小"><ZoomOut size={14} /></button>
          {/* W02: 适应画布 used to reset zoom only, so a panned canvas stayed panned and the button
              lied about what it had adapted. Both axes of the view transform are reset. */}
          <button type="button" className="ghost-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }) }} aria-label="适应画布" title="重置缩放与平移"><Maximize size={14} /></button>
          <button type="button" className="ghost-btn" onClick={() => setZoom((z) => Math.min(2.4, z + 0.1))} aria-label="放大"><ZoomIn size={14} /></button>
          <button type="button" className="ghost-btn" onClick={deleteSelected} disabled={!selectedId} aria-label="删除所选节点" title="删除所选节点"><Trash2 size={14} /></button>
        </div>
      </div>

      {/* canvas — B10 `.canvas` (30px grid + primary wash) + `.flow-svg` */}
      <div
        ref={canvasRef}
        className="canvas"
        style={{ cursor: panStart.current ? 'grabbing' : 'default' }}
        onPointerDown={onBgPointerDown}
        onPointerMove={(e) => { onBgPointerMove(e); onPointerMove(e) }}
        onPointerUp={() => { onBgPointerUp(); onPointerUp() }}
        onPointerLeave={() => { onBgPointerUp(); onPointerUp() }}
      >
        <div
          className="absolute inset-0"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, transformOrigin: '0 0' }}
        >
          <svg className="flow-svg" style={{ width: '100%', height: '100%', overflow: 'visible' }}>
            {edges.map((e) => {
              const a = nodeById.get(e.from), b = nodeById.get(e.to)
              if (!a || !b) return null
              return <path key={e.id} d={edgePath(a, b)} />
            })}
            {connecting ? (
              <path
                d={`M ${nodeById.get(connecting.from) ? nodeCenter(nodeById.get(connecting.from)!).x : 0} ${nodeById.get(connecting.from) ? nodeCenter(nodeById.get(connecting.from)!).y : 0} L ${connecting.x} ${connecting.y}`}
              />
            ) : null}
          </svg>
          {nodes.map((n) => {
            const sel = selectedId === n.id
            return (
              <div
                key={n.id}
                data-node-id={n.id}
                className={cn('node', sel && 'active')}
                style={{ left: n.x, top: n.y, minWidth: NODE_W, minHeight: NODE_H }}
                onPointerDown={(e) => startDrag(e, n.id)}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onClick={() => onSelect?.(n.id)}
                // Nodes are the editor's primary interaction and were reachable
                // only by mouse. Keyboard selection works without touching drag.
                role="button"
                tabIndex={0}
                aria-pressed={sel}
                aria-label={n.label}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    onSelect?.(n.id)
                  }
                }}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0">
                    <div className="title truncate">{n.label}</div>
                    <div className="meta truncate">{n.meta || n.kind}</div>
                  </div>
                  <button
                    type="button"
                    onPointerDown={(e) => { e.stopPropagation(); startConnect(e, n.id) }}
                    onPointerMove={onPointerMove}
                    onPointerUp={onPointerUp}
                    title="拖出连线"
                    aria-label={`从 ${n.label} 连线`}
                    className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-secondary/50 bg-panel2 text-secondary-ink hover:border-secondary"
                  >
                    <Plus size={10} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* save / publish / run — honest when the real contract is not wired.
          A disabled button receives no focus and no pointer events, so the
          reason cannot live only in a hover tooltip: it is stated in the
          adjacent note AND bound to each control by aria-describedby, which is
          what a screen reader reads when it lands on the control. */}
      <div className="flex flex-wrap items-center gap-2">
        <p
          id={HINT_ID}
          role="note"
          className={cn('text-[12px] text-muted', !(publishHint || runHint) && 'hidden')}
        >
          {publishHint || runHint}
        </p>
        <button
          type="button"
          onClick={onRun}
          aria-label="运行"
          disabled={runDisabled}
          aria-disabled={runDisabled || undefined}
          title={runDisabled ? runHint : undefined}
          aria-describedby={runDisabled && runHint ? HINT_ID : undefined}
          className="ghost-btn"
        >
          运行
        </button>
        <button
          type="button"
          onClick={onPublish}
          aria-label="保存并发布"
          disabled={publishDisabled}
          aria-disabled={publishDisabled || undefined}
          title={publishDisabled ? publishHint : undefined}
          aria-describedby={publishDisabled && publishHint ? HINT_ID : undefined}
          className="primary-btn"
        >
          保存并发布
        </button>
      </div>
    </div>
  )
}
