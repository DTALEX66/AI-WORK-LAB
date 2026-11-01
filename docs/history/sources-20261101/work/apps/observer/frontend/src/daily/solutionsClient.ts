// CL-06 界面 · the read-only client for `GET /api/v1/solutions`.
// Same transport discipline as repairPack.ts: GET only, no-store, bounded read,
// endpoint derived from the validated snapshot base. The wire body is
// `worklab/solution-search/v1`; anything else is unreadable, never rendered.
import { loadRuntimeDescriptor, isTrustedObserverEndpoint, isTrustedRepairPacksEndpoint } from '@/lib/api'

export const SOLUTION_SEARCH_SCHEMA_VERSION = 'worklab/solution-search/v1'

export type SolutionSearchStatus = 'OK' | 'EMPTY' | 'NO_MATCH' | 'SOURCE_ABSENT'

export const SOLUTION_STATUSES: readonly SolutionSearchStatus[] = [
  'OK', 'EMPTY', 'NO_MATCH', 'SOURCE_ABSENT',
]

export interface SolutionVersionHint {
  state: string
  recordedVersion?: string | null
  currentVersion?: string | null
  message?: string
}

export interface SolutionItem {
  solutionId: string
  revision: number | null
  title: string | null
  status: string | null
  recommended: boolean
  software: { softwareId?: string | null; [k: string]: unknown }
  versionHint: SolutionVersionHint
  limits: string[]
  steps: string[]
  verificationSteps: string[]
  preconditions: string[]
  risks: string[]
  invalidWhen: string[]
  issueRefs: string[]
  evidenceRefs: string[]
  source: Record<string, unknown>
  score: number
  matchedTerms: string[]
  issueMatch: boolean
}

export interface SolutionSearchView {
  schemaVersion: string
  status: SolutionSearchStatus
  reason: string
  query: string
  results: SolutionItem[]
  summary: Record<string, unknown> | null
}

export function solutionsEndpoint(): { url: string; authoritative: boolean } | null {
  const descriptor = loadRuntimeDescriptor()
  const base = descriptor.snapshotUrl
  // 校验对象是快照基址本身（/api/v1/snapshot），再派生 /api/v1/solutions 并复检。
  if (!isTrustedObserverEndpoint(base)) return null
  const url = base.replace(/\/api\/v1\/snapshot$/, '/api/v1/solutions')
  return isTrustedRepairPacksEndpoint(url.replace('/api/v1/solutions', '/api/v1/repair-packs'))
    ? { url, authoritative: descriptor.authoritative }
    : null
}

const asString = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const asStringList = (v: unknown): string[] =>
  Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []

export function parseSolutionSearchView(value: unknown):
  { ok: true; view: SolutionSearchView } | { ok: false; why: string } {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { ok: false, why: '响应体不是一个对象' }
  }
  const body = value as Record<string, unknown>
  if (body.schemaVersion !== SOLUTION_SEARCH_SCHEMA_VERSION) {
    return { ok: false, why: `契约版本不符（收到 ${asString(body.schemaVersion) ?? '无 schemaVersion'}）` }
  }
  const status = asString(body.status)
  if (!status || !(SOLUTION_STATUSES as readonly string[]).includes(status)) {
    return { ok: false, why: `status 不在 ${SOLUTION_STATUSES.join(' / ')}（收到 ${status ?? '缺失'}）` }
  }
  if (!asString(body.reason)) return { ok: false, why: '缺少 reason：状态没有可读的原因' }
  if (!Array.isArray(body.results)) return { ok: false, why: 'results 不是数组' }
  if (status === 'SOURCE_ABSENT' && Array.isArray(body.results) && body.results.length > 0) {
    return { ok: false, why: 'status=SOURCE_ABSENT 却携带结果：两种说法互相矛盾' }
  }
  const results: SolutionItem[] = []
  for (const raw of body.results) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return { ok: false, why: 'results 里存在非对象条目' }
    }
    const item = raw as Record<string, unknown>
    const solutionId = asString(item.solutionId)
    if (!solutionId) return { ok: false, why: '结果条目缺少 solutionId：无法作为稳定记录打开' }
    const software = (item.software && typeof item.software === 'object' && !Array.isArray(item.software))
      ? item.software as SolutionItem['software'] : {}
    const versionHint = (item.versionHint && typeof item.versionHint === 'object' && !Array.isArray(item.versionHint))
      ? item.versionHint as SolutionVersionHint : { state: 'UNKNOWN' }
    results.push({
      solutionId,
      revision: typeof item.revision === 'number' ? item.revision : null,
      title: asString(item.title),
      status: asString(item.status),
      recommended: item.recommended === true,
      software,
      versionHint,
      limits: asStringList(item.limits),
      steps: asStringList(item.steps),
      verificationSteps: asStringList(item.verificationSteps),
      preconditions: asStringList(item.preconditions),
      risks: asStringList(item.risks),
      invalidWhen: asStringList(item.invalidWhen),
      issueRefs: asStringList(item.issueRefs),
      evidenceRefs: asStringList(item.evidenceRefs),
      source: (item.source && typeof item.source === 'object' && !Array.isArray(item.source))
        ? item.source as Record<string, unknown> : {},
      score: typeof item.score === 'number' ? item.score : 0,
      matchedTerms: asStringList(item.matchedTerms),
      issueMatch: item.issueMatch === true,
    })
  }
  return {
    ok: true,
    view: {
      schemaVersion: SOLUTION_SEARCH_SCHEMA_VERSION,
      status: status as SolutionSearchStatus,
      reason: body.reason as string,
      query: asString(body.query) ?? '',
      results,
      summary: (body.summary && typeof body.summary === 'object') ? body.summary as Record<string, unknown> : null,
    },
  }
}

export type SolutionsOutcome =
  | { kind: 'RESULT'; view: SolutionSearchView }
  | { kind: 'UNREACHABLE'; detail: string }
  | { kind: 'BAD_PAYLOAD'; why: string }

export async function fetchSolutions(query: string, signal?: AbortSignal): Promise<SolutionsOutcome> {
  const endpoint = solutionsEndpoint()
  if (!endpoint) return { kind: 'UNREACHABLE', detail: '没有可信任的 loopback 端点' }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 8000)
  const forward = () => controller.abort()
  if (signal) {
    if (signal.aborted) controller.abort()
    else signal.addEventListener('abort', forward, { once: true })
  }
  const sep = endpoint.url.includes('?') ? '&' : '?'
  const url = `${endpoint.url}${sep}q=${encodeURIComponent(query)}`
  try {
    const response = await fetch(url, {
      method: 'GET', cache: 'no-store', signal: controller.signal,
      headers: { Origin: url.replace(/https?:\/\/([^/]+)/, 'http://$1') },
    })
    let body: unknown = null
    try { body = await response.json() } catch {
      return { kind: 'UNREACHABLE', detail: `端点返回 ${response.status} 且无可解析响应体` }
    }
    const parsed = parseSolutionSearchView(body)
    return parsed.ok ? { kind: 'RESULT', view: parsed.view } : { kind: 'BAD_PAYLOAD', why: parsed.why }
  } catch (error) {
    return {
      kind: 'UNREACHABLE',
      detail: (error as Error)?.name === 'AbortError' ? '读取在 8000ms 内未送达' : `传输失败：${(error as Error)?.message || '原因未知'}`,
    }
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', forward)
  }
}
