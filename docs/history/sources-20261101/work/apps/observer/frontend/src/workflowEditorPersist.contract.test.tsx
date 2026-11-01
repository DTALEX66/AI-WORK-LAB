// WL-L04 (source: WL-REC-0104 cloud audit) — the 「已自动保存」 claim must be earned by the write.
//
// The defect: `try { localStorage.setItem(...) } catch { /* quota — non-fatal */ }` swallowed the
// failure while the header printed 「已自动保存」 unconditionally. A reader whose storage was full or
// disabled was told their edits were safe when they were not. These tests render the real view and
// drive the real write path: with setItem throwing, the header must NOT claim saved; the retry must
// be a real attempt (it is what makes the failure recoverable rather than merely reported).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import React from 'react'
import { WorkflowEditorView, writeModel } from '@/views/WorkflowEditorView'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('workflow editor persistence claim', () => {
  it('claims saved only when the write actually succeeded', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    setItem.mockImplementation(() => undefined)
    render(<WorkflowEditorView snap={null} />)
    expect(screen.getByText('已自动保存')).toBeTruthy()
    expect(document.querySelector('[data-persist-state="NOT_SAVED"]')).toBeNull()
    expect(setItem).toHaveBeenCalled()
  })

  it('says not-saved when the write throws, and does not claim saved', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('quota exceeded', 'QuotaExceededError')
    })
    render(<WorkflowEditorView snap={null} />)
    // Negative half: the whole point of the fix. The old render printed this unconditionally.
    expect(screen.queryByText('已自动保存')).toBeNull()
    expect(screen.getByText('未保存')).toBeTruthy()
    const state = document.querySelector('[data-persist-state="NOT_SAVED"]')
    expect(state).not.toBeNull()
    expect(state?.textContent).toContain('quota exceeded')
  })

  it('retry is a real second attempt and upgrades the claim only on success', async () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    setItem.mockImplementation(() => {
      throw new DOMException('quota exceeded', 'QuotaExceededError')
    })
    render(<WorkflowEditorView snap={null} />)
    const before = setItem.mock.calls.length
    const retry = () => screen.getByText('重试保存')
    expect(retry()).toBeTruthy()
    // Still failing -> the claim must stay negative. A retry that always "succeeds" would be the
    // same lie wearing a button.
    fireEvent.click(retry())
    expect(setItem.mock.calls.length).toBeGreaterThan(before)
    expect(screen.queryByText('已自动保存')).toBeNull()
    expect(screen.getByText('未保存')).toBeTruthy()

    setItem.mockImplementation(() => undefined)
    fireEvent.click(retry())
    expect(screen.getByText('已自动保存')).toBeTruthy()
    expect(screen.queryByText('未保存')).toBeNull()
  })

  it('writeModel reports the outcome instead of swallowing it', () => {
    const ok = writeModel({ nodes: [], edges: [] })
    expect(ok.status).toBe('SAVED')
    expect(ok.reason).toBeNull()

    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    const failed = writeModel({ nodes: [], edges: [] })
    expect(failed.status).toBe('NOT_SAVED')
    expect(failed.reason).toContain('denied')
  })
})
