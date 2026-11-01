// REQ-RANGE-20261007 · the read-only client for `GET /api/v1/evidence-range`.
//
// THE SHAPE IS THE BACKEND'S, NOT OURS. `packages/client-neutral-core/scripts/evidence_range_reader.py`
// is the authority for this payload and it mixes cases on purpose (`schema_version` / `reason_code`
// snake_case, `sliceDigest` / `endOffset` / `eofReached` camelCase). A tidy camelCase model here would
// have silently dropped the two fields that carry the verdict, so this module mirrors the wire exactly and
// the view reads those keys.
//
// Two rules this module exists to enforce:
//
// * HTTP status is transport, the verdict is the body. A 200 can carry `REFUSED` (and a 403 carries the
//   typed `PEER_NOT_LOOPBACK` verdict), so the client parses the body whenever it parses as a
//   range result and never infers success from `res.ok`;
// * a read that never arrived is NOT a refusal. `UNREACHABLE` / `BAD_PAYLOAD` are their own kinds, so the
//   panel cannot paint a transport failure as `REFUSED` with an invented reason code.
import type { SnapshotV3 } from '@/types'

export const EVIDENCE_RANGE_SCHEMA_VERSION = 'worklab/evidence-range-result/v1'

export type EvidenceRangeStatus = 'OK' | 'REFUSED' | 'OUT_OF_RANGE'
export const EVIDENCE_RANGE_STATUSES: readonly EvidenceRangeStatus[] = ['OK', 'REFUSED', 'OUT_OF_RANGE']

/** Every code the reader (`REFUSALS` + the two out-of-range paths) and the sidecar route emit.
 *  Mirrored, not invented: a code outside this list still renders, labelled as 未登记的判定码. */
export const EVIDENCE_BACKEND_REASON_CODES = [
  'READ_OK',
  'HANDLE_REQUIRED',
  'ABSOLUTE_PATH_REQUIRED',
  'OUT_OF_BOUNDARY',
  'OUT_OF_EVIDENCE_SURFACE',
  'SENSITIVE_NAME',
  'UNRESOLVABLE',
  'NOT_A_FILE',
  'UNREADABLE',
  'LIMIT_TOO_LARGE',
  'DIGEST_MISMATCH',
  'DIGEST_SHAPE',
  'IDENTITY_TOO_LARGE_TO_MEASURE',
  'LIMIT_NON_POSITIVE',
  'OFFSET_NEGATIVE',
  'OFFSET_PAST_END',
  'PEER_NOT_LOOPBACK',
  'BAD_QUERY',
] as const
export type EvidenceBackendReasonCode = typeof EVIDENCE_BACKEND_REASON_CODES[number]

/** The reader's own ceiling, mirrored for display only. The client never caps a limit itself: an
 *  over-large request must come back as the backend's `LIMIT_TOO_LARGE` refusal, not a silent truncation. */
export const EVIDENCE_MAX_LIMIT = 4 * 1024 * 1024
/** sha256 hex length, same constant as `DIGEST_HEX_LENGTH` in the reader. */
export const DIGEST_HEX_LENGTH = 64

export interface EvidenceRangeCost {
  bytesRead?: number | null
  fileSize?: number | null
  wholeFileWasRead?: boolean | null
}

export interface EvidenceRangeIdentity {
  /** The digest the CALLER pinned (`?expectedDigest=`). A claim, never a measurement. */
  expectedDigest?: string | null
  /** The digest the reader measured off the file's own bytes. Never a caller echo (ERR-284). */
  wholeDigest?: string | null
  sizeBytes?: number | null
  /** 'measured-by-reader' | 'not-requested' | 'not-measurable'. */
  digestSource?: string | null
  /** True only when a pin existed and the reader's measurement equalled it. */
  verified?: boolean | null
}

export interface EvidenceRangeResult {
  schema_version: string
  status: EvidenceRangeStatus
  reason_code: string
  reason: string
  handle?: string
  offset?: number
  limit?: number
  bytesRequested?: number
  endOffset?: number
  eofReached?: boolean
  /** null on every REFUSED / OUT_OF_RANGE result — the reader returns no bytes it cannot vouch for. */
  content: string | null
  sliceDigest?: string
  identity?: EvidenceRangeIdentity
  cost?: EvidenceRangeCost
}

/** A plain object (not null, not an array). Exported because the handle lane reads the same runtime
 *  shapes — a sub-record that is absent is a source gap, one that is an array is a shape mismatch, and
 *  the two must not be folded into each other by a lane-local copy of this predicate. */
export const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const str = (value: unknown): string | null =>
  typeof value === 'string' ? value : (typeof value === 'number' ? String(value) : null)

/** Fail-closed structural read. A legacy body, a HTML error page or a truncated JSON must not be cast into
 *  an `EvidenceRangeResult` and rendered as if the backend had ruled on it. */
export function parseEvidenceRangePayload(value: unknown):
  { ok: true; result: EvidenceRangeResult } | { ok: false; why: string } {
  if (!isRecord(value)) return { ok: false, why: '响应体不是一个对象' }
  if (value.schema_version !== EVIDENCE_RANGE_SCHEMA_VERSION) {
    return { ok: false, why: `契约版本不符（收到 ${str(value.schema_version) ?? '无 schema_version'}）` }
  }
  const status = str(value.status)
  if (!status || !(EVIDENCE_RANGE_STATUSES as readonly string[]).includes(status)) {
    return { ok: false, why: `status 不是 OK / REFUSED / OUT_OF_RANGE（收到 ${status ?? '缺失'}）` }
  }
  const reasonCode = str(value.reason_code)
  if (!reasonCode) return { ok: false, why: '缺少 reason_code：判定无法署名' }
  const content = value.content
  if (content !== null && typeof content !== 'string') {
    return { ok: false, why: 'content 既不是文本也不是 null，无法判定它代表什么' }
  }
  if (status !== 'OK' && content !== null && content !== '') {
    return { ok: false, why: `非 OK 判定却携带了内容（status=${status}）` }
  }
  if (status === 'OK' && content === null) {
    return { ok: false, why: 'OK 判定却没有返回字节' }
  }
  return { ok: true, result: value as unknown as EvidenceRangeResult }
}

export const isRegisteredReasonCode = (code: string): boolean =>
  (EVIDENCE_BACKEND_REASON_CODES as readonly string[]).includes(code)

// ---------------------------------------------------------------------------
// Addressing: the artifact read is a link, not a form field.
// ---------------------------------------------------------------------------

export interface EvidenceAddress {
  handle: string
  offset: number | null
  limit: number | null
  expectedDigest: string | null
}

/** The two names the handle block's filter state travels under. Declared once, here, and re-used by
 *  `EVIDENCE_PARAM_NAMES` below and by both link builders — the lane's own copy of this list is what
 *  drifted out of step (WUI-15 review ⑤/⑥). */
export const HANDLES_PARAM_NAMES = ['handlesSurface', 'handlesDigest'] as const

export const EVIDENCE_PARAM_NAMES = ['artifact', 'offset', 'limit', 'expectedDigest',
  ...HANDLES_PARAM_NAMES] as const

/** A Windows path is the normal handle shape here, so unlike a ledger id it carries separators, spaces and
 *  a drive letter. What it may not carry is a control character or an unbounded length. Absolute-ness,
 *  surface membership and credential-shaped names are the reader's decisions — the UI must not pre-empt
 *  them, because the typed refusal is the thing the panel exists to show. */
const MAX_HANDLE_LENGTH = 512
/** Exported: the handle filter lane validates its URL value with this same rule, and one regex per
 *  character class is what keeps the two refusals worded the same way. */
export const CONTROL_CHARS = /[\u0000-\u001f\u007f]/

export type AddressVerdict =
  | { kind: 'absent' }
  | { kind: 'addressed'; address: EvidenceAddress }
  | { kind: 'rejected'; reasons: string[] }

const intParam = (raw: string | null, name: string, reasons: string[]): number | null => {
  if (raw === null || raw.trim() === '') return null
  if (!/^-?\d+$/.test(raw.trim())) {
    reasons.push(`${name} 必须是整数，已拒绝：${raw.slice(0, 24)}`)
    return null
  }
  const parsed = Number(raw.trim())
  if (!Number.isSafeInteger(parsed)) {
    reasons.push(`${name} 超出可表示范围，已拒绝`)
    return null
  }
  return parsed
}

/** Read the addressed slice from a search string, the same way `readRecordFocus` reads a record id:
 *  a wanted-but-illegal value is reported, never interpolated into a request. */
export function readEvidenceAddress(search: string): AddressVerdict {
  let params: URLSearchParams
  try { params = new URLSearchParams(search) } catch { return { kind: 'absent' } }
  const rawHandle = params.get('artifact')
  if (rawHandle === null || rawHandle.trim() === '') return { kind: 'absent' }
  const reasons: string[] = []
  const handle = rawHandle.trim()
  if (handle.length > MAX_HANDLE_LENGTH) reasons.push(`artifact 超过 ${MAX_HANDLE_LENGTH} 个字符，已拒绝`)
  if (CONTROL_CHARS.test(handle)) reasons.push('artifact 含控制字符，已拒绝')
  const offset = intParam(params.get('offset'), 'offset', reasons)
  const limit = intParam(params.get('limit'), 'limit', reasons)
  const digest = (raw: string | null, name: string): string | null => {
    if (raw === null || raw.trim() === '') return null
    const value = raw.trim()
    if (value.length > DIGEST_HEX_LENGTH * 2) { reasons.push(`${name} 过长，已拒绝`); return null }
    return value
  }
  const expectedDigest = digest(params.get('expectedDigest'), 'expectedDigest')
  if (reasons.length > 0) return { kind: 'rejected', reasons }
  return {
    kind: 'addressed',
    address: { handle, offset, limit, expectedDigest },
  }
}

/** What a lane link must carry over. `palette` is a theme channel the shell reads off the address, and
 *  the two handle-filter names are that block's state — it lives in the URL because web storage is
 *  forbidden here, so dropping them is how one click on a source silently reset a filter the reader had
 *  just set (WUI-15 review ⑥). The artifact address itself is deliberately NOT preserved: `evidenceHref`
 *  writes it from the address it is handed, and copying a previous `offset`/`limit` onto a new handle
 *  would read bytes nobody asked for. */
const PRESERVED_PARAMS = ['theme', 'layout', 'palette', 'api', 'shell', 'taskId', 'executionId',
  ...HANDLES_PARAM_NAMES] as const

/** The shareable address for one slice: the same single `?view=` mechanism the shell already uses. */
export function evidenceHref(address: EvidenceAddress | null, search: string, laneId = 'evidence'): string {
  const params = new URLSearchParams()
  params.set('view', laneId)
  const current = new URLSearchParams(search)
  for (const name of PRESERVED_PARAMS) {
    const value = current.get(name)
    if (value) params.set(name, value)
  }
  if (address) {
    params.set('artifact', address.handle)
    if (address.offset !== null) params.set('offset', String(address.offset))
    if (address.limit !== null) params.set('limit', String(address.limit))
    if (address.expectedDigest) params.set('expectedDigest', address.expectedDigest)
  }
  const qs = params.toString()
  return `${window.location.pathname}${qs ? '?' + qs : ''}`
}

// ---------------------------------------------------------------------------
// The read itself: GET only, loopback only, derived from the runtime descriptor.
// ---------------------------------------------------------------------------

export interface EvidenceSliceRequest {
  handle: string
  offset?: number | null
  limit?: number | null
  expectedDigest?: string | null
}

export type EvidenceSliceOutcome =
  /** a typed verdict arrived (any HTTP status); `httpStatus` is transport context, not the verdict */
  | { kind: 'RESULT'; result: EvidenceRangeResult; httpStatus: number; endpoint: string; authoritative: boolean }
  /** the request never produced a verdict: unreachable, non-2xx-without-body, timeout */
  | { kind: 'UNREACHABLE'; httpStatus: number | null; detail: string; endpoint: string; authoritative: boolean }
  /** a body arrived but is not a range result — reported as an unreadable contract, never as a refusal */
  | { kind: 'BAD_PAYLOAD'; why: string; httpStatus: number; endpoint: string; authoritative: boolean }

/** Only the params the caller actually set. An unset offset/limit is not sent as `0`: the reader's own
 *  defaults (0 / DEFAULT_LIMIT) are the truth, and a padded 0 here would silently change the request. */
export function evidenceQuery(request: EvidenceSliceRequest): string {
  const params = new URLSearchParams()
  params.set('handle', request.handle)
  if (request.offset !== null && request.offset !== undefined) params.set('offset', String(request.offset))
  if (request.limit !== null && request.limit !== undefined) params.set('limit', String(request.limit))
  if (request.expectedDigest) params.set('expectedDigest', request.expectedDigest)
  return params.toString()
}

export type SliceReader = (request: EvidenceSliceRequest) => Promise<EvidenceSliceOutcome>

/** `endpoint` comes from api.ts's validated descriptor (loopback, no credentials, the sidecar's own
 *  path). It is passed in rather than re-derived here so this module stays free of URL-trust logic. */
export function makeHttpSliceReader(endpoint: string, authoritative: boolean, timeoutMs = 8000): SliceReader {
  return async (request) => {
    const url = `${endpoint}?${evidenceQuery(request)}`
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(url, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
        headers: { Origin: url.replace(/https?:\/\/([^/]+)/, 'http://$1') },
      })
      let body: unknown = null
      let parseFailed: string | null = null
      try {
        body = await response.json()
      } catch {
        parseFailed = '响应体不是 JSON'
      }
      if (parseFailed === null) {
        const parsed = parseEvidenceRangePayload(body)
        if (parsed.ok) {
          return { kind: 'RESULT', result: parsed.result, httpStatus: response.status, endpoint, authoritative }
        }
        return { kind: 'BAD_PAYLOAD', why: parsed.why, httpStatus: response.status, endpoint, authoritative }
      }
      return {
        kind: 'UNREACHABLE',
        httpStatus: response.status,
        detail: response.status >= 400 ? `端点返回 ${response.status} 且无可解析判定体` : parseFailed,
        endpoint,
        authoritative,
      }
    } catch (error) {
      return {
        kind: 'UNREACHABLE',
        httpStatus: null,
        detail: (error as Error)?.name === 'AbortError'
          ? `读取在 ${timeoutMs}ms 内未送达`
          : `传输失败：${(error as Error)?.message || '原因未知'}`,
        endpoint,
        authoritative,
      }
    } finally {
      clearTimeout(timer)
    }
  }
}

// ---------------------------------------------------------------------------
// Verdict helpers — one place that decides what a result means, so the columns agree.
// ---------------------------------------------------------------------------

export type DigestVerdictKind = 'AGREE' | 'MISMATCH' | 'UNDETERMINED' | 'NOT_REQUESTED'

export interface DigestVerdict {
  kind: DigestVerdictKind
  detail: string
}

/** Whether the reader's own measurement matches the digest the caller pinned.
 *
 *  ERR-284: this function used to read `identity.wholeDigest` twice — once as the "recorded" value and once
 *  as the "expected" one — so the two were equal by construction and every successful read came back AGREE
 *  under the words "返回字节属于被记录的那份产物". The two sides now come from different fields with
 *  different provenance: `expectedDigest` is the caller's claim, `wholeDigest` is what the reader hashed off
 *  the file. AGREE needs both, and needs the reader to have actually measured.
 */
export function digestVerdictOf(result: EvidenceRangeResult): DigestVerdict {
  const pinned = str(result.identity?.expectedDigest ?? null)
  const measured = str(result.identity?.wholeDigest ?? null)
  const source = str(result.identity?.digestSource ?? 'UNKNOWN')
  if (result.reason_code === 'DIGEST_MISMATCH') {
    return { kind: 'MISMATCH', detail: '读取器实测的整文件摘要与地址里钉住的摘要不一致，因此后端没有返回字节' }
  }
  if (result.reason_code === 'DIGEST_SHAPE') {
    return { kind: 'UNDETERMINED', detail: '钉住的摘要本身不合格（64 位十六进制），一致性无从判定' }
  }
  if (result.reason_code === 'IDENTITY_TOO_LARGE_TO_MEASURE') {
    return { kind: 'UNDETERMINED', detail: `文件超过实测上限，读取器没有核验身份（digestSource=${source}）` }
  }
  if (result.status !== 'OK') {
    return { kind: 'UNDETERMINED', detail: `读取停在 ${result.reason_code}，未进入摘要核对` }
  }
  if (!pinned) return { kind: 'NOT_REQUESTED', detail: `地址未钉住摘要（digestSource=${source}），身份未核验` }
  if (!measured) return { kind: 'UNDETERMINED', detail: `读取未实测整文件摘要（digestSource=${source}），身份未核验` }
  if (measured === pinned) return { kind: 'AGREE', detail: '读取器实测摘要与钉住的摘要一致' }
  return { kind: 'MISMATCH', detail: '返回体里实测摘要与钉住的摘要不一致' }
}

/** The projected artifact shelf. `sources` is a real v3 field (`workspace.sources`, produced by
 *  packages/client-neutral-core/scripts/workspace_evidence.py); ABSENT is not EMPTY. */
export interface ProjectedEvidenceSource {
  path: string | null
  evidenceKind: string | null
  loadedAt: string | null
  generatedAt: string | null
}

export type EvidenceShelf =
  | { kind: 'no-snapshot' }
  | { kind: 'not-provided' }
  | { kind: 'sources'; items: ProjectedEvidenceSource[] }

export function readEvidenceShelf(snap: SnapshotV3 | null): EvidenceShelf {
  if (!snap) return { kind: 'no-snapshot' }
  const raw = (snap.workspace as Record<string, unknown> | undefined)?.sources
  if (raw === undefined || !Array.isArray(raw)) return { kind: 'not-provided' }
  return {
    kind: 'sources',
    items: raw.map((entry) => {
      const item = isRecord(entry) ? entry : {}
      return {
        path: str(item.path),
        evidenceKind: str(item.evidenceKind),
        loadedAt: str(item.loadedAt),
        generatedAt: str(item.generatedAt),
      }
    }),
  }
}

/** Byte counts are never printed as a bare 0 when the source is missing: `null` stays UNKNOWN. */
export function fmtBytes(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return 'UNKNOWN'
  return `${value.toLocaleString('en-US')} B`
}
