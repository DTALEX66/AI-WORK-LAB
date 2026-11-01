/**
 * G1 of the UI prompt pack: a write action that is not available must say WHY,
 * at the control that is blocked, and a read-only lane must name the owner of
 * the write instead of going quiet.
 *
 * These are not cosmetic: `disabled` removes a control from the focus order and
 * from pointer events, so a hover tooltip alone is unreachable for the keyboard
 * and screen-reader path the acceptance gate tests. The reason therefore has to
 * exist in the accessibility tree, not only under the mouse.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

import { PermissionState } from '@/components/ui/states'
import { ApprovalsView } from '@/views/ApprovalsView'
import { WorkflowEditorView } from '@/views/WorkflowEditorView'

afterEach(cleanup)

const snap = {
  schemaVersion: 'workflow/snapshot/v3',
  workspace: { plan: { approvals: [{ taskId: 'APPR-1', state: 'pending', reason: '写外部文件' }] } },
} as any

describe('G1 · permission and blocked-action contract', () => {
  it('PermissionState states what is blocked, why, and what is still available', () => {
    const { container } = render(
      <PermissionState
        blocked="本视图不提供批准"
        reason="裁决由审批契约持有"
        stillAvailable="每行仍可阅读"
      />,
    )
    const shell = screen.getByRole('status')
    expect(shell.textContent).toContain('本视图不提供批准')
    expect(shell.textContent).toContain('裁决由审批契约持有')
    expect(shell.textContent).toContain('每行仍可阅读')
    // A read-only notice that shipped a control would be the defect it exists to prevent.
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })

  it('ApprovalsView names the owner of the decision when rows exist, and still exposes no verdict control', () => {
    render(<ApprovalsView snap={snap} />)
    expect(screen.getByRole('status').textContent).toContain('裁决由后端审批契约与 Permission Gate 持有')
    const words = ['批准', '拒绝', '撤销', 'Approve', 'Reject']
    const offenders = Array.from(document.querySelectorAll('button'))
      .map((b) => (b.textContent || '') + ' ' + (b.getAttribute('aria-label') || ''))
      .filter((t) => words.some((w) => t.includes(w)))
    expect(offenders).toEqual([])
  })

  it('the editor binds each blocked action to its contract reason in the accessibility tree', () => {
    render(<WorkflowEditorView snap={snap} />)
    const run = screen.getByRole('button', { name: '运行' })
    expect(run).toBeDisabled()
    expect(run.getAttribute('aria-disabled')).toBe('true')
    const describedBy = run.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    const note = document.getElementById(describedBy as string)
    expect(note).not.toBeNull()
    expect(note?.getAttribute('role')).toBe('note')
    expect(note?.textContent).toContain('契约')
    expect(run.getAttribute('title')).toContain('契约')
  })
})
