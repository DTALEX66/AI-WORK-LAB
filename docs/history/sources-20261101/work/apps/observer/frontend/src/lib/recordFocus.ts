// P1-02 · record focus inside the existing ?view= lane contract.
//
// The deep-link mechanism stays exactly one: a lane is chosen by `?view=`. A record inside that lane is
// addressed by `?taskId=` / `?executionId=`. Adding a second router would have been the easy version of
// this and would have split "what am I looking at" across two systems, so this module only reads and
// writes query parameters.
//
// Two rules that make the link honest rather than decorative:
//
// * an unparseable or over-long identifier is REJECTED at the edge (never interpolated into a lookup),
//   and reported as its own state;
// * a wanted id that the projection does not contain renders as 记录不存在 — the code never falls back
//   to "the first record", because showing a different task than the one that was asked for is worse
//   than showing nothing.
export interface RecordFocus {
  taskId: string | null
  executionId: string | null
  /**
   * WUI-02: the project this surface is addressed to. Optional rather than required because the record
   * addresses that already exist (a task, an execution) are complete without it — and a lane that never
   * spoke about a project must not start asserting `projectId: null`, which would read as "no project"
   * where the truth is "this lane does not address one".
   */
  projectId?: string | null
}

export const EMPTY_FOCUS: RecordFocus = { taskId: null, executionId: null, projectId: null }

/** Ledger ids in this repository are short and ASCII; a longer or control-character-laden value is an
 *  attack surface or a paste accident, not a record. */
const MAX_ID_LENGTH = 200
const LEGAL_ID = /^[A-Za-z0-9][A-Za-z0-9._:/@+#=-]*$/

export type IdVerdict =
  | { kind: 'absent' }
  | { kind: 'ok'; value: string }
  | { kind: 'rejected'; reason: string; raw: string }

export function validateRecordId(raw: string | null): IdVerdict {
  if (raw === null) return { kind: 'absent' }
  const trimmed = raw.trim()
  if (trimmed === '') return { kind: 'absent' }
  if (trimmed.length > MAX_ID_LENGTH) {
    return { kind: 'rejected', reason: `定位标识超过 ${MAX_ID_LENGTH} 个字符，已拒绝`, raw: trimmed }
  }
  if (!LEGAL_ID.test(trimmed)) {
    return { kind: 'rejected', reason: '定位标识包含非法字符，已拒绝', raw: trimmed }
  }
  return { kind: 'ok', value: trimmed }
}

function param(search: string, name: string): IdVerdict {
  try {
    return validateRecordId(new URLSearchParams(search).get(name))
  } catch {
    return { kind: 'absent' }
  }
}

/** Read the focus from a search string. Rejected ids come back as `rejected` so the caller can say so. */
export function readRecordFocus(search: string): { focus: RecordFocus; rejected: string[] } {
  const task = param(search, 'taskId')
  const execution = param(search, 'executionId')
  const project = param(search, 'projectId')
  const rejected: string[] = []
  const focus: RecordFocus = { taskId: null, executionId: null, projectId: null }
  if (task.kind === 'ok') focus.taskId = task.value
  else if (task.kind === 'rejected') rejected.push(`taskId · ${task.reason}`)
  if (execution.kind === 'ok') focus.executionId = execution.value
  else if (execution.kind === 'rejected') rejected.push(`executionId · ${execution.reason}`)
  if (project.kind === 'ok') focus.projectId = project.value
  else if (project.kind === 'rejected') rejected.push(`projectId · ${project.reason}`)
  return { focus, rejected }
}

/** Write the focus back, with the browser doing the encoding (a space or a slash in an id must survive a
 *  copy-paste round trip rather than silently becoming a different id). */
export function writeRecordFocus(params: URLSearchParams, focus: RecordFocus): void {
  if (focus.taskId) params.set('taskId', focus.taskId)
  if (focus.executionId) params.set('executionId', focus.executionId)
  if (focus.projectId) params.set('projectId', focus.projectId)
}

export type FocusState<T> =
  | { kind: 'unasked' }
  | { kind: 'backend-not-provided' }
  | { kind: 'matched'; record: T }
  | { kind: 'not-found'; wanted: string }

/** Resolve one wanted id against records the backend actually carries.
 *  `records === undefined` is not an empty list: it means the producer never queried. */
export function resolveFocus<T>(
  wanted: string | null,
  records: T[] | undefined,
  idOf: (record: T) => string | null,
): FocusState<T> {
  if (!wanted) return { kind: 'unasked' }
  if (records === undefined) return { kind: 'backend-not-provided' }
  const found = records.find((record) => idOf(record) === wanted)
  return found ? { kind: 'matched', record: found } : { kind: 'not-found', wanted }
}

/** The shareable address for one record inside one lane. Same mechanism as the URL writer uses, so a
 *  copied link and a refresh cannot disagree. */
export function recordLink(laneId: string, focus: RecordFocus, search: string): string {
  const params = new URLSearchParams()
  if (laneId) params.set('view', laneId)
  const theme = new URLSearchParams(search).get('theme')
  const layout = new URLSearchParams(search).get('layout')
  const api = new URLSearchParams(search).get('api')
  const shell = new URLSearchParams(search).get('shell')
  if (theme) params.set('theme', theme)
  if (layout) params.set('layout', layout)
  if (api) params.set('api', api)
  if (shell) params.set('shell', shell)
  writeRecordFocus(params, focus)
  const qs = params.toString()
  return `${window.location.pathname}${qs ? '?' + qs : ''}`
}
