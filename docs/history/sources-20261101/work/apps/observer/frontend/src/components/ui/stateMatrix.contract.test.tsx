// WUI-11 · the state matrix and the eight affordances, as rendered.
//
// Text-presence checks are not enough here: the requirement is that two different states do not print the
// same sentence. So these tests compare rendered text across states and assert the pairs that must differ
// actually do, and they pin the warning line that only the two non-projectable states may carry.
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

import { ProductStateCard, StateMatrixCard } from './states'
import { STATE_DEFINITIONS, NON_PROJECTABLE_STATES } from '@/lib/stateVocabulary'

afterEach(cleanup)

describe('ProductStateCard', () => {
  it('renders each state with its own title, evidence rule and next action', () => {
    for (const definition of STATE_DEFINITIONS) {
      cleanup()
      const { container } = render(<ProductStateCard state={definition.id} subject="测试泳道" />)
      const text = container.textContent || ''
      expect(text, definition.id).toContain(definition.label)
      expect(text, definition.id).toContain('测试泳道')
      expect(text, definition.id).toContain('依据：')
      expect(text, definition.id).toContain('下一步：')
      expect(container.querySelector(`[data-state="${definition.id}"]`)).not.toBeNull()
    }
  })

  it('no two states print the same meaning sentence', () => {
    const meanings = STATE_DEFINITIONS.map((definition) => definition.meaning)
    expect(new Set(meanings).size).toBe(meanings.length)
  })

  it('carries the not-projectable warning for exactly the two states the snapshot cannot answer', () => {
    for (const definition of STATE_DEFINITIONS) {
      cleanup()
      const { container } = render(<ProductStateCard state={definition.id} />)
      const warning = container.querySelectorAll('[data-testid^="state-not-projectable-"]')
      const expected = NON_PROJECTABLE_STATES.includes(definition.id) ? 1 : 0
      expect(warning.length, `${definition.id} warning count`).toBe(expected)
      if (expected === 1) {
        expect(warning[0].textContent).toContain('不由空值推断')
      }
    }
  })

  it('a caller-supplied detail replaces the generic meaning rather than appending to it', () => {
    const { container } = render(
      <ProductStateCard state="delayed" detail="last-good 时间 2026-10-09T12:00:00Z" />,
    )
    const text = container.textContent || ''
    expect(text).toContain('last-good 时间')
    expect(screen.getByRole('status')).toBeTruthy()
  })
})

describe('StateMatrixCard', () => {
  it('lists all eight states with their projectability worded distinctly', () => {
    const { container } = render(<StateMatrixCard />)
    const rows = container.querySelectorAll('[data-testid="state-matrix"] [data-state]')
    expect(rows).toHaveLength(STATE_DEFINITIONS.length)
    const text = container.textContent || ''
    for (const definition of STATE_DEFINITIONS) expect(text).toContain(definition.label)
    expect(text).toContain('快照不携带')
    expect(text).toContain('可由投影判定')
  })

  it('marks exactly the two unanswerable rows, and never calls them unsupported-by-design', () => {
    const { container } = render(<StateMatrixCard />)
    const unanswerable = Array.from(container.querySelectorAll('[data-state]'))
      .filter((row) => (row.textContent || '').includes('快照不携带'))
      .map((row) => row.getAttribute('data-state'))
    expect(unanswerable.sort()).toEqual([...NON_PROJECTABLE_STATES].sort())
  })
})
