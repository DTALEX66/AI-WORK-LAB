/**
 * Contract: the resume cursor is the browser's, and the app must not throw it away.
 *
 * The sidecar answers `Last-Event-ID` with either the gap or a named `resync_required`
 * (`tests/workflow-assistance/test_sidecar_sse_reconnect_replays_the_gap.py` proves the server half). The
 * browser implements the request half: `EventSource` reconnects on its own and sends the last `id:` it saw.
 * What the client had to stop doing was DESTROY that knowledge — `api.ts` reset its local cursor to `null`
 * on every error, which also made `onReconnect` unreachable at exactly the moment a reconnect was happening,
 * and left the first `open` handler firing on every subsequent one with no way to tell them apart.
 *
 * `onOpen` and `onReconnect` are therefore mutually exclusive by construction, and the surface keeps its
 * conservative re-read on each — one re-read per open, never two.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { openEventStream } from './api'

class FakeEventSource {
  static instances: FakeEventSource[] = []
  listeners: Record<string, Array<(ev: any) => void>> = {}
  lastEventId: string | null = null
  closed = false
  constructor(public url: string) { FakeEventSource.instances.push(this) }
  addEventListener(name: string, handler: (ev: any) => void) {
    (this.listeners[name] ||= []).push(handler)
  }
  close() { this.closed = true }
  emit(name: string, data = '', lastEventId: string | null = null) {
    // A browser sets the source's cursor from the frame's id field, and hands the frame its own copy.
    if (lastEventId !== null) this.lastEventId = lastEventId
    const frame = { type: name, data, lastEventId }
    for (const handler of this.listeners[name] || []) handler(frame)
  }
  open() { this.emit('open') }
  error() { this.emit('error') }
}

function stubEventSource() {
  FakeEventSource.instances = []
  vi.stubGlobal('EventSource', FakeEventSource)
}

const source = () => FakeEventSource.instances[FakeEventSource.instances.length - 1] as unknown as FakeEventSource

describe('SSE resume cursor', () => {
  beforeEach(() => stubEventSource())
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

  it('treats the first open as an open and every later one as a reconnect carrying the cursor', () => {
    const onOpen = vi.fn()
    const onReconnect = vi.fn()
    openEventStream({ onEvent: vi.fn(), onOpen, onReconnect }, 'http://127.0.0.1:1/api/v1/events')
    expect(FakeEventSource.instances).toHaveLength(1)

    source().open()
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onReconnect).not.toHaveBeenCalled()

    source().emit('snapshot', JSON.stringify({ schemaVersion: 'workflow/snapshot/v3' }), '17')
    source().open()
    expect(onOpen).toHaveBeenCalledTimes(1)
    expect(onReconnect).toHaveBeenCalledTimes(1)
    expect(onReconnect).toHaveBeenCalledWith('17')

    source().open()
    expect(onReconnect).toHaveBeenCalledTimes(2)
  })

  it('reports an interruption without closing the stream, because closing forfeits the resume', () => {
    // This is the fault that would actually break reconnection: a handler that "cleans up" on error kills
    // the browser's automatic retry and the cursor it carries. The client's job on error is to stop claiming
    // LIVE and to leave the socket alone.
    const onReconnect = vi.fn()
    const onError = vi.fn()
    openEventStream({ onEvent: vi.fn(), onOpen: vi.fn(), onError, onReconnect },
                    'http://127.0.0.1:1/api/v1/events')
    source().open()
    source().emit('observed', '{}', '41')
    source().error()
    expect(onError).toHaveBeenCalledTimes(1)
    expect(source().closed).toBe(false)
    source().open()
    expect(onReconnect).toHaveBeenCalledTimes(1)
    expect(onReconnect).toHaveBeenCalledWith('41')
  })

  it('reads the browser cursor when the frame carried no id of its own', () => {
    // EventSource.lastEventId is what actually goes back in the Last-Event-ID header; the local mirror is a
    // convenience. If a frame arrives without an id, the mirror must not become the authority.
    const onReconnect = vi.fn()
    openEventStream({ onEvent: vi.fn(), onOpen: vi.fn(), onReconnect }, 'http://127.0.0.1:1/api/v1/events')
    source().open()
    const es = source()
    es.lastEventId = '88'
    es.emit('heartbeat', '{}', null)
    es.open()
    expect(onReconnect).toHaveBeenCalledWith('88')
  })

  it('routes resync frames to the caller and counts them as carrying a cursor', () => {
    const onResync = vi.fn()
    const onReconnect = vi.fn()
    openEventStream({ onEvent: vi.fn(), onOpen: vi.fn(), onResync, onReconnect },
                    'http://127.0.0.1:1/api/v1/events')
    source().open()
    source().emit('resync_required', JSON.stringify({ reason: 'history_gap', revision: 9 }), '9')
    expect(onResync).toHaveBeenCalledTimes(1)
    source().open()
    expect(onReconnect).toHaveBeenCalledWith('9')
  })

  it('does not treat a heartbeat as an event that costs a snapshot read', () => {
    const onEvent = vi.fn()
    const onHeartbeat = vi.fn()
    openEventStream({ onEvent, onHeartbeat }, 'http://127.0.0.1:1/api/v1/events')
    source().open()
    source().emit('heartbeat', '{}', '5')
    expect(onHeartbeat).toHaveBeenCalledTimes(1)
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('never claims a stream when no events url is authoritative', () => {
    const onError = vi.fn()
    const close = openEventStream({ onEvent: vi.fn(), onError }, '')
    expect(onError).toHaveBeenCalledTimes(1)
    expect(FakeEventSource.instances).toHaveLength(0)
    expect(() => close()).not.toThrow()
  })
})
