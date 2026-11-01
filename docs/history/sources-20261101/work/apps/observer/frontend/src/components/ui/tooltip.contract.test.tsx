/** The refusal must be readable without a mouse.
 *
 * `disabled: pointer-events-none` plus a native `disabled` button means the control cannot be focused,
 * and the tooltip only revealed on `group-hover` — so the app's own contract ("a disabled action
 * explains why") held for a mouse and silently failed for a keyboard. Measured 2026-10-07 by rendering
 * all 21 registry lanes: four disabled write-actions existed (新建工作流, 运行, 保存并发布 and one node
 * op), and none of their reasons could be reached by Tab.
 */
import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'

import { Tooltip } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'

const REASON = '工作流契约（workflows[]）未接入 — 无真实创建入口'

function tipClass(container: HTMLElement): string {
  return container.querySelector('[role="tooltip"]')?.className ?? ''
}

describe('tooltip refusal contract', () => {
  it('reveals on keyboard focus as well as hover', () => {
    const { container } = render(
      <Tooltip text={REASON}><Button variant="ghost">新建工作流</Button></Tooltip>,
    )
    const cls = tipClass(container)
    expect(cls).toContain('group-hover/tt:opacity-100')
    expect(cls, 'the reason would be mouse-only').toContain('group-focus-within/tt:opacity-100')
  })

  it('takes the tab stop itself when it hides a disabled control', () => {
    // the call-site shape: a positioning span between the tooltip and the button
    const { container } = render(
      <Tooltip text={REASON}><span><Button disabled variant="primary">新建工作流</Button></span></Tooltip>,
    )
    const wrapper = container.querySelector('[aria-label]' ) as HTMLElement
    expect(wrapper.getAttribute('tabindex'), 'a disabled action with no focusable route to its reason')
      .toBe('0')
    expect(wrapper.getAttribute('role')).toBe('note')
    expect(wrapper.textContent).toContain('新建工作流')
  })

  it('does not add a tab stop when the control is already reachable', () => {
    const { container } = render(
      <Tooltip text={REASON}><Button variant="ghost">新建工作流</Button></Tooltip>,
    )
    const wrapper = container.querySelector('[aria-label]') as HTMLElement
    expect(wrapper.hasAttribute('tabindex'), 'every tooltip became a tab stop; the keyboard tour is polluted')
      .toBe(false)
    expect(wrapper.hasAttribute('role')).toBe(false)
  })

  it('carries the reason in the accessible name, not only in the visual tip', () => {
    const { container } = render(
      <Tooltip text={REASON}><Button disabled>新建工作流</Button></Tooltip>,
    )
    const wrapper = container.querySelector('[aria-label]') as HTMLElement
    expect(wrapper.getAttribute('aria-label')).toBe(REASON)
    expect(container.querySelector('[role="tooltip"]')?.textContent).toBe(REASON)
  })
})
