import * as React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Modal } from './modal'
import { CommandPalette, type PaletteItem } from './command-palette'
import { EmptyState, UnknownState } from './states'

describe("UI components", () => {
  it("Modal: renders with aria-modal, closes on Escape, calls onClose", () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="测试弹窗" footer={<span>footer</span>}>
        <p>内容</p>
      </Modal>,
    )
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toHaveAttribute('aria-label', '测试弹窗')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("Modal: does not render when closed", () => {
    render(<Modal open={false} onClose={() => {}} title="x">内容</Modal>)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  const mk = (label: string, ran: () => void): PaletteItem => ({
    id: label,
    label,
    run: ran,
  })

  it("CommandPalette: filters by query and Enter runs the item", async () => {
    const a = vi.fn()
    const b = vi.fn()
    const items = [mk('总览', a), mk('规则与策略', b)]
    render(
      <CommandPalette open onClose={vi.fn()} items={items} />,
    )
    const input = screen.getByRole('textbox') as HTMLInputElement
    fireEvent.change(input, { target: { value: '规则' } })
    await waitFor(() => {
      expect(screen.getByText('规则与策略')).toBeTruthy()
    })
    expect(screen.queryByText('总览')).toBeNull()
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(b).toHaveBeenCalledTimes(1)
    expect(a).not.toHaveBeenCalled()
  })

  it("CommandPalette: ArrowDown moves selection, Escape closes", () => {
    const onClose = vi.fn()
    const items = [mk('A', vi.fn()), mk('B', vi.fn()), mk('C', vi.fn())]
    render(<CommandPalette open onClose={onClose} items={items} />)
    const input = screen.getByRole('textbox')
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowUp' })
    // net position = 1 (Down,Down,Up) → 'B' is the active item
    const second = screen.getByText('B')
    expect(second.closest('button')?.getAttribute('aria-current')).toBe('true')
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it("EmptyState / UnknownState: render honest titles without fabricated data", () => {
    render(<EmptyState title="无审计记录" description="快照未携带审计明细" />)
    expect(screen.getByText('无审计记录')).toBeTruthy()
    expect(screen.getByText('快照未携带审计明细')).toBeTruthy()
    render(<UnknownState title="数据未知" description="审批数据将由审批契约投影" />)
    expect(screen.getByText('审批数据将由审批契约投影')).toBeTruthy()
  })
})
