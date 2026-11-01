/** WUI-15 · the artifact-handle block of the evidence lane, mounted.
 *
 * The live v3 snapshot carries `artifactHandles` + `artifactHandlesSummary` (a cap-bounded window of
 * identity rows plus the scope report that chose them) and until this round NO view rendered either key.
 * These tests are the falsification half of that change: each one fails if the lane pads a missing count,
 * offers a content affordance the payload refuses, re-sorts what the producer ordered, or loses a filter
 * that the address says is set.
 *
 * Numbers are asserted against the fixture values, and one test reads the component's own source to prove
 * those numbers are not typed into it.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup, fireEvent } from '@testing-library/react'
import { readFileSync } from 'node:fs'

import { EvidenceView } from '@/views/EvidenceView'
import type { ArtifactHandle, SnapshotV3 } from '@/types'
import type { SliceReader } from '@/lib/evidenceRange'
import {
  HANDLES_CAP, HANDLES_ENUMERATED, HANDLES_OMITTED, HANDLES_ROWS_WITH_DIGEST,
  HANDLES_SENSITIVE_NAMES_REFUSED, HANDLES_PRUNED_REGENERABLE,
  mkArtifactHandle, mkArtifactHandleRows, mkArtifactHandlesSummary, mkSnap, mkSnapWithArtifactHandles,
} from '@/test/snapshotFixture'

const noRead = async () => { throw new Error('the handle block must never drive a read') }

function renderHandles(snap: SnapshotV3 | null, search = '?view=evidence') {
  return render(<EvidenceView snap={snap} search={search} readSlice={noRead} />)
}

function block(container: HTMLElement): HTMLElement {
  const element = container.querySelector<HTMLElement>('[data-testid="evidence-handles"]')
  expect(element, 'the evidence lane must carry the handle block').not.toBeNull()
  return element!
}

function capacityLine(container: HTMLElement): HTMLElement {
  const element = block(container).querySelector<HTMLElement>('[data-testid="evidence-handles-capacity"]')
  expect(element, 'the capacity facts are what makes a truncated window readable as one').not.toBeNull()
  return element!
}

function fieldCell(container: HTMLElement, field: string): HTMLElement | null {
  return block(container).querySelector<HTMLElement>(`[data-field="${field}"]`)
}

function rows(container: HTMLElement): string[] {
  return Array.from(block(container).querySelectorAll<HTMLElement>('[data-handle-row]'))
    .map((element) => element.getAttribute('data-handle-row') ?? '')
}

function digestCell(row: HTMLElement): HTMLElement {
  const cell = row.querySelector<HTMLElement>('[data-handles-cell="digest"]')
  expect(cell, 'every handle row carries its own digest cell').not.toBeNull()
  return cell!
}

function dropFlag(row: ArtifactHandle): ArtifactHandle {
  const copy: Record<string, unknown> = { ...row }
  delete copy.digestRecorded
  return copy as unknown as ArtifactHandle
}

afterEach(() => {
  cleanup()
})

describe('WUI-15 fixture controls — a vacuous pass is the failure mode this file exists to avoid', () => {
  it('the fixture really carries the measured key shapes', () => {
    const rowsFixture = mkArtifactHandleRows()
    expect(rowsFixture).toHaveLength(HANDLES_CAP)
    expect(rowsFixture.filter((row) => row.digestRecorded === true)).toHaveLength(HANDLES_ROWS_WITH_DIGEST)
    // the two keys the payload emits and the row type does not name, and nothing else
    const first = rowsFixture[0] as unknown as Record<string, unknown>
    expect(Object.keys(first).sort()).toEqual(
      ['digest', 'digestRecorded', 'digestSource', 'handle', 'kind', 'modifiedAt', 'sizeBytes', 'surface', 'surfaceRoot'].sort(),
    )
    // whole-second ISO, no milliseconds — the precision the block has to disclose
    expect(first.modifiedAt).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/)
    const summary = mkArtifactHandlesSummary()
    expect(summary.contentIncluded).toBe(false)
    expect(summary.enumeratedCount).toBe(HANDLES_ENUMERATED)
    expect(summary.omittedCount).toBe(HANDLES_OMITTED)
    expect(summary.refused.sensitiveNames).toBe(HANDLES_SENSITIVE_NAMES_REFUSED)
    expect(summary.refused.prunedRegenerableDirectories).toBe(HANDLES_PRUNED_REGENERABLE)
    // the live producer emits an OBJECT here while types.ts declares a number — the drift is the test case
    expect(typeof summary.refused.droppedOnVerification).toBe('object')
  })
})

describe('WUI-15 · a missing handle field is a gap, not a zero', () => {
  it('snapshot without artifactHandles: the block reads UNKNOWN and prints no count', () => {
    const { container } = renderHandles(mkSnap())
    const text = block(container).textContent ?? ''
    expect(container.querySelector('[data-testid="evidence-handles-unknown"]')).not.toBeNull()
    expect(text).toContain('UNKNOWN')
    expect(text).toContain('没有 artifactHandles 字段')
    // the gap is stated as a gap, and the empty list is never substituted for it
    expect(text).not.toContain('没有把手行')
    expect(capacityLine(container).textContent).toContain('快照下发 UNKNOWN / 枚举 UNKNOWN / 省略 UNKNOWN')
    expect(capacityLine(container).getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(container.querySelector('[data-testid="evidence-handles-summary-gap"]')?.getAttribute('data-origin'))
      .toBe('SOURCE_GAP')
    // the per-field list is not conjured up field by field when the whole report is missing
    expect(fieldCell(container, 'handlesCap')).toBeNull()
    expect(container.querySelector('[data-testid="evidence-handles-summary-gap"]')?.textContent).toContain('cap')
    expect(text).not.toMatch(/快照下发 0/)
  })

  it('an empty array is a queried answer, and says so instead of naming a missing field', () => {
    const { container } = renderHandles(mkSnap({
      artifactHandles: [],
      artifactHandlesSummary: mkArtifactHandlesSummary({ projectedCount: 0, truncated: false, complete: true }),
    }))
    const text = block(container).textContent ?? ''
    expect(text).toContain('空列表是答案，不是缺源')
    expect(text).not.toContain('没有 artifactHandles 字段')
    expect(block(container).querySelector('[data-testid="evidence-handles-count"]')?.textContent)
      .toContain('可见 0 行 / 窗口内 0 行')
    expect(rows(container)).toHaveLength(0)
    // the summary facts are still real numbers, including the measured zero
    expect(capacityLine(container).textContent).toContain('快照下发 0')
  })

  it('no snapshot at all is a third statement: nothing is claimed about handles', () => {
    const { container } = renderHandles(null)
    const text = block(container).textContent ?? ''
    expect(text).toContain('数据源未接入')
    expect(text).toContain('UNKNOWN')
    expect(text).not.toMatch(/快照下发 \d/)
    expect(block(container).querySelectorAll('.tag.ok')).toHaveLength(0)
    expect(block(container).querySelectorAll('[data-tone="success"]')).toHaveLength(0)
  })
})

describe('WUI-15 · contentIncluded=false means no content affordance in either direction', () => {
  it('the block renders zero controls and zero content links, and states the refusal', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const region = block(container)
    expect(region.querySelectorAll('button, input, textarea, select, a[href^="file"]')).toHaveLength(0)
    expect(region.querySelector('pre')).toBeNull()
    // every anchor in the block is a filter chip on the same query-string mechanism
    for (const anchor of Array.from(region.querySelectorAll('a'))) {
      const label = `${anchor.textContent ?? ''} ${anchor.getAttribute('href') ?? ''}`
      expect(label, `content affordance smuggled in: ${label}`).not.toMatch(/预览|打开|读取|下载|preview|open|read-bytes/i)
      expect((anchor.getAttribute('href') ?? '').startsWith('//'), 'protocol-relative href').toBe(false)
    }
    const cell = fieldCell(container, 'handlesContentIncluded')!
    expect(cell.textContent).toContain('false')
    expect(cell.textContent).toContain('不随快照下发')
    expect(cell.getAttribute('data-origin')).toBe('PROJECTED')
    expect(region.querySelector('[data-testid="evidence-handles-boundary"]')?.textContent)
      .toContain('没有任何预览、打开文件或读取字节的入口')
  })

  it('a payload that DID include content still gets no content rendered here', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles({
      artifactHandlesSummary: mkArtifactHandlesSummary({ contentIncluded: true }),
    }))
    const cell = fieldCell(container, 'handlesContentIncluded')!
    expect(cell.textContent).toContain('true')
    expect(cell.textContent).toContain('本区块仍然只列身份')
    expect(block(container).querySelectorAll('button, input, textarea')).toHaveLength(0)
  })
})

describe('WUI-15 · an unrecorded digest is missing, not empty', () => {
  it('digestRecorded=false rows carry 未记录 with the NULL_FIELD marker', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const unrecorded = block(container).querySelectorAll('[data-digest-recorded="false"]')
    expect(unrecorded.length).toBe(HANDLES_CAP - HANDLES_ROWS_WITH_DIGEST)
    for (const row of Array.from(unrecorded).slice(0, 5)) {
      const cell = digestCell(row as HTMLElement)
      expect(cell.textContent).toContain('摘要未记录')
      expect(cell.getAttribute('data-origin')).toBe('NULL_FIELD')
      expect((cell.textContent ?? '').trim().length).toBeGreaterThan(0)
      expect(cell.textContent).not.toMatch(/^\s*$/)
    }
  })

  it('digestRecorded=true rows show the real digest and its source as PROJECTED', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const recorded = block(container).querySelector('[data-digest-recorded="true"]') as HTMLElement
    const cell = digestCell(recorded)
    expect(cell.textContent).toContain('摘要已登记')
    expect(cell.textContent).toContain('0000')
    expect(cell.textContent).toContain('来源 ledger-record')
    expect(cell.getAttribute('data-origin')).toBe('PROJECTED')
  })

  it('a row flagged recorded without a digest value is a projection gap, never an empty string', () => {
    const { container } = renderHandles(mkSnap({
      artifactHandles: [mkArtifactHandle({ digestRecorded: true })],
      artifactHandlesSummary: mkArtifactHandlesSummary({ projectedCount: 1, enumeratedCount: 1, omittedCount: 0 }),
    }))
    const cell = digestCell(block(container).querySelector('[data-digest-recorded="true"]') as HTMLElement)
    expect(cell.textContent).toContain('快照投影里没有摘要值')
    expect(cell.getAttribute('data-origin')).toBe('NULL_FIELD')
  })

  it('a row without the digestRecorded key at all belongs to neither side of the filter', () => {
    const [head, ...tail] = mkArtifactHandleRows(3)
    const { container } = renderHandles(mkSnap({
      artifactHandles: [dropFlag(head), ...tail],
      artifactHandlesSummary: mkArtifactHandlesSummary(),
    }))
    const unflagged = block(container).querySelector('[data-digest-recorded="absent"]') as HTMLElement
    expect(digestCell(unflagged).textContent).toContain('摘要状态未取自快照投影')
    expect(digestCell(unflagged).getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(block(container).querySelector('[data-testid="evidence-handles-unflagged"]')?.textContent)
      .toContain('1 行没有 digestRecorded 字段')

    // and the flagless row is not counted as 未记录 when the reader asks for 未记录
    const filtered = renderHandles(mkSnap({
      artifactHandles: [dropFlag(head), ...tail],
      artifactHandlesSummary: mkArtifactHandlesSummary(),
    }), '?view=evidence&handlesDigest=unrecorded')
    expect(rows(filtered.container)).toEqual([tail[0].handle, tail[1].handle])
  })
})

describe('WUI-15 · filters live in the address, not in web storage', () => {
  it('the URL read at mount is what the block renders, so a refresh keeps the filter', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles(), '?view=evidence&handlesSurface=runtime')
    const shown = Array.from(block(container).querySelectorAll('[data-handle-row]'))
    expect(shown.length).toBeGreaterThan(0)
    for (const row of shown) expect(row.getAttribute('data-handles-surface')).toBe('runtime')
    const chip = block(container).querySelector('a[data-filter-value="runtime"]') as HTMLElement
    expect(chip.getAttribute('aria-current')).toBe('true')
    expect(block(container).querySelector('[data-testid="evidence-handles-count"]')?.textContent)
      .toContain(`可见 ${shown.length} 行`)
  })

  it('both parameters together narrow to the intersection of the two predicates', () => {
    const { container } = renderHandles(
      mkSnapWithArtifactHandles(), '?view=evidence&handlesSurface=runtime&handlesDigest=unrecorded',
    )
    const shown = Array.from(block(container).querySelectorAll('[data-handle-row]'))
    expect(shown.length).toBeGreaterThan(0)
    for (const row of shown) {
      expect(row.getAttribute('data-handles-surface')).toBe('runtime')
      expect(row.getAttribute('data-digest-recorded')).toBe('false')
    }
    // the fixture's recorded rows are every fifth one, so the runtime surface does contain recorded rows
    // and they must disappear under this filter
    const recorded = renderHandles(
      mkSnapWithArtifactHandles(), '?view=evidence&handlesSurface=runtime&handlesDigest=recorded',
    )
    for (const row of Array.from(block(recorded.container).querySelectorAll('[data-handle-row]'))) {
      expect(row.getAttribute('data-digest-recorded')).toBe('true')
    }
  })

  it('a filter click writes the address, and that address is what a reload reads back', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const chip = block(container).querySelector('a[data-filter-value="reports"]') as HTMLElement
    expect(chip.getAttribute('href')).toContain('handlesSurface=reports')
    fireEvent.click(chip)
    expect(window.location.search).toContain('handlesSurface=reports')
    expect(window.location.search).toContain('view=evidence')
    // no web storage may hold the state (the project forbids it)
    expect(window.localStorage.length + Object.keys(sessionStorage).length).toBe(0)

    const reloaded = renderHandles(mkSnapWithArtifactHandles(), window.location.search)
    for (const row of Array.from(block(reloaded.container).querySelectorAll('[data-handle-row]'))) {
      expect(row.getAttribute('data-handles-surface')).toBe('reports')
    }
  })

  it('an illegal filter value is reported and never applied, and never falls back to the first face', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles(), '?view=evidence&handlesSurface=%20')
    expect(block(container).querySelector('[data-testid="evidence-handles-filter-rejected"]')).toBeNull()

    const hostile = renderHandles(
      mkSnapWithArtifactHandles(),
      '?view=evidence&handlesSurface=' + encodeURIComponent('not-a-projected-surface') + '&handlesDigest=sometimes',
    )
    const rejected = hostile.container.querySelector('[data-testid="evidence-handles-filter-rejected"]') as HTMLElement
    expect(rejected.textContent).toContain('不是取自快照投影的证据面')
    expect(rejected.textContent).toContain('handlesDigest 只接受 all / recorded / unrecorded')
    expect(rejected.querySelectorAll('[data-origin="NULL_FIELD"]')).toHaveLength(2)
    // nothing was filtered: an unusable value does not silently become a query
    expect(rows(hostile.container)).toHaveLength(HANDLES_CAP)
  })

  it('a filter that matches nothing is stated as a query result over a non-empty projection', () => {
    // rows 1..3 of the fixture are the unrecorded ones, so `recorded` has nothing to return
    const unrecorded = mkArtifactHandleRows(4).slice(1)
    const { container } = renderHandles(mkSnap({
      artifactHandles: unrecorded,
      artifactHandlesSummary: mkArtifactHandlesSummary(),
    }), '?view=evidence&handlesDigest=recorded')
    expect(rows(container)).toHaveLength(0)
    const note = block(container).querySelector('[data-testid="evidence-handles-filter-empty"]') as HTMLElement
    expect(note.textContent).toContain('过滤后没有行')
    expect(note.textContent).toContain('窗口本身并没有变空')
    expect(note.getAttribute('data-origin')).toBe('PROJECTED')
  })
})

describe('WUI-15 · the capacity facts are the snapshot\u2019s, and nothing is reordered', () => {
  it('the header states the window against the enumeration, from the fixture values', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const text = capacityLine(container).textContent ?? ''
    expect(text).toContain('快照下发 200 / 枚举 4898 / 省略 4698 / 敏感名拒 195 / 再生目录剪 112')
    expect(text).not.toMatch(/UNKNOWN/)
    expect(block(container).querySelector('[data-testid="evidence-handles-truncation"]')?.textContent)
      .toContain('列表顺序就是快照顺序')
    expect(fieldCell(container, 'handlesCap')!.textContent).toContain('200')
    expect(fieldCell(container, 'handlesRowsWithDigest')!.textContent).toContain('40')
    expect(fieldCell(container, 'handlesRowsWithoutDigest')!.textContent).toContain('160')
    expect(fieldCell(container, 'handlesComputedByHashing')!.textContent).toContain('取自登记的摘要')
  })

  it('the component does not know these numbers — they arrive through the snapshot', () => {
    // WUI-15 review ⑤: the block moved to views/EvidenceHandles.tsx, so the guard follows it. A guard that
    // read the old path would still pass on a file that renders nothing, which is a green that guards
    // nothing — hence the anchors asserted on the file this test actually reads.
    const source = readFileSync('src/views/EvidenceHandles.tsx', 'utf8')
    expect(source).toContain('artifactHandles')
    expect(source).toContain('artifactHandlesSummary')
    for (const anchor of ['data-testid="evidence-handles"', 'data-handle-row', 'data-handles-cell="digest"']) {
      expect(source, `the handle block no longer writes ${anchor} in the file this guard reads`).toContain(anchor)
    }
    for (const literal of ['4898', '4698', '195', '112', '40/200']) {
      expect(source, `hardcoded capacity literal ${literal}`).not.toContain(literal)
      // the host file is where a literal could be re-introduced on the way back; it renders the block too
      expect(readFileSync('src/views/EvidenceView.tsx', 'utf8'), `hardcoded ${literal} in EvidenceView`)
        .not.toContain(literal)
    }
  })

  it('rows render in the order the snapshot published them, even when that order is inverted', () => {
    const reversed = [...mkArtifactHandleRows()].reverse()
    const { container } = renderHandles(mkSnap({
      artifactHandles: reversed,
      artifactHandlesSummary: mkArtifactHandlesSummary(),
    }))
    expect(rows(container)).toEqual(reversed.map((row) => row.handle))
    expect(block(container).querySelector('[data-testid="evidence-handles-rows"]')?.getAttribute('data-ordering'))
      .toBe('projected')
  })

  it('the ordering rule and the window time are printed as the snapshot words them', () => {
    const summary = mkArtifactHandlesSummary({ orderingRule: '生产者自定义规则原文 · 逐字渲染' })
    const { container } = renderHandles(mkSnap({
      artifactHandles: mkArtifactHandleRows(2),
      artifactHandlesSummary: summary,
    }))
    expect(fieldCell(container, 'handlesOrderingRule')!.textContent).toContain('生产者自定义规则原文 · 逐字渲染')
    expect(fieldCell(container, 'handlesOrderingRule')!.getAttribute('data-origin')).toBe('PROJECTED')
    const generated = fieldCell(container, 'handlesGeneratedAt')!.textContent ?? ''
    expect(generated).toContain('整秒')
    expect(generated).toContain('2026-10-19T08:31:22Z')
  })

  it('a refusal count that is not a number prints no count', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const cell = fieldCell(container, 'handlesDroppedOnVerification')!
    expect(cell.textContent).toContain('未提供')
    expect(cell.textContent).toContain('实测 object')
    expect(cell.getAttribute('data-origin')).toBe('NULL_FIELD')
    expect(cell.textContent).not.toMatch(/丢弃 0/)
  })
})

describe('WUI-15 · row facts keep their units and their precision', () => {
  it('size and time are printed with the units the payload supports', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const row = block(container).querySelector('[data-handle-row]') as HTMLElement
    const size = row.querySelector('[data-handles-cell="size"]') as HTMLElement
    expect(size.textContent).toContain('512 B')
    expect(size.getAttribute('data-origin')).toBe('PROJECTED')
    const time = row.querySelector('[data-handles-cell="modifiedAt"]') as HTMLElement
    expect(time.getAttribute('data-precision')).toBe('second')
    expect(time.textContent).toContain('整秒精度')
    expect(time.textContent).toContain('2026-10-19T08:31:22Z')
  })

  it('a null size and an unparseable time stay 未提供 instead of becoming 0 B or a clock', () => {
    const { container } = renderHandles(mkSnap({
      artifactHandles: [
        mkArtifactHandle({ handle: 'D:/x/size-null.json', sizeBytes: null }),
        mkArtifactHandle({ handle: 'D:/x/time-bad.json', modifiedAt: '2026-13-45T99:99:99Z' }),
        mkArtifactHandle({ handle: 'D:/x/size-zero.json', sizeBytes: 0 }),
      ],
      artifactHandlesSummary: mkArtifactHandlesSummary({ projectedCount: 3, enumeratedCount: 3, omittedCount: 0 }),
    }))
    const shown = Array.from(block(container).querySelectorAll('[data-handle-row]'))
    expect(shown).toHaveLength(3)
    const nullSize = shown[0].querySelector('[data-handles-cell="size"]') as HTMLElement
    expect(nullSize.textContent).toContain('大小未提供')
    expect(nullSize.getAttribute('data-origin')).toBe('NULL_FIELD')
    expect(nullSize.textContent).not.toContain('0 B')
    const badTime = shown[1].querySelector('[data-handles-cell="modifiedAt"]') as HTMLElement
    expect(badTime.textContent).toContain('时间未提供')
    expect(badTime.getAttribute('data-precision')).toBeNull()
    expect(badTime.getAttribute('data-origin')).toBe('NULL_FIELD')
    // a measured zero is data, and must still print as a number
    const zeroSize = shown[2].querySelector('[data-handles-cell="size"]') as HTMLElement
    expect(zeroSize.textContent).toContain('0 B')
    expect(zeroSize.getAttribute('data-origin')).toBe('PROJECTED')
  })
})

describe('WUI-15 · the fault state belongs to refusals, not to the designed cap window', () => {
  const zeroRefusals = {
    notRegularFiles: 0, reparseDirectories: 0, sensitiveNames: 0,
    unreadableEntries: 0, prunedRegenerableDirectories: 0, droppedOnVerification: {},
  }

  function faultCard(container: HTMLElement): HTMLElement | null {
    return block(container).querySelector<HTMLElement>('[data-state="partial-failure"]')
  }

  it('truncated by cap is disclosed as a window, not announced as an incident', () => {
    const snap = mkSnapWithArtifactHandles({
      artifactHandlesSummary: mkArtifactHandlesSummary({ truncated: true, refused: zeroRefusals }),
    })
    const { container } = renderHandles(snap)
    const window = block(container).querySelector<HTMLElement>('[data-testid="evidence-handles-window"]')
    expect(window, 'a cap window must still be disclosed').not.toBeNull()
    expect(window!.textContent).toContain('不是故障')
    expect(faultCard(container), 'truncation alone is designed behaviour and must not wear the fault card')
      .toBeNull()
  })

  it('a refusal count does raise the fault card and names the count', () => {
    const snap = mkSnapWithArtifactHandles({
      artifactHandlesSummary: mkArtifactHandlesSummary({
        truncated: false,
        refused: { ...zeroRefusals, sensitiveNames: 231, prunedRegenerableDirectories: 114 },
      }),
    })
    const { container } = renderHandles(snap)
    const card = faultCard(container)
    expect(card, 'the producer declined entries; that is the partial failure the vocabulary names').not.toBeNull()
    expect(card!.textContent).toContain('231')
    expect(card!.textContent).toContain('敏感名')
    expect(card!.textContent).toContain('没有被折算成')
  })

  it('an absent refusal record cannot mint a zero-sum fault card', () => {
    const summary = { ...mkArtifactHandlesSummary({ truncated: true }), refused: undefined } as never
    const { container } = renderHandles(mkSnapWithArtifactHandles({ artifactHandlesSummary: summary }))
    expect(faultCard(container)).toBeNull()
    const cell = fieldCell(container, 'handlesNotRegularFiles')
    expect(cell, 'the refusal cells stay 未提供 instead of being filled with 0').not.toBeNull()
    expect(cell!.getAttribute('data-origin')).toBe('SOURCE_GAP')
  })

  it('the handle rows come before the bookkeeping grid', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles())
    const firstRow = block(container).querySelector<HTMLElement>('[data-handle-row]')
    const capCell = fieldCell(container, 'handlesCap')
    expect(firstRow).not.toBeNull()
    expect(capCell).not.toBeNull()
    const all = Array.from(block(container).querySelectorAll('*'))
    expect(all.indexOf(firstRow!)).toBeLessThan(all.indexOf(capCell!))
  })
})

// ---------------------------------------------------------------------------
// The 2026-10-20 review items, each with the test it asked for. Every one of these fails against the
// bytes that were shipped before the fix, and each also states the case that must KEEP working — a
// guard that only ever sees the broken branch cannot tell a fix from a deletion.
// ---------------------------------------------------------------------------

/** Drop a key entirely: the payload shape that must read as a gap, never as a value. */
function withoutKey(row: ArtifactHandle, key: string): ArtifactHandle {
  const copy: Record<string, unknown> = { ...row }
  delete copy[key]
  return copy as unknown as ArtifactHandle
}

function refusalCard(container: HTMLElement): HTMLElement {
  const card = block(container).querySelector<HTMLElement>('[data-state="partial-failure"]')
  expect(card, 'the producer declined entries; the vocabulary names that a partial failure').not.toBeNull()
  return card!
}

/** A reader that resolves: these cases are about the address a click writes, never about bytes. */
const resolveWithoutReading: SliceReader = async () => ({
  kind: 'UNREACHABLE', httpStatus: null, detail: '本用例只验地址，不读字节',
  endpoint: 'http://127.0.0.1:1/api/v1/evidence-range', authoritative: false,
})

describe('WUI-15 review ① · surfaceRoot is stated as measured, and a missing key stays a gap', () => {
  function surfaceRootCell(container: HTMLElement, handle: string): HTMLElement {
    const row = block(container).querySelector<HTMLElement>(`[data-handle-row="${handle}"]`)
    expect(row, 'the row must be on screen').not.toBeNull()
    const cell = row!.querySelector<HTMLElement>('[data-handles-cell="surfaceRoot"]')
    expect(cell, 'every handle row carries its own surfaceRoot cell').not.toBeNull()
    return cell!
  }

  it('a row that carries surfaceRoot prints the value it carries', () => {
    const row = mkArtifactHandle({ handle: 'D:/x/with-root.json', surfaceRoot: '.project-local/runs' })
    const { container } = renderHandles(mkSnap({
      artifactHandles: [row],
      artifactHandlesSummary: mkArtifactHandlesSummary({ projectedCount: 1, enumeratedCount: 1, omittedCount: 0 }),
    }))
    const cell = surfaceRootCell(container, row.handle)
    expect(cell.textContent).toContain('.project-local/runs')
    expect(cell.getAttribute('data-origin')).toBe('PROJECTED')
    // the sentence the live snapshot contradicts (05-artifact-handles-shape.json: every row of the
    // window carries the field) must not come back, in this cell or anywhere in the block
    expect(cell.textContent).not.toContain('不发 surfaceRoot')
    expect(block(container).textContent).not.toContain('不发 surfaceRoot')
  })

  it('a row without the key says 未提供 with the source gap marker, never an empty cell', () => {
    const row = withoutKey(mkArtifactHandle({ handle: 'D:/x/no-root.json' }), 'surfaceRoot')
    const { container } = renderHandles(mkSnap({
      artifactHandles: [row],
      artifactHandlesSummary: mkArtifactHandlesSummary({ projectedCount: 1, enumeratedCount: 1, omittedCount: 0 }),
    }))
    const cell = surfaceRootCell(container, 'D:/x/no-root.json')
    expect(cell.textContent).toContain('未提供')
    expect(cell.textContent).toContain('surfaceRoot')
    expect((cell.textContent ?? '').trim().length).toBeGreaterThan('根（surfaceRoot）'.length)
    expect(cell.getAttribute('data-origin')).toBe('SOURCE_GAP')
    // and this is the row where the old sentence lived: a gap in ONE row must not be reported as a
    // property of the producer, because the measured window carries the field on every row
    expect(cell.textContent).not.toContain('不发 surfaceRoot')
  })
})

describe('WUI-15 review ② · an absent refusal key does not borrow the map’s zero', () => {
  const refusedWithoutTheKey = {
    notRegularFiles: 0, reparseDirectories: 0, sensitiveNames: 231,
    unreadableEntries: 0, prunedRegenerableDirectories: 114,
  }

  it('refused present but droppedOnVerification absent: the card says 未提供 and prints no 0', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles({
      artifactHandlesSummary: mkArtifactHandlesSummary({ truncated: false, refused: refusedWithoutTheKey as never }),
    }))
    const text = refusalCard(container).textContent ?? ''
    expect(text).toContain('核对时丢弃 未提供')
    expect(text).not.toMatch(/丢弃 0/)
    // the counts the producer really published still print — the clause is not being silenced
    expect(text).toContain('敏感名 231')
    expect(text).toContain('再生目录剪枝 114')
    // and the bookkeeping grid keeps the same answer for the same key
    const cell = fieldCell(container, 'handlesDroppedOnVerification')!
    expect(cell.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(cell.textContent).toContain('未提供')
  })

  it('a map that carries per-reason counts still reaches the card as its sum', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles({
      artifactHandlesSummary: mkArtifactHandlesSummary({
        truncated: false,
        refused: { ...refusedWithoutTheKey, droppedOnVerification: { digest_mismatch: 3, size_changed: 2 } } as never,
      }),
    }))
    const text = refusalCard(container).textContent ?? ''
    expect(text).toContain('核对时丢弃 5')
    // 231 + 114 + 5: the summed map is part of the total, so the two lines cannot disagree
    expect(text).toContain('生产者拒绝或剪枝 350 个条目')
  })
})

describe('WUI-15 review ④ · a long-term refusal is a compact strip, not a page-level shell', () => {
  const standing = {
    notRegularFiles: 0, reparseDirectories: 0, sensitiveNames: 231,
    unreadableEntries: 0, prunedRegenerableDirectories: 114,
  }

  it('keeps every word and count and drops only the 64px circle and the page-height band', () => {
    const { container } = renderHandles(mkSnapWithArtifactHandles({
      artifactHandlesSummary: mkArtifactHandlesSummary({ truncated: false, refused: standing as never }),
    }))
    const card = refusalCard(container)
    expect(card.getAttribute('data-presentation')).toBe('compact')
    expect(card.querySelector('.icon')).toBeNull()
    expect(card.className).not.toContain('empty')
    expect(card.textContent).toContain('局部故障 · 证据把手枚举')
    expect(card.textContent).toContain('生产者拒绝或剪枝 345 个条目：敏感名 231')
    // the state vocabulary the card prints is the point of the card, so it travels with the compact shell
    expect(card.textContent).toContain('依据：')
    expect(card.textContent).toContain('下一步：')
  })

  it('the page-level shell is still what a one-off degraded state wears', () => {
    // control for the assertion above: `.empty .icon` is not gone from the product, only demoted here
    const { container } = renderHandles(mkSnap())
    expect(container.querySelector('.empty .icon')).not.toBeNull()
  })
})

describe('WUI-15 review ⑥ · following a source keeps the handle filter in the address', () => {
  it('the shelf link carries handlesDigest and palette, and so does the URL it writes', () => {
    const snap = mkSnapWithArtifactHandles({
      workspace: {
        sources: [{ path: 'reports/evidence-note.md', evidenceKind: 'MARKDOWN_REPORT', loadedAt: '2026-10-19T08:31:22Z' }],
      } as never,
    })
    const { container } = render(
      <EvidenceView
        snap={snap}
        search="?view=evidence&palette=master&handlesDigest=unrecorded"
        readSlice={resolveWithoutReading}
      />,
    )
    const source = Array.from(container.querySelectorAll('a'))
      .find((anchor) => (anchor.getAttribute('href') ?? '').includes('artifact='))
    expect(source, 'each projected source is offered as an address').toBeTruthy()
    const href = source!.getAttribute('href') ?? ''
    expect(href).toContain('handlesDigest=unrecorded')
    expect(href).toContain('palette=master')

    fireEvent.click(source!)
    const search = window.location.search
    expect(search).toContain('artifact=')
    expect(search).toContain('handlesDigest=unrecorded')
    expect(search).toContain('palette=master')
    // and the filter the reader set is still in force in the block after the click
    expect(block(container).querySelector('a[data-filter-value="unrecorded"]')?.getAttribute('aria-current'))
      .toBe('true')
    // a reload from that address comes back filtered — the state is the URL, not the component
    const reloaded = render(
      <EvidenceView snap={snap} search={search} readSlice={resolveWithoutReading} />,
    )
    for (const row of Array.from(block(reloaded.container).querySelectorAll('[data-handle-row]'))) {
      expect(row.getAttribute('data-digest-recorded')).toBe('false')
    }
  })
})
