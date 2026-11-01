import * as React from 'react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { Modal } from './modal'
import { Drawer } from './drawer'
import { Toaster, useToaster, TOAST_EXIT_MS } from './toast'

// M-3 (UI-CHECK-20261006): these overlays declared aria-modal without trapping
// Tab. A declared-but-unenforced modal contract is a defect, not a nicety: the
// keyboard user is told they are inside a dialog and then tabbed straight out of
// it into the surface behind the overlay.

describe("overlay focus trap", () => {
  it("Modal: moves focus inside on open and keeps Tab within the dialog", () => {
    const trigger = document.createElement('button')
    trigger.textContent = 'trigger'
    document.body.appendChild(trigger)
    trigger.focus()
    expect(document.activeElement).toBe(trigger)

    const { unmount } = render(
      <Modal open onClose={() => {}} title="对话框" footer={<button>确认</button>}>
        <button>面板内操作</button>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog.contains(document.activeElement)).toBe(true)

    // Tab from the LAST control must wrap back inside rather than leave.
    const inside = Array.from(dialog.querySelectorAll('button'))
    inside[inside.length - 1].focus()
    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(dialog.contains(document.activeElement)).toBe(true)

    // Shift+Tab from the FIRST control wraps to the last, still inside.
    inside[0].focus()
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true })
    expect(dialog.contains(document.activeElement)).toBe(true)

    unmount()
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it("Drawer: traps Tab and returns focus to the trigger on close", () => {
    const trigger = document.createElement('button')
    trigger.textContent = 'drawer-trigger'
    document.body.appendChild(trigger)
    trigger.focus()

    const onClose = vi.fn()
    const { rerender } = render(
      <Drawer open onClose={onClose} title="工作区">
        <button>抽屉内操作</button>
      </Drawer>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog.contains(document.activeElement)).toBe(true)
    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(dialog.contains(document.activeElement)).toBe(true)

    rerender(
      <Drawer open={false} onClose={onClose} title="工作区">
        <button>抽屉内操作</button>
      </Drawer>,
    )
    expect(document.activeElement).toBe(trigger)
    trigger.remove()
  })

  it("a control outside the open dialog is never the Tab target", () => {
    const outside = document.createElement('button')
    outside.textContent = 'behind-the-overlay'
    document.body.appendChild(outside)

    render(
      <Modal open onClose={() => {}} title="对话框">
        <button>唯一操作</button>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    dialog.querySelector('button')!.focus()
    fireEvent.keyDown(dialog, { key: 'Tab' })
    expect(outside).not.toBe(document.activeElement)
    expect(dialog.contains(document.activeElement)).toBe(true)
    outside.remove()
  })
})

describe("toast severity semantics", () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it("an error announces assertively and does not disappear by itself", () => {
    const { rerender } = render(<Toaster toasts={[{ id: 1, title: '读取失败', variant: 'error' }]} onDismiss={() => {}} />)
    const toast = screen.getByText('读取失败').closest('[role]')!
    expect(toast).toHaveAttribute('role', 'alert')
    expect(toast).toHaveAttribute('aria-live', 'assertive')

    act(() => { vi.advanceTimersByTime(60_000) })
    expect(screen.queryByText('读取失败')).not.toBeNull()
    rerender(<Toaster toasts={[]} onDismiss={() => {}} />)
  })

  it("an informational toast stays polite and expires on the default lifetime", () => {
    render(<Toaster toasts={[{ id: 2, title: '已同步', variant: 'info' }]} onDismiss={() => {}} />)
    const toast = screen.getByText('已同步').closest('[role]')!
    expect(toast).toHaveAttribute('role', 'status')
    expect(toast).toHaveAttribute('aria-live', 'polite')
  })

  it("useToaster keeps errors until dismissed but times out status messages", () => {
    let push: ((input: { title: string; variant?: 'success' | 'error' | 'info' }) => void) | null = null
    function Harness() {
      const { toasts, toast, dismiss, Toaster: Stack } = useToaster(1800)
      push = toast
      return <Stack toasts={toasts} onDismiss={dismiss} />
    }
    render(<Harness />)

    act(() => { push!({ title: '状态消息', variant: 'info' }) })
    act(() => { push!({ title: '失败消息', variant: 'error' }) })
    expect(screen.getAllByRole('status')).toHaveLength(1)
    expect(screen.getAllByRole('alert')).toHaveLength(1)

    act(() => { vi.advanceTimersByTime(1801) })
    // Expiring now means "fade out, then leave": at the lifetime the row is still in the document without
    // `.show`, and only after the skin's own transition budget is it gone. Asserting the disappearance at
    // 1801 ms would have hidden the fade — and asserting nothing at all would hide a row that never leaves.
    expect(screen.getByText('状态消息'), 'the status toast must still be painting its fade-out')
      .toBeInTheDocument()
    const statusRow = screen.getByText('状态消息').closest('div.toast')
    expect(statusRow, 'the fading row is the same element, not a re-created one').not.toBeNull()
    expect(statusRow!.classList.contains('show'), 'the lifetime expires the `.show` class, not the node')
      .toBe(false)
    expect(screen.getByText('失败消息')).toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(TOAST_EXIT_MS + 1) })
    expect(screen.queryByText('状态消息')).toBeNull()
    expect(screen.getByText('失败消息')).toBeInTheDocument()
  })
})
