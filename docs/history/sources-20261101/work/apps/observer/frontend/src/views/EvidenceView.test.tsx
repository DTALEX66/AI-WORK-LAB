/** REQ-RANGE-20261007 · the evidence slice lane, mounted.
 *
 * Fixtures are the wire shape `packages/client-neutral-core/scripts/evidence_range_reader.py` actually
 * returns (`schema_version` / `reason_code` snake_case, the rest camelCase) — not a tidied model, because a
 * tidied model is how a verdict field gets dropped silently.
 *
 * What jsdom CAN measure here: the number of column regions, the text each one renders, whether a content
 * block exists at all, and whether a cell padded a missing number into 0. What it cannot measure: pixel
 * geometry (every rect is 0x0 with no layout engine), so no assertion below claims a width or an x-offset —
 * the stylesheet claim about `minmax(0, …)` tracks the source text instead, and is labelled as such.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { readFileSync } from 'node:fs'

import { EvidenceView } from '@/views/EvidenceView'
import {
  parseEvidenceRangePayload, makeHttpSliceReader, evidenceQuery, readEvidenceAddress,
  type EvidenceRangeResult, type SliceReader,
} from '@/lib/evidenceRange'
import { mkSnap } from '@/test/snapshotFixture'
import type { SnapshotV3 } from '@/types'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const WHOLE = 'a1b2c3d4'.repeat(8)
const SLICE = '11223344'.repeat(8)
const HANDLE = 'D:/All projects/WORK-LAB/.project-local/runs/qoder-agent-ui/evidence.log'

/** Exactly what `read_range()` returns on a successful interval. */
function readOk(over: Partial<EvidenceRangeResult> = {}): EvidenceRangeResult {
  return {
    schema_version: 'worklab/evidence-range-result/v1',
    status: 'OK',
    reason_code: 'READ_OK',
    reason: '按精确区间读取。',
    handle: HANDLE,
    offset: 4096,
    limit: 8192,
    bytesRequested: 6144,
    endOffset: 10240,
    eofReached: false,
    content: 'first slice line\nsecond slice line',
    sliceDigest: SLICE,
    identity: { expectedDigest: WHOLE, wholeDigest: WHOLE, sizeBytes: 8388614,
      digestSource: 'measured-by-reader', verified: true },
    cost: { bytesRead: 6144, fileSize: 8388614, wholeFileWasRead: false },
    ...over,
  }
}

/** The refusal envelope: no offset, no slice digest, content null, cost padded to 0 by the backend. */
function refused(code: string, reason: string, over: Partial<EvidenceRangeResult> = {}): EvidenceRangeResult {
  return {
    schema_version: 'worklab/evidence-range-result/v1',
    status: 'REFUSED',
    reason_code: code,
    reason,
    handle: HANDLE,
    content: null,
    cost: { bytesRead: 0, fileSize: null, wholeFileWasRead: false },
    ...over,
  }
}

const REFUSALS: Array<[string, string]> = [
  ['OUT_OF_EVIDENCE_SURFACE', 'handle 不在声明的证据目录内：项目内部本身就是敏感的，边界不等于许可。'],
  ['SENSITIVE_NAME', 'handle 指向凭证、配置、会话库或密钥类文件，读取投影在任何边界内都不提供这类内容。'],
  ['DIGEST_MISMATCH', '期望摘要与读取器实测的整文件摘要不符：返回的字节不属于被记录的那份产物，因此不返回内容。'],
]

const ADDRESS = `?view=evidence&artifact=${encodeURIComponent(HANDLE)}&offset=4096&limit=8192`
  + `&expectedDigest=${WHOLE}`

function snapWithShelf(): SnapshotV3 {
  return mkSnap({
    workspace: {
      sources: [
        { path: 'taskpacks/history/pre-convergence-20261019/WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md', evidenceKind: 'PLAN', loadedAt: '2026-10-08T01:00:00Z' },
        { path: '.project/governance/generated/CURRENT_STATE.json', evidenceKind: 'STATIC_BASELINE', loadedAt: '2026-10-08T01:00:00Z', generatedAt: '2026-10-07T22:00:00Z' },
      ],
    },
  })
}

function readerReturning(result: EvidenceRangeResult): SliceReader {
  return async () => ({ kind: 'RESULT', result, httpStatus: 200, endpoint: 'http://127.0.0.1:61867/api/v1/evidence-range', authoritative: true })
}

async function renderWithResult(result: EvidenceRangeResult, search = ADDRESS, snap = snapWithShelf()) {
  const calls: Array<Record<string, unknown>> = []
  const reader: SliceReader = async (request) => {
    calls.push({ ...request })
    return { kind: 'RESULT', result, httpStatus: 200, endpoint: 'http://127.0.0.1:61867/api/v1/evidence-range', authoritative: true }
  }
  const view = render(<EvidenceView snap={snap} search={search} readSlice={reader} />)
  await waitFor(() => expect(view.container.querySelector('[data-testid="evidence-columns"]')?.getAttribute('data-state')).toBe(result.status))
  return { ...view, calls }
}

function columnsOf(container: HTMLElement): HTMLElement {
  const grid = container.querySelector('[data-testid="evidence-columns"]') as HTMLElement
  expect(grid, 'the three-column region must exist').not.toBeNull()
  return grid
}

function fieldOf(container: HTMLElement, field: string): HTMLElement | null {
  return columnsOf(container).querySelector(`[data-field="${field}"]`) as HTMLElement | null
}

describe('REQ-RANGE · three columns from a realistic READ_OK', () => {
  it('renders exactly three column regions and each one carries its own answer', async () => {
    const { container } = await renderWithResult(readOk())
    const grid = columnsOf(container)
    const regions = Array.from(grid.children) as HTMLElement[]
    expect(regions).toHaveLength(3)
    // reading order is part of the contract: identity, then what was sliced, then the verdict
    expect(regions.map((region) => region.getAttribute('data-column'))).toEqual(['identity', 'slice', 'verdict'])
    expect(regions[0].textContent).toContain('身份')
    expect(regions[1].textContent).toContain('切片')
    expect(regions[2].textContent).toContain('判定')
    // a column that rendered nothing would still be a node; the claim is about its visible text
    for (const [index, region] of regions.entries()) {
      const text = (region.textContent || '').trim()
      expect(text.length, `column ${index} renders an empty pane`).toBeGreaterThan(24)
    }
  })

  it('identity column shows the handle, the pinned and measured digests apart, and the measured size', async () => {
    const { container } = await renderWithResult(readOk())
    expect(fieldOf(container, 'handle')!.textContent).toContain(HANDLE)
    // the full digest is on screen, not a prefix with no way to check the rest
    expect(fieldOf(container, 'pinnedDigest')!.textContent).toContain(WHOLE)
    expect(fieldOf(container, 'measuredDigest')!.textContent).toContain(WHOLE)
    expect(fieldOf(container, 'size')!.textContent).toContain('8,388,614 B')
    expect(fieldOf(container, 'digestSource')!.textContent).toContain('measured-by-reader')
  })

  it('ERR-284: a body carrying one digest cannot be read as agreement', async () => {
    // The shape the reader used to return: `wholeDigest` echoed back whatever the caller sent, and the
    // verdict helper compared that field with itself. One value on the wire is not two agreeing values.
    const bare = `?view=evidence&artifact=${encodeURIComponent(HANDLE)}&offset=4096&limit=8192`
    const { container } = await renderWithResult(readOk({
      identity: { wholeDigest: WHOLE, sizeBytes: 8388614, digestSource: 'not-requested' },
    }), bare)
    const digest = container.querySelector('[data-testid="evidence-digest-verdict"]') as HTMLElement
    expect(digest.textContent).toContain('未请求')
    expect(digest.textContent).not.toContain('AGREE')
    expect(fieldOf(container, 'measuredDigest')!.textContent).toContain(WHOLE)
    expect(fieldOf(container, 'pinnedDigest')!.textContent).toContain('未提供')
  })

  it('a measured digest that differs from the pinned one is a MISMATCH even on an OK body', async () => {
    const other = 'b'.repeat(64)
    const { container } = await renderWithResult(readOk({
      identity: { expectedDigest: other, wholeDigest: WHOLE, sizeBytes: 8388614,
        digestSource: 'measured-by-reader', verified: false },
    }))
    const digest = container.querySelector('[data-testid="evidence-digest-verdict"]') as HTMLElement
    expect(digest.textContent).toContain('MISMATCH')
    expect(digest.textContent).not.toContain('AGREE')
  })

  it('slice column shows the interval the read actually returned', async () => {
    const { container } = await renderWithResult(readOk())
    expect(fieldOf(container, 'offset')!.textContent).toContain('4096')
    expect(fieldOf(container, 'limit')!.textContent).toContain('8192')
    expect(fieldOf(container, 'bytesRequested')!.textContent).toContain('6144')
    expect(fieldOf(container, 'endOffset')!.textContent).toContain('10240')
    expect(fieldOf(container, 'eofReached')!.textContent).toContain('否（仍有后续字节）')
    expect(fieldOf(container, 'sliceDigest')!.textContent).toContain(SLICE)
    expect(fieldOf(container, 'bytesRead')!.textContent).toContain('6,144 B')
    expect(fieldOf(container, 'wholeRead')!.textContent).toContain('否（只读了这一段）')
  })

  it('an eof at the end of the file is shown as 是, not left at the default', async () => {
    const { container } = await renderWithResult(readOk({ eofReached: true }))
    expect(fieldOf(container, 'eofReached')!.textContent).toContain('是（已到文件尾）')
  })

  it('verdict column states the body verdict, the backend reason and the digest agreement', async () => {
    const { container } = await renderWithResult(readOk())
    const grid = columnsOf(container)
    expect(grid.textContent).toContain('OK · READ_OK')
    expect(grid.textContent).toContain('按精确区间读取。')
    expect(grid.textContent).toContain('传输层 HTTP 200 —— 判定取自响应体，不取自状态码')
    const digest = grid.querySelector('[data-testid="evidence-digest-verdict"]') as HTMLElement
    expect(digest.textContent).toContain('一致')
    expect(digest.textContent).toContain('AGREE')
  })

  it('the returned bytes are previewed with their interval, and the preview declares its own truncation', async () => {
    const long = readOk({ content: 'x'.repeat(1400) })
    const { container } = await renderWithResult(long)
    const block = container.querySelector('[data-testid="evidence-content"]') as HTMLElement
    expect(block.textContent).toContain('[4096, 10240)')
    expect(block.textContent).toContain('xxxxx')
    expect(block.textContent).toContain('预览截断')
    // the preview is a preview: it may not silently pass itself off as the whole slice
    expect((block.querySelector('pre')?.textContent || '').length).toBeLessThan(1400)
  })
})

describe('REQ-RANGE · a refusal is rendered as a refusal', () => {
  it.each(REFUSALS)('%s shows the backend reason and returns no content pane', async (code, reason) => {
    const result = code === 'DIGEST_MISMATCH'
      ? refused(code, reason, { cost: { bytesRead: 0, fileSize: 8388614, wholeFileWasRead: false }, identity: { wholeDigest: WHOLE, sizeBytes: 8388614 } })
      : refused(code, reason)
    const { container } = await renderWithResult(result)
    const grid = columnsOf(container)
    expect(grid.getAttribute('data-state')).toBe('REFUSED')
    expect(grid.getAttribute('data-reason')).toBe(code)
    expect(grid.textContent).toContain(code)
    expect(grid.textContent).toContain(reason)
    // no content block, and no blank standing in for one
    expect(container.querySelector('[data-testid="evidence-content"]')).toBeNull()
    expect(grid.querySelector('[data-testid="evidence-no-content"]')!.textContent).toContain('没有返回字节')
    // a refusal is never a success pill
    expect(grid.querySelectorAll('.tag.ok')).toHaveLength(0)
  })

  it('every slice field the refusal never reached says 未提供, not 0 and not false', async () => {
    const { container } = await renderWithResult(refused(REFUSALS[0][0], REFUSALS[0][1]))
    for (const field of ['offset', 'endOffset', 'eofReached', 'sliceDigest', 'bytesRead', 'wholeRead', 'size']) {
      const cell = fieldOf(container, field)!
      expect(cell.textContent, `${field} padded a value`).toContain('未提供')
      expect(cell.textContent).not.toMatch(/(^|\D)0(\D|$|\s)/)
      expect(cell.textContent).not.toMatch(/\bfalse\b|\bnull\b/)
    }
  })

  it('DIGEST_MISMATCH is answered as a mismatch and the real sizes still show', async () => {
    const { container } = await renderWithResult(refused('DIGEST_MISMATCH', REFUSALS[2][1], {
      cost: { bytesRead: 0, fileSize: 8388614, wholeFileWasRead: false },
      identity: { wholeDigest: WHOLE, sizeBytes: 8388614 },
    }))
    const digest = container.querySelector('[data-testid="evidence-digest-verdict"]') as HTMLElement
    expect(digest.textContent).toContain('不一致')
    expect(digest.textContent).toContain('MISMATCH')
    expect(fieldOf(container, 'size')!.textContent).toContain('8,388,614 B')
    expect(container.querySelector('[data-testid="evidence-content"]')).toBeNull()
  })

  it('a read that never arrived is 无判定, not a refusal with an invented code', async () => {
    const snap = snapWithShelf()
    const view = render(
      <EvidenceView
        snap={snap}
        search={ADDRESS}
        readSlice={async () => ({
          kind: 'UNREACHABLE', httpStatus: null, detail: '传输失败：Failed to fetch',
          endpoint: 'http://127.0.0.1:61867/api/v1/evidence-range', authoritative: true,
        })}
      />,
    )
    await waitFor(() => expect(columnsOf(view.container).getAttribute('data-state')).toBe('unreachable'))
    const grid = columnsOf(view.container)
    expect(grid.textContent).toContain('无判定（读取未送达）')
    expect(grid.textContent).toContain('传输失败：Failed to fetch')
    expect(grid.textContent).not.toContain('REFUSED')
    expect(grid.textContent).not.toMatch(/bytesRead|\s0 B/)
    expect(view.container.querySelector('[data-testid="evidence-content"]')).toBeNull()
    expect(grid.querySelectorAll('.tag.ok')).toHaveLength(0)
  })

  it('an unaddressed read shows three columns of stated absence, never a zeroed table', async () => {
    const { container } = render(<EvidenceView snap={snapWithShelf()} search="?view=evidence" readSlice={async () => { throw new Error('must not read') }} />)
    const grid = columnsOf(container)
    expect(grid.getAttribute('data-state')).toBe('unaddressed')
    expect(Array.from(grid.children)).toHaveLength(3)
    expect(grid.textContent).toContain('没有把手就没有对象')
    expect(grid.textContent).toContain('未提供')
    expect(grid.textContent).not.toMatch(/(^|\D)0(\D|$)/)
    expect(container.querySelectorAll('.tag.ok')).toHaveLength(0)
  })
})

describe('REQ-RANGE · shelf honesty and addressing', () => {
  it('no snapshot: the shelf names the missing source instead of an empty list', () => {
    const { container } = render(<EvidenceView snap={null} search="?view=evidence" readSlice={async () => { throw new Error('must not read') }} />)
    const text = container.textContent || ''
    expect(text).toContain('数据源未接入')
    expect(text).not.toContain('无来源')
    expect(text.trim()).not.toMatch(/^0+$/)
  })

  it('a snapshot without workspace.sources is 来源缺口, and an empty list is a queried answer', () => {
    const missing = render(<EvidenceView snap={mkSnap({ workspace: {} })} search="?view=evidence" readSlice={async () => { throw new Error('x') }} />)
    expect(missing.container.textContent).toContain('没有 workspace.sources 字段')
    missing.unmount()
    const empty = render(<EvidenceView snap={mkSnap({ workspace: { sources: [] } })} search="?view=evidence" readSlice={async () => { throw new Error('x') }} />)
    expect(empty.container.textContent).toContain('空列表是查询结果，不是缺源')
    expect(empty.container.textContent).not.toContain('没有 workspace.sources 字段')
  })

  it('the projected handle is offered as a same-path query link and drives the read when followed', async () => {
    const seen: Array<Record<string, unknown>> = []
    const reader: SliceReader = async (request) => {
      seen.push({ ...request })
      return { kind: 'RESULT', result: refused('ABSOLUTE_PATH_REQUIRED', 'handle 必须是绝对路径；相对路径会随调用者的工作目录改变所指文件。'), httpStatus: 200, endpoint: 'e', authoritative: true }
    }
    const { container } = render(<EvidenceView snap={snapWithShelf()} search="?view=evidence" readSlice={reader} />)
    const link = Array.from(container.querySelectorAll('a'))
      .find((a) => (a.getAttribute('href') || '').includes('artifact='))
    expect(link, 'each projected source must carry its own address').toBeTruthy()
    const href = link!.getAttribute('href') || ''
    expect(/^\/\?view=evidence(&|$)/.test(href), `link escaped the lane contract: ${href}`).toBe(true)
    fireEvent.click(link!)
    await waitFor(() => expect(columnsOf(container).getAttribute('data-state')).toBe('REFUSED'))
    expect(seen[0].handle).toBe('taskpacks/history/pre-convergence-20261019/WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md')
    // the refusal is what the owner sees: no content, and the backend's own reason
    expect(container.querySelector('[data-testid="evidence-content"]')).toBeNull()
    expect(columnsOf(container).textContent).toContain('ABSOLUTE_PATH_REQUIRED')
    expect(columnsOf(container).textContent).toContain('相对路径')
  })

  it('an illegal handle in the address is reported and never sent to the endpoint', async () => {
    let called = 0
    const reader: SliceReader = async () => { called += 1; throw new Error('unreachable') }
    const { container } = render(
      <EvidenceView snap={snapWithShelf()} search={'?view=evidence&artifact=' + encodeURIComponent('a\u0001b')} readSlice={reader} />,
    )
    expect(container.textContent).toContain('区间地址被拒绝')
    expect(container.textContent).toContain('控制字符')
    expect(called).toBe(0)
    const grid = columnsOf(container)
    expect(grid.getAttribute('data-state')).toBe('rejected')
    expect(grid.textContent).toContain('无判定：地址在校验处就被拒绝')
    expect(grid.textContent).toContain('未提供')
    expect(grid.querySelectorAll('.tag.ok')).toHaveLength(0)
  })

  it('the read is addressed only by the parameters the URL actually carried', () => {
    const parsed = readEvidenceAddress('?view=evidence&artifact=' + encodeURIComponent(HANDLE))
    expect(parsed.kind).toBe('addressed')
    if (parsed.kind === 'addressed') {
      expect(parsed.address.handle).toBe(HANDLE)
      // unset stays null: it is the backend's default, not a 0 this side invented
      expect(parsed.address.offset).toBeNull()
      expect(parsed.address.limit).toBeNull()
      expect(parsed.address.expectedDigest).toBeNull()
    }
    expect(evidenceQuery({ handle: HANDLE }).includes('offset')).toBe(false)
    expect(evidenceQuery({ handle: HANDLE, offset: 4096, limit: 8192 })).toContain('offset=4096')
    const bad = readEvidenceAddress('?artifact=' + encodeURIComponent(HANDLE) + '&offset=abc')
    expect(bad.kind).toBe('rejected')
  })

  it('a focused record does not silently become an artifact list', () => {
    const { container } = render(
      <EvidenceView
        snap={snapWithShelf()}
        focus={{ taskId: 'WL-900', executionId: null }}
        search="?view=evidence"
        readSlice={async () => { throw new Error('must not read') }}
      />,
    )
    const note = container.querySelector('[data-testid="evidence-record-binding"]') as HTMLElement
    expect(note.textContent).toContain('WL-900')
    expect(note.textContent).toContain('record↔artifact 外键')
    // the addressed read is still unaddressed: the record focus did not buy a handle
    expect(columnsOf(container).getAttribute('data-state')).toBe('unaddressed')
  })

  it('the lane exposes zero write affordances', async () => {
    const { container } = await renderWithResult(readOk())
    expect(container.innerHTML).not.toContain('<button')
    expect(container.innerHTML).not.toContain('<input')
    expect(container.innerHTML).not.toContain('<textarea')
    for (const anchor of Array.from(container.querySelectorAll('a'))) {
      const href = anchor.getAttribute('href') || ''
      expect(href.startsWith('//'), `protocol-relative link: ${href}`).toBe(false)
    }
  })
})

describe('REQ-RANGE · the client keeps the verdict out of the status code', () => {
  it('a 200 that carries REFUSED is a refusal, and a 403 that carries a verdict is still a verdict', async () => {
    const bodies: Array<{ status: number; body: unknown }> = [
      { status: 200, body: refused('OUT_OF_EVIDENCE_SURFACE', REFUSALS[0][1]) },
      { status: 403, body: { schema_version: 'worklab/evidence-range-result/v1', status: 'REFUSED', reason_code: 'PEER_NOT_LOOPBACK', reason: '证据区间只从环回地址提供。', content: null } },
    ]
    for (const { status, body } of bodies) {
      vi.stubGlobal('fetch', vi.fn(async () => ({ ok: status < 400, status, json: async () => body })))
      const reader = makeHttpSliceReader('http://127.0.0.1:61867/api/v1/evidence-range', true)
      const outcome = await reader({ handle: HANDLE })
      expect(outcome.kind).toBe('RESULT')
      if (outcome.kind === 'RESULT') {
        expect(outcome.httpStatus).toBe(status)
        expect(outcome.result.status).toBe('REFUSED')
      }
    }
  })

  it('every request is a GET with no body, no-store, and no method that could mutate', async () => {
    const init: Array<Record<string, unknown>> = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options?: RequestInit) => {
      init.push({ ...(options || {}) })
      return { ok: true, status: 200, json: async () => readOk() }
    }))
    const reader = makeHttpSliceReader('http://127.0.0.1:61867/api/v1/evidence-range', true)
    await reader({ handle: HANDLE, offset: 0, limit: 1024 })
    expect(init).toHaveLength(1)
    expect(init[0].method).toBe('GET')
    expect(init[0].cache).toBe('no-store')
    expect(init[0].body).toBeUndefined()
    expect(init[0].signal).toBeTruthy()
  })

  it('a body that is not a range result is an unreadable contract, never a fabricated verdict', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ status: 'OK' }) })))
    const reader = makeHttpSliceReader('http://127.0.0.1:61867/api/v1/evidence-range', true)
    const outcome = await reader({ handle: HANDLE })
    expect(outcome.kind).toBe('BAD_PAYLOAD')
    if (outcome.kind === 'BAD_PAYLOAD') expect(outcome.why).toContain('schema_version')
  })

  it('the parser refuses a foreign schema and a non-OK that carries content', () => {
    expect(parseEvidenceRangePayload({ ...readOk(), schema_version: 'other/v9' }).ok).toBe(false)
    expect(parseEvidenceRangePayload(refused('NOT_A_FILE', 'x', { content: 'smuggled' } as never)).ok).toBe(false)
    expect(parseEvidenceRangePayload(readOk({ content: null as never })).ok).toBe(false)
    expect(parseEvidenceRangePayload(readOk()).ok).toBe(true)
  })

  it('the evidence endpoint is derived from the descriptor, and an injected ?api= cannot point it off-loopback', async () => {
    window.history.replaceState(null, '', '/?api=' + encodeURIComponent('http://127.0.0.1:61867/api/v1/snapshot'))
    vi.resetModules()
    const trusted = await import('@/lib/api')
    expect(trusted.evidenceRangeEndpoint())
      .toEqual({ url: 'http://127.0.0.1:61867/api/v1/evidence-range', authoritative: true })

    // a hostile injection must not become an evidence read target: the descriptor falls back to the
    // declared local preview source and marks it non-authoritative, which the lane then shows verbatim
    window.history.replaceState(null, '', '/?api=' + encodeURIComponent('https://attacker.example/api/v1/snapshot'))
    vi.resetModules()
    const injected = await import('@/lib/api')
    const derived = injected.evidenceRangeEndpoint()
    expect(derived).not.toBeNull()
    expect(derived!.url.startsWith('http://127.0.0.1:')).toBe(true)
    expect(derived!.authoritative).toBe(false)
    expect(injected.isTrustedEvidenceRangeEndpoint('http://attacker.example/api/v1/evidence-range')).toBe(false)
    expect(injected.isTrustedEvidenceRangeEndpoint('http://127.0.0.1:61867/api/v1/snapshot')).toBe(false)
  })
})

describe('REQ-RANGE · the column track cannot be widened by a digest', () => {
  it('the skin keeps .three-col on minmax(0, …), the rule that stops a 64-hex digest blowing the layout', () => {
    // This is a claim about the stylesheet the lane depends on, not about a rendered pixel: jsdom has no
    // layout engine, so no rect assertion here would prove anything. A bare `1fr` track has a min-content
    // floor, and a 64-character hex digest is exactly the token that used to widen it.
    const shell = readFileSync('src/skins/l10b-shell.css', 'utf8')
    const base = readFileSync('src/skins/b10.css', 'utf8')
    expect(base).toMatch(/\.three-col\s*\{\s*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/)
    expect(shell).toMatch(/\.three-col\s*\{\s*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/)
    // and the narrow-viewport fallbacks keep minmax(0, …) too
    expect(shell).toMatch(/\.three-col\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/)
    expect(shell).toMatch(/\.two-col,\s*\.three-col,\s*\.split\s*\{\s*grid-template-columns:\s*1fr/)
  })

  it('the three column regions are three distinct regions, each non-empty and none of them the others', async () => {
    const { container } = await renderWithResult(readOk())
    const regions = Array.from(columnsOf(container).children)
    const texts = regions.map((r) => (r.textContent || '').trim())
    expect(new Set(texts).size).toBe(3)
    expect(regions.every((r) => (r.textContent || '').trim().length > 0)).toBe(true)
    // the digest lands in the columns that own it, and nowhere else
    expect(texts[0]).toContain(WHOLE)
    expect(texts[1]).toContain(SLICE)
    expect(texts[2]).not.toContain(SLICE)
  })
})
