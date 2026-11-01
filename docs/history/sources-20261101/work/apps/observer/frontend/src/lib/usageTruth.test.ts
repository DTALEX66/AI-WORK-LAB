// WUI-05 · the usage read model is the single place that decides what a number means on this page,
// so its rules are tested here rather than only through a render.
//
// Both directions are pinned: a missing field must never become 0, a reported 0 must never be read as
// missing, a subset count must come from the rows and not from the summary label, a ratio must never be
// computed where a denominator is absent (or even where it is present), and every named gap must carry
// the producer's own behaviour as its reason.
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'

import {
  TOKEN_PRECISION, TOKEN_UNIT, USAGE_GAP_BLOCKS, USAGE_READONLY_BOUNDARY, USAGE_SOURCE_GAPS,
  coverageReading, gapBlockKeysInUse, gapsForBlock, groupInteger, projectUsageRows,
  qualitySubsetCounts, readNumberField, summaryQuality, summaryTokenFields, usageConsistency,
  type NumberReading,
} from './usageTruth'
import { mkProject, mkSnap } from '@/test/snapshotFixture'

const field = (key: string, list: NumberReading[]): NumberReading => {
  const found = list.find((reading) => reading.key === key)
  if (!found) throw new Error(`no reading for ${key}`)
  return found
}

describe('usageTruth · 字段值与三起源（WUI-05）', () => {
  it('reads a null token field as an absent value, never as 0', () => {
    const snap = mkSnap({ tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' } })
    const readings = summaryTokenFields(snap)
    expect(readings).toHaveLength(3)
    for (const reading of readings) {
      expect(reading.origin).toBe('NULL_FIELD')
      expect(reading.value).toBeNull()
      expect(reading.text).toBe('UNKNOWN')
      expect(reading.text).not.toBe('0')
      expect(reading.reportedZero).toBe(false)
      expect(reading.completeness).toBe('未报告')
      expect(reading.abbrevText).toBeNull()
      // the reason is stated in the reading, so no page has to guess it
      expect(reading.note).toContain('不按零计')
    }
  })

  it('keeps a source-reported 0 distinct from a missing field', () => {
    const snap = mkSnap({ tokenSummary: { inputTokens: 0, outputTokens: null, totalTokens: 0, costQuality: 'EXACT' } })
    const readings = summaryTokenFields(snap)
    const input = field('inputTokens', readings)
    const output = field('outputTokens', readings)
    const total = field('totalTokens', readings)

    expect(input.origin).toBe('PROJECTED')
    expect(input.value).toBe(0)
    expect(input.text).toBe('0')
    expect(input.reportedZero).toBe(true)
    expect(input.completeness).toBe('已报告')
    expect(input.note).toContain('零')

    // the sibling of a reported zero is still missing, and stays missing
    expect(output.origin).toBe('NULL_FIELD')
    expect(output.text).toBe('UNKNOWN')
    expect(total.reportedZero).toBe(true)
  })

  it('does not read a non-number on the wire as a zero', () => {
    for (const raw of [undefined, null, '0', '12', true, false, Number.NaN, Infinity]) {
      const reading = readNumberField({ key: 'x', label: 'X', raw, source: 'test' })
      expect(reading.origin, `raw=${String(raw)}`).toBe('NULL_FIELD')
      expect(reading.text).toBe('UNKNOWN')
      expect(reading.reportedZero).toBe(false)
    }
  })

  it('carries unit, precision and completeness with every value and keeps decimals as reported', () => {
    const reading = field('totalTokens', summaryTokenFields(mkSnap({
      tokenSummary: { inputTokens: 64391, outputTokens: 26821, totalTokens: 91212, costQuality: 'ESTIMATED' },
    })))
    expect(reading.unit).toBe(TOKEN_UNIT)
    expect(reading.precision).toBe(TOKEN_PRECISION)
    expect(reading.completeness).toBe('已报告')
    expect(reading.text).toBe('91,212')
    expect(reading.abbrevText).toBe('91k')
    expect(reading.source).toContain('snapshot_api.py')

    // a producer that ever hands over a decimal gets it printed, not rounded into a new truth
    const decimal = readNumberField({ key: 'd', label: 'D', raw: 12.5, source: 'test' })
    expect(decimal.origin).toBe('PROJECTED')
    expect(decimal.text).toBe('12.5')
    expect(decimal.precision).toContain('非整数')
  })

  it('explains 总 Token as the source-reported total, not as input plus output', () => {
    const total = field('totalTokens', summaryTokenFields(mkSnap()))
    expect(total.note).toContain('不用输入加输出反推')
  })

  it('treats the quality label as a verdict, not as an amount or a rate', () => {
    const unknown = summaryQuality(mkSnap({
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
    }))
    expect(unknown.origin).toBe('PROJECTED')
    expect(unknown.text).toBe('UNKNOWN')
    expect(unknown.isUnknownVerdict).toBe(true)
    expect(unknown.note).toContain('不是金额')

    const absent = summaryQuality(null)
    expect(absent.origin).toBe('NULL_FIELD')
    expect(absent.text).toBe('UNKNOWN')
  })

  it('returns absent readings for every field when no snapshot arrived', () => {
    for (const reading of summaryTokenFields(null)) {
      expect(reading.origin).toBe('NULL_FIELD')
      expect(reading.source).toContain('快照未到达')
    }
    expect(projectUsageRows(null)).toEqual([])
    const coverage = coverageReading(null)
    expect(coverage.numerator.origin).toBe('NULL_FIELD')
    expect(coverage.denominator.text).toBe('UNKNOWN')
    expect(coverage.scope.value).toBeNull()
    expect(qualitySubsetCounts(null).rows).toBe(0)
  })
})

describe('usageTruth · 覆盖与分母（不算任何比率）', () => {
  it('keeps numerator and denominator as two numbers and never divides them', () => {
    const coverage = coverageReading(mkSnap({ coverage: { numerator: 3, denominator: 4, scope: 'collectors' } }))
    expect(coverage.numerator.text).toBe('3')
    expect(coverage.denominator.text).toBe('4')
    expect(coverage.ratioText).toBeNull()
    expect(coverage.note).toContain('不把分子分母相除')
    expect(coverage.scope.value).toBe('collectors')
    // the arithmetic the page refuses to do would have produced this; it must not appear anywhere
    expect(JSON.stringify(coverage)).not.toMatch(/75/)
  })

  it('says 分母未知 and 分母为零 as two different sentences', () => {
    const unknownDenominator = coverageReading(mkSnap({ coverage: { numerator: 3, denominator: null, scope: null } }))
    expect(unknownDenominator.denominator.origin).toBe('NULL_FIELD')
    expect(unknownDenominator.denominator.text).toBe('UNKNOWN')
    expect(unknownDenominator.denominator.note).toContain('不算任何比率')
    expect(unknownDenominator.scope.note).toContain('口径未说明')

    const zeroDenominator = coverageReading(mkSnap({ coverage: { numerator: 0, denominator: 0, scope: 'collectors' } }))
    expect(zeroDenominator.denominator.origin).toBe('PROJECTED')
    expect(zeroDenominator.denominator.text).toBe('0')
    expect(zeroDenominator.denominator.reportedZero).toBe(true)
    expect(zeroDenominator.denominator.note).toContain('分母为零')
    expect(zeroDenominator.numerator.reportedZero).toBe(true)
  })

  it('names the snapshot revision as the snapshot revision, never as a usage revision', () => {
    // the same distinction RecordInspector draws for a task's own revision
    const snap = mkSnap({ revision: 11 })
    expect(snap.revision).toBe(11)
    const revisionGap = USAGE_SOURCE_GAPS.find((gap) => gap.key === 'usageRevisions')
    expect(revisionGap?.reason).toContain('快照自己的修订')
  })
})

describe('usageTruth · 精确 / 估算 / 未知子集来自行', () => {
  const mixed = mkSnap({
    projects: [
      mkProject({ projectId: 'a', displayName: 'A', token: { inputTokens: 10, outputTokens: 5, totalTokens: 15, costQuality: 'EXACT' } }),
      mkProject({ projectId: 'b', displayName: 'B', token: { inputTokens: 0, outputTokens: null, totalTokens: 0, costQuality: 'ESTIMATED' } }),
      mkProject({ projectId: 'c', displayName: null, token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' } }),
    ],
    tokenSummary: { inputTokens: 10, outputTokens: 5, totalTokens: 15, costQuality: 'EXACT' },
  })

  it('counts rows, and does not read the summary label as a count', () => {
    const counts = qualitySubsetCounts(mixed)
    expect(counts.rows).toBe(3)
    expect(counts.exact).toBe(1)
    expect(counts.estimated).toBe(1)
    expect(counts.unknown).toBe(1)
    expect(counts.summaryQuality).toBe('EXACT')
    // the summary says EXACT; that must not inflate the row count of EXACT rows
    expect(counts.exact).not.toBe(counts.rows)
    expect(counts.basis).toContain('逐行数')
    expect(counts.note).toContain('行数不等于样本数')
  })

  it('separates an unknown verdict from a row that reported nothing at all', () => {
    const counts = qualitySubsetCounts(mixed)
    expect(counts.rowsWithoutAnyReportedNumber).toBe(1)
    const reported = field('noReportedField', counts.readings)
    expect(reported.text).toBe('1')
    expect(reported.unit).toBe('行')
    expect(reported.source).toContain('派生')
  })

  it('keeps a zero count honest and a zero value reported', () => {
    const counts = qualitySubsetCounts(mixed)
    const estimated = field('estimated', counts.readings)
    expect(estimated.value).toBe(1)
    expect(estimated.reportedZero).toBe(false)

    const allExact = qualitySubsetCounts(mkSnap({
      projects: [mkProject({ projectId: 'a', token: { inputTokens: 1, outputTokens: 1, totalTokens: 2, costQuality: 'EXACT' } })],
    }))
    expect(allExact.exact).toBe(1)
    expect(field('estimated', allExact.readings).text).toBe('0')
    expect(field('estimated', allExact.readings).reportedZero).toBe(true)
    expect(field('estimated', allExact.readings).note).not.toContain('缺失')
  })

  it('reads an empty project set as an absence of rows, not as an absence of usage', () => {
    const counts = qualitySubsetCounts(mkSnap({ projects: [] }))
    expect(field('rows', counts.readings).text).toBe('0')
    expect(counts.rowsWithoutAnyReportedNumber).toBe(0)
    expect(field('rows', counts.readings).note).toContain('不等于没有用量样本')
  })

  it('keys project rows by projectId and keeps display name nullness', () => {
    const rows = projectUsageRows(mixed)
    expect(rows.map((row) => row.projectId)).toEqual(['a', 'b', 'c'])
    expect(rows[2].displayName).toBeNull()
    expect(rows[2].hasAnyReportedNumber).toBe(false)
    expect(rows[2].looksLikeNoSample).toBe(true)
    // a row that reports a real 0 is NOT "no sample"
    expect(rows[1].hasAnyReportedNumber).toBe(true)
    expect(rows[1].looksLikeNoSample).toBe(false)
    expect(rows[1].reportedFieldCount).toBe(2)
    expect(rows[0].fields.map((f) => f.text)).toEqual(['10', '5', '15'])
  })

  it('treats a project row without a token object as unreported, not zeroed', () => {
    const broken = mkSnap({ projects: [{ projectId: 'z' } as never] })
    const rows = projectUsageRows(broken)
    expect(rows[0].fields.every((f) => f.origin === 'NULL_FIELD')).toBe(true)
    expect(rows[0].quality.text).toBe('UNKNOWN')
    expect(rows[0].quality.origin).toBe('NULL_FIELD')
  })
})

describe('usageTruth · 口径核对（界面派生，缺失不相加）', () => {
  it('refuses to compute a row total when any row is missing the field', () => {
    const snap = mkSnap({
      projects: [
        mkProject({ projectId: 'a', token: { inputTokens: null, outputTokens: null, totalTokens: 10, costQuality: 'EXACT' } }),
        mkProject({ projectId: 'b', token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' } }),
      ],
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: 10, costQuality: 'UNKNOWN' },
    })
    const check = usageConsistency(snap)
    expect(check.rowsTotal.computable).toBe(false)
    expect(check.rowsTotal.value).toBeNull()
    expect(check.rowsTotal.text).toBe('不可计算')
    expect(check.rowsTotal.rowsMissing).toBe(1)
    expect(check.rowsTotal.note).toContain('不按零相加')
    expect(check.verdict).toContain('不做比较')
  })

  it('reports an attribution difference without overwriting either side', () => {
    const snap = mkSnap({
      projects: [mkProject({ projectId: 'a', token: { inputTokens: null, outputTokens: null, totalTokens: 40, costQuality: 'EXACT' } })],
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: 100, costQuality: 'UNKNOWN' },
    })
    const check = usageConsistency(snap)
    expect(check.rowsTotal.computable).toBe(true)
    expect(check.rowsTotal.text).toBe('40')
    expect(check.verdict).toContain('相差 60')
    expect(check.verdict).toContain('不修正任何一个投影值')
  })

  it('does not invent a row total when there are no rows', () => {
    const check = usageConsistency(mkSnap({ projects: [], tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' } }))
    expect(check.rowsTotal.computable).toBe(false)
    expect(check.rowsTotal.text).toBe('UNKNOWN')
    expect(check.verdict).toContain('不做比较')
  })
})

describe('usageTruth · 命名缺口（NO-FIELD 项）', () => {
  const REQUIRED_GAP_KEYS = [
    'cacheReadTokens', 'cacheWriteTokens', 'reasoningTokens', 'toolTokens', 'subagentTokens',
    'credits', 'quota', 'costEstimate', 'costReconciled', 'cacheHitRate', 'requestSampleCount',
    'ingestionMode', 'usageRevisions', 'parentChildRollup', 'forkReplayDedupe',
  ]

  it('names every NO-FIELD item the acceptance line asks about', () => {
    const keys = USAGE_SOURCE_GAPS.map((gap) => gap.key)
    expect(keys).toEqual(expect.arrayContaining(REQUIRED_GAP_KEYS))
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('gives each gap a producer reason, and cites the store columns where they exist', () => {
    for (const gap of USAGE_SOURCE_GAPS) {
      expect(gap.question.trim().length).toBeGreaterThan(0)
      expect(gap.reason, `${gap.key} has no reason`).not.toHaveLength(0)
      // a gap that names where the number would come from is auditable; a bare "不支持" is not
      expect(gap.reason, `${gap.key} reason does not name a source layer`)
        .toMatch(/canonical_store|snapshot_api|usage_rollup|usage_samples|快照|投影|合同/)
    }
    // the exact claim this page has to be able to make about cache tokens
    for (const key of ['cacheReadTokens', 'cacheWriteTokens', 'reasoningTokens', 'toolTokens', 'subagentTokens', 'costEstimate', 'costReconciled']) {
      const reason = USAGE_SOURCE_GAPS.find((gap) => gap.key === key)!.reason
      expect(reason, `${key} must cite the store column`).toContain('canonical_store.py')
      expect(reason, `${key} must say the snapshot does not project it`).toContain('snapshot_api.py')
    }
    // the rollup script computes cache totals and fingerprints OUTSIDE the snapshot path
    for (const key of ['cacheReadTokens', 'forkReplayDedupe', 'latency']) {
      expect(USAGE_SOURCE_GAPS.find((gap) => gap.key === key)!.reason).toContain('usage_rollup.py')
    }
  })

  it('carries no number in a gap reason, because a gap has no value to report', () => {
    for (const gap of USAGE_SOURCE_GAPS) {
      expect(gap.reason, `${gap.key} leaks a percentage`).not.toContain('%')
      expect(gap.reason, `${gap.key} leaks a quantity`).not.toMatch(/\d+(\.\d+)?\s*(tokens|Token|K\b|USD|\$|元)/)
      expect(gap.reason, `${gap.key} leaks a ratio`).not.toMatch(/\d+\s*\/\s*\d+/)
    }
  })

  it('groups gaps into blocks and loses none of them', () => {
    const declared = USAGE_GAP_BLOCKS.map((block) => block.key)
    expect(gapBlockKeysInUse().every((key) => declared.includes(key))).toBe(true)
    for (const block of USAGE_GAP_BLOCKS) {
      expect(gapsForBlock(block.key).length, `${block.key} renders nothing`).toBeGreaterThan(0)
      expect(gapsForBlock(block.key).every((gap) => gap.block === block.key)).toBe(true)
      expect(block.lead.length).toBeGreaterThan(0)
    }
    const total = declared.reduce((acc, key) => acc + gapsForBlock(key).length, 0)
    expect(total).toBe(USAGE_SOURCE_GAPS.length)
  })

  it('states the read-only boundary in words and offers no action verb of its own', () => {
    expect(USAGE_READONLY_BOUNDARY.length).toBeGreaterThan(0)
    expect(USAGE_READONLY_BOUNDARY.join(' ')).toContain('不触发重算')
    expect(USAGE_READONLY_BOUNDARY.join(' ')).toContain('不把缺失改写成零')
  })
})

describe('usageTruth · 演示数字不得进入产品代码', () => {
  // the母版 fixture's arithmetic (docs/history/owner-inputs/20261009/ui-readable/docs/03_数据与状态合同.md).
  // These are EXAMPLES of metering, never product defaults or rendered values.
  const FORBIDDEN = ['58', '24K', '16K', '2K', '100K', '28.4', '128.4', '74K', '60%', '40%', '50K', '30K']
  const PRODUCT_SOURCES = ['src/lib/usageTruth.ts', 'src/views/UsageCacheView.tsx']

  it.each(PRODUCT_SOURCES)('%s carries none of the demo arithmetic', (relPath) => {
    const text = readFileSync(relPath, 'utf8')
    for (const token of FORBIDDEN) {
      expect(text, `${relPath} contains demo token ${token}`).not.toContain(token)
    }
  })

  it('prints no percentage character at all', () => {
    for (const relPath of PRODUCT_SOURCES) {
      expect(readFileSync(relPath, 'utf8'), relPath).not.toContain('%')
    }
  })

  it('groups integers deterministically', () => {
    expect(groupInteger(0)).toBe('0')
    expect(groupInteger(999)).toBe('999')
    expect(groupInteger(1000)).toBe('1,000')
    expect(groupInteger(91212)).toBe('91,212')
    expect(groupInteger(-1234567)).toBe('-1,234,567')
  })
})
