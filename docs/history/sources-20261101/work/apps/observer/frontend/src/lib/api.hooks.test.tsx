// W06 (2026-10-17): the poll is a safety net once the stream is healthy, and an unchanged signature must not
// re-render. Both halves are asserted the way the defect was described -- by counting requests and by watching
// what the surface is asked to re-render -- not by reading the code.
//
// The descriptor is module-level state in api.ts, so the module is imported AFTER the config is planted;
// otherwise the hook would be built against the non-authoritative static-preview fallback and never open a
// stream. The stream itself is stubbed, not the hook: the real `openEventStream` runs and the test fires its
// listeners, so the health transitions under test are the production ones.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import type { SnapshotV3 } from '@/types'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  listeners: Record<string, ((ev: unknown) => void)[]> = {}
  lastEventId = ''
  constructor(public url: string) { FakeEventSource.instances.push(this) }
  addEventListener(type: string, fn: (ev: unknown) => void) {
    ;(this.listeners[type] ||= []).push(fn)
  }
  fire(type: string) { (this.listeners[type] || []).forEach((fn) => fn({ type, data: '' })) }
  close() {}
}

function snap(revision: number, transportState: SnapshotV3['transport']['transportState'] = 'LIVE'): SnapshotV3 {
  return {
    schemaVersion: 'workflow/snapshot/v3',
    revision,
    generatedAt: null,
    sourceWatermark: 'w1',
    transport: { transportState, freshnessState: 'FRESH', connectedSince: null, eventsUrl: null },
    coverage: { numerator: 1, denominator: 1, scope: 'x' },
    governance: { state: 'UNKNOWN' },
    tokenSummary: {},
    git: {},
    projects: [],
    executions: [],
  } as unknown as SnapshotV3
}

/** Load the hook against an authoritative descriptor, with the stream stubbed and fetch counted. */
async function loadHook(payloads: SnapshotV3[]) {
  vi.resetModules()
  vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource)
  ;(window as unknown as { __OBSERVER_CONFIG__?: { apiBase?: string } }).__OBSERVER_CONFIG__ = {
    apiBase: 'http://127.0.0.1:61867',
  }
  FakeEventSource.instances = []
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async () => {
    calls += 1
    return { ok: true, json: async () => payloads.shift() ?? snap(7) } as Response
  }))
  const mod = await import('@/lib/api')
  return { mod, count: () => calls }
}

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  ;(window as unknown as { __OBSERVER_CONFIG__?: unknown }).__OBSERVER_CONFIG__ = undefined
})

describe('W06 · read cadence', () => {
  it('stops re-reading the snapshot while a healthy stream keeps it fresh, and re-reads past the cap', async () => {
    const { mod, count } = await loadHook([snap(1), snap(1), snap(1), snap(1), snap(1), snap(1)])
    renderHook(() => mod.useLiveSnapshot(1000))
    await vi.advanceTimersByTimeAsync(0)
    expect(count()).toBe(1)                       // the mount read
    FakeEventSource.instances[0]?.fire('open')    // the stream says it is up
    await vi.advanceTimersByTimeAsync(0)
    const afterOpen = count()
    expect(afterOpen).toBe(2)                     // an event is a reason to read; a timer is not

    await vi.advanceTimersByTimeAsync(10000)      // ten timer periods inside the staleness cap
    expect(count()).toBe(afterOpen)               // every one of them skipped

    await vi.advanceTimersByTimeAsync(mod.MAX_STALENESS_MS)
    expect(count()).toBe(afterOpen + 1)           // the safety net fired, once
  })

  it('a stream error puts the timer back on duty', async () => {
    const { mod, count } = await loadHook([snap(1), snap(2), snap(3)])
    renderHook(() => mod.useLiveSnapshot(1000))
    await vi.advanceTimersByTimeAsync(0)
    FakeEventSource.instances[0]?.fire('open')
    await vi.advanceTimersByTimeAsync(0)
    const healthy = count()
    FakeEventSource.instances[0]?.fire('error')   // the stream dies
    await vi.advanceTimersByTimeAsync(3000)
    expect(count()).toBeGreaterThan(healthy)      // the fallback resumes immediately, not after the cap
  })
})

describe('W06 · re-render on change, not on read', () => {
  it('does not advance "updated at" while the signature is unchanged, and does when transport moves', async () => {
    const { mod } = await loadHook([snap(7), snap(7), snap(7, 'DELAYED'), snap(7, 'DELAYED')])
    const { result } = renderHook(() => mod.useLiveSnapshot(1000))
    // Two turns: the fetch promise has to settle and React has to flush the state it produces. A single
    // microtask turn is enough for the request count in the cadence test but not for the rendered value.
    await vi.advanceTimersByTimeAsync(0)
    await vi.advanceTimersByTimeAsync(0)
    const firstStamp = result.current.dataUpdatedAt
    expect(result.current.snap?.revision).toBe(7)

    await vi.advanceTimersByTimeAsync(1000)       // same revision, same transport/coverage
    await vi.advanceTimersByTimeAsync(0)          // let the read's state (there is none) flush
    expect(result.current.dataUpdatedAt).toBe(firstStamp)

    // Two more periods, so the third read is certainly in flight regardless of how the timer aligns.
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(1000)
    await vi.advanceTimersByTimeAsync(0)
    expect(result.current.snap?.transport.transportState).toBe('DELAYED')
    expect(result.current.dataUpdatedAt).not.toBe(firstStamp)
  })
})
