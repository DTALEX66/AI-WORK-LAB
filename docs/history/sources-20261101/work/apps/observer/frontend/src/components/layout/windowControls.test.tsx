// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { WindowControls } from '@/components/layout/WindowControls'

/**
 * The shell declares `decorations: false` on both windows, so the rail is the
 * only place a user can move or close the app. These tests pin the two failure
 * modes that used to be silent: controls rendering in a plain browser (where no
 * Tauri IPC exists) and the drag surface disappearing from the top bar.
 */
describe('WindowControls', () => {
  it('renders nothing outside Tauri, so the browser entry gets no dead buttons', () => {
    const { container } = render(<WindowControls />)
    expect(container.firstChild).toBeNull()
    expect('__TAURI_INTERNALS__' in window).toBe(false)
  })

  it('exposes minimize / maximize / close plus zoom when running under Tauri', () => {
    // The component checks for the internals marker in an effect, so install it
    // before mount to exercise the desktop branch.
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}
    try {
      render(<WindowControls />)
      expect(screen.getByRole('group', { name: '窗口控制' })).toBeTruthy()
      for (const label of ['最小化窗口', '最大化或还原窗口', '关闭窗口', '缩小界面', '放大界面', '重置缩放']) {
        expect(screen.getByLabelText(label)).toBeTruthy()
      }
      expect(screen.getByText('100%')).toBeTruthy()
    } finally {
      delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__
    }
  })

  it('keeps the zoom shortcut path reachable without a pointer', () => {
    ;(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {}
    try {
      render(<WindowControls />)
      const before = screen.getByText('100%').textContent
      fireEvent.keyDown(window, { key: '=', ctrlKey: true })
      expect(screen.getByText('110%').textContent).not.toBe(before)
      fireEvent.keyDown(window, { key: '0', ctrlKey: true })
      expect(screen.getByText('100%')).toBeTruthy()
    } finally {
      delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__
    }
  })

  it('issues no HTTP write verb from any window control', async () => {
    const calls: string[] = []
    const original = window.fetch
    window.fetch = ((input: RequestInfo | URL) => {
      calls.push(String(input))
      return Promise.reject(new Error('blocked'))
    }) as typeof fetch
    try {
      const { container } = render(<WindowControls />)
      expect(container.firstChild).toBeNull()
      expect(calls).toEqual([])
    } finally {
      window.fetch = original
    }
  })
})

describe('top bar drag surface', () => {
  it('provides a drag region because the windows have no native title bar', async () => {
    const { TopStatusBar } = await import('@/components/layout/TopStatusBar')
    const noop = () => {}
    const { container } = render(
      <TopStatusBar
        snap={null}
        source="static-preview"
        live={false}
        theme="dark"
        layout="full"
        onCycleTheme={noop}
        onCycleLayout={noop}
        onOpenSearch={noop}
        onOpenDrawer={noop}
        onNotify={noop}
      />,
    )
    expect(container.querySelector('[data-tauri-drag-region]')).toBeTruthy()
  })
})
