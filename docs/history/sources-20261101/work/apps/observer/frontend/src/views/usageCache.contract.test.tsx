/**
 * WUI-05 · the usage page as rendered, not as computed.
 *
 * `usageTruth.test.ts` proves the reading functions; this file proves the page does not turn those
 * readings into something the reader misreads. The three properties that matter are the ones a unit test
 * on a pure function cannot see:
 *
 *   1. a missing field never renders as `0` and a reported zero never renders as a gap — the two must be
 *      distinguishable in the DOM, by origin attribute and by the sentence printed beside them;
 *   2. no percentage appears anywhere on the page, because the snapshot carries no cache-read numerator
 *      and no judgeable-request denominator (verified against `snapshot_api.py`); a ratio would be the
 *      fabricated number this project keeps having to hunt down;
 *   3. the metering dimensions stay separate — tokens, credits, cost and resources never share a cell,
 *      and the ones with no field are named as gaps with their producer reason.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { UsageCacheView } from '@/views/UsageCacheView'
import { mkSnap, mkProject } from '@/test/snapshotFixture'
import type { SnapshotV3 } from '@/types'

function snapWithToken(over: Partial<SnapshotV3> = {}): SnapshotV3 {
  return mkSnap({
    projects: [
      mkProject({ projectId: 'alpha', displayName: 'ALPHA',
        token: { inputTokens: 1000, outputTokens: 0, totalTokens: 1000, costQuality: 'EXACT' } }),
    ],
    tokenSummary: { inputTokens: 1000, outputTokens: null, totalTokens: 1000, costQuality: 'UNKNOWN' },
    ...over,
  })
}

afterEach(cleanup)

describe('UsageCacheView (WUI-05)', () => {
  it('renders a missing field as UNKNOWN with the not-counted-as-zero sentence', () => {
    const { container } = render(<UsageCacheView snap={snapWithToken()} />)
    const output = container.querySelector('[data-dim="outputTokens"]')
    expect(output, 'the output-token field never rendered').not.toBeNull()
    expect(output!.getAttribute('data-origin')).toBe('NULL_FIELD')
    const text = output!.textContent || ''
    expect(text).toContain('UNKNOWN')
    expect(text).toContain('不按零计')
    expect(text).not.toMatch(/\b0\b\s*(token|个|次)/i)
  })

  it('renders a source-reported zero as a reported value, and never as a gap', () => {
    // The summary reports outputTokens = 0 here. That zero is a different claim from the null in the
    // test above, and the page must not print either of them the way the other one reads.
    const { container } = render(<UsageCacheView snap={snapWithToken({
      tokenSummary: { inputTokens: 1000, outputTokens: 0, totalTokens: 1000, costQuality: 'EXACT' },
    })} />)
    const zeros = Array.from(container.querySelectorAll('[data-origin="PROJECTED"]'))
      .filter((node) => (node.textContent || '').includes('这个零是源报告的值'))
    expect(zeros.length, 'a reported zero was not rendered as a reported value').toBeGreaterThan(0)
    expect(zeros[0].getAttribute('data-dim')).toBe('outputTokens')
  })

  it('keeps a derived row count of zero from claiming a source-reported zero', () => {
    // qualitySubsetCounts counts rows in the browser. Its 0 must not borrow the source sentence, or
    // "no ESTIMATED rows in this projection" reads as "the source reported zero estimated usage".
    const { container } = render(<UsageCacheView snap={snapWithToken({
      projects: [mkProject({ projectId: 'alpha',
        token: { inputTokens: 1, outputTokens: 1, totalTokens: 2, costQuality: 'EXACT' } })],
      tokenSummary: { inputTokens: 2, outputTokens: 2, totalTokens: 4, costQuality: 'EXACT' },
    })} />)
    const estimated = container.querySelector('[data-dim="estimated"]')
    expect(estimated, 'the estimated row count never rendered').not.toBeNull()
    expect(estimated!.textContent).toContain('0')
    expect(estimated!.textContent).not.toContain('这个零是源报告的值')
  })

  it('prints no percentage anywhere, because the cache denominators are not projected', () => {
    const { container } = render(<UsageCacheView snap={snapWithToken()} />)
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d+(\.\d+)?\s*%/)
    expect(text).not.toMatch(/命中率\s*[:：]\s*\d/)
    expect(text).not.toMatch(/占比\s*[:：]\s*\d/)
  })

  it('names the cache, credits, cost and dedupe questions as gaps with a producer reason', () => {
    const { container } = render(<UsageCacheView snap={snapWithToken()} />)
    const text = container.textContent || ''
    for (const fragment of ['缓存', 'Credits', '费用', '去重']) {
      expect(text, `the page never addresses ${fragment}`).toContain(fragment)
    }
    // the reason has to point at the projection, not at a vague "not available"
    expect(text).toMatch(/canonical_store|未投影|不进入只读投影|快照/)
  })

  it('keeps the exact / estimated / unknown subsets as counts of rows, not as a blended quality', () => {
    const { container } = render(<UsageCacheView snap={snapWithToken()} />)
    const text = container.textContent || ''
    expect(text).toContain('EXACT')
    expect(text).toContain('UNKNOWN')
    // one blended label would let an estimated row inherit an exact headline
    expect(text).not.toMatch(/总体质量\s*[:：]\s*EXACT/)
  })

  it('with no snapshot at all it says the fields cannot be read, and shows no digits', () => {
    const { container } = render(<UsageCacheView snap={null} />)
    const text = container.textContent || ''
    expect(text).toContain('快照未到达')
    expect(text).not.toMatch(/\b\d[\d,]*\s*(token|Token)\b/)
  })
})
