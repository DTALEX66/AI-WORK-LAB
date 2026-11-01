// 2026-10-18 · compact-HUD read model (Agent HUD phenotype, WORK-LAB data).
//
// Pure derivations only. Every number here comes from the v3 projection:
//   * provider = projects[].agentPlatform (the projection's own grouping word);
//   * value    = the sum of projects[].token.totalTokens that were REPORTED;
//   * a null token is not a zero and never enters a denominator.
// The UI labels the ring as a derived view, not a second truth (tokenSummary
// stays the one aggregate truth).
import type { ExecutionState, SnapshotV3 } from '@/types'
import { fmtTokens, tokenTruth } from '@/lib/api'

export const HUD_UNKNOWN_PLATFORM = 'UNKNOWN'

/** Worst reported quality wins: a sum that contains an estimate is an estimate. */
export type HudCostQuality = 'EXACT' | 'ESTIMATED' | 'UNKNOWN'
const QUALITY_RANK: Record<HudCostQuality, number> = { EXACT: 0, ESTIMATED: 1, UNKNOWN: 2 }

function worstQuality(values: HudCostQuality[]): HudCostQuality {
  if (values.length === 0) return 'UNKNOWN'
  // Seeding with UNKNOWN would make every group UNKNOWN, since UNKNOWN ranks
  // worst and no other value can beat it.
  let worst = values[0]
  for (const value of values) {
    if (QUALITY_RANK[value] > QUALITY_RANK[worst]) worst = value
  }
  return worst
}

export interface HudProjectSource {
  projectId: string
  label: string
  totalTokens: number
}

export interface HudProvider {
  /** raw projection word (agentPlatform), or UNKNOWN */
  key: string
  projectCount: number
  /** projects whose token.totalTokens was a number (a reported zero counts) */
  reportedProjects: number
  /** projects whose token.totalTokens was null */
  unknownProjects: number
  /** sum of reported totals; null when no project in the group reported one */
  totalTokens: number | null
  /** sum of reported input values; null when none was reported */
  inputTokens: number | null
  /** sum of reported output values; null when none was reported */
  outputTokens: number | null
  /**
   * total - input - output, but ONLY when every token-reporting project carried
   * both parts. A missing part is unknown, not zero, so a partial group leaves
   * this null rather than calling the whole total "unclassified".
   */
  unclassifiedTokens: number | null
  /** sum of projects[].activeExecutionCount (a reported count, not inferred) */
  activeExecutions: number
  /** worst cost quality among the projects that reported a total */
  costQuality: HudCostQuality
  /** up to three token-reporting projects, largest first */
  topProjects: HudProjectSource[]
  /** share of the known-token total; null when the denominator is not usable */
  share: number | null
  /** display label, e.g. "42%", "≥42%" (partial group), "—" */
  shareLabel: string
  /** CSS custom property carrying this provider's accent */
  color: string
  /** 0..1 ring arc; 0 when share is null */
  ringFraction: number
  /** True for the summary card that stands in for the folded tail. */
  aggregate?: boolean
}

interface Group {
  projectCount: number
  reportedProjects: number
  unknownProjects: number
  sum: number
  inputSum: number
  inputReported: number
  outputSum: number
  outputReported: number
  /** every token-reporting project also reported BOTH input and output */
  completePairs: boolean
  pairedInput: number
  pairedOutput: number
  activeExecutions: number
  qualities: HudCostQuality[]
  rows: HudProjectSource[]
}

/** Group the registry by agentPlatform. Sorting is by REPORTED token sum, so it
 *  orders the display only; a group with no reported token is never ranked as 0. */
export function buildHudProviders(snap: SnapshotV3 | null): HudProvider[] {
  if (!snap) return []
  const groups = new Map<string, Group>()
  for (const project of snap.projects) {
    const raw = typeof project.agentPlatform === 'string' ? project.agentPlatform.trim() : ''
    const key = raw || HUD_UNKNOWN_PLATFORM
    const g = groups.get(key) ?? {
      projectCount: 0,
      reportedProjects: 0,
      unknownProjects: 0,
      sum: 0,
      inputSum: 0,
      inputReported: 0,
      outputSum: 0,
      outputReported: 0,
      completePairs: true,
      pairedInput: 0,
      pairedOutput: 0,
      activeExecutions: 0,
      qualities: [],
      rows: [],
    }
    g.projectCount += 1

    const total = project.token?.totalTokens
    const input = project.token?.inputTokens
    const output = project.token?.outputTokens
    const hasTotal = typeof total === 'number' && Number.isFinite(total)
    if (hasTotal) {
      g.reportedProjects += 1
      g.sum += total
      g.qualities.push(project.token?.costQuality ?? 'UNKNOWN')
      g.rows.push({
        projectId: project.projectId,
        label: project.displayName || project.projectId,
        totalTokens: total,
      })
      const hasInput = typeof input === 'number' && Number.isFinite(input)
      const hasOutput = typeof output === 'number' && Number.isFinite(output)
      if (hasInput && hasOutput) {
        g.pairedInput += input
        g.pairedOutput += output
      } else {
        // One missing part makes the group's split unknowable; do not treat
        // the absent part as a zero and call the remainder "unclassified".
        g.completePairs = false
      }
    } else {
      g.unknownProjects += 1
    }
    if (typeof input === 'number' && Number.isFinite(input)) {
      g.inputSum += input
      g.inputReported += 1
    }
    if (typeof output === 'number' && Number.isFinite(output)) {
      g.outputSum += output
      g.outputReported += 1
    }
    const active = project.activeExecutionCount
    if (typeof active === 'number' && Number.isFinite(active) && active > 0) {
      g.activeExecutions += active
    }
    groups.set(key, g)
  }

  const knownTotal = [...groups.values()].reduce((sum, g) => sum + g.sum, 0)
  return [...groups.entries()]
    .sort((a, b) => b[1].sum - a[1].sum || a[0].localeCompare(b[0]))
    .map(([key, g], index) => {
      const share = g.reportedProjects > 0 && knownTotal > 0 ? g.sum / knownTotal : null
      const pct = share == null ? null : Math.round(share * 100)
      return {
        key,
        projectCount: g.projectCount,
        reportedProjects: g.reportedProjects,
        unknownProjects: g.unknownProjects,
        totalTokens: g.reportedProjects > 0 ? g.sum : null,
        inputTokens: g.inputReported > 0 ? g.inputSum : null,
        outputTokens: g.outputReported > 0 ? g.outputSum : null,
        unclassifiedTokens: g.reportedProjects > 0 && g.completePairs
          ? Math.max(0, g.sum - g.pairedInput - g.pairedOutput)
          : null,
        activeExecutions: g.activeExecutions,
        costQuality: worstQuality(g.qualities),
        topProjects: [...g.rows].sort((a, b) => b.totalTokens - a.totalTokens).slice(0, 3),
        share,
        // "≥" is not decoration: the group has projects missing from the
        // denominator, so its true share can only be larger than this number.
        shareLabel: pct == null ? '—' : (g.unknownProjects > 0 ? '≥' : '') + pct + '%',
        color: `var(--hud-accent-${(index % 5) + 1})`,
        ringFraction: share ?? 0,
      }
    })
}

/**
 * Bound the card row to one line. A fixed 440×680 panel cannot grow a second
 * row of rings without pushing the footer below the window, so the tail is
 * folded into ONE summary card. The card is a derived view of the same reported
 * project tokens (never a new number), and it states how many sources it hides
 * so the fold is visible rather than silent.
 */
export const HUD_MAX_PROVIDER_CARDS = 3

export function foldHudProviders(
  providers: HudProvider[],
  maxCards = HUD_MAX_PROVIDER_CARDS,
): HudProvider[] {
  if (providers.length <= maxCards) return providers
  const head = providers.slice(0, maxCards - 1)
  const rest = providers.slice(maxCards - 1)
  const knownTotal = providers.reduce((sum, p) => sum + (p.totalTokens ?? 0), 0)
  const reportedProjects = rest.reduce((sum, p) => sum + p.reportedProjects, 0)
  const unknownProjects = rest.reduce((sum, p) => sum + p.unknownProjects, 0)
  const projectCount = rest.reduce((sum, p) => sum + p.projectCount, 0)
  const sum = rest.reduce((total, p) => total + (p.totalTokens ?? 0), 0)
  const inputs = rest.filter((p) => p.inputTokens != null)
  const outputs = rest.filter((p) => p.outputTokens != null)
  const complete = rest.every((p) => p.unclassifiedTokens != null)
  const share = reportedProjects > 0 && knownTotal > 0 ? sum / knownTotal : null
  const pct = share == null ? null : Math.round(share * 100)
  return [
    ...head,
    {
      key: `其他 ${rest.length} 个来源`,
      projectCount,
      reportedProjects,
      unknownProjects,
      totalTokens: reportedProjects > 0 ? sum : null,
      inputTokens: inputs.length > 0 ? inputs.reduce((n, p) => n + (p.inputTokens ?? 0), 0) : null,
      outputTokens: outputs.length > 0 ? outputs.reduce((n, p) => n + (p.outputTokens ?? 0), 0) : null,
      unclassifiedTokens: complete && reportedProjects > 0
        ? rest.reduce((n, p) => n + (p.unclassifiedTokens ?? 0), 0)
        : null,
      activeExecutions: rest.reduce((n, p) => n + p.activeExecutions, 0),
      costQuality: worstQuality(rest.map((p) => p.costQuality)),
      topProjects: rest.flatMap((p) => p.topProjects)
        .sort((a, b) => b.totalTokens - a.totalTokens)
        .slice(0, 3),
      share,
      shareLabel: pct == null ? '—' : (unknownProjects > 0 ? '≥' : '') + pct + '%',
      color: 'var(--hud-accent-3)',
      ringFraction: share ?? 0,
      aggregate: true,
    },
  ]
}

/** One observed token total, keyed by the snapshot revision that carried it. */
export interface TokenSample {
  revision: number
  total: number
}

/**
 * Append one observation of tokenSummary.totalTokens. The series is what this
 * session actually saw, in arrival order:
 *   * the same revision with the same value is a no-op (poll repeats);
 *   * the same revision with a corrected value replaces it;
 *   * an older revision is refused (the read hook already rejects it upstream);
 *   * null is a gap, not a zero, so it never becomes a point.
 * Keeping the last 24 bounds the sparkline without hiding that it is a session
 * window rather than a source history.
 */
export function appendTokenSample(series: TokenSample[], snap: SnapshotV3 | null): TokenSample[] {
  const total = tokenTruth(snap)?.totalTokens
  if (!snap || typeof total !== 'number' || !Number.isFinite(total)) return series
  const last = series[series.length - 1]
  if (last && last.revision === snap.revision) {
    if (last.total === total) return series
    return [...series.slice(0, -1), { revision: snap.revision, total }]
  }
  if (last && snap.revision < last.revision) return series
  return [...series, { revision: snap.revision, total }].slice(-24)
}

/** A token value for the hero: exact grouping, never an abbreviation. */
const EXACT = new Intl.NumberFormat('en-US')
export function fmtExactTokens(n: number | null | undefined): string {
  return typeof n === 'number' && Number.isFinite(n) ? EXACT.format(n) : 'UNKNOWN'
}

/** The short form the rest of the Observer uses, extended to B/T so an
 *  extreme project total does not render as "100000000.00M". */
export function fmtHudTokens(n: number | null | undefined): string {
  if (n == null) return 'UNKNOWN'
  if (n === 0) return '0'
  // Below ten thousand the exact grouping is short enough for the card AND is
  // the only honest form: fmtTokens rounds 700 to "1k", a 43% overstatement.
  if (n < 1e4) return EXACT.format(n)
  if (n >= 1e12) return (n / 1e12).toFixed(2) + 'T'
  if (n >= 1e9) return (n / 1e9).toFixed(2) + 'B'
  return fmtTokens(n)
}

/** The HUD's own status key, derived from the word this surface may claim. */
export type HudState = 'live' | 'offline' | 'waiting' | 'unknown'
export function hudStateOf(transport: string): HudState {
  if (transport === 'LIVE') return 'live'
  if (transport === 'OFFLINE') return 'offline'
  if (transport === 'DELAYED' || transport === 'CONNECTING') return 'waiting'
  return 'unknown'
}

/** SVG arc for a per-provider ring. Rounded so tiny shares still paint a dot. */
export function ringArc(fraction: number, radius: number): { dasharray: string; circumference: number } {
  const c = 2 * Math.PI * radius
  const clamped = Math.max(0, Math.min(1, Number.isFinite(fraction) ? fraction : 0))
  const len = clamped === 0 ? 0 : Math.max(1.5, c * clamped)
  return { dasharray: `${len} ${Math.max(0, c - len)}`, circumference: c }
}

/* -------------------------------------------------------------------------
 * Fusion with the Agent HUD execution model (jazzenchen/agent-hud-open,
 * Apache-2.0): the same notch panel, segmented views, per-source cards and
 * waiting list. The DATA is the v3 projection; the reference's quota,
 * balance, 30-day bucket and per-session token lanes have no producer here,
 * so they are named as unavailable instead of being drawn from guesses.
 * ---------------------------------------------------------------------- */

/** The three faces of the fused HUD. */
export const HUD_TABS = [
  { id: 'usage', label: '用量' },
  { id: 'sessions', label: '会话' },
  { id: 'approvals', label: '审批' },
] as const
export type HudTab = typeof HUD_TABS[number]['id']

export function hudTabFromParam(value: string | null): HudTab {
  return value === 'sessions' || value === 'approvals' ? value : 'usage'
}

export interface HudAgentBar {
  /** false when a part is unreported or the parts exceed the reported total */
  known: boolean
  input: number
  output: number
  unclassified: number
}

/**
 * The stacked bar under an agent card. It is drawn ONLY from a complete
 * input/output/total triple; a partial triple has no honest width.
 */
export function hudAgentBar(provider: HudProvider): HudAgentBar {
  const total = provider.totalTokens
  const input = provider.inputTokens
  const output = provider.outputTokens
  const unclassified = provider.unclassifiedTokens
  // `unclassified` is null whenever ANY token-reporting project lacked a part.
  // A bar must not read the missing part as a zero-sized segment, so the null
  // is the authority here, not a recomputed remainder.
  if (total == null || input == null || output == null || unclassified == null
      || total <= 0 || input + output > total) {
    return { known: false, input: 0, output: 0, unclassified: 0 }
  }
  return { known: true, input, output, unclassified }
}

/** Current-session net change: newest reported total minus the first one seen. */
export function sessionTokenDelta(samples: TokenSample[]): number | null {
  if (samples.length < 2) return null
  return samples[samples.length - 1].total - samples[0].total
}

export type HudSessionGroup = 'waiting' | 'active' | 'other' | 'ended'

export interface HudSessionRow {
  executionId: string
  state: ExecutionState
  stateLabel: string
  group: HudSessionGroup
  /** displayName/ projectId when the anchor resolves; else the raw anchor id */
  projectLabel: string | null
  projectKnown: boolean
  agent: string | null
  workingArea: string | null
  sessionId: string | null
}

export interface HudSessionSummary {
  rows: HudSessionRow[]
  total: number
  waiting: number
  waitingApproval: number
  waitingUser: number
  active: number
  blocked: number
  completed: number
  failed: number
  unknown: number
}

const EXECUTION_PRESENTATION: Record<ExecutionState, {
  label: string; group: HudSessionGroup; order: number
}> = {
  WAITING_APPROVAL: { label: '等待批准', group: 'waiting', order: 0 },
  WAITING_USER: { label: '等待回答', group: 'waiting', order: 1 },
  RUNNING: { label: '运行中', group: 'active', order: 2 },
  STARTING: { label: '启动中', group: 'active', order: 3 },
  BLOCKED: { label: '已阻塞', group: 'other', order: 4 },
  FAILED: { label: '已失败', group: 'ended', order: 5 },
  COMPLETED: { label: '已完成', group: 'ended', order: 6 },
  UNKNOWN: { label: '未知', group: 'other', order: 7 },
}

/**
 * The reference puts sessions waiting on the user first. The projection's
 * ordering carries no timestamps, so "first" here is a state priority plus
 * the execution id -- never an invented elapsed time.
 */
export function buildHudSessions(snap: SnapshotV3 | null): HudSessionSummary {
  const summary: HudSessionSummary = {
    rows: [], total: 0, waiting: 0, waitingApproval: 0, waitingUser: 0,
    active: 0, blocked: 0, completed: 0, failed: 0, unknown: 0,
  }
  if (!snap) return summary
  const projects = new Map(snap.projects.map((p) => [p.projectId, p]))
  const rows: HudSessionRow[] = snap.executions.map((execution) => {
    const state: ExecutionState = EXECUTION_PRESENTATION[execution.state]
      ? execution.state
      : 'UNKNOWN'
    const presentation = EXECUTION_PRESENTATION[state]
    const anchor = execution.anchorProjectId
    const project = anchor ? projects.get(anchor) : undefined
    return {
      executionId: execution.executionId,
      state,
      stateLabel: presentation.label,
      group: presentation.group,
      projectLabel: project ? (project.displayName || project.projectId) : anchor,
      projectKnown: Boolean(project),
      agent: execution.agent,
      workingArea: execution.workingArea,
      sessionId: execution.sessionId,
    }
  })
  rows.sort((a, b) => EXECUTION_PRESENTATION[a.state].order - EXECUTION_PRESENTATION[b.state].order
    || a.executionId.localeCompare(b.executionId))
  summary.rows = rows
  summary.total = rows.length
  for (const row of rows) {
    if (row.state === 'WAITING_APPROVAL') summary.waitingApproval += 1
    else if (row.state === 'WAITING_USER') summary.waitingUser += 1
    else if (row.state === 'RUNNING' || row.state === 'STARTING') summary.active += 1
    else if (row.state === 'BLOCKED') summary.blocked += 1
    else if (row.state === 'COMPLETED') summary.completed += 1
    else if (row.state === 'FAILED') summary.failed += 1
    else summary.unknown += 1
  }
  summary.waiting = summary.waitingApproval + summary.waitingUser
  return summary
}

export interface HudPlanApproval {
  label: string
  state: string
  detail: string | null
}

export interface HudApprovalSummary {
  /** executions whose state explicitly says they wait for a person */
  waiting: HudSessionRow[]
  questions: HudSessionRow[]
  /** workspace.plan.approvals rows that are still open -- a DIFFERENT object */
  plan: HudPlanApproval[]
  /** false means the producer did not provide the key, not that the list is empty */
  planPresent: boolean
  count: number
}

const OPEN_PLAN_STATES = new Set(['PENDING', 'DEFERRED'])

/**
 * Two distinct waiting lanes must never be merged:
 *   * `executions[]` with WAITING_APPROVAL / WAITING_USER is agent-side work
 *     stopped on a person;
 *   * `workspace.plan.approvals[]` is the task pack's own rollout list.
 * The badge counts only the first; the second is rendered under its own name.
 * Observer cannot approve either -- it is a read-only projection.
 */
export function buildHudApprovals(snap: SnapshotV3 | null): HudApprovalSummary {
  const sessions = buildHudSessions(snap)
  const waiting = sessions.rows.filter((r) => r.state === 'WAITING_APPROVAL')
  const questions = sessions.rows.filter((r) => r.state === 'WAITING_USER')
  const raw = snap?.workspace?.plan?.approvals
  const planPresent = Array.isArray(raw)
  const plan = planPresent
    ? raw
      .filter((row) => OPEN_PLAN_STATES.has(String(row?.state ?? '')))
      .map((row) => ({
        label: typeof row?.label === 'string' && row.label.trim() ? row.label.trim() : '(未命名事项)',
        state: typeof row?.state === 'string' ? row.state : 'UNKNOWN',
        detail: typeof row?.detail === 'string' ? row.detail : null,
      }))
    : []
  return {
    waiting,
    questions,
    plan,
    planPresent,
    count: waiting.length + questions.length,
  }
}
