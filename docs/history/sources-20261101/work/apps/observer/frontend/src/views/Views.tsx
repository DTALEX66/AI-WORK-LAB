import * as React from 'react'
import { Card, CardHeader, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { PageHeader } from '@/components/ui/page-header'
import type {
  SnapshotV3, Execution, Project, GitMatchState,
} from '@/types'
import { fmtTokens, fmtCostQuality, fmtTimestamp, stateTone, activityTone } from '@/lib/api'
import { AdapterCapabilityCards } from '@/views/AdapterCapabilityCards'
import { StateMatrixCard } from '@/components/ui/states'
import { CollectorDeliverySummary } from '@/components/ui/collector-delivery'

type Snap = SnapshotV3 | null

// L10b: B10 `.list-item` row — muted key on the left, real value (or UNKNOWN)
// in mono on the right. Never a fabricated value.
function Row({ k, v }: { k: string; v: React.ReactNode }) {
  const empty = v === null || v === undefined || v === ''
  return (
    <div className="list-item">
      <span className="text-[12px] text-muted">{k}</span>
      <span className="ml-3 min-w-0 truncate text-right font-mono text-[12px] text-ink">{empty ? 'UNKNOWN' : v}</span>
    </div>
  )
}

function toneVariant(tone: string): 'success' | 'warning' | 'error' | 'info' | 'muted' {
  switch (tone) {
    case 'running': return 'success'
    case 'pending': case 'blocked': return 'warning'
    case 'failed': return 'error'
    case 'done': return 'info'
    default: return 'muted'
  }
}

/**
 * Keyed by the union rather than switch-cased, so a seventh producer outcome is a compile error here
 * instead of a badge that quietly renders `muted`. The row used to read
 * `matchState === 'DRIFT' ? 'error' : 'muted'`: `DRIFT` is not a value `_git_match_state` returns, so
 * `MISMATCH` — the state a user actually needs to see in red — was falling through to muted.
 */
const GIT_MATCH_VARIANT: Record<GitMatchState, 'success' | 'warning' | 'error' | 'info' | 'muted'> = {
  MATCH: 'success',
  LOCAL_REMOTE_MATCH: 'warning',
  LOCAL_CI_MATCH: 'warning',
  MISMATCH: 'error',
  NO_LOCAL_CLAIM: 'muted',
  UNVERIFIED: 'muted',
}

function gitMatchVariant(state: GitMatchState | undefined) {
  return state === undefined ? 'muted' : GIT_MATCH_VARIANT[state]
}

const STATE_TEXT: Record<string, string> = {
  RUNNING: '运行中', STARTING: '启动中', WAITING_USER: '待用户', WAITING_APPROVAL: '待审批',
  BLOCKED: '受阻', COMPLETED: '完成', FAILED: '失败', UNKNOWN: '未知',
}

// ---------- 共享：项目平台表（P1-01 抽出，ProjectsView 与旧 AgentsView 复用同一真值投影）----------
export function ProjectsTable({ projects }: { projects: Project[] }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>项目</th>
            <th>平台</th>
            <th>活动</th>
            <th>执行</th>
            <th>Token</th>
            <th>Git</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => {
            const tone = activityTone(p.activityState)
            const dirty = p.git.dirtyCount
            return (
              <tr key={p.projectId}>
                <td>
                  <strong className="block text-[12px] font-semibold text-ink">{p.displayName || p.projectId}</strong>
                  <small className="font-mono text-[12px] text-muted">{p.identityState === 'RESOLVED' ? '已解析身份' : '身份未解析'}</small>
                </td>
                <td className="text-muted">{p.agentPlatform || 'UNKNOWN'}</td>
                <td><Badge variant={tone === 'active' ? 'success' : 'muted'}>{p.activityState || 'UNKNOWN'}</Badge></td>
                <td className="tabular-nums text-ink">{p.activeExecutionCount}</td>
                <td className="tabular-nums text-ink" title="costQuality（后端权威）">
                  {fmtTokens(p.token.totalTokens)} <span className="text-[12px] text-muted">{fmtCostQuality(p.token.costQuality)}</span>
                </td>
                <td>
                  <span className="font-mono text-[12px] text-muted">{p.git.branch || '—'}@{p.git.localSha ? p.git.localSha.slice(0, 7) : '—'}</span>{' '}
                  {dirty == null ? <Badge variant="muted">脏 UNKNOWN</Badge>
                    : dirty ? <Badge variant="warning">脏 {dirty}</Badge>
                    : <Badge variant="muted">干净</Badge>}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------- 项目（P1-D §3.1 一级入口 · 原 AgentsView 折叠的项目平台表，独立成视图）----------
export function ProjectsView({ snap }: { snap: Snap }) {
  const projects: Project[] = snap?.projects || []
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader><span>项目平台</span><span className="text-[12px] text-muted">{projects.length} 个项目 · 真实 registry</span></CardHeader>
        <CardContent>
          {projects.length === 0 ? (
            <div className="empty py-10">
              <div className="icon" aria-hidden="true">◇</div>
              <p className="m-0 text-sm font-semibold text-ink">暂无已注册项目（registry 为空）</p>
              <p className="mx-auto mt-1 max-w-md text-xs">数据源未接入时不伪造项目身份</p>
            </div>
          ) : (
            <ProjectsTable projects={projects} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ---------- 智能体（agent 实例：真实 executions 按 agent 聚合，不发明字段）----------
export function AgentsView({ snap }: { snap: Snap }) {
  const exs: Execution[] = snap?.executions || []
  // group executions by agent (null agent bucketed as UNKNOWN) — real rows only
  const byAgent = new Map<string, Execution[]>()
  for (const e of exs) {
    const key = e.agent || 'UNKNOWN'
    const arr = byAgent.get(key)
    if (arr) arr.push(e); else byAgent.set(key, [e])
  }
  return (
    <div className="flex flex-col gap-4">
      {/* P1-03: declared / detected / available / invoked / natively verified are five different facts.
          The execution table below only ever showed the fourth-ish; the cards show all seven layers with
          the reason any layer is still unprobed. */}
      <AdapterCapabilityCards snap={snap} />
      <Card>
        <CardHeader><span>Agent 实例</span><span className="text-[12px] text-muted">{byAgent.size} 个 agent · {exs.length} 条执行 · 真实投影</span></CardHeader>
        <CardContent>
          {exs.length === 0 ? (
            <div className="empty py-10">
              <div className="icon" aria-hidden="true">◎</div>
              <p className="m-0 text-sm font-semibold text-ink">暂无 agent 执行记录（保持 UNKNOWN）</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Agent</th>
                    <th>状态</th>
                    <th>会话</th>
                    <th>工作区</th>
                  </tr>
                </thead>
                <tbody>
                  {exs.map((e) => (
                    <tr key={e.executionId}>
                      <td className="font-mono text-ink">{e.agent || 'UNKNOWN'}</td>
                      <td><Badge variant={toneVariant(stateTone(e.state))}>{STATE_TEXT[e.state] || e.state}</Badge></td>
                      <td className="font-mono text-[12px] text-muted">{e.sessionId || 'UNKNOWN'}</td>
                      <td className="font-mono text-[12px] text-muted">{e.workingArea || 'UNKNOWN'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ---------- 执行 ----------
export function ExecutionsView({ snap }: { snap: Snap }) {
  const exs: Execution[] = snap?.executions || []
  const transport = snap?.transport
  const tasks = snap?.tasks
  const taskRows = tasks ? Object.entries(tasks) : []
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader><span>执行详情</span><span className="text-[12px] text-muted">{exs.length} 个执行 · 真实</span></CardHeader>
        <CardContent>
          {exs.length === 0 ? (
            <div className="empty py-10">
              <div className="icon" aria-hidden="true">◎</div>
              <p className="m-0 text-sm font-semibold text-ink">暂无执行记录（保持 UNKNOWN）</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>执行 ID</th>
                    <th>Agent</th>
                    <th>状态</th>
                    <th>项目</th>
                    <th>会话</th>
                    <th>工作区</th>
                  </tr>
                </thead>
                <tbody>
                  {exs.map((e) => (
                    <tr key={e.executionId}>
                      <td className="font-mono text-muted">{e.executionId}</td>
                      <td>{e.agent || 'UNKNOWN'}</td>
                      <td><Badge variant={toneVariant(stateTone(e.state))}>{STATE_TEXT[e.state] || e.state}</Badge></td>
                      <td className="text-ink">{e.anchorProjectId || 'UNKNOWN'}</td>
                      <td className="font-mono text-[12px] text-muted">{e.sessionId || 'UNKNOWN'}</td>
                      <td className="font-mono text-[12px] text-muted">{e.workingArea || 'UNKNOWN'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      <div className="two-col">
        <Card><CardHeader><span>传输与水位（真实）</span></CardHeader><CardContent>
          <div className="list">
            <Row k="传输状态" v={transport?.transportState} />
            <Row k="新鲜度" v={transport?.freshnessState} />
            <Row k="事件流" v={transport?.eventStreamConnected ? '已连接' : '未连接'} />
            <Row k="最后心跳" v={fmtTimestamp(transport?.lastHeartbeatAt, 'time')} />
            <Row k="写入水位" v={fmtTimestamp(transport?.writerWatermarkAt, 'time')} />
          </div>
        </CardContent></Card>
        <Card><CardHeader><span>任务状态桶 + 快照</span></CardHeader><CardContent>
          <div className="list">
            {taskRows.length === 0
              ? <Row k="任务桶" v="UNKNOWN" />
              : taskRows.map(([k, v]) => <Row key={k} k={k} v={String(v)} />)}
            <Row k="修订号" v={snap ? String(snap.revision) : 'UNKNOWN'} />
            <Row k="数据水位" v={snap?.sourceWatermark} />
          </div>
        </CardContent></Card>
      </div>
    </div>
  )
}

// ---------- 模型 / Token 用量 ----------
export function ModelsView({ snap }: { snap: Snap }) {
  const ts = snap?.tokenSummary
  const inT = ts?.inputTokens ?? null
  const outT = ts?.outputTokens ?? null
  const total = ts?.totalTokens ?? null
  const max = Math.max(inT ?? 0, outT ?? 0, 1)
  const projects: Project[] = snap?.projects || []
  const dist = [
    { name: '输入 Token', value: inT, color: 'rgb(var(--primary-rgb))' },
    { name: '输出 Token', value: outT, color: 'rgb(var(--secondary-rgb))' },
  ]
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader><span>Token 汇总</span><span className="text-[12px] text-muted">质量 {fmtCostQuality(ts?.costQuality)} · 后端权威 · 前端不估算金额</span></CardHeader>
        <CardContent className="flex flex-col gap-4">
          {dist.map((d) => (
            <div key={d.name}>
              <div className="mb-1 flex justify-between text-xs">
                <span className="flex items-center gap-1.5 text-ink">
                  <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />{d.name}
                </span>
                <span className="tabular-nums">{fmtTokens(d.value)}</span>
              </div>
              <div className="progress">
                <div style={{ width: (max ? ((d.value ?? 0) / max) * 100 : 0) + '%', background: d.color }} />
              </div>
            </div>
          ))}
          <div className="flex justify-between text-xs text-muted"><span>总计</span><span className="tabular-nums text-ink">{fmtTokens(total)}</span></div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader><span>项目 Token 明细</span></CardHeader>
        <CardContent>
          {projects.length === 0 ? <div className="py-4 text-center text-xs text-muted">无项目</div> : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr><th>项目</th><th>输入</th><th>输出</th><th>总计</th><th>质量</th></tr>
                </thead>
                <tbody>
                  {projects.map((p) => (
                    <tr key={p.projectId}>
                      <td>{p.displayName || p.projectId}</td>
                      <td className="tabular-nums text-ink">{fmtTokens(p.token.inputTokens)}</td>
                      <td className="tabular-nums text-ink">{fmtTokens(p.token.outputTokens)}</td>
                      <td className="tabular-nums">{fmtTokens(p.token.totalTokens)}</td>
                      <td className="tabular-nums text-muted">{fmtCostQuality(p.token.costQuality)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

// ---------- 记忆 / 治理 ----------
export function MemoryView({ snap }: { snap: Snap }) {
  const gov = snap?.governance
  const fams = gov?.families
  const hist = (snap?.workspace as any)?.history || {}
  const famItems = [
    { name: '规则', state: fams?.rules?.state, drift: fams?.rules?.drift },
    { name: '技能', state: fams?.skills?.state, drift: fams?.skills?.drift },
    { name: '记忆', state: fams?.memory?.state, drift: fams?.memory?.drift },
    { name: '适配器', state: fams?.adapters?.state, drift: fams?.adapters?.drift },
  ]
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Memory Registry / 记忆注册"
        description="治理四大家族（规则/技能/记忆/适配器）的漂移真值 + 错误账本（workspace.history）的真实投影。缺失即 UNKNOWN，Observer 只读，不写记忆。"
      />
      <div className="two-col">
        <Card><CardHeader><span>治理漂移状态（真实）</span></CardHeader><CardContent>
          <div className="list">
            {famItems.map((i) => (
              <Row key={i.name} k={i.name} v={<span>{i.state || 'UNKNOWN'}{i.drift ? ' · 漂移 ' + i.drift : ''}</span>} />
            ))}
          </div>
        </CardContent></Card>
        <Card><CardHeader><span>错误账本（workspace.history）</span></CardHeader><CardContent>
          <div className="list">
            <Row k="总错误数" v={(hist.totalErrors != null ? String(hist.totalErrors) : 'UNKNOWN')} />
            {(hist.recentErrors || []).slice(0, 6).map((e: any, i: number) => (
              <div key={i} className="list-item">
                <span className="font-mono text-[12px] text-muted">{e.errorId || 'UNKNOWN'}</span>
                <span className="ml-3 min-w-0 truncate text-[12px] text-ink">{e.title || e.classification || ''}</span>
              </div>
            ))}
          </div>
          {(!hist.recentErrors || hist.recentErrors.length === 0) && <div className="py-4 text-center text-xs text-muted">无错误记录（UNKNOWN）</div>}
        </CardContent></Card>
      </div>
    </div>
  )
}

// ---------- 工具 / 能力 ----------
export function ToolsView({ snap }: { snap: Snap }) {
  const areas = Array.from(new Set((snap?.executions || []).map((e) => e.workingArea).filter((a): a is string => !!a)))
  const gov = snap?.governance
  return (
    <div className="flex flex-col gap-4">
      <Card><CardHeader><span>执行工作区</span></CardHeader><CardContent>
        {areas.length ? (
          <div className="list">
            {areas.map((w) => <div key={w} className="list-item font-mono text-xs text-ink">{w}</div>)}
          </div>
        ) : <div className="py-4 text-center text-xs text-muted">暂无执行工作区（UNKNOWN）</div>}
      </CardContent></Card>
      <Card><CardHeader><span>治理家族状态</span></CardHeader><CardContent>
        <div className="list">
          {(['rules', 'skills', 'memory', 'adapters'] as const).map((k) => (
            <Row key={k} k={k} v={gov?.families?.[k]?.state || 'UNKNOWN'} />
          ))}
        </div>
      </CardContent></Card>
    </div>
  )
}

// ---------- 监控 / 系统 ----------
export function MonitoringView({ snap }: { snap: Snap }) {
  const transport = snap?.transport
  const cov = snap?.coverage
  return (
    <div className="flex flex-col gap-4">
      <Card><CardHeader><span>传输真值（永不伪造 LIVE）</span></CardHeader><CardContent>
        <div className="list">
          <Row k="传输状态" v={<Badge variant={transport?.transportState === 'LIVE' ? 'success' : transport?.transportState === 'OFFLINE' ? 'error' : 'muted'}>{transport?.transportState || 'UNKNOWN'}</Badge>} />
          <Row k="新鲜度" v={transport?.freshnessState || 'UNKNOWN'} />
          <Row k="连接起点" v={fmtTimestamp(transport?.connectedSince, 'time')} />
          <Row k="覆盖度" v={cov && cov.numerator != null ? cov.numerator + '/' + (cov.denominator ?? '?') + ' · ' + (cov.scope || 'UNKNOWN') : 'UNKNOWN'} />
        </div>
      </CardContent></Card>
      <Card><CardHeader><span>产品状态矩阵（八态，含投影能否回答）</span></CardHeader><CardContent>
        {/* Reachability, not decoration: this card shipped with WUI-11 and was imported only by its own
            test, so no user could ever see which of the eight states the projection can answer. The
            diagnostics lane is where that reference belongs. */}
        <StateMatrixCard />
      </CardContent></Card>
      <Card><CardHeader><span>采集器交付与拒绝（快照级）</span><span className="text-[12px] text-muted">与设置页同一读法</span></CardHeader><CardContent>
        {/* The matrix states which answers the projection can give; this card is the one
            producer-backed answer behind 局部故障. Same component as Settings, so the two
            surfaces cannot drift into different wording for the same rows. */}
        <CollectorDeliverySummary collectors={snap?.collectors} />
      </CardContent></Card>
      <Card><CardHeader><span>说明</span></CardHeader><CardContent className="text-xs text-muted">
        服务健康 = 传输真值，不是伪造的 healthy。LIVE 仅当 live-gate verdict 为 LIVE；canonical readback 失败回退 DELAYED/OFFLINE。Observer 严格只读。
      </CardContent></Card>
    </div>
  )
}

// ---------- 交付 ----------
export function DeliveryView({ snap }: { snap: Snap }) {
  const git = snap?.git
  const ci = snap?.ci || []
  return (
    <div className="flex flex-col gap-4">
      <div className="two-col">
        <Card><CardHeader><span>Git 状态（真实）</span></CardHeader><CardContent>
          <div className="list">
            <Row k="本地" v={git?.localSha ? git.localSha.slice(0, 7) : 'UNKNOWN'} />
            <Row k="远程" v={git?.remoteSha ? git.remoteSha.slice(0, 7) : 'UNKNOWN'} />
            <Row k="CI HEAD" v={git?.ciSha ? git.ciSha.slice(0, 7) : 'UNKNOWN'} />
            <Row k="匹配状态" v={<Badge variant={gitMatchVariant(git?.matchState)}>{git?.matchState || 'UNKNOWN'}</Badge>} />
          </div>
        </CardContent></Card>
        <Card><CardHeader><span>CI 运行</span></CardHeader><CardContent>
          {ci.length ? (
            <div className="list">
              {ci.slice(0, 5).map((r, i) => (
                <div key={i} className="list-item">
                  <span className="min-w-0 truncate font-mono text-xs text-muted">{r.headSha ? r.headSha.slice(0, 7) : 'UNKNOWN'} · {r.workflow || 'UNKNOWN'}</span>
                  <Badge variant={r.conclusion === 'success' || r.status === 'success' ? 'success' : r.status ? 'warning' : 'muted'}>{r.conclusion || r.status || 'UNKNOWN'}</Badge>
                </div>
              ))}
            </div>
          ) : <div className="py-2 text-xs text-muted">无 CI 记录（UNKNOWN）</div>}
        </CardContent></Card>
      </div>
    </div>
  )
}

// ---------- 可信 ----------
export function TrustView({ snap }: { snap: Snap }) {
  const ts = snap?.tokenSummary
  const quality = ts?.costQuality || 'UNKNOWN'
  const transport = snap?.transport
  const cov = snap?.coverage
  const refs = snap?.sourceRefs || []
  return (
    <div className="flex flex-col gap-4">
      <Card><CardHeader><span>数据可信度（真实投影）</span></CardHeader><CardContent>
        <div className="list">
          <Row k="Token 质量" v={<Badge variant={quality === 'EXACT' ? 'success' : quality === 'ESTIMATED' ? 'warning' : 'muted'}>{quality}</Badge>} />
          <Row k="传输状态" v={transport?.transportState || 'UNKNOWN'} />
          <Row k="新鲜度" v={transport?.freshnessState || 'UNKNOWN'} />
          <Row k="覆盖度" v={cov && cov.numerator != null ? cov.numerator + '/' + (cov.denominator ?? '?') + ' · ' + (cov.scope || 'UNKNOWN') : 'UNKNOWN'} />
          <Row k="证据引用数" v={refs.length ? String(refs.length) : '0'} />
          <Row k="快照生成" v={fmtTimestamp(snap?.generatedAt)} />
        </div>
      </CardContent></Card>
      <Card><CardHeader><span>原则</span></CardHeader><CardContent className="text-xs text-muted">
        未知值保持 UNKNOWN，不伪造 0；Token/成本仅后端投影的质量标签（EXACT/ESTIMATED/UNKNOWN），前端不算金额、不算汇率、不算配额；Observer 严格只读，不构成第二 Update Authority。
      </CardContent></Card>
    </div>
  )
}

// ---------- 设置 ----------
export function SettingsView({ snap }: { snap: Snap }) {
  const cfg = (window as any).__OBSERVER_CONFIG__
  const descriptorSource = cfg?.apiBase ? 'window-config' : 'static-preview/tauri-injected'
  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Settings / 设置"
        description="数据源、事件流、版本与数据水位的真实投影。本地个人研究使用：无访问令牌、无锁定、无鉴权入口；Observer 严格只读。"
      />
      <div className="split">
        <Card><CardHeader><span>数据源（真实）</span></CardHeader><CardContent>
          <div className="list">
            <Row k="快照端点来源" v={descriptorSource} />
            <Row k="事件流" v={snap?.transport.eventsUrl || 'UNKNOWN'} />
            <Row k="传输状态" v={snap?.transport.transportState || 'UNKNOWN'} />
          </div>
        </CardContent></Card>
        <div className="flex flex-col gap-4">
          <Card><CardHeader><span>版本信息</span></CardHeader><CardContent>
            <div className="list">
              <Row k="修订号" v={snap ? String(snap.revision) : 'UNKNOWN'} />
              <Row k="Schema" v={snap?.schemaVersion || 'UNKNOWN'} />
              <Row k="生成时间" v={fmtTimestamp(snap?.generatedAt)} />
              <Row k="数据水位" v={snap?.sourceWatermark || 'UNKNOWN'} />
            </div>
          </CardContent></Card>
          <Card><CardHeader><span>关于</span></CardHeader><CardContent className="text-xs text-muted">
            WORK-LAB Observer · 客户端中立控制塔 · 只读投影 · 严格真实（sidecar v3 snapshot + SSE；无 Prometheus/本地资源伪造）
          </CardContent></Card>
        </div>
      </div>
    </div>
  )
}
