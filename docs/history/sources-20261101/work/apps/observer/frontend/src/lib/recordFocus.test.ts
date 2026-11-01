// Unit tests for the record-focus contract (P1-02).
//
// These are the parts a rendering test cannot prove: what the URL means before any component exists.
// Encoding, rejection, and the difference between "absent" and "empty" are decided here, once.
import { describe, it, expect } from 'vitest'
import {
  EMPTY_FOCUS, readRecordFocus, resolveFocus, validateRecordId, writeRecordFocus, recordLink,
} from '@/lib/recordFocus'

describe('validateRecordId', () => {
  it('treats missing and blank as absent rather than as a lookup of the empty string', () => {
    expect(validateRecordId(null)).toEqual({ kind: 'absent' })
    expect(validateRecordId('')).toEqual({ kind: 'absent' })
    expect(validateRecordId('   ')).toEqual({ kind: 'absent' })
  })

  it('accepts the identifier shapes the ledger actually uses', () => {
    for (const id of ['WL-777', 'task:12', 'run/a/b', 'sess_9.2', 'user+tag=1', '39f2ab@']) {
      expect(validateRecordId(id)).toEqual({ kind: 'ok', value: id })
    }
  })

  it('refuses an over-long value and anything with control characters or quotes', () => {
    const long = 'x'.repeat(201)
    expect(validateRecordId(long).kind).toBe('rejected')
    for (const bad of ['a"b', "a'b", 'a`b', 'a<b>', 'x\ny', '<script>', 'a b', 'tab\there']) {
      expect(validateRecordId(bad).kind, bad).toBe('rejected')
    }
  })

  it('a scheme-looking id stays inert because a link is always built as a same-path query', () => {
    // ':' is legal — native session-style identifiers use it. What makes the link safe is that the shell
    // never puts a raw value in front of the href; the value only ever lands after `?view=work&taskId=`.
    const hostile = 'javascript:alert'
    expect(validateRecordId(hostile)).toEqual({ kind: 'ok', value: hostile })
    const params = new URLSearchParams()
    writeRecordFocus(params, { taskId: hostile, executionId: null })
    expect(params.toString()).toBe('taskId=javascript%3Aalert')
    expect(recordLink('work', { taskId: hostile, executionId: null }, '')).toMatch(/^\/\?view=work&taskId=javascript%3Aalert$/)
  })

  it('trims instead of interpolating the raw value into a lookup', () => {
    expect(validateRecordId('  WL-777  ')).toEqual({ kind: 'ok', value: 'WL-777' })
  })
})

describe('readRecordFocus / writeRecordFocus', () => {
  it('reads the record ids and keeps rejection reasons beside the usable focus', () => {
    const parsed = readRecordFocus('?view=work&taskId=WL-1&executionId=ex-9&note=%22private%20text%22')
    expect(parsed.focus).toEqual({ taskId: 'WL-1', executionId: 'ex-9', projectId: null })
    expect(parsed.rejected).toEqual([])
  })

  // WUI-02: 项目详情 is addressed by projectId on this SAME mechanism, not by a second router. The rules
  // that make a task link honest apply unchanged: validated at the edge, refused loudly, round-tripped.
  it('the project address rides the same one mechanism, with the same refusals', () => {
    const parsed = readRecordFocus('?view=project-detail&projectId=WORK-LAB')
    expect(parsed.focus.projectId).toBe('WORK-LAB')
    expect(parsed.rejected).toEqual([])

    const refused = readRecordFocus('?view=project-detail&projectId=' + encodeURIComponent('D:\\all projects'))
    expect(refused.focus.projectId).toBeNull()
    expect(refused.rejected).toEqual(['projectId · 定位标识包含非法字符，已拒绝'])

    const params = new URLSearchParams()
    writeRecordFocus(params, { taskId: null, executionId: null, projectId: 'repo:origin/main' })
    expect(params.toString()).toBe('projectId=repo%3Aorigin%2Fmain')
    expect(readRecordFocus('?' + params.toString()).focus.projectId).toBe('repo:origin/main')
  })

  it('a value that is not an identifier is refused, and the refusal is named', () => {
    const parsed = readRecordFocus('?view=work&taskId=' + encodeURIComponent('WL 777') + '&executionId=' + encodeURIComponent('ex\t9'))
    expect(parsed.focus).toEqual({ taskId: null, executionId: null, projectId: null })
    expect(parsed.rejected).toEqual([
      'taskId · 定位标识包含非法字符，已拒绝',
      'executionId · 定位标识包含非法字符，已拒绝',
    ])
  })

  it('a rejected id never becomes a focus value', () => {
    const parsed = readRecordFocus('?view=work&taskId=' + encodeURIComponent('a"b'))
    expect(parsed.focus.taskId).toBeNull()
    expect(parsed.rejected).toHaveLength(1)
    expect(parsed.rejected[0]).toContain('taskId')
  })

  it('round-trips an id that contains a slash and a dot', () => {
    const params = new URLSearchParams()
    writeRecordFocus(params, { taskId: 'WL.777/x', executionId: null })
    expect(params.toString()).toBe('taskId=WL.777%2Fx')
    expect(readRecordFocus('?' + params.toString()).focus.taskId).toBe('WL.777/x')
  })

  it('writes nothing when there is no focus, so a plain lane link stays plain', () => {
    const params = new URLSearchParams()
    writeRecordFocus(params, EMPTY_FOCUS)
    expect(params.toString()).toBe('')
  })
})

describe('resolveFocus', () => {
  const records = [{ taskId: 'A' }, { taskId: 'B' }]
  const idOf = (record: { taskId: string }) => record.taskId

  it('does not look anything up when no record was asked for', () => {
    expect(resolveFocus(null, records, idOf)).toEqual({ kind: 'unasked' })
  })

  it('keeps 后端未提供 apart from 无记录', () => {
    expect(resolveFocus('A', undefined, idOf)).toEqual({ kind: 'backend-not-provided' })
    expect(resolveFocus('A', [], idOf).kind).toBe('not-found')
  })

  it('matches the requested record and reports the wanted id when it is missing', () => {
    expect(resolveFocus('B', records, idOf)).toEqual({ kind: 'matched', record: { taskId: 'B' } })
    expect(resolveFocus('Z', records, idOf)).toEqual({ kind: 'not-found', wanted: 'Z' })
  })
})

describe('recordLink', () => {
  it('builds one query string that carries the lane, the record and the runtime params', () => {
    const href = recordLink('work', { taskId: 'WL-1', executionId: null },
      '?theme=light&layout=compact&api=http%3A%2F%2F127.0.0.1%3A1&shell=tauri')
    expect(href).toContain('?view=work')
    expect(href).toContain('taskId=WL-1')
    expect(href).toContain('theme=light')
    expect(href).toContain('layout=compact')
    expect(href).toContain('api=http')
    expect(href).toContain('shell=tauri')
  })

  it('drops a cleared focus from the address instead of leaving a stale record behind', () => {
    const href = recordLink('work', EMPTY_FOCUS, '?taskId=WL-1&executionId=ex-1')
    expect(href).not.toContain('taskId')
    expect(href).not.toContain('executionId')
  })
})
