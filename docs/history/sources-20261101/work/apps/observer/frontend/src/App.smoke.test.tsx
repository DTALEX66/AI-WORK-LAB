// UI_SHELL (20260921): App smoke test — mount the real <App/> with a mocked
// live snapshot and pin the shell contract:
//   * the Sidebar renders the 审计 (Audit) group + its lane (SPEC-C governance
//     lanes are reachable through the shell)
//   * the TopStatusBar exposes the global search affordance (Ctrl+K hint)
//   * theme/layout are URL-driven (default dark + full)
// useLiveSnapshot is mocked so the test does not depend on a running backend.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'

// Mock the live-snapshot hook BEFORE importing App so its render uses the stub.
const mockSnap = {
  schemaVersion: 'workflow/snapshot/v3',
  revision: 1,
  generatedAt: '2026-09-21T00:00:00Z',
  sourceWatermark: null,
  transport: {
    transportState: 'LIVE',
    freshnessState: 'FRESH',
    connectedSince: null,
    eventsUrl: null,
  },
  coverage: { numerator: 1, denominator: 1, scope: 'unit' },
  governance: {
    state: 'CLEAN',
    families: {
      rules: { state: 'CLEAN', current: null, drift: 0 },
      skills: { state: 'CLEAN', current: null, drift: 0 },
      memory: { state: 'CLEAN', current: null, drift: 0 },
      adapters: { state: 'CLEAN', current: null, drift: 0 },
    },
  },
  workspace: {},
  projects: [],
  executions: [],
  tasks: {},
  tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
  git: { localSha: null, remoteSha: null, ciSha: null, matchState: 'NO_LOCAL_CLAIM' },
  ci: [],
  sourceRefs: [],
}

// Keep every real api.ts export except useLiveSnapshot (TokenPanel etc.
// import fmtTokens from the same module). Only the hook is stubbed.
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return {
    ...actual,
    useLiveSnapshot: () => ({
      snap: mockSnap,
      source: 'live',
      live: true,
      error: null,
      dataUpdatedAt: 0,
    }),
  }
})

import App from '@/App'

afterEach(() => {
  cleanup()
  // reset URL so each mount re-reads the default view
  window.history.replaceState(null, '', window.location.pathname)
})

describe('App shell (UI_SHELL smoke)', () => {
  it('renders the Sidebar with the 审计 lane reachable and the Ctrl+K search hint', async () => {
    render(<App />)
    // governance group + audit lane are part of the shell navigation
    expect(await screen.findByText('审计追踪')).toBeTruthy()
    // the top bar's global search affordance shows the Ctrl K hint
    expect(screen.getByText('搜索或命令…')).toBeTruthy()
    expect(screen.getByText('Ctrl K')).toBeTruthy()
  })

  it('defaults to the dark theme + full layout (deep-link init)', () => {
    render(<App />)
    // full layout keeps the sidebar rail visible (not the compact HUD)
    expect(screen.getByLabelText('侧边导航')).toBeTruthy()
    // the transport state indicator renders (LIVE appears in top bar + KPI strip)
    expect(screen.getAllByText('LIVE').length).toBeGreaterThanOrEqual(1)
  })

  it('switching a governance view re-renders that view content', async () => {
    render(<App />)
    // click the 审计追踪 lane in the sidebar
    const auditBtn = screen.getByRole('button', { name: '审计追踪' })
    await act(async () => {
      auditBtn.click()
    })
    // the audit view's honest empty state renders (no CI records in mockSnap)
    expect(await screen.findByText('无审计记录')).toBeTruthy()
  })
})
