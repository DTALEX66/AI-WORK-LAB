// U05 (taskpack 20260919) · L10b (2026-09-27) · 2026-10-18 phenotype pass · 2026-10-19 fusion.
//
// Compact is the DEDICATED 440×680 floating HUD: no rail, one column, and it
// reads the REAL v3 transport/token/coverage truth. The EXECUTION model follows
// the open-source Agent HUD (jazzenchen/agent-hud-open, Apache-2.0): a notch
// panel with segmented views, one card per source, a recent-usage strip and a
// waiting list. No source code is copied -- the shape is ported, and every slot
// is filled from the v3 projection only:
//
//   * the hero total is tokenSummary.totalTokens; null prints UNKNOWN;
//   * each ring is one projects[].agentPlatform group, and its arc is that
//     group's share of the REPORTED project-token sum — labelled as derived;
//   * a null project token never enters the denominator (no zero-padding);
//   * input/output are summed only over values that were reported, and
//     "unclassified" stays uncomputable when a project lacks a part;
//   * sessions are executions[] (state priority, no invented elapsed time);
//   * the waiting lane splits execution waits from workspace.plan.approvals,
//     because they are different objects, and offers NO approve/deny action:
//     Observer is a read-only projection;
//   * the sparkline is this session's own observation series. With fewer than
//     two points it says so instead of drawing a trend nobody measured;
//   * the reference's quota, balance, 30-day bucket and per-session token lanes
//     have no producer in v3 and are named unavailable, never drawn.
import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import type { SnapshotV3 } from '@/types'
import {
  fmtCostQuality, fmtTimestamp, tokenTruth, transportTruth,
} from '@/lib/api'
import {
  appendTokenSample, buildHudApprovals, buildHudProviders, buildHudSessions,
  fmtExactTokens, fmtHudTokens, foldHudProviders, HUD_MAX_PROVIDER_CARDS,
  HUD_TABS, hudAgentBar, hudStateOf, hudTabFromParam, ringArc, sessionTokenDelta,
  type HudProvider, type HudTab, type TokenSample,
} from './hudModel'

const RING_RADIUS = 42

function HudSpark({ samples }: { samples: TokenSample[] }) {
  const values = samples.map((s) => s.total)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100
      // A flat series sits on the mid-line; it is not a rise or a fall.
      const y = span === 0 ? 50 : 94 - ((v - min) / span) * 88
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')
  const area = `0,100 ${pts} 100,100`
  return (
    <svg
      className="hud-spark-svg"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      role="img"
      aria-label={`本次会话 token 观测序列，${samples.length} 个修订，最新 ${fmtExactTokens(values[values.length - 1])}`}
    >
      <defs>
        <linearGradient id="hud-spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.26" />
          <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="hud-spark-stroke" x1="0" x2="1">
          <stop offset="0%" stopColor="var(--primary)" />
          <stop offset="100%" stopColor="var(--secondary)" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#hud-spark-fill)" />
      <polyline
        points={pts}
        fill="none"
        stroke="url(#hud-spark-stroke)"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

function providerTitle(provider: HudProvider): string {
  if (provider.aggregate) return `${provider.key}（合并显示，明细在下方）`
  return provider.key === 'UNKNOWN' ? '未声明 agentPlatform 的项目' : provider.key
}

function readUrlParam(name: string): string | null {
  try {
    return new URLSearchParams(window.location.search).get(name)
  } catch {
    return null
  }
}

export function CompactHUD({ snap, live, error = null }: {
  snap: SnapshotV3 | null; live: boolean; error?: string | null
}) {
  const tt = tokenTruth(snap)
  // Same derivation as the top bar: a payload's own LIVE word is not ours to
  // repeat after the read path stops, and a LIVE transport whose sampling went
  // stale is "LIVE · 采样已过期", not a plain green LIVE.
  const truth = transportTruth(snap, live, error)
  const stale = truth.state === 'LIVE' && truth.samplingStale
  const transport = stale ? 'LIVE · 采样已过期' : truth.state
  const state = stale ? 'waiting' : hudStateOf(truth.state)
  const total = tt?.totalTokens ?? null
  const totalLabel = fmtExactTokens(total)
  // The hero must not run under the status pill. Above ten glyphs the exact
  // grouping is kept and the type shrinks; the value is never abbreviated here.
  const totalFontSize = total != null && totalLabel.length > 10
    ? `${Math.min(40, Math.max(22, 420 / totalLabel.length)).toFixed(1)}px`
    : undefined
  const providers = useMemo(() => buildHudProviders(snap), [snap])
  // One row of rings. A fixed panel cannot grow a second row without pushing
  // the footer out of the window; the tail becomes one explicit summary card.
  const displayProviders = useMemo(() => foldHudProviders(providers), [providers])
  const sessions = useMemo(() => buildHudSessions(snap), [snap])
  const approvals = useMemo(() => buildHudApprovals(snap), [snap])
  const foldedCount = providers.length > HUD_MAX_PROVIDER_CARDS
    ? providers.length - (HUD_MAX_PROVIDER_CARDS - 1)
    : 0
  const reportedProjects = providers.reduce((n, p) => n + p.reportedProjects, 0)
  const unknownProjects = providers.reduce((n, p) => n + p.unknownProjects, 0)
  const knownSum = providers.reduce((n, p) => n + (p.totalTokens ?? 0), 0)

  const coverageText = snap && snap.coverage.numerator != null
    ? snap.coverage.numerator + '/' + (snap.coverage.denominator ?? '?')
    : 'UNKNOWN'

  // Tab + selected source travel in the URL, like view/theme/layout: a HUD
  // state is deep-linkable and no web storage is written.
  const [tab, setTab] = useState<HudTab>(() => hudTabFromParam(readUrlParam('hud')))
  const [requestedAgent, setRequestedAgent] = useState<string | null>(() => readUrlParam('agent'))
  const selected = useMemo(() => {
    if (displayProviders.length === 0) return null
    return displayProviders.find((p) => p.key === requestedAgent) ?? displayProviders[0]
  }, [displayProviders, requestedAgent])
  const effectiveAgent = selected && requestedAgent === selected.key ? requestedAgent : null
  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search)
      if (tab === 'usage') params.delete('hud')
      else params.set('hud', tab)
      if (effectiveAgent) params.set('agent', effectiveAgent)
      else params.delete('agent')
      const qs = params.toString()
      window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''))
    } catch { /* no URL (SSR/test) */ }
  }, [tab, effectiveAgent])

  const tabRefs = useRef<Partial<Record<HudTab, HTMLButtonElement | null>>>({})
  // Every panel stays mounted so `aria-controls` always names a real element
  // (the nav contract already pins that rule for disclosures). Inactive panels
  // are `hidden`, and the stylesheet pairs `[hidden] { display:none }` because an
  // author `display:flex` would otherwise beat the UA sheet.
  const bodyRef = useRef<HTMLDivElement | null>(null)
  // The usage view is taller than the fixed panel, so its body scrolls. A fade
  // at the fold is the only visible affordance WebView2 gives us (scrollbars
  // are overlay-only); it clears once the reader reaches the end.
  const [bodyEdge, setBodyEdge] = useState<'more' | 'none'>('none')
  useEffect(() => {
    const el = bodyRef.current
    if (!el) return
    const check = () => {
      const overflow = el.scrollHeight > el.clientHeight + 1
      const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 1
      setBodyEdge(overflow && !atBottom ? 'more' : 'none')
    }
    check()
    el.addEventListener('scroll', check, { passive: true })
    window.addEventListener('resize', check)
    return () => {
      el.removeEventListener('scroll', check)
      window.removeEventListener('resize', check)
    }
  }, [tab, snap])

  const onTabKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>, id: HudTab) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const index = HUD_TABS.findIndex((t) => t.id === id)
    const nextIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? HUD_TABS.length - 1
        : (index + (event.key === 'ArrowRight' ? 1 : -1) + HUD_TABS.length) % HUD_TABS.length
    const next = HUD_TABS[nextIndex].id
    setTab(next)
    tabRefs.current[next]?.focus()
  }

  // The reference HUD's glyphs watch the pointer. This is decoration only: one
  // panel-level listener writes two CSS variables and no data path reads them.
  const rootRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    if (typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      if (frame) return
      frame = window.requestAnimationFrame(() => {
        frame = 0
        const r = root.getBoundingClientRect()
        if (!r.width || !r.height) return
        const dx = ((event.clientX - (r.left + r.width / 2)) / (r.width / 2)) * 2.5
        const dy = ((event.clientY - (r.top + r.height / 2)) / (r.height / 2)) * 2
        root.style.setProperty('--hud-eye-x', Math.max(-2.5, Math.min(2.5, dx)).toFixed(2) + 'px')
        root.style.setProperty('--hud-eye-y', Math.max(-2, Math.min(2, dy)).toFixed(2) + 'px')
      })
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      if (frame) window.cancelAnimationFrame(frame)
    }
  }, [])

  // Session observation series: one point per distinct token revision.
  const [samples, setSamples] = useState<TokenSample[]>([])
  useEffect(() => {
    setSamples((prev) => appendTokenSample(prev, snap))
  }, [snap])

  const sourceRef = snap?.sourceRefs?.[0] || null
  const newest = samples[samples.length - 1]
  const delta = sessionTokenDelta(samples)
  const attention = approvals.count > 0

  const tabCount: Record<HudTab, number | null> = {
    usage: null,
    sessions: sessions.total > 0 ? sessions.total : null,
    approvals: approvals.count > 0 ? approvals.count : null,
  }

  const usagePanel = (
    <section
      role="tabpanel" id="hud-panel-usage" aria-labelledby="hud-tab-usage"
      className="hud-view" data-view="usage" hidden={tab !== 'usage'}
    >
      <header className="hud-hero">
        <div className="hud-total-block">
          <span className="hud-label">TOKEN 总量 · 本次快照</span>
          <strong
            className={'hud-total' + (total == null ? ' is-unknown' : '')}
            style={totalFontSize ? { fontSize: totalFontSize } : undefined}
          >
            {totalLabel}
          </strong>
          <span className="hud-total-meta">
            {total == null
              ? (snap ? 'tokenSummary 未报告' : '数据源未接入')
              : totalLabel + ' tokens'}
            {' · 质量 ' + fmtCostQuality(tt?.costQuality)}
          </span>
        </div>
      </header>

      {/* The exact strings `覆盖 …` and `rev …` are one text node each: the
          render-truth contract matches them as words, and splitting a label
          from its value would change what a reader (and the test) sees. */}
      <div className="hud-facts">
        <div className="hud-fact">
          <span className="hud-fact-label">项目</span>
          <b className="hud-fact-value">{snap ? String(snap.projects.length) : 'UNKNOWN'}</b>
        </div>
        <div className="hud-fact hud-fact-line">{`覆盖 ${coverageText}`}</div>
        <div className="hud-fact hud-fact-line">{snap ? `rev ${snap.revision}` : 'rev —'}</div>
      </div>

      <div className="hud-spark-block">
        <div className="hud-spark-head">
          <span>本次会话观测</span>
          <span>{samples.length < 2 ? '序列未形成' : samples.length + ' 个修订'}</span>
        </div>
        {samples.length > 1 ? (
          <>
            <div className="hud-spark"><HudSpark samples={samples} /></div>
            <div className="hud-spark-meta">
              最新 {newest ? fmtExactTokens(newest.total) : 'UNKNOWN'} · 修订 {newest?.revision ?? '—'} · 会话内采样，不是来源历史
            </div>
          </>
        ) : (
          <div className="hud-spark-empty">
            尚无趋势：需要至少两个不同修订的 token 读数（不补点、不估算）。
          </div>
        )}
      </div>

      <div className="hud-agents-head">
        <span className="hud-agents-title">按来源的 token 份额</span>
        <span className="hud-agents-note">
          {foldedCount > 0
            ? `摘要 ${displayProviders.length}/${providers.length} · 派生视图`
            : '项目行 · 派生视图'}
        </span>
      </div>

      {providers.length === 0 ? (
        <div className="hud-empty">
          <span className="hud-empty-ring" aria-hidden="true"><i /></span>
          <div className="hud-empty-copy">
            <strong>{snap ? '没有可归组的项目来源' : '数据源未接入'}</strong>
            <small>
              {snap
                ? '项目集合为空或没有 agentPlatform —— 不预填来源，也不画空环'
                : '保持 UNKNOWN：不预填来源，也不把未知写成 0'}
            </small>
          </div>
        </div>
      ) : (
        <>
          <div className="hud-agents" role="group" aria-label="按 agentPlatform 的项目 token 份额（仅已报告值）">
            {displayProviders.map((p) => {
              // HUD_UNKNOWN_PLATFORM is a real projection state (a project
              // with no agentPlatform), not a placeholder for a missing row.
              const arc = ringArc(p.ringFraction, RING_RADIUS)
              const isAggregate = p.aggregate === true
              const title = isAggregate
                ? p.key
                : p.key === 'UNKNOWN' ? '未声明平台' : p.key
              const fullTitle = providerTitle(p)
              const bar = hudAgentBar(p)
              const barTotal = bar.known ? bar.input + bar.output + bar.unclassified : 0
              const width = (n: number) => barTotal > 0 ? (n / barTotal) * 100 : 0
              const split = bar.known
                ? `，输入 ${fmtExactTokens(bar.input)}，输出 ${fmtExactTokens(bar.output)}`
                : ''
              return (
                <button
                  key={p.key}
                  type="button"
                  className="hud-agent"
                  data-provider={isAggregate ? 'aggregate' : p.key}
                  data-aggregate={isAggregate ? 'true' : undefined}
                  data-partial={p.unknownProjects > 0 ? 'true' : 'false'}
                  data-selected={selected?.key === p.key ? 'true' : 'false'}
                  aria-pressed={selected?.key === p.key}
                  title={fullTitle}
                  style={{ ['--accent' as string]: p.color }}
                  aria-label={`${fullTitle}：${p.shareLabel === '—' ? '份额不可计算' : '份额 ' + p.shareLabel}，${p.totalTokens == null ? 'token 未知' : fmtExactTokens(p.totalTokens) + ' tokens'}，${p.projectCount} 个项目（${p.unknownProjects} 个未报告 token）${split}`}
                  onClick={() => setRequestedAgent(p.key)}
                >
                  <span className="hud-ring" aria-hidden="true">
                    <svg viewBox="0 0 96 96" focusable="false">
                      <circle className="hud-ring-track" cx="48" cy="48" r={RING_RADIUS} />
                      <circle
                        className="hud-ring-arc"
                        cx="48" cy="48" r={RING_RADIUS}
                        strokeDasharray={arc.dasharray}
                        // The stylesheet sets `stroke-linecap: round`, and a CSS
                        // declaration beats this presentation attribute, so the
                        // empty case is also marked for a `butt` rule below.
                        data-empty={p.share == null ? 'true' : undefined}
                        strokeLinecap={p.share == null ? 'butt' : 'round'}
                        transform="rotate(-90 48 48)"
                      />
                    </svg>
                    <span className="hud-bot">
                      <i className="hud-eye hud-eye-l" />
                      <i className="hud-eye hud-eye-r" />
                    </span>
                  </span>
                  <span className="hud-share">{'份额 ' + p.shareLabel}</span>
                  <span className="hud-agent-name" title={fullTitle}>{title}</span>
                  <span className="hud-agent-total">
                    {p.totalTokens == null ? 'UNKNOWN' : fmtHudTokens(p.totalTokens)}
                  </span>
                  <span className="hud-agent-bar" data-known={bar.known ? 'true' : 'false'} aria-hidden="true">
                    {bar.known && barTotal > 0 && (
                      <>
                        <i data-part="input" style={{ width: width(bar.input) + '%' }} />
                        <i data-part="output" style={{ width: width(bar.output) + '%' }} />
                        <i data-part="rest" style={{ width: width(bar.unclassified) + '%' }} />
                      </>
                    )}
                  </span>
                </button>
              )
            })}
          </div>
          <p className="hud-note">
            {unknownProjects > 0
              ? `份额只按已报告的 token 计算；${unknownProjects} 个项目的 token 未报告，未计入分母（不按零相加）。`
              : reportedProjects > 0 && knownSum === 0
                ? '来源报告为零：份额不可定义（不做 0/0），显示仍是真实的 0。'
                : '分量与分母都来自项目行的 totalTokens；tokenSummary 仍是唯一的汇总真值。'}
          </p>
          {foldedCount > 0 && (
            <p className="hud-note hud-note-fold" data-folded={String(foldedCount)}>
              其余 {foldedCount} 个来源合并为一张摘要卡（份额仍只按已报告 token 计算），明细见下方来源明细。
            </p>
          )}
        </>
      )}

      {selected && (
        <section className="hud-detail" aria-label={`来源明细：${selected.key}`}>
          <div className="hud-detail-head">
            <strong className="hud-detail-name">{selected.aggregate ? selected.key : selected.key === 'UNKNOWN' ? '未声明平台' : selected.key} · 明细</strong>
            <span className="hud-detail-sub">
              合计 {selected.totalTokens == null ? 'UNKNOWN' : fmtHudTokens(selected.totalTokens)}
            </span>
          </div>
          <div className="hud-detail-grid">
            <div><span>输入</span><b>{selected.inputTokens == null ? '—' : fmtHudTokens(selected.inputTokens)}</b></div>
            <div><span>输出</span><b>{selected.outputTokens == null ? '—' : fmtHudTokens(selected.outputTokens)}</b></div>
            <div><span>未分类</span><b>{selected.unclassifiedTokens == null ? '—' : fmtHudTokens(selected.unclassifiedTokens)}</b></div>
            <div><span>项目</span><b>{selected.projectCount} 个</b></div>
            <div><span>活跃执行</span><b>{selected.activeExecutions} 个</b></div>
            <div><span>质量</span><b>{selected.costQuality}</b></div>
          </div>
          {selected.topProjects.length > 0 && (
            <ol className="hud-detail-projects" aria-label="来源项目（按已报告 token）">
              {selected.topProjects.map((project) => (
                <li key={project.projectId}>
                  <span title={project.label}>{project.label}</span>
                  <b>{fmtHudTokens(project.totalTokens)}</b>
                </li>
              ))}
            </ol>
          )}
          {selected.unclassifiedTokens == null && (
            <p className="hud-detail-note">
              输入/输出未完整报告：缺项不当 0，未分类保持不可计算。
            </p>
          )}
        </section>
      )}

      <section className="hud-recent" aria-label="近期用量">
        <div className="hud-recent-head">
          <span>近期用量</span>
          <span>会话口径 · 非来源历史</span>
        </div>
        <div className="hud-recent-grid">
          <div className="hud-recent-cell">
            <span>本次快照</span>
            <b>{total == null ? 'UNKNOWN' : fmtHudTokens(total)}</b>
            <small>{fmtCostQuality(tt?.costQuality)}</small>
          </div>
          <div className="hud-recent-cell">
            <span>会话净变化</span>
            <b>{delta == null ? '—' : (delta > 0 ? '+' : '') + fmtHudTokens(delta)}</b>
            <small>{delta == null ? '序列未形成' : '首点→最新修订'}</small>
          </div>
          <div className="hud-recent-cell">
            <span>来源历史</span>
            <b className="is-unknown">无真值</b>
            <small>无按日/按小时桶</small>
          </div>
        </div>
      </section>

      <section className="hud-heat" aria-label="活动热力图（未采集）">
        <div className="hud-heat-head">
          <span>活动热力图</span>
          <span>未采集</span>
        </div>
        <p className="hud-heat-empty">
          快照没有按小时历史，未绘制热图——不把缺失画成低活跃。
        </p>
      </section>
    </section>
  )

  const sessionsPanel = (
    <section
      role="tabpanel" id="hud-panel-sessions" aria-labelledby="hud-tab-sessions"
      className="hud-view" data-view="sessions" hidden={tab !== 'sessions'}
    >
      <div className="hud-view-head">
        <div className="hud-view-title">
          <strong>会话</strong>
          <span>{sessions.total} 条执行</span>
        </div>
        <div className="hud-counts">
          <span data-tone={sessions.waiting > 0 ? 'waiting' : undefined}>等待 {sessions.waiting}</span>
          <span data-tone={sessions.active > 0 ? 'active' : undefined}>运行 {sessions.active}</span>
          <span data-tone={sessions.failed > 0 ? 'failed' : undefined}>失败 {sessions.failed}</span>
        </div>
      </div>
      {sessions.rows.length === 0 ? (
        <div className="hud-empty-line">
          投影未报告执行（executions 为空）。这不等于 agent 没有运行，只等于快照没有记录。
        </div>
      ) : (
        <ul className="hud-session-list">
          {sessions.rows.slice(0, 6).map((row) => (
            <li key={row.executionId} className="hud-session" data-state={row.state} data-group={row.group}>
              <span className="hud-session-dot" aria-hidden="true" />
              <div className="hud-session-main">
                <span className="hud-session-title">
                  {row.projectLabel ?? '未归属项目'}
                  {!row.projectKnown && row.projectLabel ? '（未在项目表）' : ''}
                </span>
                <span className="hud-session-meta">
                  {row.stateLabel} · {row.agent ?? 'agent 未报告'} · {row.workingArea ?? '工作区未报告'}
                </span>
                <span className="hud-session-id" title={`${row.executionId}${row.sessionId ? ' · ' + row.sessionId : ''}`}>
                  {row.executionId}{row.sessionId ? ' · 会话 ' + row.sessionId : ''}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
      {sessions.rows.length > 6 && (
        <p className="hud-note">另有 {sessions.rows.length - 6} 条执行未显示（快照内共 {sessions.rows.length} 条）。</p>
      )}
      <p className="hud-note">快照没有按会话的 token 或时间字段，因此不显示每会话用量与耗时。</p>
    </section>
  )

  const approvalsPanel = (
    <section
      role="tabpanel" id="hud-panel-approvals" aria-labelledby="hud-tab-approvals"
      className="hud-view" data-view="approvals" hidden={tab !== 'approvals'}
    >
      <div className="hud-view-head">
        <div className="hud-view-title">
          <strong>等待</strong>
          <span>{approvals.count} 项</span>
        </div>
        <span className="hud-readonly-pill">只读</span>
      </div>
      {approvals.count === 0 ? (
        <div className="hud-empty-line">
          executions 中没有 WAITING_APPROVAL / WAITING_USER。
        </div>
      ) : (
        <div className="hud-approval-list">
          {[...approvals.waiting, ...approvals.questions].slice(0, 3).map((row) => (
            <article
              key={row.executionId}
              className="hud-approval"
              data-kind={row.state === 'WAITING_APPROVAL' ? 'approval' : 'question'}
            >
              <header>
                <span className="hud-approval-agent">{row.agent ?? 'agent 未报告'}</span>
                <span className="hud-approval-kind">{row.stateLabel}</span>
              </header>
              <strong className="hud-approval-project">{row.projectLabel ?? '未归属项目'}</strong>
              <span className="hud-approval-meta">
                {row.executionId} · {row.workingArea ?? '工作区未报告'}
              </span>
              <footer className="hud-readonly-line">
                Observer 只读投影 · 请到执行端批准或回答
              </footer>
            </article>
          ))}
        </div>
      )}
      {approvals.count > 3 && (
        <p className="hud-note">另有 {approvals.count - 3} 项等待未显示。</p>
      )}
      <section className="hud-plan" aria-label="任务包等待项">
        <div className="hud-plan-head">
          <span>任务包等待项</span>
          <span>{approvals.plan.length} 项</span>
        </div>
        {!approvals.planPresent ? (
          <p className="hud-note">未提供：workspace.plan.approvals 缺失。</p>
        ) : approvals.plan.length === 0 ? (
          <p className="hud-note">已读取，当前没有 PENDING / DEFERRED 事项。</p>
        ) : (
          <ul className="hud-plan-list">
            {approvals.plan.slice(0, 3).map((row, index) => (
              <li key={`${row.label}-${index}`}>
                <span className="hud-plan-label" title={row.label}>{row.label}</span>
                <span className="hud-plan-state" data-state={row.state}>{row.state}</span>
              </li>
            ))}
          </ul>
        )}
        <p className="hud-note">来自 workspace.plan.approvals，是任务包事项，不是 agent 权限请求。</p>
      </section>
      <p className="hud-note hud-approval-boundary">
        Observer 不执行、不批准、不重试：本页只显示快照里的等待证据。
      </p>
    </section>
  )

  return (
    <div
      ref={rootRef}
      className="compact-hud hud-phenotype text-ink"
      data-state={state}
      data-attention={attention ? 'true' : 'false'}
    >
      <div className="hud-notch" aria-hidden="true">
        <span className="hud-notch-dot" />
        <span>WORK-LAB · HUD</span>
        {attention && <span className="hud-notch-badge">{approvals.count}</span>}
      </div>

      <section className="hud-panel" aria-label="WORK-LAB 紧凑 HUD">
        <span className="hud-top-glow" aria-hidden="true" />

        <div className="hud-toolbar">
          <div className="hud-tabs" role="tablist" aria-label="HUD 视图">
            {HUD_TABS.map(({ id, label }) => {
              const count = tabCount[id]
              return (
                <button
                  key={id}
                  ref={(el) => { tabRefs.current[id] = el }}
                  type="button"
                  role="tab"
                  id={`hud-tab-${id}`}
                  className="hud-tab"
                  aria-selected={tab === id}
                  aria-controls={`hud-panel-${id}`}
                  tabIndex={tab === id ? 0 : -1}
                  data-tone={id === 'approvals' && count ? 'waiting' : undefined}
                  onClick={() => setTab(id)}
                  onKeyDown={(event) => onTabKeyDown(event, id)}
                >
                  {label}
                  {count != null && <span className="hud-tab-count">{count}</span>}
                </button>
              )
            })}
          </div>
          {/* No role="status"/aria-live here: App's global announcer owns the
              one polite live region, and a second one both duplicates the
              announcement and lets announce() overwrite React's children. */}
          <div className="hud-status" data-state={state} role="group" aria-label="连接状态">
            <span className="hud-status-dot" aria-hidden="true" />
            <span className="hud-status-text">{transport}</span>
          </div>
        </div>

        <div className="hud-body" ref={bodyRef} data-edge={bodyEdge}>
          {usagePanel}
          {sessionsPanel}
          {approvalsPanel}
        </div>

        <footer className="hud-footer">
          <span className="hud-footer-source" title={sourceRef ?? undefined}>
            {sourceRef || (snap ? '投影未命名来源' : '数据源未接入')}
          </span>
          <span className="hud-footer-time">{snap ? fmtTimestamp(snap.generatedAt) : '—'}</span>
        </footer>
      </section>
    </div>
  )
}
