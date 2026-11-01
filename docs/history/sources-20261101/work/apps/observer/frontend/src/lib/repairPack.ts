// CL-07 · the read-only client for `GET /api/v1/repair-packs`.
//
// The pack and its `handoffText` are produced by `packages/client-neutral-core/scripts/
// repair_pack_projection.py` on the sidecar. This module copies the wire shape and refuses anything else:
// rendering a body that is not the projection's own view would let the page show a handoff the backend
// never rendered. `handoff.sent` / `handoff.dispatched` are checked on every pack because the material a
// human copies must still read 未发送 — a body that claims otherwise is not a draft this client can show.
import type { IssuesSummary } from '@/types'

export const REPAIR_PACKS_VIEW_SCHEMA_VERSION = 'worklab/repair-packs-view/v1'

export type RepairPacksStatus = 'OK' | 'NO_OPEN_ISSUES' | 'NO_PACK' | 'SOURCE_ABSENT'
export const REPAIR_PACKS_STATUSES: readonly RepairPacksStatus[] = [
  'OK', 'NO_OPEN_ISSUES', 'NO_PACK', 'SOURCE_ABSENT',
]

export interface ManualRepairPack {
  schemaVersion: string
  packId: string
  generatedAt: string
  status: string
  readiness: { state: string; reasons: string[] }
  target: {
    kind: string
    projectId: string
    projectName: string | null
    projectRoot: string
    adapter: string | null
    declaredOperations: string[]
    operation: string
    routingSource: string
  }
  binds: {
    issueFingerprints: string[]
    evidenceRefs: string[]
    classes: string[]
    priorities: string[]
    issueCount: number
    softwareIds: string[]
    unattributedCount: number
  }
  verification: { known: boolean; command: string; basis: string }
  handoff: {
    mode: string
    copyable: boolean
    sent: boolean
    dispatched: boolean
    requiresOwnerAction: string
  }
  /** The exact text `render_handoff_text` produced; this is what the copy button writes. */
  handoffText: string
}

export interface RepairPacksSummary {
  schemaVersion?: string
  openIssueCount?: number | null
  packCount?: number
  refusalCount?: number
  refusals?: Array<{ adapter: string; reason: string; projectId?: string }>
  refusalReasons?: Record<string, number>
  truncated?: boolean
  cap?: number
  boundIssueCount?: number
  unboundOpenIssueCount?: number | null
  projectsSeen?: number
  issuesWithoutProject?: number
  verificationKnownCount?: number
  sent?: boolean
  dispatchPerformed?: boolean
}

export interface RepairPacksView {
  schemaVersion: string
  status: RepairPacksStatus
  reason: string
  generatedAt: string
  issuesSummary: IssuesSummary | null
  packs: ManualRepairPack[]
  summary: RepairPacksSummary | null
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const asString = (value: unknown): string | null => (typeof value === 'string' ? value : null)

function parsePack(value: unknown): { ok: true; pack: ManualRepairPack } | { ok: false; why: string } {
  if (!isRecord(value)) return { ok: false, why: 'pack 不是一个对象' }
  const packId = asString(value.packId)
  if (!packId) return { ok: false, why: 'pack 缺少 packId' }
  if (!isRecord(value.target) || !asString(value.target.projectId)) {
    return { ok: false, why: `pack ${packId} 缺少 target.projectId：无法定位它属于哪个项目` }
  }
  if (!isRecord(value.binds) || !Array.isArray(value.binds.evidenceRefs)) {
    return { ok: false, why: `pack ${packId} 缺少 binds.evidenceRefs：交接材料无法逐条复核` }
  }
  if (!isRecord(value.handoff)) {
    return { ok: false, why: `pack ${packId} 缺少 handoff 状态块` }
  }
  if (value.handoff.sent !== false || value.handoff.dispatched !== false) {
    return { ok: false, why: `pack ${packId} 声称已发送或已派发；本页面只展示未发送的草稿` }
  }
  const text = asString(value.handoffText)
  if (!text || !text.trim()) {
    return { ok: false, why: `pack ${packId} 没有可复制的 handoffText` }
  }
  return { ok: true, pack: value as unknown as ManualRepairPack }
}

/** Fail-closed structural read: a foreign schema, an impossible status, or a pack that contradicts its own
 *  draft state is unreadable, never a handoff the page may render. */
export function parseRepairPacksView(value: unknown):
  { ok: true; view: RepairPacksView } | { ok: false; why: string } {
  if (!isRecord(value)) return { ok: false, why: '响应体不是一个对象' }
  if (value.schemaVersion !== REPAIR_PACKS_VIEW_SCHEMA_VERSION) {
    return { ok: false, why: `契约版本不符（收到 ${asString(value.schemaVersion) ?? '无 schemaVersion'}）` }
  }
  const status = asString(value.status)
  if (!status || !(REPAIR_PACKS_STATUSES as readonly string[]).includes(status)) {
    return { ok: false, why: `status 不在 ${REPAIR_PACKS_STATUSES.join(' / ')}（收到 ${status ?? '缺失'}）` }
  }
  if (!asString(value.reason)) return { ok: false, why: '缺少 reason：状态没有可读的原因' }
  if (!Array.isArray(value.packs)) return { ok: false, why: 'packs 不是数组' }
  const packs: ManualRepairPack[] = []
  for (const raw of value.packs) {
    const parsed = parsePack(raw)
    if (!parsed.ok) return parsed
    packs.push(parsed.pack)
  }
  if (status === 'OK' && packs.length === 0) {
    return { ok: false, why: 'status=OK 却没有任何 pack' }
  }
  if (status !== 'OK' && packs.length > 0) {
    return { ok: false, why: `status=${status} 却携带了 pack：两种说法互相矛盾` }
  }
  return { ok: true, view: { ...(value as unknown as RepairPacksView), packs } }
}

export type RepairPacksOutcome =
  | { kind: 'RESULT'; view: RepairPacksView; httpStatus: number; endpoint: string }
  | { kind: 'UNREACHABLE'; httpStatus: number | null; detail: string; endpoint: string }
  | { kind: 'BAD_PAYLOAD'; why: string; httpStatus: number; endpoint: string }

export type RepairPackReader = (signal?: AbortSignal) => Promise<RepairPacksOutcome>

/** Same transport discipline as the evidence reader: GET only, no body, no-store, a bounded read that
 *  reports UNREACHABLE rather than pretending a timeout was a refusal. */
export function makeHttpRepairPackReader(endpoint: string, timeoutMs = 8000): RepairPackReader {
  return async (outer?: AbortSignal) => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    const forward = () => controller.abort()
    if (outer) {
      if (outer.aborted) controller.abort()
      else outer.addEventListener('abort', forward, { once: true })
    }
    try {
      const response = await fetch(endpoint, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
        headers: { Origin: endpoint.replace(/https?:\/\/([^/]+)/, 'http://$1') },
      })
      let body: unknown = null
      try {
        body = await response.json()
      } catch {
        return {
          kind: 'UNREACHABLE',
          httpStatus: response.status,
          detail: response.status >= 400 ? `端点返回 ${response.status} 且无可解析响应体` : '响应体不是 JSON',
          endpoint,
        }
      }
      const parsed = parseRepairPacksView(body)
      if (parsed.ok) return { kind: 'RESULT', view: parsed.view, httpStatus: response.status, endpoint }
      return { kind: 'BAD_PAYLOAD', why: parsed.why, httpStatus: response.status, endpoint }
    } catch (error) {
      return {
        kind: 'UNREACHABLE',
        httpStatus: null,
        detail: (error as Error)?.name === 'AbortError'
          ? `读取在 ${timeoutMs}ms 内未送达`
          : `传输失败：${(error as Error)?.message || '原因未知'}`,
        endpoint,
      }
    } finally {
      clearTimeout(timer)
      outer?.removeEventListener('abort', forward)
    }
  }
}

export function packForProject(view: RepairPacksView, projectId: string): ManualRepairPack | null {
  return view.packs.find((pack) => pack.target.projectId === projectId) || null
}

/** Write the material to the clipboard. Failure is returned, never styled as success: the page keeps the
 *  text visible so the user can copy it by hand. */
export async function writeClipboardText(text: string): Promise<{ ok: true } | { ok: false; why: string }> {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return { ok: true }
    }
  } catch (error) {
    // Fall through to the selection-based path; a denied permission is not the only failure mode.
  }
  try {
    if (typeof document === 'undefined') return { ok: false, why: '此环境没有剪贴板接口' }
    const area = document.createElement('textarea')
    area.value = text
    area.setAttribute('readonly', '')
    area.style.position = 'fixed'
    area.style.opacity = '0'
    document.body.appendChild(area)
    area.select()
    const copied = typeof document.execCommand === 'function' && document.execCommand('copy')
    document.body.removeChild(area)
    return copied ? { ok: true } : { ok: false, why: '浏览器拒绝了剪贴板写入' }
  } catch (error) {
    return { ok: false, why: `剪贴板写入失败：${(error as Error)?.message || '原因未知'}` }
  }
}
