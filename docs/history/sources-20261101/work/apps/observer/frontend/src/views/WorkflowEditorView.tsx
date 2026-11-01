// L10 (2026-09-27) · L10b (2026-09-27): B10 Workflow Editor — the CORE
// interactive page, in the verbatim B10 `.split` grid:
//   .page-head → .split[ .panel > .canvas(.flow-svg + .node tiles) | .panel 属性与运行配置 ]
// The right panel carries `.list-item` rows and the nested 部署说明 panel.
//
// Interactive node canvas (drag/zoom/pan/select/connect/delete) via the shared
// WorkflowCanvas + the B10 property panel for the selected node. Local editing
// model (positions/edges in React state, persisted to localStorage). Honest:
// 发布/运行 are disabled until a real workflow-schema backend contract is wired
// (no fake success — UI_DECISIONS D-06).
import * as React from 'react'
import { Save } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { WorkflowCanvas, type FlowNode, type FlowEdge, type NodeKind } from '@/components/graph/workflow-canvas'
import { Tooltip } from '@/components/ui/tooltip'

const LS_KEY = 'work-lab/editor/model'

interface EditorModel {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

// WL-L04 (2026-10-11): the header used to print 「已自动保存」 unconditionally while the write itself
// sat in `try { setItem(...) } catch { /* quota — non-fatal */ }`. The claim was therefore made by the
// code path, not by the write: a quota error, a disabled storage setting or a private-mode throw all
// still produced "saved". The claim now comes from the write's own result, and a failed write says so.
export type PersistOutcome = {
  status: 'SAVED' | 'NOT_SAVED'
  reason: string | null
}

export function writeModel(model: EditorModel): PersistOutcome {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(model))
    return { status: 'SAVED', reason: null }
  } catch (err) {
    return { status: 'NOT_SAVED', reason: err instanceof Error ? err.message : String(err) }
  }
}

function loadModel(): EditorModel {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (raw) return JSON.parse(raw) as EditorModel
  } catch { /* no stored model -> fresh default */ }
  return {
    nodes: [
      { id: 'n1', kind: 'Trigger', label: '触发器', meta: 'cron · 每日 02:00', x: 40, y: 60 },
      { id: 'n2', kind: 'Validate', label: '校验', meta: 'schema v3', x: 240, y: 60 },
      { id: 'n3', kind: 'Agent', label: 'Hermes Agent', meta: 'task-pack', x: 440, y: 60 },
      { id: 'n4', kind: 'Approval', label: '审批门', meta: 'human-gate', x: 440, y: 200 },
      { id: 'n5', kind: 'Output', label: '产出', meta: 'artifact', x: 640, y: 130 },
    ],
    edges: [
      { id: 'e-1-2', from: 'n1', to: 'n2' },
      { id: 'e-2-3', from: 'n2', to: 'n3' },
      { id: 'e-2-4', from: 'n2', to: 'n4' },
      { id: 'e-3-5', from: 'n3', to: 'n5' },
    ],
  }
}

export function WorkflowEditorView({ snap }: { snap: unknown }) {
  void snap
  const [model, setModel] = React.useState<EditorModel>(loadModel)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)
  const [persist, setPersist] = React.useState<PersistOutcome | null>(null)
  const selected = model.nodes.find((n) => n.id === selectedId) ?? null

  const setNodes = (nodes: FlowNode[]) => setModel((m) => ({ ...m, nodes }))
  const setEdges = (edges: FlowEdge[]) => setModel((m) => ({ ...m, edges }))

  // Null before the first write result is known: "not claimed yet" is not the same as "saved".
  React.useEffect(() => {
    setPersist(writeModel(model))
  }, [model])
  const retrySave = () => setPersist(writeModel(model))

  const addNode = (kind: NodeKind) => {
    const id = `n-${Date.now().toString(36)}`
    setNodes([...model.nodes, { id, kind, label: kind, meta: '未命名', x: 80 + (model.nodes.length % 4) * 180, y: 80 + Math.floor(model.nodes.length / 4) * 140 }])
  }

  const updateSelected = (patch: Partial<FlowNode>) => {
    if (!selected) return
    setNodes(model.nodes.map((n) => (n.id === selected.id ? { ...n, ...patch } : n)))
  }

  const edgeCount = selected
    ? model.edges.filter((e) => e.from === selected.id || e.to === selected.id).length
    : 0

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Workflow Editor / 工作流编辑器"
        description="交互式节点画布：拖动 / 缩放 / 平移 / 选择 / 连线 / 删除。本地编辑模型（localStorage 持久化）；发布与运行在真实 workflow-schema 契约接入前保持禁用。"
        actions={
          /* WL-L04: what the header claims is decided by the write result above, not by this render. */
          persist?.status === 'SAVED' ? (
            <Tooltip text="本地编辑已自动持久化">
              {/* This had no onClick: a button that looks pressable and does
                  nothing is exactly the fake affordance the read-only rule is
                  about, so it is a status label instead. */}
              <span className="tag info" role="status" data-persist-state="SAVED">已自动保存</span>
            </Tooltip>
          ) : persist?.status === 'NOT_SAVED' ? (
            <div className="flex items-center gap-2" role="status" data-persist-state="NOT_SAVED">
              <span className="tag bad">未保存</span>
              <Button size="sm" onClick={retrySave} data-persist-retry>重试保存</Button>
              {persist.reason ? <span className="text-[12px] text-muted">{persist.reason}</span> : null}
            </div>
          ) : null
        }
      />

      <div className="split">
        <div className="panel">
          <h3>Workflow Canvas</h3>
          <WorkflowCanvas
            nodes={model.nodes}
            edges={model.edges}
            onNodesChange={setNodes}
            onEdgesChange={setEdges}
            onAddNode={addNode}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onPublish={() => { /* contract not wired — disabled */ }}
            onRun={() => { /* contract not wired — disabled */ }}
            publishDisabled
            runDisabled
            publishHint="发布需 workflow-schema 契约（未接入，不伪造成功）"
            runHint="运行需执行契约（未接入，不伪造成功）"
          />
        </div>

        {/* B10 property panel — 属性与运行配置 */}
        <Card>
          <CardHeader>
            <span>属性面板</span>
            <span className="text-[12px] text-muted">{selected ? selected.kind : '未选中'}</span>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {selected ? (
              <>
                <label className="flex flex-col gap-1 text-[12px] text-muted">
                  节点名称
                  <Input value={selected.label} onChange={(e) => updateSelected({ label: e.target.value })} />
                </label>
                <label className="flex flex-col gap-1 text-[12px] text-muted">
                  说明
                  <Input value={selected.meta ?? ''} onChange={(e) => updateSelected({ meta: e.target.value })} placeholder="节点说明" />
                </label>
                <div className="list">
                  <div className="list-item">
                    <span className="text-muted">节点类型</span>
                    <span className="font-mono text-xs text-ink">{selected.kind}</span>
                  </div>
                  <div className="list-item">
                    <span className="text-muted">连接数</span>
                    <span className="font-mono text-xs text-ink">{edgeCount}</span>
                  </div>
                </div>
                <p className="text-[12px] leading-relaxed text-muted">
                  选中节点后在画布内拖动以移动；点节点右上 + 手柄向目标节点拖出即可连线；工具栏删除所选。
                </p>
              </>
            ) : (
              <div className="empty py-8">
                <div className="icon" aria-hidden="true">＋</div>
                <p className="m-0 text-sm font-semibold text-ink">点击画布中的节点查看属性</p>
                <p className="mx-auto mt-1 max-w-md text-xs">未选中任何节点（无本地编辑焦点）</p>
              </div>
            )}
          </CardContent>
          {/* B10 nested 部署说明 panel (panel inside panel) */}
          <div className="panel mt-3.5">
            <h3>部署说明</h3>
            <div className="muted text-xs">
              该编辑器为本地编辑模型；发布 / 运行在真实 workflow-schema 与执行契约接入前保持禁用（不伪造成功）。
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
