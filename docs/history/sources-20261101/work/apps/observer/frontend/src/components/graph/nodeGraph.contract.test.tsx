// The topology keeps its shapes; its names moved to a legend a person can read.
//
// `NodeGraph` scales a 100-unit viewBox into a ~100 CSS px stage, so `fontSize="5"` rendered at
// 5 CSS px — the legibility instrument measured it on screen in both themes, and it is the exact shape
// DESIGN.md forbids ("no text a user must read below 12px"). Raising the SVG size instead would have
// made the labels collide with the ring, so the names are HTML now: reachable, selectable, and 12px.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { GraphLegend, NodeGraph, type GraphNode } from '@/components/graph/node-graph'

const NODES: GraphNode[] = [
  { id: 'agent', label: 'Agent', state: 'active' },
  { id: 'workflow', label: 'Workflow', state: 'idle' },
  { id: 'taskpack', label: 'Task Pack', state: 'error' },
] as GraphNode[]

afterEach(cleanup)

describe('the observer topology names itself legibly', () => {
  it('paints no text inside the scaled graphic', () => {
    const { container } = render(<NodeGraph core="Observer" nodes={NODES} />)
    expect(container.querySelectorAll('svg text')).toHaveLength(0)
    expect(container.querySelector('svg')?.getAttribute('aria-label')).toContain('Observer')
  })

  it('lists the core and every shown node as a 12px control', () => {
    render(<GraphLegend core="Observer" nodes={NODES} selected={null} onSelect={() => {}} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons).toHaveLength(NODES.length + 1)
    // Asserted through the accessible name rather than textContent: adjacent spans concatenate without
    // a space, and the name is what a screen-reader user hears — including the state word, which is
    // the colour-independence half of the claim (SC 1.4.1).
    for (const [label, state] of [['Observer', 'active'], ['Agent', 'active'],
                                  ['Workflow', 'idle'], ['Task Pack', 'error']] as const) {
      expect(screen.getByRole('button', { name: `${label} ${state}` })).toBeTruthy()
    }
    for (const button of buttons) {
      expect(button.className, `${button.textContent} escaped the type floor`)
        .toContain('text-[12px]')
    }
  })

  it('selects and clears through the same handler the dots use', () => {
    const onSelect = vi.fn()
    render(<GraphLegend core="Observer" nodes={NODES} selected="agent" onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /Workflow/ }))
    expect(onSelect).toHaveBeenLastCalledWith('workflow')
    fireEvent.click(screen.getByRole('button', { name: /Agent/ }))
    expect(onSelect).toHaveBeenLastCalledWith(null)     // already selected -> clears, like the dot
  })

  it('states each node condition in words, not only as a colour dot', () => {
    render(<GraphLegend core="Observer" nodes={NODES} selected={null} onSelect={() => {}} />)
    const pack = screen.getByRole('button', { name: /Task Pack/ })
    expect(pack.textContent).toContain('error')
    expect(pack.querySelector('[aria-hidden="true"]')).toBeTruthy()  // the dot is the decoration
  })

  it('never lists more nodes than the graphic draws', () => {
    const many: GraphNode[] = Array.from({ length: 9 }, (_, i) => (
      { id: `n${i}`, label: `Node ${i}`, state: 'idle' as const }))
    render(<GraphLegend core="Observer" nodes={many} selected={null} onSelect={() => {}} />)
    expect(screen.getAllByRole('button')).toHaveLength(7)   // core + the same 6 the SVG shows
  })
})
