/**
 * WUI-18(e)/WUI-11: the collector reading classifies absence, emptiness and zero correctly.
 *
 * Three statements must stay three: the health table was never read (absent key), it was read and nothing is
 * registered (empty list), and it reported rows. And "refused 0 rows" is a measured zero, not an unknown —
 * while a refusal REASON of null means "no reason was recorded", which is not the same as "nothing refused".
 * No rate is ever computed, because the payload never publishes an offered-rows denominator.
 */
import { describe, expect, it } from 'vitest'
import type { CollectorDelivery } from '@/types'
import {
  GAP_MESSAGE, NO_RATE_NOTE, UNREGISTERED_MESSAGE,
  freshButRefusing, readCollectorDelivery,
} from '@/lib/collectorDelivery'

function row(overrides: Partial<CollectorDelivery> = {}): CollectorDelivery {
  return {
    collector: 'usage-files',
    totalRuns: 5,
    lastRunAt: '2026-10-10T00:00:00Z',
    lastSuccessAt: '2026-10-10T00:00:00Z',
    consecutiveFailures: 0,
    circuitOpen: false,
    droppedEvents: 0,
    refusedRows: 0,
    deliveredRows: 12,
    lastRefusalReason: null,
    fresh: true,
    ...overrides,
  }
}

describe('readCollectorDelivery', () => {
  it('treats an absent section as a source gap, never as an empty collector set', () => {
    const reading = readCollectorDelivery(undefined)
    expect(reading.state).toBe('gap')
    expect(reading.state === 'gap' && reading.message).toBe(GAP_MESSAGE)
    expect(GAP_MESSAGE).toContain('这不表示没有采集器')
  })

  it('treats an empty list as "read, nothing registered" and says so differently', () => {
    const reading = readCollectorDelivery([])
    expect(reading.state).toBe('unregistered')
    expect(reading.state === 'unregistered' && reading.message).toBe(UNREGISTERED_MESSAGE)
    expect(UNREGISTERED_MESSAGE).not.toBe(GAP_MESSAGE)
  })

  it('renders zero refused rows as a measured zero, not as a gap', () => {
    const reading = readCollectorDelivery([row()])
    if (reading.state !== 'reporting') throw new Error('expected rows')
    const [only] = reading.rows
    expect(only.refused).toBe('0 行')
    expect(only.delivered).toBe('12 行')
    expect(only.refusing).toBe(false)
    // no reason line is owed when nothing was refused
    expect(only.refusal).toBe('无具名拒绝原因记录')
  })

  it('keeps a refusal reason visible with its location and marks the row as refusing', () => {
    const reading = readCollectorDelivery([row({
      refusedRows: 3,
      lastRefusalReason: '3 row(s) refused, most frequent reason: ValueError: forbidden sensitive field(s) '
        + "(first seen at .hermes/task-artifacts/usage.jsonl:4)",
    })])
    if (reading.state !== 'reporting') throw new Error('expected rows')
    expect(reading.rows[0].refused).toBe('3 行')
    expect(reading.rows[0].refusing).toBe(true)
    expect(reading.rows[0].refusal).toContain('usage.jsonl:4')
  })

  it('names the breaker, the failure streak and freshness as three different words', () => {
    const reading = readCollectorDelivery([
      row({ collector: 'fresh', fresh: true }),
      row({ collector: 'failing', fresh: false, consecutiveFailures: 2, lastSuccessAt: null }),
      row({ collector: 'tripped', fresh: false, circuitOpen: true }),
    ])
    if (reading.state !== 'reporting') throw new Error('expected rows')
    const byName = Object.fromEntries(reading.rows.map((r) => [r.name, r.freshness]))
    expect(byName).toEqual({ fresh: '新鲜', failing: '连续失败 2 次', tripped: '熔断打开' })
    const distinct = new Set(Object.values(byName))
    expect(distinct.size, 'three different causes rendered with the same word').toBe(3)
  })

  it('identifies the combination coverage cannot express: fresh but still refusing', () => {
    const reading = readCollectorDelivery([
      row({ collector: 'quiet' }),
      row({ collector: 'leaky', refusedRows: 4, lastRefusalReason: '4 row(s) refused' }),
      row({ collector: 'stale-refusing', fresh: false, refusedRows: 9, lastRefusalReason: '9 row(s) refused' }),
    ])
    if (reading.state !== 'reporting') throw new Error('expected rows')
    expect(freshButRefusing(reading.rows).map((r) => r.name)).toEqual(['leaky'])
  })

  it('publishes no rate anywhere in the reading', () => {
    const reading = readCollectorDelivery([row({ refusedRows: 3, deliveredRows: 9 })])
    const serialised = JSON.stringify(reading)
    expect(serialised).not.toMatch(/%/)
    expect(serialised).not.toMatch(/ratio|rate|百分比/i)
    expect(NO_RATE_NOTE).toContain('不算比率')
  })

  it('carries dropped events without confusing them with refused rows', () => {
    const reading = readCollectorDelivery([row({ droppedEvents: 7, refusedRows: 2 })])
    if (reading.state !== 'reporting') throw new Error('expected rows')
    expect(reading.rows[0].dropped).toBe('7 行')
    expect(reading.rows[0].refused).toBe('2 行')
    expect(reading.rows[0].dropped).not.toBe(reading.rows[0].refused)
  })
})
