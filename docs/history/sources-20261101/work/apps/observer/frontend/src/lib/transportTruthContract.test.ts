// U03 step 3: the read-only TRANSPORT contracts that only the retired static
// surface pinned (apps/observer/tests/test_read_only_surface.js — measured at 24
// assertions, 17 t() + 7 asyncTest()). Each title names the legacy assertion it
// replaces. These are the OPEN rows that could produce a false impression: an
// untrusted injected endpoint, a cached or legacy payload read as current, an
// out-of-order projection replacing newer facts, a heartbeat turning into a read
// storm, and a corrupt frame leaving a stale LIVE claim on screen.
import { describe, it, expect, afterEach, vi } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import {
  isTrustedObserverEndpoint, loadRuntimeDescriptor, parseSnapshotPayload, fetchSnapshot,
  useLiveSnapshot,
} from '@/lib/api'
import type { SnapshotV3 } from '@/types'

const TRUSTED_SNAPSHOT = 'http://127.0.0.1:61867/api/v1/snapshot'

function setUrl(search: string) {
  window.history.replaceState(null, '', search || window.location.pathname)
}

function mkV3(revision: number, transportState: SnapshotV3['transport']['transportState'] = 'LIVE'): SnapshotV3 {
  return {
    schemaVersion: 'workflow/snapshot/v3',
    revision,
    generatedAt: '2026-10-07T09:12:33Z',
    sourceWatermark: '2026-10-07T09:12:30Z',
    transport: { transportState, freshnessState: 'FRESH', connectedSince: null, eventsUrl: 'http://evil.example.com/api/v1/events' },
    coverage: { numerator: 3, denominator: 4, scope: 'collectors' },
    governance: { state: 'CLEAN', families: {
      rules: { state: 'CLEAN', current: null, drift: 0 }, skills: { state: 'CLEAN', current: null, drift: 0 },
      memory: { state: 'UNKNOWN', current: null, drift: null }, adapters: { state: 'CLEAN', current: null, drift: 0 } } },
    workspace: {},
    projects: [],
    executions: [],
    tasks: {},
    tokenSummary: { inputTokens: 64391, outputTokens: 26821, totalTokens: 91212, costQuality: 'EXACT' },
    git: { localSha: 'abc1234', remoteSha: 'abc1234', ciSha: 'abc1234', matchState: 'MATCH' },
    ci: [],
    sourceRefs: [],
  }
}

interface Frame { type: string; data?: string; lastEventId?: string | null }

class FakeEventSource {
  static instances: FakeEventSource[] = []
  listeners: Record<string, Array<(ev: Frame) => void>> = {}
  closed = false
  constructor(public url: string) { FakeEventSource.instances.push(this) }
  addEventListener(name: string, fn: (ev: Frame) => void) {
    (this.listeners[name] ||= []).push(fn)
  }
  close() { this.closed = true }
  emit(name: string, data = '', lastEventId: string | null = null) {
    const frame: Frame = { type: name, data, lastEventId }
    for (const fn of this.listeners[name] || []) fn(frame as unknown as MessageEvent)
  }
  boundEvents(): string[] { return Object.keys(this.listeners) }
}

function stubEventSource() {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
}

function respond(value: unknown, ok = true) {
  return ok ? { ok: true, status: 200, json: async () => value }
    : { ok: false, status: 503, json: async () => ({}) }
}

function mountHook() {
  return renderHook(() => useLiveSnapshot(100000))
}

afterEach(() => {
  setUrl('')
  vi.unstubAllGlobals()
})

describe('U03 step 3 — read-only transport contracts re-anchored to api.ts', () => {
  it('legacy "snapshot endpoint accepts only explicit loopback read-only URL (v3)": https, external hosts, credentials, an added query and non-/api/v1 paths are all refused', () => {
    expect(isTrustedObserverEndpoint(TRUSTED_SNAPSHOT)).toBe(true)
    expect(isTrustedObserverEndpoint('http://localhost:61867/api/v1/events')).toBe(true)
    expect(isTrustedObserverEndpoint('http://[::1]:61867/api/v1/snapshot')).toBe(true)
    expect(isTrustedObserverEndpoint('https://127.0.0.1:61867/api/v1/snapshot')).toBe(false)
    expect(isTrustedObserverEndpoint('http://evil.example.com/api/v1/snapshot')).toBe(false)
    expect(isTrustedObserverEndpoint('http://127.0.0.1:61867/api/v1/snapshot?write=1')).toBe(false)
    expect(isTrustedObserverEndpoint('http://user:pw@127.0.0.1:61867/api/v1/snapshot')).toBe(false)
    expect(isTrustedObserverEndpoint('http://127.0.0.1:61867/api/dashboard')).toBe(false)
    expect(isTrustedObserverEndpoint('not-a-url')).toBe(false)

    // An untrusted injected endpoint is refused outright: it is never used, and it
    // never makes the descriptor authoritative.
    setUrl('?api=' + encodeURIComponent('http://evil.example.com/api/v1/snapshot'))
    const d = loadRuntimeDescriptor()
    expect(d.authoritative).toBe(false)
    expect(d.source).toBe('static-preview')
    expect(d.snapshotUrl).not.toContain('evil.example.com')
    expect(isTrustedObserverEndpoint(d.snapshotUrl)).toBe(true)
  })

  it('legacy "api layer never writes; only GET fetch exists" + "snapshot fetch is explicitly cache-bypassed": the read is GET with cache:no-store', async () => {
    const seen: Array<{ url: string; init?: RequestInit }> = []
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      seen.push({ url, init })
      return respond(mkV3(1))
    }))
    expect(await fetchSnapshot()).not.toBeNull()
    expect(seen).toHaveLength(1)
    expect((seen[0].init?.method ?? 'GET')).toBe('GET')
    expect(seen[0].init?.cache).toBe('no-store')
    expect(isTrustedObserverEndpoint(seen[0].url)).toBe(true)
  })

  it('legacy "snapshot fetch rejects legacy and partial LIVE success payloads": the payload is validated structurally before it is ever typed', () => {
    expect(parseSnapshotPayload(mkV3(3))?.revision).toBe(3)
    const v2 = { ...mkV3(3), schemaVersion: 'workflow/snapshot/v2' } as unknown as SnapshotV3
    expect(parseSnapshotPayload(v2)).toBeNull()
    const modeOnly = { mode: 'LIVE', summary: {} }
    expect(parseSnapshotPayload(modeOnly)).toBeNull()
    const noCoverage = JSON.parse(JSON.stringify(mkV3(3))) as Record<string, unknown>
    delete noCoverage.coverage
    expect(parseSnapshotPayload(noCoverage)).toBeNull()
    expect(parseSnapshotPayload({ ...mkV3(3), revision: '3' })).toBeNull()
    expect(parseSnapshotPayload(null)).toBeNull()
    expect(parseSnapshotPayload([])).toBeNull()
    expect(parseSnapshotPayload('snapshot')).toBeNull()

    // A 200 response carrying a rejected body is a read failure, not a render.
    vi.stubGlobal('fetch', vi.fn(async () => respond({ mode: 'LIVE' })))
    return expect(fetchSnapshot()).resolves.toBeNull()
  })

  it('legacy "state rejects an out-of-order lower-revision projection": a delayed older revision never replaces newer facts on screen', async () => {
    setUrl('?api=' + encodeURIComponent(TRUSTED_SNAPSHOT))
    stubEventSource()
    vi.stubGlobal('fetch', vi.fn(async () => respond(null, false)))
    const { result, unmount } = mountHook()
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const es = FakeEventSource.instances[0]

    es.emit('snapshot', JSON.stringify(mkV3(9)))
    await waitFor(() => expect(result.current.snap?.revision).toBe(9))
    expect(result.current.live).toBe(true)

    // A response generated before rev 9 but delivered late must lose.
    es.emit('snapshot', JSON.stringify(mkV3(4)))
    await waitFor(() => expect(result.current.error).toMatch(/乱序/))
    expect(result.current.snap?.revision).toBe(9)
    unmount()
    void act(() => {})
  })

  it('legacy "rejected lower revision cannot rotate the EventSource endpoint": the subscribed URL comes from the descriptor, never from a payload field', async () => {
    stubEventSource()
    vi.stubGlobal('fetch', vi.fn(async () => respond(null, false)))
    const { unmount } = mountHook()
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const es = FakeEventSource.instances[0]
    expect(es.url).toMatch(/^http:\/\/(127\.0\.0\.1|localhost):61867\/api\/v1\/events$/)

    // mkV3 carries an external eventsUrl — it must not open a second stream.
    es.emit('snapshot', JSON.stringify(mkV3(2)))
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    expect(FakeEventSource.instances[0].url).toBe(es.url)
    unmount()
  })

  it('legacy "v3 display mode cannot override the backend transport verdict" + "bundled snapshot is always rendered stale rather than live": a non-authoritative source can never make the surface LIVE', async () => {
    stubEventSource()
    vi.stubGlobal('fetch', vi.fn(async () => respond(null, false)))
    // No ?api= at all -> the static-preview fallback (authoritative:false).
    const a = mountHook()
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    FakeEventSource.instances[0].emit('snapshot', JSON.stringify(mkV3(1)))
    await waitFor(() => expect(a.result.current.snap?.revision).toBe(1))
    expect(a.result.current.live).toBe(false)
    expect(a.result.current.source).toBe('static-preview')
    a.unmount()

    // The identical payload from an authoritative endpoint is LIVE.
    FakeEventSource.instances = []
    setUrl('?api=' + encodeURIComponent(TRUSTED_SNAPSHOT))
    const b = mountHook()
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    FakeEventSource.instances[0].emit('snapshot', JSON.stringify(mkV3(1)))
    await waitFor(() => expect(b.result.current.live).toBe(true))
    b.unmount()
  })

  it('legacy "malformed SSE payload degrades without waiting for a transport reopen": a corrupt frame degrades at once and keeps the last-good projection', async () => {
    setUrl('?api=' + encodeURIComponent(TRUSTED_SNAPSHOT))
    stubEventSource()
    vi.stubGlobal('fetch', vi.fn(async () => respond(null, false)))
    const { result, unmount } = mountHook()
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const es = FakeEventSource.instances[0]

    es.emit('snapshot', JSON.stringify(mkV3(5)))
    await waitFor(() => expect(result.current.live).toBe(true))

    es.emit('snapshot', '{ this is not json')
    await waitFor(() => expect(result.current.error).toMatch(/不合 v3 结构/))
    expect(result.current.live).toBe(false)
    expect(result.current.snap?.revision).toBe(5)
    // An untyped `message` frame carries no projection and must not degrade.
    es.emit('message', 'keep-alive')
    expect(result.current.error).toMatch(/不合 v3 结构/)
    unmount()
  })

  it('legacy "heartbeat avoids snapshot GET and refresh bursts are coalesced": heartbeat frames cost no read, and a burst collapses to one in-flight read plus one follow-up', async () => {
    setUrl('?api=' + encodeURIComponent(TRUSTED_SNAPSHOT))
    stubEventSource()

    // Part A — a heartbeat is proof of life only. With nothing in flight, it must
    // not add a read.
    let calls = 0
    vi.stubGlobal('fetch', vi.fn(async () => { calls += 1; return respond(mkV3(calls + 10)) }))
    const settled = mountHook()
    await waitFor(() => expect(calls).toBe(1))
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const esA = FakeEventSource.instances[0]
    esA.emit('heartbeat', '')
    await act(async () => { await Promise.resolve() })
    expect(calls).toBe(1)
    settled.unmount()

    // Part B — a burst arriving while one read is in flight is served by ONE
    // follow-up, not one read per event.
    calls = 0
    FakeEventSource.instances = []
    let release: (() => void) | null = null
    vi.stubGlobal('fetch', vi.fn(async () => {
      calls += 1
      await new Promise<void>((resolve) => { release = resolve })
      return respond(mkV3(calls + 10))
    }))
    const { unmount } = mountHook()
    await waitFor(() => expect(calls).toBe(1))
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const es = FakeEventSource.instances[0]
    es.emit('resync_required', '')
    es.emit('resync_required', '')
    es.emit('observed', '')
    await waitFor(() => expect(calls).toBe(1))
    expect(release).not.toBeNull()
    ;(release as unknown as () => void)()
    await waitFor(() => expect(calls).toBe(2))
    unmount()
  })

  it('legacy "onOpen refreshes the read-only snapshot after sidecar reconnect": a (re)connect schedules a canonical re-read', async () => {
    stubEventSource()
    let calls = 0
    vi.stubGlobal('fetch', vi.fn(async () => { calls += 1; return respond(mkV3(calls)) }))
    const { unmount } = mountHook()
    await waitFor(() => expect(calls).toBe(1))
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const es = FakeEventSource.instances[0]
    es.emit('open')
    await waitFor(() => expect(calls).toBe(2))
    expect(es.boundEvents()).toEqual(expect.arrayContaining(['open', 'snapshot', 'message', 'heartbeat', 'observed', 'resync_required', 'error']))
    unmount()
  })

  it('legacy "state last-good survives refresh error (never clears to zero)" + "refresh errors preserve string-valued v3 quality fields without throwing": a failed refresh keeps the retained projection and its quality labels', async () => {
    setUrl('?api=' + encodeURIComponent(TRUSTED_SNAPSHOT))
    stubEventSource()
    let failing = false
    vi.stubGlobal('fetch', vi.fn(async () => {
      if (failing) return respond(null, false)
      return respond(mkV3(7))
    }))
    const { result, unmount } = mountHook()
    await waitFor(() => expect(result.current.snap?.revision).toBe(7))
    expect(result.current.live).toBe(true)
    const retained = result.current.snap

    // Force a re-read (the interval is deliberately out of reach at this scale).
    failing = true
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    FakeEventSource.instances[0].emit('resync_required', '')
    await waitFor(() => expect(typeof result.current.error).toBe('string'))
    expect(result.current.error).toMatch(/快照获取失败/)
    expect(result.current.source).toBe('stale')
    expect(result.current.snap).toBe(retained)
    expect(result.current.snap?.tokenSummary.costQuality).toBe('EXACT')
    expect(result.current.snap?.git.matchState).toBe('MATCH')
    expect(result.current.snap?.governance.families.memory.state).toBe('UNKNOWN')
    expect(result.current.live).toBe(false)
    unmount()
  })

  it('legacy "last-good becomes visibly OFFLINE when the EventSource transport fails" + "SSE failure fences an older GET and preserves native reconnect": a stream error stops the LIVE claim at once, the source is never closed by us, and the next good read restores it', async () => {
    setUrl('?api=' + encodeURIComponent(TRUSTED_SNAPSHOT))
    stubEventSource()
    let failing = false
    vi.stubGlobal('fetch', vi.fn(async () => (failing ? respond(null, false) : respond(mkV3(8)))))
    const { result, unmount } = mountHook()
    await waitFor(() => expect(result.current.snap?.revision).toBe(8))
    expect(result.current.live).toBe(true)

    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1))
    const es = FakeEventSource.instances[0]
    es.emit('error')
    await waitFor(() => expect(result.current.error).toMatch(/事件流中断/))
    expect(result.current.live).toBe(false)
    // The hook must not close the EventSource on an error: the browser's own
    // reconnect is the transport, closing it would kill recovery.
    expect(es.closed).toBe(false)
    // The projection survives the transport error.
    expect(result.current.snap?.revision).toBe(8)

    // Recovery: the next successful read clears the failure without a wipe.
    failing = false
    es.emit('resync_required', '')
    await waitFor(() => expect(result.current.live).toBe(true))
    expect(result.current.error).toBeNull()
    unmount()
  })
})
