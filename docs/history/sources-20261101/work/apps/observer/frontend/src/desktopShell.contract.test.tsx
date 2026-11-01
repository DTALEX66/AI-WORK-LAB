/**
 * DESKTOP-ONLY SHELL CONTRACT (owner instruction 2026-10-07: 优先跑通全量执行桌面端电脑端
 * UI，先删除手机端其他端).
 *
 * The Observer ships one navigation surface: the B10 rail. The mobile drawer, its hamburger trigger
 * and its overlay are deleted. jsdom applies no media queries, so the width and configuration half
 * of this contract is asserted by tests/ci/test_desktop_only_shell.py against the CSS and the Tauri
 * window config; what a DOM can prove is that no drawer path is reachable any more.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'

import { Sidebar } from '@/components/layout/Sidebar'

afterEach(cleanup)

describe('desktop-only shell: the rail is the only navigation surface', () => {
  it('renders the rail and no overlay', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const rail = container.querySelector('aside.sidebar.sidebar-slot')
    expect(rail).not.toBeNull()
    expect(screen.getAllByLabelText('侧边导航')).toHaveLength(1)
    expect(container.querySelector('.mobile-nav')).toBeNull()
    expect(container.querySelectorAll('button[aria-label="打开导航"]')).toHaveLength(0)
    expect(container.querySelectorAll('button[aria-label="关闭导航"]')).toHaveLength(0)
  })

  it('selecting a lane moves selection and never needs a close step', () => {
    const seen: string[] = []
    render(<Sidebar activeView="overview" onSelect={(id) => seen.push(id)} />)
    const buttons = Array.from(document.querySelectorAll('.nav button'))
    expect(buttons.length).toBeGreaterThan(10)
    fireEvent.click(buttons[3])
    expect(seen).toHaveLength(1)
    expect(typeof seen[0]).toBe('string')
    expect(seen[0]).toBe(buttons[3].getAttribute('data-lane'))
  })
})
