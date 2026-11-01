// U03 (2026-10-07) step 2: the render-level truth contracts that only the
// retired static surface pinned (`apps/observer/tests/test_render_v3.js`,
// 19 assertions) re-anchored to mounted production components. Each title names
// the legacy assertion it replaces, so retiring `web/` cannot delete a truth
// test with it. See apps/observer/parity-matrix-u03.md for the per-assertion map
// (4 COVERED by existing titles, 5 LEGACY-ONLY, 10 OPEN — the ten collapse to
// the six properties pinned here).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { TokenPanel } from '@/components/dashboard/TokenPanel'
import { ProjectPanel } from '@/components/dashboard/ProjectPanel'
import { OverviewView } from '@/views/OverviewView'
import { CompactHUD } from '@/views/CompactHUD'
import { useLiveSnapshot } from '@/lib/api'
import { mkProject, mkSnap } from '@/test/snapshotFixture'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

// B10 `.panel.kpi` cards are (strong.kpi-number, small label) pairs.
function kpiValue(label: string): string {
  const card = Array.from(document.querySelectorAll('.panel.kpi'))
    .find((k) => (k.querySelector('small')?.textContent ?? '') === label)
  return card?.querySelector('.kpi-number')?.textContent ?? ''
}

describe('U03 step 2 — render_v3 truth contracts mounted on the production tree', () => {
  it('legacy "project surface keeps canonical registry and local Git facts": the panel renders the real registry identity, platform, execution count, branch@sha and dirty count', () => {
    render(<ProjectPanel snap={mkSnap()} />)
    expect(screen.getByText('WORK-LAB')).toBeTruthy()
    expect(screen.getByText('codex · 2 执行 · 91k ESTIMATED')).toBeTruthy()
    // Both registry entries render (the panel lists up to 8, not one), and they
    // share the same observed git facts here — so the assertions count them.
    expect(screen.getAllByText('main@abc1234')).toHaveLength(2)
    expect(screen.getAllByText('脏 3')).toHaveLength(2)
    expect(screen.getAllByText('ACTIVE')).toHaveLength(2)
    // 2 of the registry, both rendered — the panel does not truncate to one card
    expect(screen.getByText('2 个 · 真实')).toBeTruthy()
    expect(screen.getByText('DESIGN-LAB')).toBeTruthy()
  })

  it('legacy "CC2: project card shows platform/git/status": an UNOBSERVED worktree is never shown as 干净', () => {
    const unobserved = mkSnap({
      projects: [mkProject({ git: { ...mkProject().git, dirtyCount: null } })],
    })
    render(<ProjectPanel snap={unobserved} />)
    expect(screen.getByText('脏 UNKNOWN')).toBeTruthy()
    expect(screen.queryByText('干净')).toBeNull()

    // The two observed states still read correctly — UNKNOWN is not a catch-all.
    render(<ProjectPanel snap={mkSnap({ projects: [mkProject({ git: { ...mkProject().git, dirtyCount: 0 } })] })} />)
    expect(screen.getByText('干净')).toBeTruthy()
    render(<ProjectPanel snap={mkSnap({ projects: [mkProject({ git: { ...mkProject().git, dirtyCount: 7 } })] })} />)
    expect(screen.getByText('脏 7')).toBeTruthy()
  })

  it('legacy "token dashboard renders real tokens only" + "CC2: telemetry renders real tokens": real tokenSummary renders its real figures, and no cache-hit rate is invented (v3 has no cache field)', () => {
    render(<TokenPanel snap={mkSnap()} />)
    expect(screen.getByText('64k')).toBeTruthy()
    expect(screen.getByText('27k')).toBeTruthy()
    expect(screen.getByText('91k')).toBeTruthy()
    expect(screen.getByText('质量 ESTIMATED')).toBeTruthy()
    // v3 TokenSummary is input/output/total/costQuality only.
    expect(screen.queryByText(/命中率|cacheHit|缓存/)).toBeNull()
  })

  it('legacy "token dashboard empty when no sample" + "task and usage sections appear only when canonical samples exist": a snapshot without token data draws no bar and no zero', () => {
    const noTokens = mkSnap({
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
    })
    render(<TokenPanel snap={noTokens} />)
    expect(screen.getByText(/无 token 数据 · 快照已接入但 token 未知/)).toBeTruthy()
    expect(screen.getAllByText('UNKNOWN').length).toBeGreaterThanOrEqual(3)
    // The bar needs a real source: with no token figure there is no progressbar.
    expect(document.querySelector('[role="progressbar"], .progress, progress')).toBeNull()
  })

  it('legacy "metric cards render real data only": the overview KPI strip renders the snapshot figures, not placeholders', () => {
    render(<OverviewView snap={mkSnap()} source="live" live={true} />)
    expect(kpiValue('项目')).toBe('2')
    expect(kpiValue('Token')).toBe('91k')
    expect(kpiValue('活跃执行')).toBe('0')
    expect(kpiValue('数据源')).toBe('LIVE')
    // and the metric row keeps the real coverage triple
    expect(screen.getByText('3/4')).toBeTruthy()
  })

  it('legacy "connection strip reports the real sidecar/event state without 0/0 coverage": an absent coverage triple reads 覆盖 UNKNOWN, never 0/0', () => {
    const noCoverage = mkSnap({ coverage: { numerator: null, denominator: null, scope: null } })
    render(<CompactHUD snap={noCoverage} live={true} />)
    expect(screen.getByText('覆盖 UNKNOWN')).toBeTruthy()
    expect(screen.queryByText('覆盖 0/0')).toBeNull()
    expect(screen.getAllByText('LIVE').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('rev 11')).toBeTruthy()

    // A measured 0/0 is data, not absence, and must still be shown as a number.
    render(<CompactHUD snap={mkSnap({ coverage: { numerator: 0, denominator: 0, scope: 'collectors' } })} live={false} />)
    expect(screen.getByText('覆盖 0/0')).toBeTruthy()
  })

  it('legacy "unsupported execution/CI/governance fields never become cards": no surface metric exists for fields the v3 snapshot does not carry', () => {
    // No word boundaries: `textContent` concatenates the label and its value, so
    // a `\bCPU\b` needle silently misses a real `CPU11` box (the first version of
    // this assertion passed while an injected CPU metric card stayed green).
    const fabricated = /CPU|GPU|内存|显存|磁盘|QPS|模型数|每秒请求/
    render(<OverviewView snap={mkSnap()} source="live" live={true} />)
    expect(document.body.textContent ?? '').not.toMatch(fabricated)
    cleanup()
    render(<CompactHUD snap={mkSnap()} live={true} />)
    expect(document.body.textContent ?? '').not.toMatch(fabricated)
  })

  it('legacy "last-good becomes visibly OFFLINE when the EventSource transport fails": a failed read stops the LIVE claim and keeps the retained projection', async () => {
    const first = mkSnap()
    let calls = 0
    vi.stubGlobal('fetch', vi.fn(async () => {
      calls += 1
      return calls === 1
        ? { ok: true, status: 200, json: async () => first }
        : { ok: false, status: 503, json: async () => ({}) }
    }))
    // A controllable EventSource stand-in: the production hook subscribes, and the
    // stream simply never delivers.
    vi.stubGlobal('EventSource', class {
      addEventListener() {}
      close() {}
      onerror = null
    })

    function Harness() {
      const { snap, live, error } = useLiveSnapshot(20)
      return <CompactHUD snap={snap} live={live} error={error} />
    }
    render(<Harness />)

    // The first transport word has to clear the subscription before the test can fail the transport, so it
    // waits on rendering. Measured 2026-07-12: with the default 1s patience this assertion failed under
    // full-suite load (63 files, vitest reporting ~348s of environment time) while passing standalone --
    // a timing artefact, not a truth-contract failure. The OFFLINE wait below already names 2000ms;
    // this one now states the same budget instead of relying on the default.
    //
    // The word is UNVERIFIED, not LIVE: jsdom has no `?api=`, so the runtime descriptor is the
    // non-authoritative preview fallback and `useLiveSnapshot` keeps `live:false`. Repeating the payload's
    // own LIVE word from a source this surface does not trust is exactly what `transportTruth` forbids.
    await waitFor(() => expect(screen.getAllByText('UNVERIFIED').length).toBeGreaterThanOrEqual(1), { timeout: 2000 })
    expect(screen.getByText('覆盖 3/4')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy() // the retained project count is real data

    // The read path then fails: the HUD must stop calling itself LIVE while the
    // last-good projection stays on screen (no wipe, no fabricated zero).
    await waitFor(() => expect(screen.getAllByText('OFFLINE').length).toBeGreaterThanOrEqual(1), { timeout: 2000 })
    expect(screen.queryByText('LIVE')).toBeNull()
    expect(screen.getByText('2')).toBeTruthy()
    expect(screen.getByText('覆盖 3/4')).toBeTruthy()
    expect(calls).toBeGreaterThan(1)
  })

  it('the alert chip has three states: with no data source it reads UNKNOWN, not a green "no alerts"', () => {
    // The panel body already refused to say "all clear" without a snapshot
    // (保持 UNKNOWN，不伪造「全部正常」), but the status chip counted zero alerts from
    // an absent snapshot and painted it green — the two halves disagreed.
    render(<OverviewView snap={null} source="stale" live={false} />)
    expect(screen.getByText('告警状态 UNKNOWN')).toBeTruthy()
    expect(screen.queryByText('无告警信号')).toBeNull()
    cleanup()
    render(<OverviewView snap={mkSnap()} source="live" live={true} />)
    expect(screen.getByText('无告警信号')).toBeTruthy()
    cleanup()
    render(<OverviewView snap={mkSnap({ ci: [{ runId: 'r1', workflow: 'gate', headSha: 'abc', status: 'completed', conclusion: 'failure', sourceRef: null }] })} source="live" live={true} />)
    expect(screen.getByText('1 条告警信号')).toBeTruthy()
    expect(screen.queryByText('无告警信号')).toBeNull()
  })
})
