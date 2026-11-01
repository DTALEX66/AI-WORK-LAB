// L10 (2026-09-27) · L10b (2026-09-27) · WUI-01 (2026-10-09): the landing surface — 项目监控.
//
// The lane id stays `overview`: the 20261009 route table maps `overview` INTO 项目监控 and forbids a
// second home ("不建立双首页"), so the id and its deep links survive while the content changes. What did
// change follows that table's own instruction ("复用可用摘要，去掉无事实图表和禁用执行主按钮"):
//
//   * the project collection is what the home answers first (components/dashboard/ProjectSummaryTable);
//   * the trend panel that had no series behind it and the six hardcoded signal-map nodes are gone — a
//     chart frame holding no fact is still a claim the projection cannot make;
//   * the permanently-disabled 新建执行 / 导出状态 buttons are gone. A control that can never act is not a
//     read-only boundary, it is a dead control; the boundary is stated in words instead.
//
// B5 discipline preserved: without a snapshot the three fact KPIs read UNKNOWN (never a fabricated 0),
// the "数据源未接入" honest indicator is present, and NO trend percentage is invented.
import * as React from 'react'
import { PageHeader } from '@/components/ui/page-header'
import { KPICard } from '@/components/dashboard/KPICard'
import { ProjectSummaryTable } from '@/components/dashboard/ProjectSummaryTable'
import { Badge } from '@/components/ui/badge'
import { IssueCenter } from '@/views/IssueCenter'
import { OVERVIEW_LABEL } from '@/lib/viewRegistry'
import {
  fmtCostQuality, fmtTimestamp, tokenTruth, executionsToRows,
  type LiveSnapshotState,
} from '@/lib/api'
import type { SnapshotV3 } from '@/types'

export interface OverviewViewProps {
  snap: SnapshotV3 | null
  source: LiveSnapshotState['source']
  live: boolean
}

function fmtTokensSafe(tt: ReturnType<typeof tokenTruth>): string {
  if (!tt || tt.totalTokens == null) return 'UNKNOWN'
  const n = tt.totalTokens
  return n >= 1e6 ? (n / 1e6).toFixed(2) + 'M' : (n / 1e3).toFixed(0) + 'k'
}

export function OverviewView({ snap, source, live }: OverviewViewProps) {
  const tt = tokenTruth(snap)
  const rows = executionsToRows(snap)
  const activeExecs = rows.filter((r) => r.state === 'RUNNING' || r.state === 'STARTING').length
  const tr = snap?.transport
  const cov = snap?.coverage

  // Alerts = honest signals only: failed CI runs / failed executions /
  // transport OFFLINE. No fabricated alert counts.
  const alerts = React.useMemo(() => {
    const out: { leading?: string; title: string; sub?: string; tag: string; variant: 'success' | 'warning' | 'error' | 'info' | 'muted' }[] = []
    for (const r of snap?.ci || []) {
      if (r.conclusion === 'failure' || r.conclusion === 'cancelled') {
        out.push({ leading: r.runId ?? '—', title: `${r.workflow ?? 'CI'} 失败`, sub: r.headSha ? `@ ${r.headSha.slice(0, 8)}` : undefined, tag: r.conclusion ?? 'failure', variant: 'error' })
      }
    }
    for (const r of rows) {
      if (r.state === 'FAILED' || r.state === 'BLOCKED') {
        out.push({ leading: r.id, title: '执行受阻 / 失败', sub: r.name || r.id, tag: r.state, variant: 'error' })
      }
    }
    if (tr && tr.transportState === 'OFFLINE') {
      out.push({ title: '数据源离线', sub: 'sidecar 快照不可达', tag: 'OFFLINE', variant: 'error' })
    }
    return out.slice(0, 8)
  }, [snap, rows, tr])

  // B10 `.status-stack` tags — driven by REAL transport/coverage values only.
  const stack: { text: string; variant: 'success' | 'warning' | 'info' | 'muted' }[] = [
    live
      ? { text: 'Transport LIVE', variant: 'success' }
      : { text: `Transport ${tr?.transportState || 'UNKNOWN'}`, variant: tr?.transportState === 'OFFLINE' ? 'warning' : 'muted' },
    { text: tr?.freshnessState ? `Freshness ${tr.freshnessState}` : 'Freshness UNKNOWN', variant: tr?.freshnessState === 'FRESH' ? 'info' : 'muted' },
    // Three states, not two: with no snapshot there are no alerts *and* no way to
    // know — the panel below already says 保持 UNKNOWN，不伪造「全部正常」, so a green
    // "no alert signals" chip here would contradict it and read as a clean system.
    !snap
      ? { text: '告警状态 UNKNOWN', variant: 'muted' as const }
      : alerts.length
        ? { text: `${alerts.length} 条告警信号`, variant: 'warning' as const }
        : { text: '无告警信号', variant: 'success' as const },
  ]

  const taskEntries = Object.entries(snap?.tasks || {}).slice(0, 6)

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={OVERVIEW_LABEL}
        description="按项目观察参与软件、活动、阻碍、资源与来源新鲜度。真值来自 v3 快照投影，缺失即 UNKNOWN，不伪造。筛选与选择只读取投影：Observer 不发起执行、不导出状态、不写任何业务状态。"
      />

      {/* B10 `.kpi-grid` — 4 columns; the first three are FACT KPIs (B5:
          UNKNOWN without a snapshot, never 0). The 4th reads the real
          transport word, which the CI contract requires to include LIVE. */}
      <div className="kpi-grid">
        <KPICard
          title="项目"
          value={snap ? String(snap.projects.length) : 'UNKNOWN'}
          sub={snap ? 'registry · 真实' : '数据源未接入'}
          trend={snap && snap.projects.length ? '实时投影' : undefined}
          trendTone="up"
        />
        <KPICard
          title="活跃执行"
          value={snap ? String(activeExecs) : 'UNKNOWN'}
          sub={'共 ' + (snap ? String(rows.length) : '—') + ' 条'}
          trend={snap ? '实时' : undefined}
        />
        <KPICard
          title="Token"
          value={snap ? fmtTokensSafe(tt) : 'UNKNOWN'}
          sub={'质量 ' + fmtCostQuality(tt?.costQuality)}
        />
        <KPICard
          title="数据源"
          value={live ? 'LIVE' : snap ? source.toUpperCase() : 'UNKNOWN'}
          sub={snap ? 'revision ' + String(snap.revision) : '等待数据'}
          trend={tr?.freshnessState ? '新鲜度 ' + tr.freshnessState : undefined}
          trendTone={tr?.freshnessState === 'FRESH' ? 'up' : 'warn'}
        />
      </div>

      {/* WUI-01: the project collection is the home's first answer. It is full width because nine
          readable columns do not fit a half-width panel, and `.table-wrap` is its own scroll box. */}
      <div className="panel p-4">
        <h3 className="mb-3">项目集合</h3>
        <ProjectSummaryTable
          snap={snap}
          search={typeof window !== 'undefined' ? window.location.search : ''}
        />
      </div>

      {/* CL-07: the problem centre answers 需要处理的问题 on the landing page. It reads `snap.issues` and
          `snap.issuesSummary` directly and keeps absent / empty / truncated as three different statements. */}
      <IssueCenter snap={snap} />

      {/* B10 `.two-col` — source freshness + system status. The 执行趋势 panel is gone: the v3 snapshot
          carries no trend series, so the frame plotted nothing while looking like a chart. */}
      <div className="two-col">
        <div className="panel">
          <h3>来源新鲜度</h3>
          <div className="list">
            <div className="list-item">
              <span className="text-[12px] text-muted">快照生成</span>
              <span className="ml-3 min-w-0 truncate text-right text-[12px] text-ink">{fmtTimestamp(snap?.generatedAt ?? null)}</span>
            </div>
            <div className="list-item">
              <span className="text-[12px] text-muted">源水位 sourceWatermark</span>
              <span className="ml-3 min-w-0 truncate text-right text-[12px] text-ink">{fmtTimestamp(snap?.sourceWatermark ?? null)}</span>
            </div>
            <div className="list-item">
              <span className="text-[12px] text-muted">最后心跳 lastHeartbeatAt</span>
              <span className="ml-3 min-w-0 truncate text-right text-[12px] text-ink">{fmtTimestamp(tr?.lastHeartbeatAt ?? null)}</span>
            </div>
            <div className="list-item">
              <span className="text-[12px] text-muted">写者水位 writerWatermarkAt</span>
              <span className="ml-3 min-w-0 truncate text-right text-[12px] text-ink">{fmtTimestamp(tr?.writerWatermarkAt ?? null)}</span>
            </div>
            <div className="list-item">
              <span className="text-[12px] text-muted">本次连接自 connectedSince</span>
              <span className="ml-3 min-w-0 truncate text-right text-[12px] text-ink">{fmtTimestamp(tr?.connectedSince ?? null)}</span>
            </div>
          </div>
          <div className="mt-3 text-[12px] text-muted">
            各时间的含义分开读：源产生 · 本地接收 · 页面可见。last-good 带时间；断连或滞后都不推出软件已停止。
          </div>
        </div>
        <div className="panel">
          <h3>系统状态</h3>
          <div className="metric-row">
            <div className="metric-box">
              <div className="muted text-[12px]">传输</div>
              <div className="text-[15px] font-bold tabular-nums text-ink">{tr?.transportState || 'UNKNOWN'}</div>
            </div>
            <div className="metric-box">
              <div className="muted text-[12px]">新鲜度</div>
              <div className="text-[15px] font-bold tabular-nums text-ink">{tr?.freshnessState || 'UNKNOWN'}</div>
            </div>
            <div className="metric-box">
              <div className="muted text-[12px]">覆盖</div>
              <div className="text-[15px] font-bold tabular-nums text-ink">
                {cov && cov.numerator != null ? `${cov.numerator}/${cov.denominator ?? '?'}` : 'UNKNOWN'}
              </div>
            </div>
            <div className="metric-box">
              <div className="muted text-[12px]">修订</div>
              <div className="text-[15px] font-bold tabular-nums text-ink">{snap ? String(snap.revision) : 'UNKNOWN'}</div>
            </div>
          </div>
          <div className="status-stack mt-4">
            {stack.map((s) => (
              <Badge key={s.text} variant={s.variant}>{s.text}</Badge>
            ))}
          </div>
        </div>
      </div>

      {/* B10 `.split` — recent executions + Observer Signal Map */}
      <div className="split">
        <div className="panel">
          <h3>最近执行</h3>
          {rows.length === 0 ? (
            <div className="empty py-10">
              <div className="icon" aria-hidden="true">◎</div>
              <p className="m-0 text-sm font-semibold text-ink">数据源未接入</p>
              <p className="mx-auto mt-1 max-w-md text-xs">无执行记录投影 —— 保持 UNKNOWN，不伪造执行行</p>
            </div>
          ) : (
            <div className="list">
              {rows.slice(0, 6).map((r) => (
                <div key={r.id} className="list-item">
                  <div className="min-w-0">
                    <strong className="block truncate text-[13px] font-semibold text-ink">{r.name || r.id}</strong>
                    <small className="block truncate font-mono">
                      {r.platform || 'UNKNOWN'} · {r.id}
                    </small>
                  </div>
                  <Badge variant={r.state === 'FAILED' ? 'error' : r.state === 'BLOCKED' ? 'warning' : r.state === 'COMPLETED' ? 'success' : 'info'}>
                    {r.state}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
        {/* WUI-01: this half of the split is where the six hardcoded map nodes used to sit. The block now
            carries the real blocker signals, because 主要阻碍 is one of the home page's required columns. */}
        <div className="panel">
          <h3>主要阻碍（真实信号）</h3>
          {alerts.length ? (
            <div className="list">
              {alerts.map((a, i) => (
                <div key={i} className="list-item">
                  <div className="min-w-0">
                    <strong className="block truncate text-[13px] font-semibold text-ink">{a.title}</strong>
                    <small className="block truncate font-mono">
                      {a.leading ? a.leading + ' · ' : ''}{a.sub || '—'}
                    </small>
                  </div>
                  <Badge variant={a.variant}>{a.tag}</Badge>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-5 text-center text-xs text-muted">
              {snap ? '当前无告警信号（无失败 CI / 无受阻执行 / 传输在线）' : '数据源未接入 — 无法判断告警（保持 UNKNOWN，不伪造「全部正常」）'}
            </div>
          )}
        </div>
      </div>

      <div className="panel p-4">
        <h3 className="mb-3">最近任务包</h3>
        {taskEntries.length ? (
          <div className="metric-row" style={{ gridTemplateColumns: 'repeat(3, minmax(0, 1fr))' }}>
            {taskEntries.map(([family, count]) => (
              <div key={family} className="metric-box">
                <div className="muted text-[12px]">{family}</div>
                <div className="big-number mt-1">{count}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-5 text-center text-xs text-muted">数据源未接入 — 无任务包计数（UNKNOWN）</div>
        )}
        <div className="mt-3 text-[12px] text-muted">
          任务包计数是本仓工程诊断口径，不要求被观察的项目登记任务。
        </div>
      </div>
    </div>
  )
}
