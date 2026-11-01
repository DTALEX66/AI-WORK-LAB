/**
 * The agent HUD must show agents, and each one must be recognisable.
 *
 * Two defects this pins, both measured on 2026-10-28: GitHub was drawn among the monitored agents (the strip
 * mapped over every adapter card the snapshot handed it, and GitHub's client declares
 * `role: "vcs_host"`), and every row carried the same two-letter monogram, so the icon identified nothing.
 * The predicates are the operator's own declarations -- the capability matrix's `role` for the adapter cards
 * the HUD is built from, and the software registry's `category` for the software rows -- not name lists;
 * see the header of `agentMarks.tsx` for why that distinction is the whole point.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import {
  AGENT_CATEGORIES, AGENT_ROLES, AgentMark, AgentTile,
  isMonitoredAgent, isMonitoredAgentRole,
} from '@/daily/agentMarks'
import { HudDaily } from '@/daily/HudDaily'
import type { SnapshotV3 } from '@/types'

afterEach(cleanup)

describe('isMonitoredAgent · the registry decides, not the name', () => {
  it('accepts exactly the declared agent categories', () => {
    expect(AGENT_CATEGORIES).toEqual(['agent-runtime', 'agent-harness'])
    expect(isMonitoredAgent('agent-runtime')).toBe(true)
    expect(isMonitoredAgent('agent-harness')).toBe(true)
  })

  it('rejects the delivery platform, the router and the design client', () => {
    expect(isMonitoredAgent('platform')).toBe(false)
    expect(isMonitoredAgent('provider-switch')).toBe(false)
    expect(isMonitoredAgent('design-client')).toBe(false)
  })

  it('treats an absent or UNKNOWN category as NOT an agent', () => {
    // "we do not know what this is" rendering as a monitored runtime would be the same class of defect as
    // an unknown token printing as zero.
    expect(isMonitoredAgent(undefined)).toBe(false)
    expect(isMonitoredAgent(null)).toBe(false)
    expect(isMonitoredAgent('UNKNOWN')).toBe(false)
    expect(isMonitoredAgent('')).toBe(false)
  })
})

describe('AgentMark · one character per agent', () => {
  const KNOWN = ['hermes', 'codex', 'deepseek-harness', 'openhuman', 'cc-switch', 'open-design', 'github']

  it.each(KNOWN)('renders a dedicated mark for %s', (id) => {
    const { container } = render(<AgentMark softwareId={id} />)
    const svg = container.querySelector('svg[data-agent-mark]')
    expect(svg).not.toBeNull()
    expect(svg?.getAttribute('data-agent-mark')).toBe(id)
  })

  it('never falls back to a letter avatar: an id with no glyph gets the explicit UNKNOWN figure', () => {
    const { container } = render(<AgentMark softwareId="something-new" />)
    expect(container.querySelector('svg[data-agent-mark="UNKNOWN"]')).not.toBeNull()
    // The old tile was a span of text; a mark that degrades to text is the defect returning.
    expect(container.textContent).toBe('')
  })

  it('keeps the mark decorative so the row label stays the accessible name', () => {
    const { container } = render(<AgentMark softwareId="codex" />)
    expect(container.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('isMonitoredAgentRole · the capability matrix decides the HUD population', () => {
  it('accepts exactly the declared agent role', () => {
    expect(AGENT_ROLES).toEqual(['agent_runtime'])
    expect(isMonitoredAgentRole('agent_runtime')).toBe(true)
  })

  it('rejects the roles that do not execute the work', () => {
    expect(isMonitoredAgentRole('vcs_host')).toBe(false)
    expect(isMonitoredAgentRole('provider_router')).toBe(false)
    expect(isMonitoredAgentRole('design_client')).toBe(false)
  })

  it('treats an absent or UNKNOWN role as NOT an agent', () => {
    expect(isMonitoredAgentRole(undefined)).toBe(false)
    expect(isMonitoredAgentRole(null)).toBe(false)
    expect(isMonitoredAgentRole('UNKNOWN')).toBe(false)
    expect(isMonitoredAgentRole('')).toBe(false)
  })
})

describe('AgentTile · the mark in the identity box the surfaces already draw', () => {
  it('binds the tile to the software id and paints no text', () => {
    const { container } = render(<AgentTile softwareId="hermes" size={28} />)
    expect(container.querySelector('[data-agent-tile="hermes"]')).not.toBeNull()
    expect(container.querySelector('svg[data-agent-mark="hermes"]')).not.toBeNull()
    expect(container.textContent).toBe('')
  })

  it('stays decorative: the row name beside it is the accessible name', () => {
    const { container } = render(<AgentTile softwareId="codex" />)
    expect(container.firstElementChild?.getAttribute('aria-hidden')).toBe('true')
  })
})

describe('HUD 窄面板只监控 agent 运行时', () => {
  function card(clientId: string, role?: string): Record<string, unknown> {
    return { clientId, displayName: clientId.toUpperCase(), ...(role === undefined ? {} : { role }) }
  }

  function stripSnap(cards: Array<Record<string, unknown>>): SnapshotV3 {
    return { adapterCapabilities: cards, executions: [], projects: [] } as unknown as SnapshotV3
  }

  const MIXED = [
    card('hermes', 'agent_runtime'),
    card('codex', 'agent_runtime'),
    card('github', 'vcs_host'),
    card('cc-switch', 'provider_router'),
    card('open-design', 'design_client'),
    card('openhuman'),
  ]

  it('draws one row per declared agent runtime and no other client', () => {
    const { container } = render(<HudDaily snap={stripSnap(MIXED)} nativeStrip />)
    const bound = Array.from(container.querySelectorAll('[data-hud-agent]'))
      .map((node) => node.getAttribute('data-hud-agent'))
    expect(bound).toEqual(['hermes', 'codex'])
    expect(container.textContent).not.toContain('GITHUB')
    expect(container.textContent).not.toContain('CC-SWITCH')
    expect(container.textContent).not.toContain('OPEN-DESIGN')
    // Every row that survives the filter still has to be recognisable.
    expect(container.querySelectorAll('[data-hud-agent] svg').length).toBe(2)
  })

  it('names every row for assistive tech, because the strip paints no name beside the figure', () => {
    // `AgentMark` is decorative by contract (the figure is not text, so no gate can read its contrast),
    // and the h01 row is the one surface where nothing else on the line says who the agent is: the name
    // appears only inside the h02 capsule, which exists while a pointer is on the row. Without this the
    // row's only identity is an aria-hidden shape.
    const { container } = render(<HudDaily snap={stripSnap(MIXED)} nativeStrip />)
    const rows = Array.from(container.querySelectorAll('[data-hud-agent]'))
    expect(rows.map((node) => [node.getAttribute('role'), node.getAttribute('aria-label')]))
      .toEqual([['img', 'HERMES'], ['img', 'CODEX']])
    // The name is not smuggled in as painted text either — 150px has no room for a second line per row.
    expect(container.textContent).not.toContain('HERMES')
    expect(rows[0].querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
  })

  it('says what it left out, and keeps "role not declared" a separate statement', () => {
    const { container } = render(<HudDaily snap={stripSnap(MIXED)} nativeStrip />)
    const scope = container.querySelector('[data-testid="hud-agent-scope"]')
    expect(scope).not.toBeNull()
    expect(scope?.textContent).toContain('已排除非 agent 3')
    expect(scope?.textContent).toContain('未声明角色 1')
  })

  it('shows nothing but the exclusion note when no client declares an agent role', () => {
    const { container } = render(<HudDaily snap={stripSnap([card('github', 'vcs_host')])} nativeStrip />)
    expect(container.querySelectorAll('[data-hud-agent]').length).toBe(0)
    expect(container.textContent).toContain('已排除非 agent 1')
  })

  it('states no exclusion line when the snapshot has nothing to leave out', () => {
    const { container } = render(<HudDaily snap={stripSnap([card('hermes', 'agent_runtime')])} nativeStrip />)
    expect(container.querySelector('[data-testid="hud-agent-scope"]')).toBeNull()
  })
})
