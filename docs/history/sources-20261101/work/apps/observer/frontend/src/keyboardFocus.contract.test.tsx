/**
 * Keyboard-only operation, asserted where it can break (UI prompt pack acceptance:
 * Keyboard-only 能打开/关闭 palette、dialog/drawer、移动焦点并返回焦点).
 *
 * Opening a palette from a control and then closing it must not strand the user:
 * before this contract, focus stayed on an input inside a dialog that had been
 * unmounted, so the next Tab restarted at the top of the document.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, fireEvent } from '@testing-library/react'
import * as React from 'react'

import { CommandPalette } from '@/components/ui/command-palette'

afterEach(cleanup)

const items = [
  { id: 'a', label: '进入 Overview', run: vi.fn() },
  { id: 'b', label: '进入审批', run: vi.fn() },
] as any

function Harness() {
  const [open, setOpen] = React.useState(false)
  return (
    <>
      <button type="button" data-testid="opener" onClick={() => setOpen(true)}>
        搜索
      </button>
      <CommandPalette open={open} items={items} onClose={() => setOpen(false)} />
    </>
  )
}

describe('keyboard and focus contract', () => {
  it('Escape returns focus to the control that opened the palette', () => {
    render(<Harness />)
    const opener = document.querySelector('[data-testid="opener"]') as HTMLElement
    opener.focus()
    fireEvent.click(opener)

    const input = document.querySelector('.palette input') as HTMLInputElement
    expect(input).toBeTruthy()
    expect(document.activeElement).toBe(input)

    fireEvent.keyDown(input, { key: 'Escape' })
    expect(document.querySelector('.palette input')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('running an item with Enter also restores focus, and nothing is left mounted', () => {
    render(<Harness />)
    const opener = document.querySelector('[data-testid="opener"]') as HTMLElement
    opener.focus()
    fireEvent.click(opener)
    const input = document.querySelector('.palette input') as HTMLInputElement
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(items[0].run).toHaveBeenCalledTimes(1)
    expect(document.querySelector('.palette input')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('arrow keys move the selection inside the list without leaving the dialog', () => {
    render(<Harness />)
    fireEvent.click(document.querySelector('[data-testid="opener"]') as HTMLElement)
    const input = document.querySelector('.palette input') as HTMLInputElement
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    const current = Array.from(document.querySelectorAll('.palette [aria-current]'))
    expect(current.length).toBeGreaterThan(0)
    expect(current[current.length - 1].getAttribute('aria-current')).toBe('true')
    fireEvent.keyDown(input, { key: 'ArrowUp' })
    fireEvent.keyDown(input, { key: 'ArrowUp' })
    expect(document.querySelector('.palette input')).not.toBeNull()
  })
})
