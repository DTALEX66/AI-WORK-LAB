// 日常壳（M01–M05）的数据投影：只从真实 v3 快照与既有读取结果派生，
// 缺数据一律 UNKNOWN / 未连接 / 待确认，不补 0、不虚构状态。
import type { SnapshotV3, Project, IssueRecord, AdapterCapabilityCard } from '@/types'
import type { SolutionItem } from '@/daily/solutionsClient'
import type { ManualRepairPack } from '@/lib/repairPack'

// 首页六状态（提示词 §7）：只允许由真实字段推出，推不出就是 状态待确认。
export type ProjectCardStatus =
  | '正在推进' | '需要关注' | '等待你决定' | '已完成' | '暂停' | '状态待确认'

export interface DailyProjectCard {
  projectId: string
  displayName: string
  status: ProjectCardStatus
  latestChange: string | null
  relatedTools: string[]
  updatedAt: string | null
  openIssueCount: number | null
  attentionNote: string | null
}

export function projectCardOf(
  p: Project,
  executions: { executionId: string; state: string }[],
  openIssues: number | null,
): DailyProjectCard {
  const waitingUser = executions.some((e) => e.state === 'WAITING_USER' || e.state === 'WAITING_APPROVAL')
  const blocked = executions.some((e) => e.state === 'BLOCKED' || e.state === 'FAILED')
  let status: ProjectCardStatus
  if (openIssues !== null && openIssues > 0) status = '需要关注'
  else if (waitingUser) status = '等待你决定'
  else if (blocked) status = '需要关注'
  else if (p.activityState === 'ACTIVE') status = '正在推进'
  else if (p.activityState === 'IDLE') status = '暂停'
  else status = '状态待确认'
  return {
    projectId: p.projectId,
    displayName: p.displayName ?? p.projectId,
    status,
    latestChange: p.lastStrongEvidenceAt,
    relatedTools: p.agentPlatform ? [p.agentPlatform] : [],
    updatedAt: p.lastStrongEvidenceAt,
    openIssueCount: openIssues,
    attentionNote: blocked ? '存在 BLOCKED / FAILED 执行记录' : null,
  }
}

export function dailyProjectCards(snap: SnapshotV3 | null, packs: ManualRepairPack[]): DailyProjectCard[] {
  if (!snap) return []
  const openByProject = new Map<string, number>()
  for (const issue of snap.issues ?? []) {
    if (!issue.projectId) continue
    openByProject.set(issue.projectId, (openByProject.get(issue.projectId) ?? 0) + 1)
  }
  for (const pack of packs) {
    // 一个 pack 绑定的 open issue 已由 issue 行计数，这里不重复计数。
    void pack
  }
  return (snap.projects ?? []).map((p) => {
    const own = (snap.executions ?? []).filter((e) => e.anchorProjectId === p.projectId)
    return projectCardOf(p, own, openByProject.has(p.projectId) ? (openByProject.get(p.projectId) as number) : 0)
  })
}

export interface DailyIssueRow {
  fingerprint: string
  title: string
  projectId: string | null
  priority: string
  classLabel: string
  detail: string | null
  lastSeenAt: string | null
  packId: string | null
  hasPack: boolean
}

export function dailyIssueRows(snap: SnapshotV3 | null, packs: ManualRepairPack[]): DailyIssueRow[] {
  if (!snap) return []
  const byFingerprint = new Map<string, ManualRepairPack>()
  for (const pack of packs) {
    for (const fp of pack.binds.issueFingerprints) byFingerprint.set(fp, pack)
  }
  return (snap.issues ?? []).map((issue: IssueRecord) => ({
    fingerprint: issue.fingerprint,
    title: issue.subject ?? issue.fingerprint,
    projectId: issue.projectId ?? null,
    priority: issue.priority,
    classLabel: issue.class,
    detail: issue.detail ?? null,
    lastSeenAt: issue.lastSeenAt ?? null,
    packId: byFingerprint.get(issue.fingerprint)?.packId ?? null,
    hasPack: byFingerprint.has(issue.fingerprint),
  }))
}

export interface DailyToolRow {
  clientId: string
  displayName: string
  connection: string
  capabilitySentence: string
  relatedProjects: string[]
  version: string | null
  observedAt: string | null
  writePolicy: string
  registryStatus: string
  // The operator's declared role for this client (agent runtime, provider router, repository host,
  // design client). UNKNOWN means the matrix declares none — a source gap, never a guess from the name.
  role: string
}

export function dailyToolRows(snap: SnapshotV3 | null): DailyToolRow[] {
  const cards: AdapterCapabilityCard[] = snap?.adapterCapabilities ?? []
  return cards.map((card) => {
    const entry = card.entryProbe ?? null
    const connection = entry
      ? (entry.status === 'PASS' ? '已建立基础连接（入口可执行）'
        : entry.status === 'FAIL' ? '入口探测失败（未连接）'
          : `入口探测 ${entry.status}`)
      : '未连接（无入口探测记录）'
    const declared = card.declaredOperations ?? []
    const capability = declared.length > 0
      ? `声明操作：${declared.join('、')}（${card.writePolicy}）`
      : '无已声明操作记录'
    return {
      clientId: card.clientId,
      displayName: card.displayName || card.clientId,
      connection,
      capabilitySentence: capability,
      relatedProjects: (snap?.projects ?? [])
        .filter((p) => p.agentPlatform && card.displayName
          && p.agentPlatform.toLowerCase().includes(card.clientId.toLowerCase()))
        .map((p) => p.displayName ?? p.projectId),
      version: card.declaredVersion ?? null,
      observedAt: card.observedAt ?? null,
      writePolicy: card.writePolicy,
      registryStatus: card.registryStatus,
      role: card.role ?? 'UNKNOWN',
    }
  })
}

// ── E2 · 监控对象显示筛选（?targets=）────────────────────────────────────
// 被观察的项目就是本产品的「监控对象」。这一族只做两件事：把选择编解码进 URL，
// 以及从同一份快照派生「当前显示的是哪个子集」。不发请求、不碰侧车、不写 web storage
// （apps/observer/tests/test_production_surface_static_contract.js 把 UI 层的 storage 判死），
// 地址是唯一载体：刷新、复制、粘贴即复现，Observer 仍然严格只读。
//
// 语义（写清，因为「空」在这个产品里有过两种含义）：
// * 没有 ?targets=            → 不筛选，显示全部监控对象；
// * ?targets= 或 ?targets=,,  → 与不带该参数同义（写回时删参数），不是「一个都不显示」；
// * ?targets=proj-a,proj-b    → 只显示命中这些 token 的对象；token 认 projectId 也认显示名
//                               （大小写与首尾空格不敏感），方便手写链接；
// * token 在本机投影里没有对应对象 → 不静默回退成「全部」，也不静默丢弃：未命中的 token
//                               原样报出来，空结果显示为「筛选未命中」而不是「没有对象」。

export const TARGETS_PARAM = 'targets'

export function readTargetSelection(search: string): string[] | null {
  return readSelectionParam(search, TARGETS_PARAM)
}

/** 两个显示筛选参数共用同一套编解码：缺席与空值同义＝不筛选，多值按序去重。 */
function readSelectionParam(search: string, name: string): string[] | null {
  let raw: string | null = null
  try { raw = new URLSearchParams(search).get(name) } catch { return null }
  if (raw === null) return null
  const tokens: string[] = []
  for (const part of raw.split(',')) {
    const t = part.trim()
    if (t && !tokens.includes(t)) tokens.push(t)
  }
  return tokens.length > 0 ? tokens : null
}

/** 选择 → 地址片段；null 表示「不筛选」，调用方据此删除参数而不是写空值。 */
export function encodeTargetSelection(tokens: string[] | null): string | null {
  if (!tokens || tokens.length === 0) return null
  return tokens.join(',')
}

const norm = (s: string) => s.trim().toLowerCase()

export interface TargetSubset<T> {
  active: boolean
  /** 快照里的全部监控对象（筛选不改变它：控件要能把没选中的项再选回来） */
  all: T[]
  /** 实际显示的对象 */
  shown: T[]
  /** 被筛选隐藏的对象：它们的问题依然存在，只是不在这个子集里 */
  excluded: T[]
  total: number
  /** 地址列出了、但投影里没有对应对象的 token，原样回报 */
  unmatchedTokens: string[]
  matchedProjectIds: string[]
}

export function selectTargets<T extends { projectId: string; displayName: string }>(
  cards: T[], tokens: string[] | null,
): TargetSubset<T> {
  const selection = tokens ?? []
  const active = tokens !== null
  if (!active) {
    return {
      active: false, all: cards, shown: cards, excluded: [], total: cards.length,
      unmatchedTokens: [], matchedProjectIds: cards.map((c) => c.projectId),
    }
  }
  const shown: T[] = []
  const excluded: T[] = []
  const hit = new Set<string>()
  for (const card of cards) {
    const id = norm(card.projectId)
    const name = norm(card.displayName)
    const token = selection.find((t) => { const n = norm(t); return n === id || n === name })
    if (token) { hit.add(token); shown.push(card) } else { excluded.push(card) }
  }
  return {
    active: true, all: cards, shown, excluded, total: cards.length,
    unmatchedTokens: selection.filter((t) => !hit.has(t)),
    matchedProjectIds: shown.map((c) => c.projectId),
  }
}

/** 一次点击的取舍：未筛选时点某项＝「只看它」；已筛选时点未选项＝加入；点已选项＝移出，
 *  移出到空集＝回到「不筛选」（不写 ?targets= 的空值，避免和「全部」两种含义纠缠）。 */
export function toggleTargetToken(selection: string[] | null, projectId: string): string[] | null {
  if (selection === null) return [projectId]
  const next = selection.includes(projectId)
    ? selection.filter((t) => t !== projectId)
    : [...selection, projectId]
  return next.length > 0 ? next : null
}

/** 显示筛选的诚实补句：N＝总数 − 显示数。N>0 才说「另有 N 项未显示」，
 *  N=0（含未筛选、以及地址把对象全列了一遍）时整句不出现——不写「另有 0 项未显示」，
 *  因为那既没有信息量，又把「全都在屏幕上」读成了一种筛选结果。 */
export function notShownClause(total: number, shown: number): string {
  const hidden = total - shown
  return hidden > 0 ? `另有 ${hidden} 项未显示` : ''
}

/** 首页的项目计数说明：筛选态下把范围写在数字旁边，读者不会把子集读成全机。 */
export function projectCountSentence(s: TargetSubset<unknown>): string {
  if (!s.active) return `${s.total} 个已注册项目`
  if (s.total === 0) return '快照中没有已注册项目（实测为 0，不是缺字段）'
  const hidden = notShownClause(s.total, s.shown.length)
  return `筛选显示 ${s.shown.length}／${s.total} 个已注册项目`
    + (hidden ? ` · ${hidden}` : '') + '（?targets 只限显示，不改数据）'
}

/** 筛选未命中时的空态：必须说清是筛选造成的空，不是「没有监控对象」。 */
export function targetMissSentence(tokens: string[], total: number): string {
  return `地址里列出的 ${tokens.join('、')} 在本机投影中没有对应的监控对象，`
    + `因此这一屏什么都不显示（投影里其实有 ${total} 个对象）。`
    + '这不是「没有项目」，也不是数据缺失；清除 ?targets 可恢复完整列表。'
}

export interface IssueScope<R> {
  shown: R[]
  /** 全机条数（快照产出的问题总数），与是否筛选无关 */
  total: number
  /** 属于未显示监控对象的问题条数 */
  hiddenByFilter: number
  /** 快照里就没有项目归属的问题条数（筛选态下它们同样不在子集里） */
  unattributed: number
}

export function partitionIssuesByTargets<R extends { projectId: string | null }>(
  rows: R[], subset: { active: boolean; matchedProjectIds: string[] },
): IssueScope<R> {
  const unattributed = rows.filter((r) => r.projectId === null).length
  if (!subset.active) {
    return { shown: rows, total: rows.length, hiddenByFilter: 0, unattributed }
  }
  const keep = new Set(subset.matchedProjectIds)
  const shown = rows.filter((r) => r.projectId !== null && keep.has(r.projectId))
  return {
    shown, total: rows.length,
    hiddenByFilter: rows.length - shown.length - unattributed,
    unattributed,
  }
}

/** 问题页的计数说明。displayed 是「检索之后真正列出的条数」，与筛选子集、全机三层一起报，
 *  任何一个数都不留范围不明的空间。未筛选时保持原有措辞，不改变既有可见行为。 */
export function issueCountSentence(scope: IssueScope<unknown>, active: boolean, displayed?: number): string {
  const shown = displayed ?? scope.shown.length
  const bySearch = Math.max(0, scope.shown.length - shown)
  if (!active) {
    return `共 ${shown} 条 · 快照产出 ${scope.total} 条问题`
      + (bySearch > 0 ? `（检索词排除了 ${bySearch} 条）` : '')
  }
  const reasons: string[] = []
  if (scope.hiddenByFilter > 0) reasons.push(`${scope.hiddenByFilter} 条属未显示的监控对象`)
  if (scope.unattributed > 0) reasons.push(`${scope.unattributed} 条无项目归属`)
  if (bySearch > 0) reasons.push(`${bySearch} 条被检索词排除`)
  return `筛选内 ${shown}／${scope.shown.length} 条 · 全机 ${scope.total} 条问题`
    + (reasons.length > 0 ? `（${reasons.join('；')}）` : '')
}

/** 筛选把问题清空时的说法：不得读成「当前没有打开的问题」。 */
export function filteredEmptyIssueSentence(scope: IssueScope<unknown>): string {
  if (scope.total === 0) return '快照没有产出任何问题（实测，非推断）。'
  const parts = [`筛选子集内 0 条`]
  if (scope.hiddenByFilter > 0) parts.push(`${scope.hiddenByFilter} 条属于未显示的监控对象`)
  if (scope.unattributed > 0) parts.push(`${scope.unattributed} 条在快照里没有项目归属`)
  return `本次 ?targets 筛选下没有问题可显示，但全机仍有 ${scope.total} 条问题：`
    + parts.join('；') + '。因此这里不是「没有问题」；清除筛选可看全量。'
}

// ── E2 · 监控对象的另一维：软件／工具（?tools=）────────────────────────────
// 与 ?targets 同一族、同一套语义（缺席＝全部、空值＝全部、未命中的 token 原样报出、
// 只进地址、零写入），换的只是对象：这一维筛的是被观察的软件／工具（适配器能力卡）。
// 分成两维而不是塞进一个参数：项目列表与工具列表是两类监控对象，各自筛自己的显示子集，
// 混在一个参数里就没法诚实回答「这条为什么没显示」。

export const TOOLS_PARAM = 'tools'

export function readToolSelection(search: string): string[] | null {
  return readSelectionParam(search, TOOLS_PARAM)
}

export function encodeToolSelection(tokens: string[] | null): string | null {
  if (!tokens || tokens.length === 0) return null
  return tokens.join(',')
}

export interface ToolSubset<T> {
  active: boolean
  all: T[]
  shown: T[]
  excluded: T[]
  total: number
  unmatchedTokens: string[]
  matchedClientIds: string[]
}

export function selectTools<T extends { clientId: string; displayName: string }>(
  rows: T[], tokens: string[] | null,
): ToolSubset<T> {
  const selection = tokens ?? []
  const active = tokens !== null
  if (!active) {
    return {
      active: false, all: rows, shown: rows, excluded: [], total: rows.length,
      unmatchedTokens: [], matchedClientIds: rows.map((r) => r.clientId),
    }
  }
  const shown: T[] = []
  const excluded: T[] = []
  const hit = new Set<string>()
  for (const row of rows) {
    const id = norm(row.clientId)
    const name = norm(row.displayName)
    const token = selection.find((t) => { const n = norm(t); return n === id || n === name })
    if (token) { hit.add(token); shown.push(row) } else { excluded.push(row) }
  }
  return {
    active: true, all: rows, shown, excluded, total: rows.length,
    unmatchedTokens: selection.filter((t) => !hit.has(t)),
    matchedClientIds: shown.map((r) => r.clientId),
  }
}

/** 一次点击的取舍与 ?targets 一致：未筛选时点某项＝只看它；移回空集＝删参数。 */
export function toggleToolToken(selection: string[] | null, clientId: string): string[] | null {
  if (selection === null) return [clientId]
  const next = selection.includes(clientId)
    ? selection.filter((t) => t !== clientId)
    : [...selection, clientId]
  return next.length > 0 ? next : null
}

/** 工具列表的计数说明：不补 0、不画百分比——能力卡缺席是来源缺失，不是「0 个工具」。 */
export function toolCountSentence(s: ToolSubset<unknown>): string {
  if (s.total === 0) return '快照未携带适配器能力卡（来源缺失，不是 0 个工具）'
  if (!s.active) return `${s.total} 个已登记工具`
  const hidden = notShownClause(s.total, s.shown.length)
  return `筛选显示 ${s.shown.length}／${s.total} 个已登记工具`
    + (hidden ? ` · ${hidden}` : '') + '（?tools 只限显示，不改数据）'
}

/** 筛选未命中任何能力卡时的空态：明说空来自筛选，不是「没有工具」。 */
export function toolMissSentence(tokens: string[], total: number): string {
  return `地址里列出的 ${tokens.join('、')} 在本机投影的适配器能力卡里没有对应的工具，`
    + `因此这一屏什么都不显示（投影里其实有 ${total} 张能力卡）。`
    + '这不是「没有工具」，也不是数据缺失；清除 ?tools 可恢复完整列表。'
}

// 交接材料：预览 / 复制 / 导出共用这一处生成（提示词 §9）。
export interface HandoverContext {
  projectName: string | null
  issueTitle: string | null
  method: SolutionItem | null
  pack: ManualRepairPack | null
  targetTool: string
}

export function buildHandoverMaterial(ctx: HandoverContext): { text: string; fileName: string } {
  const lines: string[] = []
  lines.push('WORK-LAB 手动交接材料')
  lines.push(`目标工具：${ctx.targetTool || '未选择'}`)
  if (ctx.pack) {
    // 后端渲染的 pack.handoffText 是唯一材料事实；本函数不重写它。
    lines.push(`项目：${ctx.pack.target.projectName ?? ctx.pack.target.projectId}`)
    lines.push('', ctx.pack.handoffText)
    return { text: lines.join('\n'), fileName: `handover-${ctx.pack.packId}.txt` }
  }
  if (ctx.method) {
    lines.push(`项目：${ctx.projectName ?? '未指定'}`)
    lines.push(`问题：${ctx.issueTitle ?? '未指定'}`)
    lines.push(`方法：${ctx.method.title ?? ctx.method.solutionId}（r${ctx.method.revision ?? '?'}，状态 ${ctx.method.status ?? 'UNKNOWN'}）`)
    if (ctx.method.preconditions.length) lines.push('', '前提：', ...ctx.method.preconditions.map((s) => `- ${s}`))
    if (ctx.method.steps.length) lines.push('', '处理步骤（供外部工具参考）：', ...ctx.method.steps.map((s, i) => `${i + 1}. ${s}`))
    if (ctx.method.verificationSteps.length) lines.push('', '验证：', ...ctx.method.verificationSteps.map((s) => `- ${s}`))
    if (ctx.method.limits.length) lines.push('', '适用限制：', ...ctx.method.limits.map((s) => `- ${s}`))
    if (ctx.method.invalidWhen.length) lines.push('', '失效条件：', ...ctx.method.invalidWhen.map((s) => `- ${s}`))
    lines.push('', `来源：方案库 ${ctx.method.solutionId}；适用性以方案自报为准，执行前需复核。`)
    return { text: lines.join('\n'), fileName: `handover-${ctx.method.solutionId}.txt` }
  }
  lines.push('没有可交接的方法或修复包材料。')
  return { text: lines.join('\n'), fileName: 'handover-empty.txt' }
}
