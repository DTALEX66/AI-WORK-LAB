// 日常壳（2026-10-24 TRAE 交接包）：M01 项目首页 / M02 项目概览 / M03 问题与经验 /
// M04 方法交接抽屉 / M05 我的工具，一级导航 项目/问题与经验/我的工具，设置底置。
// 数据只来自真实快照、/api/v1/repair-packs 与 /api/v1/solutions；缺数据如实 UNKNOWN。
// 本壳经 ?shell=daily 进入，不替换专业投影壳；高级入口从这里链接过去。
import { useState, useEffect, useMemo, useCallback } from 'react'
import type { ReactElement } from 'react'
import type { SnapshotV3 } from '@/types'
import { fmtTimestamp, repairPacksEndpoint, type ThemeMode } from '@/lib/api'
import {
  makeHttpRepairPackReader,
  writeClipboardText, type ManualRepairPack, type RepairPacksView,
} from '@/lib/repairPack'
import {
  fetchSolutions, type SolutionSearchView, type SolutionItem,
} from '@/daily/solutionsClient'
import { Rail, TopBar, SectionTitle, StatusPill, IconTile, Chip, MetaItem, TimeIcon, DisabledAction, Link2, ThemeHonestyNote, THEME_HONESTY_ID_DAILY, T } from '@/daily/DailyChrome'
import { DAILY_NAV, type DailyNav } from '@/daily/DailyChrome'
import { MonitoringView, TrustView } from '@/views/Views'
import { CollectorDeliverySummary } from '@/components/ui/collector-delivery'
import { SettingsPrivacyView } from '@/views/SettingsPrivacyView'
import { AuditTrailView } from '@/views/AuditTrailView'
import { ChevronDown, CheckCircle2, CircleAlert, FileText, Filter, Plug, Plus, Sparkles, TriangleAlert } from 'lucide-react'
import {
  dailyProjectCards, dailyIssueRows, dailyToolRows, buildHandoverMaterial,
  TARGETS_PARAM, readTargetSelection, encodeTargetSelection, selectTargets, toggleTargetToken,
  partitionIssuesByTargets, projectCountSentence, targetMissSentence, issueCountSentence,
  filteredEmptyIssueSentence,
  TOOLS_PARAM, readToolSelection, encodeToolSelection, selectTools, toggleToolToken,
  toolCountSentence, toolMissSentence,
  type DailyProjectCard, type DailyIssueRow, type DailyToolRow,
  type TargetSubset, type IssueScope, type ToolSubset,
} from '@/daily/dailyData'
import { AgentTile } from '@/daily/agentMarks'

export type DailyView = DailyNav | 'overview' | 'settings'

/**
 * What the one new daily entry, 治理与诊断, carries -- the five cards of the D2 sign-off pack
 * (`.project-local/runs/d2/D2-SIGNOFF-PACK.md` §2), in its declared order.
 *
 * These cards do not re-render governance content in the daily shell's own markup: each mounts the
 * professional view component over the same v3 snapshot, so a fact has one renderer. STITCH is the shell
 * and a daily screen is a density state of it, not a second implementation -- a copy would be the second
 * ledger in another form. Net change stays what the pack promised: nav entries +1, new components 0,
 * new URL params 0, new write paths 0.
 *
 * The ids listed here leave the settings page's "高级与专业视图" link list (`advanced` below): one thing,
 * one entry point. That exclusion is derived from this table and asserted, not maintained by hand.
 */
export const DAILY_CARRIED_VIEWS: ReadonlyArray<{ id: string, label: string }> = [
  { id: 'trust', label: '数据可信度' },
  { id: 'monitoring', label: '传输真值与状态矩阵' },
  { id: 'collectors', label: '采集器交付与拒绝' },
  { id: 'privacy', label: '只读与隐私边界' },
  { id: 'audit', label: '审计追踪' },
]

// 日常壳自有的地址参数名单：readParams 认它、writeParams 写它、App.tsx 的 URL 写回白名单
// 必须带上同样的名字（App.tsx:282），三处同步，否则冷启动与主题切换会静默丢参数。
const DAILY_PARAMS = ['shell', 'dv', 'dp', 'dq', 'dm', 'dtool', 'di', TARGETS_PARAM, TOOLS_PARAM] as const
export type IssueSegment = 'all' | 'open' | 'methods'

type DailyParams = {
  dv: DailyView; dp: string | null; dq: string; dm: string | null; dtool: string | null
  di: IssueSegment
  /** E2 的显示筛选：null＝不筛选（地址里没有 ?targets=）。只活在 URL 里。 */
  targets: string[] | null
  /** E2 的另一维：?tools= 筛的是被观察的软件／工具，与 targets 同族、互不覆盖。 */
  tools: string[] | null
}

function readParams(): DailyParams {
  try {
    const s = new URLSearchParams(window.location.search)
    const dvRaw = s.get('dv')
    const known: readonly string[] = [...DAILY_NAV.map((n) => n.id), 'overview', 'settings']
    const dv: DailyView = dvRaw && known.includes(dvRaw) ? dvRaw as DailyView : 'home'
    const raw = s.get('di')
    const di: IssueSegment = raw === 'open' || raw === 'methods' ? raw : 'all'
    return {
      dv, dp: s.get('dp'), dq: s.get('dq') ?? '', dm: s.get('dm'), dtool: s.get('dtool'), di,
      targets: readTargetSelection(s.toString()),
      tools: readToolSelection(s.toString()),
    }
  } catch {
    return { dv: 'home', dp: null, dq: '', dm: null, dtool: null, di: 'all', targets: null, tools: null }
  }
}

function writeParams(state: DailyParams) {
  if (typeof window === 'undefined') return
  const p = new URLSearchParams(window.location.search)
  const setOrDrop = (name: string, value: string | null) => {
    if (value) p.set(name, value)
    else p.delete(name)
  }
  // 入口标记写回 `surface`，不改写 `shell`：桌面入口的 shell=tauri 是无边框壳的自声明，
  // 被任何一次导航覆盖掉，窗口控件就只能靠 IPC 注入探测来判定（浏览器里则应完全没有）。
  setOrDrop('surface', 'daily')
  setOrDrop('dv', state.dv === 'home' ? null : state.dv)
  setOrDrop('dp', state.dp)
  setOrDrop('dq', state.dq || null)
  setOrDrop('dm', state.dm)
  setOrDrop('dtool', state.dtool)
  setOrDrop('di', state.di === 'all' ? null : state.di)
  // ?targets= 与 ?tools= 只在真的筛限时写；「全部」的表达方式是删掉参数，不是写空值。
  setOrDrop(TARGETS_PARAM, encodeTargetSelection(state.targets))
  setOrDrop(TOOLS_PARAM, encodeToolSelection(state.tools))
  const qs = p.toString()
  window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''))
}

const SURFACE = 'bg-[color:var(--daily-surface)] border border-[color:var(--daily-line)]'

function StatusDot({ status }: { status: string }) {
  const color = status === '正在推进' ? 'bg-[color:var(--daily-accent)]'
    : status === '需要关注' ? 'bg-[color:var(--daily-warn-mark)]'
      : status === '等待你决定' ? 'bg-[color:var(--daily-decision-mark)]'
        : status === '已完成' ? 'bg-[color:var(--daily-ok)]'
          : status === '暂停' ? 'bg-[color:var(--daily-dim)]' : 'bg-[color:var(--daily-dim)]'
  return <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${color}`} />
}

export function DailyApp(props: {
  snap: SnapshotV3 | null
  live: boolean
  error: string | null
  theme: string
  onTheme: (t: 'dark' | 'light') => void
}) {
  const { snap, live, error } = props
  const [state, setState] = useState(readParams)
  const [packsView, setPacksView] = useState<RepairPacksView | null>(null)
  const [packsState, setPacksState] = useState<'LOADING' | 'OK' | 'UNREACHABLE' | 'BAD'>('LOADING')
  const [packsWhy, setPacksWhy] = useState<string | null>(null)
  const [solutions, setSolutions] = useState<SolutionSearchView | null>(null)
  const [solutionsState, setSolutionsState] = useState<'LOADING' | 'OK' | 'UNREACHABLE' | 'BAD'>('LOADING')
  const [solutionsWhy, setSolutionsWhy] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Record<string, { verdict: string; note: string }>>({})
  const [copyState, setCopyState] = useState<Record<string, { ok: boolean; why?: string }>>({})

  const navigate = useCallback((patch: Partial<typeof state>) => {
    setState((prev) => {
      const next = { ...prev, ...patch }
      writeParams(next)
      return next
    })
  }, [])

  // 返回键保留上下文：查询与筛选都活在 URL 里，这里只负责前进动作。
  const openProject = (projectId: string) => navigate({ dv: 'overview', dp: projectId })
  const backHome = () => navigate({ dv: 'home', dp: null })
  const openMethod = (solutionId: string) => navigate({ dm: solutionId })
  const closeMethod = () => navigate({ dm: null })

  useEffect(() => {
    const endpoint = repairPacksEndpoint()
    if (!endpoint) { setPacksState('UNREACHABLE'); setPacksWhy('没有可信任的 loopback 端点'); return }
    const reader = makeHttpRepairPackReader(endpoint.url)
    const controller = new AbortController()
    reader(controller.signal).then((outcome) => {
      if (controller.signal.aborted) return
      if (outcome.kind === 'RESULT') { setPacksView(outcome.view); setPacksState('OK') }
      else if (outcome.kind === 'UNREACHABLE') { setPacksState('UNREACHABLE'); setPacksWhy(outcome.detail) }
      else { setPacksState('BAD'); setPacksWhy(outcome.why) }
    }).catch(() => { if (!controller.signal.aborted) setPacksState('UNREACHABLE') })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setSolutionsState('LOADING')
    fetchSolutions(state.dq, controller.signal).then((outcome) => {
      if (controller.signal.aborted) return
      if (outcome.kind === 'RESULT') { setSolutions(outcome.view); setSolutionsState('OK') }
      else if (outcome.kind === 'UNREACHABLE') { setSolutionsState('UNREACHABLE'); setSolutionsWhy(outcome.detail) }
      else { setSolutionsState('BAD'); setSolutionsWhy(outcome.why) }
    }).catch(() => { if (!controller.signal.aborted) setSolutionsState('UNREACHABLE') })
    return () => controller.abort()
  }, [state.dq])

  const cards = useMemo(() => dailyProjectCards(snap, packsView?.packs ?? []), [snap, packsView])
  const issues = useMemo(() => dailyIssueRows(snap, packsView?.packs ?? []), [snap, packsView])
  const tools = useMemo(() => dailyToolRows(snap), [snap])

  // E2：监控对象显示筛选。子集从同一份快照派生，纯显示，不发任何请求、不写任何状态。
  // 地址是唯一真源：?targets= 必须留在 App.tsx 的 URL 写回白名单里（与 dv/dp/dq/… 同一名单），
  // 漏掉它就会在挂载与主题切换时静默丢参数（CL-12 的 surface 就是同一处已实测的先例）；
  // targetFilter 契约测试的「共享深链」一例钉着这条属性。
  const targetSubset = useMemo(() => selectTargets(cards, state.targets), [cards, state.targets])
  const issueScope = useMemo(() => partitionIssuesByTargets(issues, targetSubset), [issues, targetSubset])
  // E2 的另一维：?tools= 筛工具（适配器能力卡）这一类监控对象，与 ?targets 各自独立。
  const toolSubset = useMemo(() => selectTools(tools, state.tools), [tools, state.tools])

  const filteredProjects = useMemo(() => {
    const q = state.dq.trim().toLowerCase()
    if (!q) return targetSubset.shown
    return targetSubset.shown.filter((c) => c.displayName.toLowerCase().includes(q) || c.projectId.toLowerCase().includes(q))
  }, [targetSubset, state.dq])

  const filteredIssues = useMemo(() => {
    const q = state.dq.trim().toLowerCase()
    const rows = issueScope.shown
    if (!q) return rows
    return rows.filter((i) => i.title.toLowerCase().includes(q) || i.classLabel.toLowerCase().includes(q)
      || (i.projectId ?? '').toLowerCase().includes(q))
  }, [issueScope, state.dq])

  const filteredTools = useMemo(() => {
    const q = state.dq.trim().toLowerCase()
    const rows = toolSubset.shown
    if (!q) return rows
    return rows.filter((t) => t.displayName.toLowerCase().includes(q) || t.clientId.toLowerCase().includes(q))
  }, [toolSubset, state.dq])

  const selectedProject = useMemo(
    () => (snap?.projects ?? []).find((p) => p.projectId === state.dp) ?? null,
    [snap, state.dp],
  )
  const selectedCard = cards.find((c) => c.projectId === state.dp) ?? null
  const projectIssues = issues.filter((i) => i.projectId === state.dp)
  const selectedMethod: SolutionItem | null = useMemo(
    () => solutions?.results.find((r) => r.solutionId === state.dm) ?? null,
    [solutions, state.dm],
  )
  const selectedTool = tools.find((t) => t.clientId === state.dtool) ?? tools[0] ?? null

  const searchDisabledNote = error && !snap ? '数据源不可用，显示 OFFLINE，不加载演示数据' : null

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        const box = document.getElementById('daily-global-search') as HTMLInputElement | null
        box?.focus()
        box?.select()
      }
      if (e.key === 'Escape') closeMethod()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const transport = error && !snap
    ? { label: '数据源不可用', tone: 'offline' as const }
    : live
      ? { label: '数据源就绪', tone: 'live' as const }
      : snap
        ? { label: '快照未验证', tone: 'unknown' as const }
        : { label: '等待快照', tone: 'unknown' as const }
  const shell = (
    <div className="flex h-screen flex-col bg-[color:var(--daily-bg)] text-[color:var(--daily-text)]" data-shell="daily">
      <TopBar query={state.dq} onQuery={(v) => navigate({ dq: v })} hudHint={null} />
      <div className="flex min-h-0 flex-1">
        <Rail
          view={state.dv === 'overview' ? 'home' : state.dv}
          onNavigate={(v) => navigate({ dv: v, dp: v === 'home' ? null : state.dp })}
          transportLabel={transport.label} transportTone={transport.tone}
        />

        <div className="flex min-h-0 flex-1 flex-col">
          {searchDisabledNote && (
            <div role="alert" className="border-b border-[color:var(--daily-line)] bg-[color:var(--daily-shell)] px-5 py-2 text-xs text-[color:var(--daily-warn-text)]">
              {searchDisabledNote}
            </div>
          )}
          <main className="min-h-0 flex-1 overflow-y-auto px-6 py-5" id="daily-content">
            {state.dv === 'home' && (
              <HomeView cards={filteredProjects} totalCount={cards.length} onOpen={openProject}
                query={state.dq} onQuery={(v) => navigate({ dq: v })}
                subset={targetSubset}
                onToggleTarget={(id) => navigate({ targets: toggleTargetToken(state.targets, id) })}
                onShowAllTargets={() => navigate({ targets: null })} />
            )}
            {state.dv === 'overview' && (
              <OverviewView
                card={selectedCard}
                issues={projectIssues}
                solutions={solutions}
                onBack={backHome}
                onOpenMethod={openMethod}
              />
            )}
            {state.dv === 'issues' && (
              <IssuesView
                rows={filteredIssues}
                totalCount={issues.length}
                scope={issueScope}
                targetFilterActive={targetSubset.active}
                issuesSummary={snap?.issuesSummary}
                solutions={solutions}
                segment={state.di}
                query={state.dq}
                onQuery={(dq) => navigate({ dq })}
                onSegment={(di) => navigate({ di })}
                onOpenMethod={openMethod}
                onOpenProject={(id) => openProject(id)}
                feedback={feedback}
                onFeedback={(fp, verdict) => setFeedback((prev) => ({
                  ...prev, [fp]: { verdict, note: prev[fp]?.note ?? '' },
                }))}
                onFeedbackNote={(fp, note) => setFeedback((prev) => ({
                  ...prev, [fp]: { verdict: prev[fp]?.verdict ?? '', note },
                }))}
              />
            )}
            {state.dv === 'tools' && (
              <ToolsView tools={filteredTools} selected={selectedTool} onSelect={(id) => navigate({ dtool: id })}
                targetFilterActive={targetSubset.active}
                subset={toolSubset}
                onToggleTool={(id) => navigate({ tools: toggleToolToken(state.tools, id) })}
                onShowAllTools={() => navigate({ tools: null })} />
            )}
            {state.dv === 'governance' && (
              <GovernanceView snap={snap} theme={props.theme} />
            )}
            {state.dv === 'settings' && (
              <SettingsView theme={props.theme} onTheme={props.onTheme} snap={snap} />
            )}
            {state.dv !== 'settings' && state.dv !== 'home' && (
              <p className="mt-6 text-xs text-[color:var(--daily-dim)]">
                {snap ? `快照修订 ${snap.revision} · 采样 ${fmtTimestamp(snap.sourceWatermark)}` : '快照未到达 · 数值保持 UNKNOWN'}
              </p>
            )}
          </main>
        </div>
      </div>

      {state.dm && (
        <MethodDrawer
          method={selectedMethod}
          solutionsState={solutionsState}
          solutionsWhy={solutionsWhy}
          projectName={selectedCard?.displayName ?? state.dp}
          issues={issues}
          packs={packsView?.packs ?? []}
          tools={tools}
          onClose={closeMethod}
        />
      )}
    </div>
  )
  void copyState
  void DAILY_PARAMS
  // The caption cluster and the drag surface live in TopBar (DailyChrome), because the
  // desktop main window is borderless (decorations:false) and the default entry is this shell.
  return shell
}

/**
 * E2 · 监控对象显示筛选。它只做一件事：把「这一屏显示哪几个监控对象」写进 ?targets=，
 * 从不请求侧车、从不写任何状态（Observer 严格只读）。默认不筛选＝参数缺席；
 * 「全部」的表达方式是删参数，不是写空值——空值和缺席一旦都表示全部，
 * 「一个都没选中」就没有诚实的写法了。
 */
function TargetFilter(props: {
  subset: TargetSubset<DailyProjectCard>
  onToggleTarget: (projectId: string) => void
  onShowAll: () => void
}) {
  const s = props.subset
  return (
    <div role="group" aria-labelledby="daily-target-filter-label" data-testid="target-filter"
      className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-shell)] p-2">
      <span id="daily-target-filter-label" className="min-w-0 text-xs text-[color:var(--daily-dim)]">
        监控对象显示筛选
      </span>
      <button type="button" onClick={props.onShowAll} aria-pressed={!s.active}
        data-testid="target-filter-all"
        title="清除 ?targets=，显示全部监控对象（默认状态）"
        className={`whitespace-nowrap rounded border px-2 py-1 text-xs ${!s.active
          ? 'border-[color:var(--daily-accent)] bg-[color:var(--daily-surface)] text-[color:var(--daily-accent)]' : 'border-[color:var(--daily-line)] text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]'}`}>
        全部
      </button>
      {s.all.map((card) => {
        const selected = s.active && s.matchedProjectIds.includes(card.projectId)
        const reason = !s.active
          ? `只显示 ${card.displayName}：写入 ?targets=${card.projectId}（纯显示筛选，不改数据）`
          : selected
            ? `从筛选中移除 ${card.displayName}；移除最后一项即回到全部`
            : `加入筛选：${card.displayName}`
        return (
          <button key={card.projectId} type="button"
            onClick={() => props.onToggleTarget(card.projectId)} aria-pressed={selected}
            data-testid={`target-filter-option-${card.projectId}`} title={reason}
            className={`max-w-full truncate whitespace-nowrap rounded border px-2 py-1 text-xs ${selected
              ? 'border-[color:var(--daily-accent)] bg-[color:var(--daily-surface)] text-[color:var(--daily-accent)]' : 'border-[color:var(--daily-line)] text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]'}`}>
            {card.displayName}
          </button>
        )
      })}
      {s.unmatchedTokens.length > 0 && (
        <span data-testid="target-filter-unmatched" className="min-w-0 basis-full text-xs text-[color:var(--daily-warn-text)]">
          地址里的 {s.unmatchedTokens.join('、')} 在本机投影中没有对应监控对象：
          未命中的选择原样保留、不静默回退成全部，也不静默丢弃。
        </span>
      )}
      <span data-testid="target-filter-scope" className="ml-auto min-w-0 text-xs text-[color:var(--daily-dim)]">
        {projectCountSentence(s)}
      </span>
    </div>
  )
}

/**
 * E2 · 工具（软件）这一维的显示筛选，与 TargetFilter 同族同语义：只写 ?tools=，
 * 从不请求侧车、从不写任何状态；「全部」＝删参数。它是同一个对象列表上的同一套控件，
 * 不是第二套筛选系统：这里筛的是工具，TargetFilter 筛的是项目。
 */
function ToolFilter(props: {
  subset: ToolSubset<DailyToolRow>
  onToggleTool: (clientId: string) => void
  onShowAll: () => void
}) {
  const s = props.subset
  return (
    <div role="group" aria-labelledby="daily-tool-filter-label" data-testid="tool-filter"
      className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-shell)] p-2">
      <span id="daily-tool-filter-label" className="min-w-0 text-xs text-[color:var(--daily-dim)]">
        工具显示筛选
      </span>
      <button type="button" onClick={props.onShowAll} aria-pressed={!s.active}
        data-testid="tool-filter-all"
        title="清除 ?tools=，显示全部工具（默认状态）"
        className={`whitespace-nowrap rounded border px-2 py-1 text-xs ${!s.active
          ? 'border-[color:var(--daily-accent)] bg-[color:var(--daily-surface)] text-[color:var(--daily-accent)]' : 'border-[color:var(--daily-line)] text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]'}`}>
        全部
      </button>
      {s.all.map((tool) => {
        const selected = s.active && s.matchedClientIds.includes(tool.clientId)
        const reason = !s.active
          ? `只显示 ${tool.displayName}：写入 ?tools=${tool.clientId}（纯显示筛选，不改数据）`
          : selected
            ? `从筛选中移除 ${tool.displayName}；移除最后一项即回到全部`
            : `加入筛选：${tool.displayName}`
        return (
          <button key={tool.clientId} type="button"
            onClick={() => props.onToggleTool(tool.clientId)} aria-pressed={selected}
            data-testid={`tool-filter-option-${tool.clientId}`} title={reason}
            className={`whitespace-nowrap rounded border px-2 py-1 text-xs ${selected
              ? 'border-[color:var(--daily-accent)] bg-[color:var(--daily-surface)] text-[color:var(--daily-accent)]' : 'border-[color:var(--daily-line)] text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]'}`}>
            {tool.displayName}
          </button>
        )
      })}
      {s.unmatchedTokens.length > 0 && (
        <span data-testid="tool-filter-unmatched" className="min-w-0 basis-full text-xs text-[color:var(--daily-warn-text)]">
          地址里的 {s.unmatchedTokens.join('、')} 在本机投影里没有对应的工具：
          未命中的选择原样保留、不静默回退成全部，也不静默丢弃。
        </span>
      )}
      <span data-testid="tool-filter-scope" className="ml-auto min-w-0 text-xs text-[color:var(--daily-dim)]">
        {toolCountSentence(s)}
      </span>
    </div>
  )
}

function HomeView(props: {
  cards: DailyProjectCard[]; totalCount: number; onOpen: (id: string) => void
  query: string; onQuery: (v: string) => void
  subset: TargetSubset<DailyProjectCard>
  onToggleTarget: (projectId: string) => void; onShowAllTargets: () => void
}) {
  const s = props.subset
  const missedEverything = s.active && s.shown.length === 0 && s.unmatchedTokens.length > 0
  const filtered = s.active && s.shown.length > 0
  return (
    <section aria-label="项目首页" data-view="m01">
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">项目</h1>
        <Chip>{projectCountSentence(s)}</Chip>
        <div className="ml-auto flex items-center gap-2">
          <span className="relative inline-flex items-center">
            <Filter size={13} aria-hidden="true" className="pointer-events-none absolute left-2.5 text-[color:var(--daily-dim)]" />
            <input
              type="search" value={props.query} onChange={(e) => props.onQuery(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); props.onQuery('') } }}
              aria-label="按名称过滤项目" placeholder="按名称过滤…"
              className="h-8 w-[212px] rounded-md border pl-8 pr-12 text-sm outline-none"
              style={{ borderColor: T.line, background: T.bg, color: T.text }}
            />
            <kbd className="pointer-events-none absolute right-2 rounded border px-1 text-xs"
              style={{ borderColor: T.line, color: T.dim }}>ESC</kbd>
          </span>
          <DisabledAction label="添加项目" reason="观察者只读：登记项目由项目侧完成"
            icon={<Plus size={13} aria-hidden="true" />} />
        </div>
      </div>
      <TargetFilter subset={s}
        onToggleTarget={props.onToggleTarget} onShowAll={props.onShowAllTargets} />
      {missedEverything ? (
        <div className={`${SURFACE} mt-4 rounded-lg p-6 text-sm text-[color:var(--daily-dim)]`} data-testid="home-empty-miss">
          {targetMissSentence(s.unmatchedTokens, s.total)}
        </div>
      ) : props.cards.length === 0 ? (
        <div className={`${SURFACE} rounded-lg p-6 text-sm text-[color:var(--daily-dim)]`}
          data-testid={s.active ? 'home-empty-filtered' : 'home-empty'}>
          {s.total === 0
            ? '快照中没有已注册项目（实测为 0，不是缺字段）。'
            : s.active && filtered
              ? `筛选子集里有 ${s.shown.length} 个监控对象，但检索词把它们都排除了；清除搜索或点「全部」可恢复。`
              : '没有匹配当前搜索的项目。清除搜索词可恢复完整列表。'}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {props.cards.map((card) => (
            <article key={card.projectId} data-landmark="project-card"
              className="flex flex-col rounded-xl border bg-[color:var(--daily-shell)] p-5"
              style={{ borderColor: T.line }}>
              <div className="flex items-start gap-3">
                <IconTile label={card.displayName} />
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-[15px] font-semibold">{card.displayName}</h2>
                  <p className="mt-0.5 truncate font-mono text-xs text-[color:var(--daily-dim)]">{card.projectId}</p>
                </div>
                <StatusPill status={card.status} />
              </div>
              <div className="mt-4 rounded-lg bg-[color:var(--daily-surface)] p-3">
                <div className="text-xs text-[color:var(--daily-dim)]">最近变化</div>
                <p className="mt-1 text-sm">
                  {card.latestChange ? fmtTimestamp(card.latestChange) : '待确认'}
                </p>
                {card.attentionNote && (
                  <p className="mt-2 text-xs text-[color:var(--daily-warn-text)]">{card.attentionNote}</p>
                )}
              </div>
              <p className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-[color:var(--daily-dim)]">
                <Link2 size={13} aria-hidden="true" />关联工具：
                {card.relatedTools.length
                  ? card.relatedTools.map((t) => <Chip key={t}>{t}</Chip>)
                  : <span>未记录</span>}
                {card.openIssueCount !== null && card.openIssueCount > 0 && (
                  <Chip tone="warn">{card.openIssueCount} 个当前问题</Chip>
                )}
              </p>
              <div className="mt-4 flex items-center justify-between border-t border-[color:var(--daily-line)] pt-3">
                <MetaItem icon={<TimeIcon />}>
                  更新：{card.updatedAt ? fmtTimestamp(card.updatedAt) : 'UNKNOWN'}
                </MetaItem>
                <button type="button" onClick={() => props.onOpen(card.projectId)}
                  className="text-sm text-[color:var(--daily-accent)] hover:underline">
                  进入项目概览 →
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      <p className="mt-5 text-xs text-[color:var(--daily-dim)]" data-testid="home-caption">
        本页只投影真实快照；缺的字段保持 UNKNOWN，不用演示数据填满。
        {s.active
          ? `当前是 ?targets 筛选子集（显示 ${s.shown.length}／快照 ${props.totalCount} 个监控对象）：`
            + '未显示的对象与它的问题依然存在，本页的数字不代表全机。'
          : ''}
      </p>
    </section>
  )
}

function OverviewView(props: {
  card: DailyProjectCard | null
  issues: DailyIssueRow[]
  solutions: SolutionSearchView | null
  onBack: () => void
  onOpenMethod: (id: string) => void
}) {
  const [techOpen, setTechOpen] = useState(false)
  if (!props.card) {
    return (
      <section aria-label="项目概览" data-view="m02">
        <button type="button" onClick={props.onBack}
          className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-surface)] px-3 py-1.5 text-sm text-[color:var(--daily-accent)]">
          ← 所有项目
        </button>
        <div className={`${SURFACE} mt-4 rounded-lg p-6 text-sm text-[color:var(--daily-dim)]`}>
          链接指向的项目在本机投影中不存在（不猜测最近的项目）。
        </div>
      </section>
    )
  }
  return (
    <section aria-label="项目概览" data-view="m02">
      <button type="button" onClick={props.onBack}
        className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-surface)] px-3 py-1.5 text-sm text-[color:var(--daily-accent)]">
        ← 所有项目
      </button>
      <header className="mt-3 rounded-xl border border-[color:var(--daily-line)] bg-[color:var(--daily-shell)] p-5">
        <div className="flex flex-wrap items-start gap-3">
          <IconTile label={props.card.displayName} size={40} />
          <div className="min-w-0 flex-1">
            <h1 className="flex flex-wrap items-center gap-2 text-xl font-semibold">
              {props.card.displayName}
              <Chip>版本 UNKNOWN</Chip>
              <StatusPill status={props.card.status} />
            </h1>
            <p className="mt-2 text-sm text-[color:var(--daily-dim)]">
              {props.card.attentionNote
                ?? `本轮状态由真实快照投影；关联工具：${props.card.relatedTools.length ? props.card.relatedTools.join('、') : '未记录'}。`}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-4">
              <MetaItem icon={<TimeIcon />}>
                确认时间：{props.card.updatedAt ? fmtTimestamp(props.card.updatedAt) : 'UNKNOWN'}
              </MetaItem>
              <MetaItem icon={<Link2 size={13} aria-hidden="true" />}>
                关联工具：{props.card.relatedTools.length ? props.card.relatedTools.join('、') : '未记录'}
              </MetaItem>
            </div>
          </div>
          <DisabledAction label="打开对应工具" reason="观察者只读：不启动外部软件" primary />
        </div>
      </header>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className={`${SURFACE} rounded-lg p-5 ${props.issues.length ? 'border-t-2 border-t-[color:var(--daily-warn-line)]' : ''}`}>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <TriangleAlert size={15} aria-hidden="true" className={props.issues.length ? 'text-[color:var(--daily-warn-text)]' : 'text-[color:var(--daily-dim)]'} />
            需要关注的事项
          </h2>
          {props.issues.length === 0 ? (
            <p className="mt-2 text-xs text-[color:var(--daily-dim)]">本项目当前没有打开的问题（实测，非推断）。</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {props.issues.map((issue) => (
                <li key={issue.fingerprint} className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                  <div className="text-sm font-medium">《{issue.title}》</div>
                  <p className="mt-1 text-xs text-[color:var(--daily-dim)]">{issue.classLabel} · {issue.priority} · 最近 {fmtTimestamp(issue.lastSeenAt)}</p>
                  <div className="mt-2 flex items-start justify-between gap-2 rounded bg-[color:var(--daily-surface)] p-2">
                    <span className="flex items-start gap-2 text-xs">
                      <Plug size={13} aria-hidden="true" className="mt-0.5 text-[color:var(--daily-accent)]" />
                      <span>
                        <span className="text-[color:var(--daily-accent)]">外部工具反馈</span>
                        <span className="block text-[color:var(--daily-dim)]">
                          {issue.hasPack ? '已有修复包草稿（未发送），可在问题与经验页交接。' : '尚无修复包；可在问题与经验页查看可参考方法。'}
                        </span>
                      </span>
                    </span>
                    <Chip tone="warn">未核验</Chip>
                  </div>
                  <button type="button" onClick={() => issue.hasPack && props.onOpenMethod(issue.packId ?? '')}
                    className="mt-2 rounded bg-[color:var(--daily-accent)] px-3 py-1.5 text-xs font-medium text-[color:var(--daily-on-accent)] disabled:cursor-not-allowed disabled:bg-[color:var(--daily-surface)] disabled:text-[color:var(--daily-dim)]"
                    disabled={!issue.hasPack}
                    title={issue.hasPack ? '打开该问题的交接材料' : '本问题还没有修复包草稿'}>
                    查看参考方法 →
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className={`${SURFACE} rounded-lg p-5`}>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles size={15} aria-hidden="true" className="text-[color:var(--daily-accent)]" />可参考的历史经验
          </h2>
          {!props.solutions ? (
            <p className="mt-2 text-xs text-[color:var(--daily-dim)]">方案库状态：读取中（不预填结果）。</p>
          ) : props.solutions.status === 'SOURCE_ABSENT' ? (
            <p className="mt-2 text-xs text-[color:var(--daily-dim)]">方案库暂无法获取：{props.solutions.reason}</p>
          ) : props.solutions.results.length === 0 ? (
            <p className="mt-2 text-xs text-[color:var(--daily-dim)]">{props.solutions.reason}</p>
          ) : (
            <>
              <p className="mt-1 text-xs text-[color:var(--daily-dim)]">发现 {props.solutions.results.length} 条相似经验可供参考</p>
              <ul className="mt-3 space-y-3">
                {props.solutions.results.slice(0, 3).map((m) => (
                  <li key={m.solutionId} className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                    <div className="text-sm font-medium">《{m.title ?? m.solutionId}》</div>
                    <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
                      项目 {String(m.software.softwareId ?? '未记录')} · {m.versionHint?.message ?? '适用性待确认'}
                    </p>
                    <button type="button" onClick={() => props.onOpenMethod(m.solutionId)}
                      className="mt-2 w-full rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-surface)] px-3 py-1.5 text-left text-xs text-[color:var(--daily-accent)]">
                      查看该方法详情 →
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
      <div className={`${SURFACE} mt-4 rounded-lg`}>
        <button type="button" onClick={() => setTechOpen((o) => !o)} aria-expanded={techOpen}
          className="flex w-full items-center justify-between px-5 py-3 text-left text-sm">
          <span className="flex items-center gap-2">
            <FileText size={15} aria-hidden="true" className="text-[color:var(--daily-dim)]" />
            查看详细依据与诊断记录
            <span className="text-xs text-[color:var(--daily-dim)]">（{techOpen ? '已展开' : '已收起'}，点击{techOpen ? '收起' : '展开'}）</span>
          </span>
          <ChevronDown size={15} aria-hidden="true"
            className={techOpen ? 'rotate-180 transition-transform' : 'transition-transform'} />
        </button>
        {techOpen && (
          <dl className="grid grid-cols-2 gap-2 px-5 pb-4 text-xs text-[color:var(--daily-dim)]">
            <dt>活动状态</dt><dd>{props.card.status}</dd>
            <dt>最近强证据</dt><dd>{fmtTimestamp(props.card.latestChange)}</dd>
          </dl>
        )}
      </div>
    </section>
  )
}

function IssuesView(props: {
  rows: DailyIssueRow[]
  totalCount: number
  /** E2：筛选子集与全机计数的分层来源 */
  scope: IssueScope<DailyIssueRow>
  targetFilterActive: boolean
  issuesSummary: SnapshotV3['issuesSummary']
  solutions: SolutionSearchView | null
  segment: IssueSegment
  query: string
  onQuery: (q: string) => void
  onSegment: (s: IssueSegment) => void
  onOpenMethod: (id: string) => void
  onOpenProject: (id: string) => void
  feedback: Record<string, { verdict: string; note: string }>
  onFeedback: (fingerprint: string, verdict: string) => void
  onFeedbackNote: (fingerprint: string, note: string) => void
}) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const summary = props.issuesSummary
  const visible = props.segment === 'methods' ? [] : props.rows
  const methods = props.segment === 'open' ? [] : (props.solutions?.results ?? [])
  const matchedMethod = (issue: DailyIssueRow) =>
    (props.solutions?.results ?? []).find((m) => m.issueRefs.includes(issue.fingerprint)) ?? null

  return (
    <section aria-label="问题与经验" data-view="m03">
      <p className="flex items-center gap-1.5 text-xs uppercase tracking-wider text-[color:var(--daily-accent)]">
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[color:var(--daily-accent)]" />
        Diagnostics &amp; Knowledge Hub
      </p>
      <h1 className="mt-1 text-xl font-semibold">问题与经验</h1>
      <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
        查看正在影响软件项目的问题，以及可供参考的过往解法。相似表现不等于相同根因。
      </p>
      {summary && (
        <p className="mt-2 text-xs text-[color:var(--daily-dim)]" data-testid="issues-summary-scope">
          来源 {summary.sourcesRead} 个 · 扫描 {summary.rowsScanned} 行 · 产出 {summary.emittedCount} 条
          {summary.truncated ? ' · 已截断' : summary.complete === false ? ' · 覆盖不完整' : ''}
          {props.targetFilterActive ? '（全机来源统计，不随 ?targets 显示筛选变化）' : ''}
        </p>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-shell)] p-2">
        <div role="group" aria-label="问题筛选分段" className="flex items-center gap-1">
          {([['all', '全部'], ['open', '需要处理'], ['methods', '方法与经验']] as [IssueSegment, string][]).map(([id, label]) => (
            <button key={id} type="button" onClick={() => props.onSegment(id)} aria-pressed={props.segment === id}
              className={`rounded px-3 py-1 text-xs ${props.segment === id
                ? 'bg-[color:var(--daily-accent)] font-medium text-[color:var(--daily-on-accent)]' : 'text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]'}`}>
              {label}
            </button>
          ))}
        </div>
        <span className="relative ml-auto inline-flex items-center">
          <Filter size={13} aria-hidden="true" className="pointer-events-none absolute left-2.5 text-[color:var(--daily-dim)]" />
          <input type="search" value={props.query} onChange={(e) => props.onQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Escape') { e.preventDefault(); props.onQuery('') } }}
            aria-label="检索标题、错误或经验" placeholder="检索标题、错误或经验…"
            className="h-7 w-[212px] rounded border pl-8 pr-3 text-xs outline-none"
            style={{ borderColor: T.line, background: T.bg, color: T.text }} />
        </span>
        <span className="text-xs text-[color:var(--daily-dim)]" data-testid="issues-count-scope">
          {props.segment === 'methods'
            ? `共 ${methods.length} 条方法（方案库列表不随监控对象筛限） · `
              + (props.targetFilterActive ? `全机 ${props.scope.total}` : `快照产出 ${props.totalCount}`) + ' 条问题'
            : issueCountSentence(props.scope, props.targetFilterActive, visible.length)}
        </span>
      </div>

      <ul className="mt-4 space-y-3">
        {visible.length === 0 && props.segment !== 'methods' && (
          <li className={`${SURFACE} rounded-lg p-6 text-sm text-[color:var(--daily-dim)]`} data-testid="issues-empty">
            {props.targetFilterActive && props.scope.shown.length === 0
              ? filteredEmptyIssueSentence(props.scope)
              : props.targetFilterActive
                ? `筛选子集里有 ${props.scope.shown.length} 条问题，但检索词把它们都排除了；清除检索或改为「全部」可恢复。`
                : props.totalCount === 0
                  ? '当前没有打开的问题（实测，非推断）。'
                  : '没有匹配当前搜索的问题。'}
          </li>
        )}
        {visible.map((issue) => {
          const open = expanded === issue.fingerprint
          const method = matchedMethod(issue)
          return (
            <li key={issue.fingerprint} data-landmark="issue-row"
              className={`${SURFACE} rounded-lg border-l-4 ${issue.priority === 'P1' ? 'border-l-[color:var(--daily-warn-line)]' : 'border-l-[color:var(--daily-line)]'} p-4`}>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Chip tone="warn">当前需要处理</Chip>
                {issue.projectId && (
                  <button type="button" onClick={() => props.onOpenProject(issue.projectId as string)}
                    className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] px-1.5 py-0.5 text-xs text-[color:var(--daily-accent)] hover:underline">
                    {issue.projectId}
                  </button>
                )}
                <MetaItem icon={<TimeIcon />}>{issue.lastSeenAt ? fmtTimestamp(issue.lastSeenAt) : 'UNKNOWN'}</MetaItem>
                <button type="button" onClick={() => setExpanded(open ? null : issue.fingerprint)}
                  aria-expanded={open} className="ml-auto text-xs text-[color:var(--daily-accent)]">
                  {open ? '收起' : '展开'}
                </button>
              </div>
              <button type="button" onClick={() => setExpanded(open ? null : issue.fingerprint)}
                aria-expanded={open} className="mt-2 block w-full text-left text-sm font-medium">
                《{issue.title}》
              </button>
              {issue.detail && <p className="mt-1 text-xs text-[color:var(--daily-dim)]">{issue.detail}</p>}
              <p className="mt-1 text-xs text-[color:var(--daily-dim)]">{issue.classLabel} · {issue.priority}</p>

              {open && (
                <div className="mt-3 border-t border-[color:var(--daily-line)] pt-3">
                  <div className="text-xs text-[color:var(--daily-dim)]">
                    证据位置：{issue.fingerprint.slice(0, 24)}…（同类表现未必同因）
                  </div>
                  <div className="mt-3 rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                    <SectionTitle right={method ? '命中已收录方案' : '未命中已验证方案'}>
                      智能经验推断 · 类似场景推荐方案
                    </SectionTitle>
                    <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
                      <div className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-surface)] p-2">
                        <div className="text-xs text-[color:var(--daily-dim)]">1 当时的情况</div>
                        <p className="mt-1 text-xs">
                          “{method?.preconditions[0] ?? issue.detail ?? '未记录'}”
                        </p>
                      </div>
                      <div className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-surface)] p-2">
                        <div className="text-xs text-[color:var(--daily-dim)]">2 采用的方法</div>
                        <p className="mt-1 text-xs">“{method?.steps[0] ?? '待确认'}”</p>
                      </div>
                      <div className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-surface)] p-2">
                        <div className="text-xs text-[color:var(--daily-dim)]">3 实际结果</div>
                        <p className="mt-1 text-xs">
                          “{method ? '已核验关闭（来源记录未提供结果原文）' : '待确认'}”
                        </p>
                      </div>
                    </div>
                    {method && (
                      <button type="button" onClick={() => props.onOpenMethod(method.solutionId)}
                        className="mt-3 rounded bg-[color:var(--daily-accent)] px-3 py-1.5 text-xs font-medium text-[color:var(--daily-on-accent)]">
                        查看方法 →
                      </button>
                    )}
                  </div>

                  <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
                    <span>处理反馈：</span>
                    {['已恢复', '仍有问题', '不确定'].map((v) => (
                      <button key={v} type="button"
                        onClick={() => props.onFeedback(issue.fingerprint, v)}
                        className={`rounded border px-2 py-1 ${props.feedback[issue.fingerprint]?.verdict === v
                          ? 'border-[color:var(--daily-accent)] text-[color:var(--daily-accent)]' : 'border-[color:var(--daily-line)] text-[color:var(--daily-dim)]'}`}>
                        {v}
                      </button>
                    ))}
                    {props.feedback[issue.fingerprint]?.verdict && (
                      <span className="text-[color:var(--daily-accent)]">你反馈：{props.feedback[issue.fingerprint].verdict}</span>
                    )}
                  </div>
                  {props.feedback[issue.fingerprint]?.verdict && (
                    <>
                      <input type="text" value={props.feedback[issue.fingerprint].note} placeholder="可附短说明（可选）"
                        onChange={(e) => props.onFeedbackNote(issue.fingerprint, e.target.value)}
                        className="mt-2 w-full rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] px-2 py-1 text-xs" />
                      <p className="mt-1 text-xs text-[color:var(--daily-warn-text)]">
                        当前侧车没有写入接口（Observer 只读），反馈仅保存在本页内存中，刷新后丢失。
                      </p>
                    </>
                  )}
                </div>
              )}
            </li>
          )
        })}

        {methods.map((m) => (
          <li key={m.solutionId} data-landmark="method-row"
            className={`${SURFACE} flex flex-wrap items-center gap-3 rounded-lg p-4`}>
            <IconTile label={String(m.software.softwareId ?? '方法')} size={32} />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium">《{m.title ?? m.solutionId}》</span>
                <Chip tone={m.recommended ? 'accent' : 'neutral'}>
                  {m.recommended ? '已收录推荐' : '候选方法'}
                </Chip>
                <span className="text-xs text-[color:var(--daily-dim)]">{String(m.software.softwareId ?? '未记录')}</span>
              </div>
              <p className="mt-1 text-xs text-[color:var(--daily-dim)]">{m.versionHint?.message ?? '适用性待确认'}</p>
            </div>
            <button type="button" onClick={() => props.onOpenMethod(m.solutionId)}
              className="text-xs text-[color:var(--daily-accent)] hover:underline">查看方法 &gt;</button>
          </li>
        ))}
        {props.segment === 'methods' && methods.length === 0 && (
          <li className={`${SURFACE} rounded-lg p-6 text-sm text-[color:var(--daily-dim)]`}>
            {props.solutions === null ? '方案库读取中（不预填结果）。' : `方案库：${props.solutions.reason}`}
          </li>
        )}
      </ul>
    </section>
  )
}

// The operator declares each client's role in config/capability-matrix.json; the producer projects it onto
// the capability card. Agents come first, everything else under its own kind, and an undeclared role is
// shown as one instead of being guessed from the name.
const ROLE_RANK = ['agent_runtime', 'provider_router', 'vcs_host', 'design_client', 'UNKNOWN']
const ROLE_LABEL: Record<string, string> = {
  agent_runtime: 'agent 运行时',
  provider_router: '供应商路由 · 仅观测，不执行任务',
  vcs_host: '版本控制与托管 · 仅观测，不是 agent',
  design_client: '设计客户端 · 仅观测，不是 agent',
  UNKNOWN: '角色未声明（来源缺声明，不是「没有角色」）',
}
const roleRank = (role: string) => {
  const index = ROLE_RANK.indexOf(role)
  return index === -1 ? ROLE_RANK.length : index
}

function ToolsView(props: {
  tools: DailyToolRow[]; selected: DailyToolRow | null; onSelect: (id: string) => void
  /** E2 的范围声明：?targets= 筛的是监控对象（项目）的显示列表，不是软件客户端。 */
  targetFilterActive: boolean
  /** E2 的另一维：?tools= 筛工具本身这一类监控对象（纯显示，只进地址）。 */
  subset: ToolSubset<DailyToolRow>
  onToggleTool: (clientId: string) => void
  onShowAllTools: () => void
}) {
  const quickAccess = [
    { id: 'usage', title: '使用方法', desc: '查看向该工具提供受控上下文与排查指引的建议做法' },
    { id: 'rules', title: '提示词与规则', desc: '查看推荐的交付格式模板与目录约束规则' },
    { id: 'faq', title: '常见问题', desc: '查看连接中断或排查超时时的常见处理问答' },
  ]
  const s = props.subset
  // 空列表有三种成因，必须分开说：投影里没有能力卡（来源缺失）、?tools 没命中任何工具、
  // 检索词排除了子集。把第一种措辞复用给后两种，就等于把「筛掉了」谎报成「没有」。
  const missAll = s.active && s.shown.length === 0 && s.unmatchedTokens.length > 0
  // Ordered by declared role so a router or a repository host cannot read as a coding agent, and each
  // group gets its own caption at its first row.
  const ordered = [...props.tools].sort(
    (a, b) => roleRank(a.role) - roleRank(b.role) || a.displayName.localeCompare(b.displayName))
  return (
    <section aria-label="我的工具" data-view="m05">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold">我的工具</h1>
          <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
            管理外部 AI 与本地开发工具的连接身份与使用辅助。分组按操作者声明的角色（agent 运行时／供应商路由／版本控制托管／设计客户端），
            未声明角色的条目单列为 UNKNOWN，不按名字猜它是哪类软件。
          </p>
          {props.targetFilterActive && (
            // 范围的诚实说明：不写这句，「我的工具」在筛选态会被读成「只剩这几个工具」。
            // 两个维度各有自己的参数，这句把界限说清：?targets 管监控对象（项目），?tools 管工具。
            <p className="mt-1 text-xs text-[color:var(--daily-dim)]" data-testid="tools-target-scope">
              ?targets 只限监控对象（项目）的显示子集，不改本页的工具列表，
              也不改下方「关联项目」的全量口径；工具这一维另有 ?tools= 显示筛选。
            </p>
          )}
        </div>
        <DisabledAction label="检测环境工具" reason="观察者只读：不发起探测运行" />
        <DisabledAction label="登记新工具" reason="观察者只读：登记由项目侧完成" />
      </div>
      <ToolFilter subset={props.subset} onToggleTool={props.onToggleTool} onShowAll={props.onShowAllTools} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        <div className={`${SURFACE} rounded-lg p-3`}>
          <div className="mb-2 flex items-center justify-between gap-2 px-1 text-xs uppercase tracking-wider text-[color:var(--daily-dim)]">
            <span>已登记工具</span>
            {/* 原来这里是一行写死的「FILTER: ALL」占位：它既不是控件也不是事实，筛限时更会读成「没在筛」。
                换成与 ?tools 一致的实测计数（normal-case 保留参数名的原样拼写）。 */}
            <span className="normal-case tracking-normal" data-testid="tools-list-scope">
              {toolCountSentence(props.subset)}
            </span>
          </div>
          <ul className="space-y-2" aria-label="工具列表">
            {props.tools.length === 0 && (
              <li className="p-4 text-xs text-[color:var(--daily-dim)]"
                data-testid={missAll ? 'tools-empty-miss' : 'tools-empty'}>
                {s.total === 0
                  ? '快照未携带适配器能力卡（来源缺失，不是 0 个工具）。'
                  : missAll
                    ? toolMissSentence(s.unmatchedTokens, s.total)
                    : s.active
                      ? `筛选子集里有 ${s.shown.length} 个工具，但检索词把它们都排除了；清除检索或点「全部」可恢复。`
                      : '没有匹配当前搜索的工具。清除搜索词可恢复完整列表（快照仍带着这些能力卡）。'}
              </li>
            )}
            {ordered.map((tool, index) => {
              const active = props.selected?.clientId === tool.clientId
              const firstOfGroup = index === 0 || ordered[index - 1].role !== tool.role
              return (
                <li key={tool.clientId}>
                  {firstOfGroup && (
                    <p className="pb-2 pt-3 text-xs tracking-wide text-[color:var(--daily-dim)]" data-group-label="true" data-role={tool.role}>
                      {ROLE_LABEL[tool.role] ?? `角色 ${tool.role}`}
                    </p>
                  )}
                  <button type="button" onClick={() => props.onSelect(tool.clientId)}
                    aria-current={active ? 'true' : undefined}
                    className={`relative w-full rounded-lg border p-3 text-left ${active
                      ? 'border-[color:var(--daily-accent)] bg-[color:var(--daily-surface)]' : 'border-[color:var(--daily-line)] bg-[color:var(--daily-shell)]'}`}>
                    {active && (
                      <span aria-hidden="true" className="absolute left-0 top-3 bottom-3 w-[2px] rounded-full bg-[color:var(--daily-accent)]" />
                    )}
                    <div className="flex items-start gap-2">
                      <AgentTile softwareId={tool.clientId} size={28} tone="surface" />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <span className="truncate text-sm font-medium">{tool.displayName}</span>
                          <Chip tone={tool.connection.includes('失败') || tool.connection.includes('未连接') ? 'warn' : 'accent'}>
                            {tool.connection.includes('失败') || tool.connection.includes('未连接') ? '未连接' : '已连接'}
                          </Chip>
                        </div>
                        <p className="mt-0.5 truncate text-xs text-[color:var(--daily-dim)]">
                          {tool.version ?? '版本 UNKNOWN'} · {tool.registryStatus.toUpperCase()}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <MetaItem icon={<TimeIcon />}>
                        {tool.observedAt ? fmtTimestamp(tool.observedAt) : 'UNKNOWN'}
                      </MetaItem>
                      <span className="text-xs uppercase tracking-wide"
                        style={{ color: active ? T.accent : T.dim }}>
                        {active ? 'SELECTED' : 'IDLE'}
                      </span>
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        </div>
        <div className="space-y-4">
          <div className={`${SURFACE} rounded-lg p-5`}>
            {!props.selected ? (
              <p className="text-sm text-[color:var(--daily-dim)]">左侧选择一个工具查看详情。</p>
            ) : (
              <div className="flex flex-wrap items-start gap-3">
                <AgentTile softwareId={props.selected.clientId} size={40} />
                <div className="min-w-0 flex-1">
                  <h2 className="flex flex-wrap items-center gap-2 text-lg font-semibold">
                    {props.selected.displayName}
                    <Chip tone="accent">{props.selected.connection}</Chip>
                  </h2>
                  <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
                    声明版本：{props.selected.version ?? 'UNKNOWN'} · 写入策略：{props.selected.writePolicy || 'UNKNOWN'}
                  </p>
                </div>
                <DisabledAction label={`打开 ${props.selected.displayName} 外部客户端`}
                  reason="观察者只读：不启动外部软件" primary />
                <div className="mt-4 grid w-full grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                    <dt className="text-xs text-[color:var(--daily-dim)]">当前可用能力</dt>
                    <dd className="mt-1 text-sm">{props.selected.capabilitySentence}</dd>
                  </div>
                  <div className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                    <dt className="text-xs text-[color:var(--daily-dim)]">关联项目</dt>
                    <dd className="mt-1 text-sm">
                      {props.selected.relatedProjects.length ? props.selected.relatedProjects.join('、') : '未记录'}
                    </dd>
                  </div>
                  <div className="rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                    <dt className="text-xs text-[color:var(--daily-dim)]">最近更新</dt>
                    <dd className="mt-1 text-sm">
                      {props.selected.observedAt ? fmtTimestamp(props.selected.observedAt) : 'UNKNOWN'}
                    </dd>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className={`${SURFACE} rounded-lg p-5`}>
            <SectionTitle right="QUICK ACCESS">使用辅助</SectionTitle>
            <ul className="mt-3 divide-y divide-[color:var(--daily-line)]">
              {quickAccess.map((row) => (
                <li key={row.id}>
                  <div className="flex items-center gap-3 py-3">
                    <FileText size={15} aria-hidden="true" className="shrink-0 text-[color:var(--daily-accent)]" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm">{row.title}</div>
                      <p className="text-xs text-[color:var(--daily-dim)]">{row.desc}</p>
                    </div>
                    <ChevronDown size={15} aria-hidden="true" className="-rotate-90 text-[color:var(--daily-dim)]" />
                  </div>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-[color:var(--daily-dim)]">
              本页不修改对方全局配置；三条辅助内容是只读指引，不代为执行。
            </p>
          </div>
          <div className={`${SURFACE} rounded-lg p-5`}>
            <div className="flex flex-wrap items-center gap-3">
              <div className="min-w-0 flex-1">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  连接配置与设置 <Chip>高级入口</Chip>
                </h3>
                <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
                  如需查看本地通信端口、工作区路径映射与授权状态，请进入专业投影的设置面板；本页不代为修改。
                </p>
              </div>
              <a href="/index.html?view=settings"
                className="inline-flex items-center gap-1.5 rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] px-3 py-1.5 text-sm text-[color:var(--daily-accent)]">
                进入工具设置面板 →
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}


/** How each declared card is mounted. Cards whose component needs more than the snapshot (the collector
 *  section reads one key; the privacy view takes the shell's appearance values) are wired here rather than
 *  being re-implemented in the daily shell. A declared id with no entry renders an explicit refusal on
 *  screen, and `daily.contract.test.tsx` convicts it. */
const CARRIED_RENDERERS: Record<string, (p: { snap: SnapshotV3 | null; theme: string }) => ReactElement> = {
  trust: ({ snap }) => <TrustView snap={snap} />,
  monitoring: ({ snap }) => <MonitoringView snap={snap} />,
  collectors: ({ snap }) => <CollectorDeliverySummary collectors={snap?.collectors} />,
  // No onTheme/onLayout/onPalette: the pack's card 4 rule is that the appearance section degrades to
  // badges here, so the daily shell never grows controls that look live and do nothing.
  privacy: ({ snap, theme }) => <SettingsPrivacyView snap={snap} theme={theme as ThemeMode} />,
  audit: ({ snap }) => <AuditTrailView snap={snap} />,
}

function GovernanceView(props: { snap: SnapshotV3 | null; theme: string }) {
  return (
    <section aria-label="治理与诊断" data-landmark="daily-governance" className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">治理与诊断</h1>
        <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
          这一屏挂载的是专业壳同一套治理与诊断视图，读同一份 v3 快照；判据不在这里重述，也不在这里另画一份。
        </p>
      </div>
      {DAILY_CARRIED_VIEWS.map((card) => {
        const render = CARRIED_RENDERERS[card.id]
        return (
          <div key={card.id} data-carried={card.id}
            className="rounded-lg border border-[color:var(--daily-line)] p-4">
            <h2 className="text-sm font-semibold">{card.label}</h2>
            {render ? render({ snap: props.snap, theme: props.theme }) : (
              <p className="mt-1 text-xs text-[color:var(--daily-warn-text)]">
                这一项还没有可复用的视图组件，因此未渲染任何内容。
              </p>
            )}
          </div>
        )
      })}
    </section>
  )
}

function SettingsView(props: { theme: string; onTheme: (t: 'dark' | 'light') => void; snap: SnapshotV3 | null }) {
  // One thing, one entry point: whatever the daily rail now renders in place leaves this list. The
  // exclusion is derived from DAILY_CARRIED_VIEWS, so the two populations cannot drift into overlap.
  const carried = new Set(DAILY_CARRIED_VIEWS.map((v) => v.id))
  const advanced = [
    { id: 'work', label: '工作' }, { id: 'projects', label: '项目（完整投影）' },
    { id: 'software', label: '软件' }, { id: 'capabilities', label: '能力资产' },
    { id: 'usage', label: '用量缓存' }, { id: 'environment', label: '软件环境' },
    { id: 'rules-policy', label: '规则策略' }, { id: 'audit', label: '审计追踪' },
    { id: 'approvals', label: '审批中心' }, { id: 'integrations', label: '集成/MCP' },
    { id: 'evidence', label: '证据区间' }, { id: 'settings', label: '专业设置' },
  ].filter((a) => !carried.has(a.id))
  return (
    <section aria-label="设置">
      <h1 className="text-xl font-semibold">设置</h1>
      <div className={`${SURFACE} mt-4 rounded-lg p-5`}>
        <h2 className="text-sm font-semibold">外观</h2>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
          <span>主题</span>
          <button type="button" onClick={() => props.onTheme(props.theme === 'dark' ? 'light' : 'dark')}
            data-testid="daily-theme-toggle" data-theme-param={props.theme}
            aria-describedby={THEME_HONESTY_ID_DAILY}
            title={props.theme === 'dark' ? '切换到浅色主题（本视图的配色随之换成 html.light 的那一套令牌值）'
              : '切换到深色主题（本视图的配色随之换成 :root 的那一套令牌值）'}
            className="rounded border border-[color:var(--daily-line)] px-3 py-1 text-[color:var(--daily-accent)]">
            {props.theme === 'dark' ? '页面主题：深色' : '页面主题：浅色'}
          </button>
        </div>
        {/* E1：2026-10-25 这句还是「这一屏暂时不跟着变」，因为当时日常壳与 HUD 窄窗的配色是写死的字面量，
            主题类换了画面不换；2026-10-27 接线到 --daily-* 令牌后，那句会变成反向说谎（否认一件真的
            发生了的事），所以标签与声明都改成如实描述机制，并保留同一条禁令：不许把产品说成只有深色，
            也不把范围夸大到别的表面。令牌与深浅两值的契约见 src/daily/dailyThemeTokens.contract.test.ts。 */}
        <ThemeHonestyNote id={THEME_HONESTY_ID_DAILY} surface="daily" />
      </div>
      <div className={`${SURFACE} mt-4 rounded-lg p-5`}>
        <h2 className="text-sm font-semibold">高级与专业视图</h2>
        <p className="mt-1 text-xs text-[color:var(--daily-dim)]">专业接口、标准接口与诊断投影；从这里进入完整观察者界面。</p>
        <ul className="mt-3 flex flex-wrap gap-2">
          {advanced.map((a) => (
            <li key={a.id}>
              <a href={`/index.html?view=${a.id}`} className="rounded border border-[color:var(--daily-line)] px-3 py-1 text-xs text-[color:var(--daily-accent)] hover:underline">
                {a.label}
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className={`${SURFACE} mt-4 rounded-lg p-5 text-xs text-[color:var(--daily-dim)]`}>
        <h2 className="text-sm font-semibold text-[color:var(--daily-text)]">数据与隐私</h2>
        <p className="mt-2">观察者严格只读：本应用不执行、不批准、不重试、不回滚，不写遥测账本。</p>
        <p className="mt-1">快照修订：{props.snap ? props.snap.revision : 'UNKNOWN'}；无快照时所有数值保持 UNKNOWN，不补 0。</p>
      </div>
    </section>
  )
}

function StepRow(props: { index: number; step: string; detail: string | null; open: boolean; onToggle: () => void }) {
  const num = String(props.index + 1).padStart(2, '0')
  const number = (
    <span className="shrink-0 rounded bg-[color:var(--daily-shell)] px-1.5 py-0.5 text-xs font-semibold text-[color:var(--daily-accent)]">
      {num}
    </span>
  )
  const title = <span className="min-w-0 flex-1 text-xs">{props.step}</span>
  if (!props.detail) {
    return (
      <li className="rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)]">
        <div className="flex items-center gap-3 px-3 py-2">{number}{title}</div>
      </li>
    )
  }
  return (
    <li className="rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)]">
      <button type="button" onClick={props.onToggle} aria-expanded={props.open}
        className="flex w-full items-center gap-3 px-3 py-2 text-left">
        {number}{title}
        <Chip tone="warn">含风险提示</Chip>
        <ChevronDown size={14} aria-hidden="true"
          className={`shrink-0 text-[color:var(--daily-dim)] transition-transform ${props.open ? 'rotate-180' : ''}`} />
      </button>
      {props.open && (
        <p className="border-t border-[color:var(--daily-line)] px-3 py-2 text-xs text-[color:var(--daily-dim)]">
          风险：{props.detail}
        </p>
      )}
    </li>
  )
}

function MethodDrawer(props: {
  method: SolutionItem | null
  solutionsState: 'LOADING' | 'OK' | 'UNREACHABLE' | 'BAD'
  solutionsWhy: string | null
  projectName: string | null
  issues: DailyIssueRow[]
  packs: ManualRepairPack[]
  tools: DailyToolRow[]
  onClose: () => void
}) {
  const [target, setTarget] = useState('')
  const [stepsOpen, setStepsOpen] = useState(false)
  const [previewOpen, setPreviewOpen] = useState(true)
  const [copyResult, setCopyResult] = useState<{ ok: boolean; why?: string } | null>(null)
  // The reference opens the first step that carries detail; a step with nothing to expand
  // renders no toggle at all, so the row never promises an interaction it cannot deliver.
  // The default is derived on every render, not captured once in useState: on a cold open the
  // method arrives after the first render, and a captured default would leave risk text hidden.
  const [chosenStep, setChosenStep] = useState<number | undefined>(undefined)
  // 修复包接缝：方法经 issueRefs 指纹对上修复包时，材料用后端渲染的 handoffText；
  // 没对上才回退到方案库方法材料。两种来源都明确标注，不混用。
  const linkedIssue = props.method
    ? props.issues.find((i) => props.method!.issueRefs.includes(i.fingerprint)) ?? null
    : null
  const linkedPack = props.method
    ? props.packs.find((p) => props.method!.issueRefs.some((fp) => p.binds.issueFingerprints.includes(fp))) ?? null
    : null
  const material = useMemo(() => buildHandoverMaterial({
    projectName: props.projectName,
    issueTitle: linkedIssue?.title ?? null,
    method: props.method,
    pack: linkedPack,
    targetTool: target,
  }), [props.projectName, props.method, linkedIssue, linkedPack, target])

  const risks = props.method?.risks ?? []
  const firstDetailed = risks.findIndex((r) => !!r)
  const stepIsOpen = (i: number) => (chosenStep === undefined
    ? i === firstDetailed : chosenStep === i)
  const doCopy = async () => {
    const outcome = await writeClipboardText(material.text)
    setCopyResult(outcome.ok ? { ok: true } : { ok: false, why: outcome.why })
  }
  const doExport = () => {
    const blob = new Blob([material.text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = material.fileName
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-[color:var(--daily-scrim)]" role="dialog" aria-modal="true" aria-label="方法详情与交接">
      <div className="flex h-full w-[440px] flex-col border-l border-[color:var(--daily-line)] bg-[color:var(--daily-shell)]">
        <div className="flex items-start justify-between gap-3 border-b border-[color:var(--daily-line)] px-5 py-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Chip tone="accent">经验详情</Chip>
              <Chip>来自 {props.method ? String(props.method.software.softwareId ?? '未记录') : '方案库'}</Chip>
            </div>
            <h2 className="mt-2 truncate text-base font-semibold">
              {props.method ? `《${props.method.title ?? props.method.solutionId}》` : '未找到该方法'}
            </h2>
            <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
              {props.method
                ? `${props.method.recommended ? '已收录推荐' : '候选方法（未验证）'} · 修订 r${props.method.revision ?? '?'} · 状态 ${props.method.status ?? 'UNKNOWN'}`
                : '链接可能指向未收录的方法'}
            </p>
          </div>
          <button type="button" onClick={props.onClose} aria-label="关闭抽屉" className="text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]">✕</button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm">
          {!props.method ? (
            props.solutionsState === 'OK'
              ? <p className="text-[color:var(--daily-dim)]">链接指向的方法在方案库中不存在（不猜测最近的方法）。</p>
              : <p className="text-[color:var(--daily-dim)]">方案库{props.solutionsState === 'LOADING' ? '读取中' : '暂无法获取'}：{props.solutionsWhy ?? '等待读取'}。</p>
          ) : (
            <>
              <SectionTitle>方法背景与历史成效</SectionTitle>
              <div className="mt-2 space-y-2">
                <div className="rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                  <div className="flex items-center gap-1.5 text-xs text-[color:var(--daily-dim)]">
                    <CircleAlert size={13} aria-hidden="true" className="shrink-0 text-[color:var(--daily-warn-text)]" />背景什么问题
                  </div>
                  <p className="mt-1 text-xs">
                    {props.method.preconditions.length
                      ? props.method.preconditions.join('；')
                      : '来源记录未提供前提条件'}
                  </p>
                </div>
                <div className="rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                  <div className="flex items-center gap-1.5 text-xs text-[color:var(--daily-dim)]">
                    <CheckCircle2 size={13} aria-hidden="true" className="shrink-0 text-[color:var(--daily-ok)]" />过去取得了什么结果
                  </div>
                  <p className="mt-1 text-xs">
                    {props.method.recommended
                      ? '该方案已被收录为推荐修订（结果原文未在来源记录中提供，不代写）'
                      : '未核验：候选方法，结果待确认'}
                  </p>
                </div>
              </div>

              <div className="mt-4">
                <SectionTitle right={props.method.versionHint?.message ?? '适用性待确认'} rightTone="chip">
                  {props.projectName ? `对当前 ${props.projectName} 的适用性` : '对当前项目的适用性'}
                </SectionTitle>
                <p className="mt-2 text-xs text-[color:var(--daily-dim)]">{props.method.limits.join('；') || '来源未记录限制条件'}</p>
                {props.method.invalidWhen.length > 0 && (
                  <div className="mt-2 rounded-lg border border-[color:var(--daily-warn-tint-line)] bg-[color:var(--daily-warn-tint)] p-3">
                    <div className="text-xs font-semibold text-[color:var(--daily-warn-text)]">失效条件</div>
                    <ul className="mt-1 list-disc pl-4 text-xs text-[color:var(--daily-dim)]">
                      {props.method.invalidWhen.map((s, i) => <li key={i}>{s}</li>)}
                    </ul>
                  </div>
                )}
              </div>

              <div className="mt-4">
                <SectionTitle right={`供工具执行 · 共 ${props.method.steps.length} 步`}>
                  给外部工具参考的处理步骤
                </SectionTitle>
                <p className="mt-1 text-xs text-[color:var(--daily-dim)]">
                  以下为准备交由外部工具（如 {target || '手动复制'}）执行的专业排查指令；
                  带风险提示的步骤可展开查看该提示原文。
                </p>
                <ol className="mt-2 space-y-2">
                  {props.method.steps.map((s, i) => (
                    <StepRow key={i} index={i} step={s} detail={risks[i] ?? null}
                      open={stepIsOpen(i)}
                      onToggle={() => setChosenStep(stepIsOpen(i) ? -1 : i)} />
                  ))}
                  {props.method.steps.length === 0 && (
                    <li className="rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] px-3 py-2 text-xs text-[color:var(--daily-dim)]">
                      来源记录未提供步骤（不代写步骤）。
                    </li>
                  )}
                </ol>
              </div>

              {linkedPack && (
                <div className="mt-4 rounded-lg border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-3">
                  <SectionTitle right="后端渲染 · 未发送">修复包交接文本</SectionTitle>
                  <p className="mt-1 text-xs text-[color:var(--daily-dim)]">来源：修复包 {linkedPack.packId}</p>
                </div>
              )}
            </>
          )}
        </div>
        <div className="border-t border-[color:var(--daily-line)] px-5 py-4">
          <label className="text-xs text-[color:var(--daily-dim)]" htmlFor="daily-target-tool">
            目标交接工具 <span className="ml-1">复制后在对应工具中粘贴</span>
          </label>
          <select id="daily-target-tool" value={target} onChange={(e) => setTarget(e.target.value)}
            className="mt-1 w-full rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] px-2 py-1.5 text-sm">
            <option value="">手动复制（未指定工具）</option>
            {props.tools.map((t) => <option key={t.clientId} value={t.displayName}>{t.displayName}</option>)}
          </select>
          <button type="button" onClick={() => setPreviewOpen((o) => !o)} aria-expanded={previewOpen}
            className="mt-2 flex w-full items-start justify-between gap-2 text-left text-xs text-[color:var(--daily-dim)]">
            <span className="min-w-0">
              交接材料预览（{linkedPack ? `来源：修复包 ${linkedPack.packId} · 后端渲染 · 未发送` : '来源：方案库方法'}）
            </span>
            <span aria-hidden="true" className="shrink-0 whitespace-nowrap">{previewOpen ? '收起' : '展开'}</span>
          </button>
          {previewOpen && (
            <textarea readOnly value={material.text} aria-label="交接材料预览"
              className="mt-1 h-28 w-full resize-y rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-2 font-mono text-xs" />
          )}
          <div className="mt-3 flex items-center gap-2">
            <button type="button" onClick={doExport}
              className="rounded border border-[color:var(--daily-line)] px-3 py-1.5 text-sm text-[color:var(--daily-dim)] hover:text-[color:var(--daily-text)]">
              导出为文本
            </button>
            <button type="button" onClick={doCopy}
              className="flex-1 rounded bg-[color:var(--daily-accent)] px-3 py-1.5 text-sm font-medium text-[color:var(--daily-on-accent)]">
              复制给外部工具
            </button>
          </div>
          {copyResult && (
            copyResult.ok
              ? <p role="status" className="mt-2 text-xs text-[color:var(--daily-ok)]">已写入剪贴板（与预览一致）。</p>
              : <div role="alert" className="mt-2 text-xs text-[color:var(--daily-warn-text)]">
                  剪贴板不可用：{copyResult.why}。上方预览文本可手动选择复制。
                </div>
          )}
        </div>
      </div>
    </div>
  )
}
