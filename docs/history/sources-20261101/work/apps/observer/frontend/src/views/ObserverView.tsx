// L10 (2026-09-27) · L10b (2026-09-27): B10 Observer lane — the READ-ONLY
// observer topology (Observer §8: topology / Agent / Workflow / Tool / MCP /
// Memory / Task Pack / abnormal nodes / running state, metrics + trend).
//
// The DOM is the verbatim B10 `.split` (1.35fr .95fr) + `.graph-stage`
// (core pulse + 6 `.node-dot` satellites + connector lines, clickable to open a
// read-only `.drawer` detail) on the left, and the `.panel` `.metric-row`
// (4 `.metric-box`) + honest `.spark` trend on the right.
//
// There are NO write/approve/retry/apply/rollback controls anywhere on this
// page — not even a disabled one.
import * as React from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { GraphLegend, NodeGraph, type GraphNode } from '@/components/graph/node-graph'
import { Sparkline } from '@/components/ui/sparkline'
import { StatusPill } from '@/components/ui/status'
import { Drawer } from '@/components/ui/drawer'
import type { SnapshotV3 } from '@/types'

// B10 `.metric-row` = 4 metric-box cells (transport / freshness / coverage /
// revision) — all REAL v3 values, UNKNOWN when absent.
interface MetricCell {
  label: string
  value: string
  tone?: 'success' | 'warning' | 'error' | 'muted'
}

export function ObserverView({ snap }: { snap: SnapshotV3 | null }) {
  const tr = snap?.transport
  const cov = snap?.coverage
  const [selected, setSelected] = React.useState<string | null>(null)

  // Topology nodes = the observer's own read-only projection entities. The
  // "active" state on a node reflects a REAL running execution (agent present
  // in a RUNNING/STARTING execution), never a fabricated healthy flag.
  const runningAgents = new Set(
    (snap?.executions || [])
      .filter((e) => e.state === 'RUNNING' || e.state === 'STARTING')
      .map((e) => e.agent)
      .filter((a): a is string => !!a),
  )
  const nodes: GraphNode[] = [
    { id: 'agent', label: 'Agent', state: runningAgents.size ? 'active' : 'idle' },
    { id: 'workflow', label: 'Workflow', state: 'idle' },
    { id: 'tool', label: 'Tool', state: 'idle' },
    { id: 'mcp', label: 'MCP', state: 'idle' },
    { id: 'memory', label: 'Memory', state: 'idle' },
    { id: 'taskpack', label: 'Task Pack', state: 'idle' },
  ]
  const selNode = nodes.find((n) => n.id === selected) ?? null

  const metrics: MetricCell[] = [
    {
      label: '传输状态',
      value: tr?.transportState || 'UNKNOWN',
      tone: tr?.transportState === 'LIVE' ? 'success' : tr?.transportState === 'OFFLINE' ? 'error' : 'muted',
    },
    {
      label: '新鲜度',
      value: tr?.freshnessState || 'UNKNOWN',
      tone: tr?.freshnessState === 'FRESH' ? 'success' : 'warning',
    },
    {
      label: '覆盖度',
      value:
        cov && cov.numerator != null
          ? `${cov.numerator}/${cov.denominator ?? '?'} · ${cov.scope || 'UNKNOWN'}`
          : 'UNKNOWN',
      tone: 'muted',
    },
    { label: '快照修订', value: snap ? String(snap.revision) : 'UNKNOWN', tone: 'muted' },
  ]

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Observer / 观察者"
        description="只读观测投影：拓扑 / Agent / Workflow / Tool / MCP / Memory / Task Pack / 异常节点 / 运行状态 / 指标 / 趋势。本页无任何 批准 / 拒绝 / 撤销 / 重试 操作（Observer §8 只读铁律）。"
        actions={
          <StatusPill variant={tr?.transportState === 'LIVE' ? 'success' : 'muted'}>
            {tr?.transportState || 'UNKNOWN'} · 只读
          </StatusPill>
        }
      />

      <div className="split">
        <Card>
          <CardHeader>
            <span>观测拓扑（只读）</span>
            <span className="text-[12px] text-muted">核心 = Observer 投影 · 卫星 = 观测实体</span>
          </CardHeader>
          <CardContent>
            <NodeGraph
              core="Observer"
              nodes={nodes}
              selected={selected}
              onSelect={setSelected}
            />
            <GraphLegend
              className="mt-2"
              core="Observer"
              nodes={nodes}
              selected={selected}
              onSelect={setSelected}
            />
          </CardContent>
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader><span>指标（真实投影）</span></CardHeader>
            <CardContent>
              <div className="metric-row" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
                {metrics.map((m) => (
                  <div key={m.label} className="metric-box">
                    <div className="muted text-[12px]">{m.label}</div>
                    <div className="mt-1 text-[15px] font-bold tabular-nums text-ink">{m.value}</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader><span>执行趋势</span></CardHeader>
            <CardContent>
              {/* Honest: the v3 snapshot carries NO execution-trend series.
                  Empty series -> the shared Sparkline renders "无趋势数据
                  (UNKNOWN)" — never a fabricated B10 demo sequence. */}
              <Sparkline values={[]} height={140} />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* read-only entity detail drawer */}
      <Drawer open={!!selNode} onClose={() => setSelected(null)} title={selNode ? `实体 · ${selNode.label}` : '实体详情'}>
        {selNode ? (
          <div className="flex flex-col gap-3">
            <div className="status-stack">
              <StatusPill variant={selNode.state === 'active' ? 'success' : selNode.state === 'error' ? 'error' : 'muted'}>
                {selNode.state === 'active' ? '运行中' : selNode.state === 'error' ? '异常' : '空闲'}
              </StatusPill>
            </div>
            <p className="text-xs leading-relaxed text-muted">
              该实体为 Observer 只读观测投影。{selNode.state === 'active' ? '当前存在真实运行中的执行（agent 维度命中）。' : '未观测到运行中的执行。'}
              无任何操作入口 — 观测不等于控制。
            </p>
          </div>
        ) : null}
      </Drawer>
    </div>
  )
}
