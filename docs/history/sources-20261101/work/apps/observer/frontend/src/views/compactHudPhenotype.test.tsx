// 2026-10-18 · compact-HUD phenotype contracts.
//
// The visual pass must not soften a single truth rule: shares are derived from
// REPORTED project tokens, a null token never enters the denominator, a
// reported zero stays a zero, the session sparkline needs two real points, and
// a failed read stops the LIVE claim while keeping the retained projection.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { CompactHUD } from './CompactHUD'
import {
  appendTokenSample, buildHudProviders, fmtHudTokens, foldHudProviders, ringArc, type TokenSample,
} from './hudModel'
import { mkProject, mkSnap } from '@/test/snapshotFixture'

afterEach(cleanup)

function token(totalTokens: number | null) {
  return {
    inputTokens: totalTokens,
    outputTokens: null,
    totalTokens,
    costQuality: 'EXACT' as const,
  }
}

describe('compact HUD read model', () => {
  it('groups by agentPlatform and sums only reported totals', () => {
    const snap = mkSnap({
      projects: [
        mkProject({ projectId: 'a', agentPlatform: 'codex', token: token(100) }),
        mkProject({ projectId: 'b', agentPlatform: 'codex', token: token(null) }),
        mkProject({ projectId: 'c', agentPlatform: 'hermes', token: token(300) }),
        mkProject({ projectId: 'd', agentPlatform: null, token: token(null) }),
      ],
    })
    const providers = buildHudProviders(snap)
    expect(providers.map((p) => p.key)).toEqual(['hermes', 'codex', 'UNKNOWN'])

    const [hermes, codex, unknown] = providers
    expect(hermes.totalTokens).toBe(300)
    expect(hermes.shareLabel).toBe('75%')
    expect(hermes.unknownProjects).toBe(0)

    // 100 of the 400 REPORTED tokens; the null sibling is not a zero and its
    // absence can only make the true share larger, hence "≥".
    expect(codex.totalTokens).toBe(100)
    expect(codex.reportedProjects).toBe(1)
    expect(codex.unknownProjects).toBe(1)
    expect(codex.shareLabel).toBe('≥25%')

    expect(unknown.totalTokens).toBeNull()
    expect(unknown.shareLabel).toBe('—')
    expect(unknown.ringFraction).toBe(0)
  })

  it('keeps a reported zero as data, but refuses a 0/0 share', () => {
    const [zero] = buildHudProviders(mkSnap({ projects: [mkProject({ token: token(0) })] }))
    expect(zero.totalTokens).toBe(0)
    expect(zero.shareLabel).toBe('—')
    expect(zero.ringFraction).toBe(0)
  })

  it('a ring arc covers the requested fraction of the circumference', () => {
    const arc = ringArc(0.25, 42)
    expect(parseFloat(arc.dasharray.split(' ')[0])).toBeCloseTo(2 * Math.PI * 42 * 0.25, 1)
    expect(ringArc(0, 42).dasharray.startsWith('0 ')).toBe(true)
    expect(ringArc(Number.NaN, 42).dasharray.startsWith('0 ')).toBe(true)
  })

  it('the session series appends, corrects and refuses out-of-order or null reads', () => {
    let series = appendTokenSample([], mkSnap())
    expect(series).toHaveLength(1)
    expect(series[0]).toEqual({ revision: 11, total: 91212 })

    // A poll repeat of the same revision and total is not a new observation.
    const repeat = appendTokenSample(series, mkSnap())
    expect(repeat).toBe(series)

    // A corrected value for the same revision replaces the point.
    series = appendTokenSample(series, mkSnap({
      tokenSummary: { inputTokens: 1, outputTokens: 1, totalTokens: 92000, costQuality: 'EXACT' },
    }))
    expect(series).toHaveLength(1)
    expect(series[0].total).toBe(92000)

    expect(appendTokenSample(series, mkSnap({ revision: 10 }))).toBe(series)
    expect(appendTokenSample(series, mkSnap({
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
    }))).toBe(series)

    // The window is bounded, and the newest point is kept.
    let capped: TokenSample[] = []
    for (let revision = 1; revision <= 30; revision += 1) {
      capped = appendTokenSample(capped, mkSnap({ revision }))
    }
    expect(capped).toHaveLength(24)
    expect(capped[capped.length - 1]).toEqual({ revision: 30, total: 91212 })
  })

  it('folds the provider tail into one summary card without changing the shares', () => {
    const projects = Array.from({ length: 9 }, (_, i) => mkProject({
      projectId: 'p' + i,
      displayName: 'P' + i,
      agentPlatform: 'p' + i,
      token: token(100),
    }))
    const providers = buildHudProviders(mkSnap({ projects }))
    expect(providers).toHaveLength(9)

    const folded = foldHudProviders(providers)
    expect(folded).toHaveLength(3)
    const aggregate = folded[2]
    expect(aggregate.key).toBe('其他 7 个来源')
    expect(aggregate.aggregate).toBe(true)
    expect(aggregate.totalTokens).toBe(700)
    expect(aggregate.shareLabel).toBe('78%')
    // The top two cards are untouched; the summary accounts for the same 900.
    expect(folded.slice(0, 2).reduce((sum, p) => sum + (p.totalTokens ?? 0), 0) + 700).toBe(900)
  })

  it('keeps small card totals exact instead of rounding them up to "1k"', () => {
    expect(fmtHudTokens(700)).toBe('700')
    expect(fmtHudTokens(0)).toBe('0')
    expect(fmtHudTokens(null)).toBe('UNKNOWN')
    expect(fmtHudTokens(1_500_000_000)).toBe('1.50B')
    expect(fmtHudTokens(99_999_999_999_999)).toBe('100.00T')
  })
})

describe('CompactHUD phenotype', () => {
  it('renders the hero, the provider ring and the real facts', () => {
    render(<CompactHUD snap={mkSnap()} live={true} />)
    expect(screen.getByText('91,212')).toBeTruthy()
    expect(screen.getByText('份额 100%')).toBeTruthy()
    expect(screen.getByText('codex')).toBeTruthy()
    expect(screen.getByText('覆盖 3/4')).toBeTruthy()
    expect(screen.getByText('rev 11')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy()
    expect(document.querySelectorAll('.hud-ring-arc')).toHaveLength(1)
  })

  it('with no snapshot: UNKNOWN everywhere, no ring, no fabricated share', () => {
    render(<CompactHUD snap={null} live={false} />)
    expect(screen.getAllByText('UNKNOWN').length).toBeGreaterThan(0)
    expect(document.querySelectorAll('.hud-ring-arc')).toHaveLength(0)
    expect(screen.queryByText(/0%/)).toBeNull()
    expect(screen.getAllByText('数据源未接入').length).toBeGreaterThan(0)
  })

  it('with no reported project token: the ring paints nothing and says why', () => {
    const snap = mkSnap({
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
      projects: [mkProject({ token: token(null) })],
    })
    render(<CompactHUD snap={snap} live={true} />)
    const arc = document.querySelector('.hud-ring-arc')
    expect(arc).not.toBeNull()
    expect(arc?.getAttribute('stroke-dasharray')?.startsWith('0 ')).toBe(true)
    // Round caps paint a dot even on a zero-length dash, which would read as a
    // small nonzero share. An undefined share must paint nothing.
    expect(arc?.getAttribute('data-empty')).toBe('true')
    expect(screen.getByText(/未计入分母/)).toBeTruthy()
    expect(screen.queryByText(/0%/)).toBeNull()
  })

  it('draws a trend only after two distinct revisions', () => {
    const { rerender } = render(<CompactHUD snap={mkSnap()} live={true} />)
    expect(screen.getByText(/尚无趋势/)).toBeTruthy()
    expect(document.querySelector('.hud-spark-svg')).toBeNull()

    rerender(<CompactHUD
      snap={mkSnap({
        revision: 12,
        tokenSummary: { inputTokens: 70000, outputTokens: 50000, totalTokens: 120000, costQuality: 'EXACT' },
      })}
      live={true}
    />)
    expect(document.querySelector('.hud-spark-svg')).not.toBeNull()
    expect(screen.getByText('2 个修订')).toBeTruthy()
  })

  it('a failed read stops the LIVE claim but keeps the projection', () => {
    render(<CompactHUD snap={mkSnap()} live={false} error="read failed" />)
    expect(screen.getByText('OFFLINE')).toBeTruthy()
    expect(screen.queryByText('LIVE')).toBeNull()
    expect(screen.getByText('codex')).toBeTruthy()
    expect(screen.getByText('覆盖 3/4')).toBeTruthy()
  })

  it('a LIVE transport with stale sampling is not printed as a plain LIVE', () => {
    const snap = mkSnap({
      transport: { transportState: 'LIVE', freshnessState: 'STALE', connectedSince: null, eventsUrl: null },
    })
    const { container } = render(<CompactHUD snap={snap} live={true} />)
    expect(screen.getByText('LIVE · 采样已过期')).toBeTruthy()
    expect(screen.queryByText('LIVE')).toBeNull()
    expect(container.querySelector('.hud-phenotype')?.getAttribute('data-state')).toBe('waiting')
  })

  it('holding a snapshot while not reading is UNVERIFIED, not LIVE', () => {
    const { container } = render(<CompactHUD snap={mkSnap()} live={false} />)
    expect(screen.getByText('UNVERIFIED')).toBeTruthy()
    expect(screen.queryByText('LIVE')).toBeNull()
    expect(container.querySelector('.hud-phenotype')?.getAttribute('data-state')).toBe('unknown')
  })

  it('caps the ring row at three cards and names the folded sources', () => {
    const projects = Array.from({ length: 9 }, (_, i) => mkProject({
      projectId: 'p' + i,
      displayName: 'P' + i,
      agentPlatform: 'p' + i,
      token: token(100),
    }))
    const snap = mkSnap({
      projects,
      tokenSummary: { inputTokens: 600, outputTokens: 300, totalTokens: 900, costQuality: 'EXACT' },
    })
    const { container } = render(<CompactHUD snap={snap} live={true} />)
    expect(container.querySelectorAll('.hud-agent')).toHaveLength(3)
    expect(container.querySelectorAll('.hud-ring-arc')).toHaveLength(3)
    expect(screen.getByText('其他 7 个来源')).toBeTruthy()
    expect(screen.getByText('份额 78%')).toBeTruthy()
    expect(screen.getByText('摘要 3/9 · 派生视图')).toBeTruthy()
    expect(screen.getByText(/其余 7 个来源合并为一张摘要卡/)).toBeTruthy()
    expect(container.querySelector('.hud-agent[data-aggregate="true"]')).not.toBeNull()
  })

  it('shrinks the hero type for a very long total instead of overflowing its box', () => {
    const huge = mkSnap({
      tokenSummary: {
        inputTokens: 99_999_999_999_999,
        outputTokens: 0,
        totalTokens: 99_999_999_999_999,
        costQuality: 'EXACT',
      },
    })
    render(<CompactHUD snap={huge} live={true} />)
    const hero = screen.getByText('99,999,999,999,999')
    expect(hero.style.fontSize).toBe('23.3px')
  })
})
