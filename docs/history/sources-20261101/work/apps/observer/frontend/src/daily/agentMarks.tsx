/**
 * Which software is an AGENT, and what it looks like.
 *
 * Two separate claims, one module, because they were being conflated on screen: the HUD drew every adapter
 * card the snapshot handed it, so GitHub -- whose client declares `role: "vcs_host"` in
 * `config/capability-matrix.json` -- appeared among the monitored agents, and every row carried the same
 * two-letter monogram, which identifies nothing.
 *
 * The predicate reads a declaration, not a name list. Two surfaces ask the question and each has its own
 * declaration: the software rows carry the registry's `category`
 * (`services/orchestration/composition_root.py::_build_software_projection`), and the adapter cards the HUD
 * is built from carry the capability matrix's `role`. Both are exposed below. `UNKNOWN` is deliberately not
 * an agent on either axis: "we do not know what this is" must not render as a monitored runtime.
 *
 * The marks are original glyphs, one character per agent, drawn here rather than fetched: shipping a
 * vendor's logo would be a trademark claim this project does not own, and the owner's alternative was
 * explicitly "宠物图标". A software id with no glyph gets the distinct UNMARKED figure -- never a letter
 * avatar, which is the thing that made every row look identical.
 */
import type { ReactElement } from 'react'

/** Categories that mean "an agent runtime the observer watches" -- the axis the software registry declares
 *  (`config/software-registry.json::category`, projected onto `snapshot.software[]`). */
export const AGENT_CATEGORIES: readonly string[] = ['agent-runtime', 'agent-harness']

/** A row is monitored-agent material only when the registry says so; absent/UNKNOWN is not an agent. */
export function isMonitoredAgent(category: string | null | undefined): boolean {
  return typeof category === 'string' && AGENT_CATEGORIES.includes(category)
}

/** The other axis, and the one the HUD actually consumes: the adapter cards come from
 *  `config/capability-matrix.json#clients[].role` and are what `snapshot.adapterCapabilities[]` carries, so
 *  the HUD's membership is decided here. `agent_runtime` is the only monitored role -- `provider_router`
 *  (CC Switch) routes models, `vcs_host` (GitHub) hosts delivery, `design_client` (Open Design) is a design
 *  surface, and `UNKNOWN` means the matrix declared nothing, which is a source gap, not an agent.
 *
 *  The two lists are kept apart on purpose: they are different files with different vocabularies
 *  (`agent-runtime` vs `agent_runtime`), and one predicate over both would let a typo in either file pass. */
export const AGENT_ROLES: readonly string[] = ['agent_runtime']

/** Whether an adapter card's declared role makes it a monitored agent runtime. */
export function isMonitoredAgentRole(role: string | null | undefined): boolean {
  return typeof role === 'string' && AGENT_ROLES.includes(role)
}

type Glyph = (key: string) => ReactElement

const stroke = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.6, strokeLinecap: 'round',
  strokeLinejoin: 'round' } as const

/** Hermes: a winged runner -- feathers over two legs. */
const hermes: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="hermes">
    <path {...stroke} d="M4 7c3-2 6-2 9 0" />
    <path {...stroke} d="M5 11c3-2 7-2 10 0" />
    <path {...stroke} d="M6 15c3-2 6-2 9 0" />
    <circle cx="17.5" cy="6.5" r="2" {...stroke} />
    <path {...stroke} d="M17 9v6M19 15h-4" />
  </svg>
)

/** Codex: an owl face -- two eyes under ear tufts, a beak between. */
const codex: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="codex">
    <path {...stroke} d="M5 6l2 3M19 6l-2 3" />
    <circle cx="9" cy="12" r="2.6" {...stroke} />
    <circle cx="15" cy="12" r="2.6" {...stroke} />
    <path {...stroke} d="M12 14l-1.2 2h2.4z" />
    <path {...stroke} d="M6 17c2 2.5 10 2.5 12 0" />
  </svg>
)

/** DeepSeek Harness: a koi -- body arc, tail fork, one eye. */
const deepseek: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true"
       data-agent-mark="deepseek-harness">
    <path {...stroke} d="M4 14c4-6 10-6 13-1" />
    <path {...stroke} d="M17 13l3-3v7l-3-3" />
    <circle cx="8" cy="12" r="1" fill="currentColor" />
    <path {...stroke} d="M6 17c3 2 7 2 9 0" />
  </svg>
)

/** OpenHuman: a standing figure -- head, shoulders, two feet. */
const openhuman: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="openhuman">
    <circle cx="12" cy="6" r="2.6" {...stroke} />
    <path {...stroke} d="M12 9v6M7 12h10M12 15l-3 5M12 15l3 5" />
  </svg>
)

/** CC Switch: a chameleon on a rail -- curled tail, two grips. */
const ccswitch: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="cc-switch">
    <path {...stroke} d="M4 16h16" />
    <path {...stroke} d="M8 16c0-4 3-6 6-6s4 2 4 3.5S16.5 16 15 15" />
    <circle cx="16.5" cy="11.5" r="1" fill="currentColor" />
    <path {...stroke} d="M10 16v3M14 16v3" />
  </svg>
)

/** Open Design: a fox head -- two ears, a pointed muzzle. */
const opendesign: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="open-design">
    <path {...stroke} d="M5 5l3 4M19 5l-3 4" />
    <path {...stroke} d="M8 9c0 5 2 8 4 10 2-2 4-5 4-10z" />
    <circle cx="10.4" cy="12" r="0.9" fill="currentColor" />
    <circle cx="13.6" cy="12" r="0.9" fill="currentColor" />
  </svg>
)

/** GitHub: a delivery platform, drawn only because the registry knows it -- the agent filter keeps it out
 *  of the HUD, and a row that does appear elsewhere must not fall back to something that looks like an agent. */
const github: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="github">
    <path {...stroke} d="M9 20v-3c-3 0-4-2-4-4l-1-1 1-1s1 0 2 1 3 0 3 0 1-2 3-2 3 1 3 1l2-1 1 1s0 1-1 2c0 2-1 4-4 4v3" />
  </svg>
)

/** No glyph for this id: a plain, unmistakable "we have no mark for this one" figure. */
const unmarked: Glyph = (k) => (
  <svg key={k} viewBox="0 0 24 24" width="100%" height="100%" aria-hidden="true" data-agent-mark="UNKNOWN">
    <circle cx="12" cy="12" r="7.5" {...stroke} strokeDasharray="3 3" />
    <path {...stroke} d="M12 8.5v4M12 15.5v.6" />
  </svg>
)

/** Keyed by `softwareId`, the registry's own identity -- not the display name, which is wording.
 *  One entry per line, always written as `key: value`: the parity gate
 *  (`tests/ci/test_agent_marks_cover_the_software_registry.py`) reads this record from source, and a
 *  shorthand key (`hermes,`) is the shape a line-based reader is most likely to miss. */
export const AGENT_MARKS: Record<string, Glyph> = {
  'hermes': hermes,
  'codex': codex,
  'deepseek-harness': deepseek,
  'openhuman': openhuman,
  'cc-switch': ccswitch,
  'open-design': opendesign,
  'github': github,
}

export function AgentMark({ softwareId }: { softwareId: string }): ReactElement {
  const glyph = AGENT_MARKS[softwareId] ?? unmarked
  return <>{glyph(softwareId)}</>
}

/**
 * The mark inside the tile the surfaces already use for an identity: same box as the initials tile it
 * replaces, same `--daily-*` theme roles, so it repaints with the light/dark switch like everything else.
 *
 * The tile is `aria-hidden` because the name is already in the text next to it; the row's identity is the
 * `data-agent-mark` on the glyph, which is what the real-browser gates match a row to.
 */
export function AgentTile({ softwareId, size = 36, tone = 'shell' }:
  { softwareId: string; size?: number; tone?: 'shell' | 'surface' }): ReactElement {
  const inset = Math.round(size * 0.24)
  return (
    <span aria-hidden="true" data-agent-tile={softwareId}
      className="flex shrink-0 items-center justify-center rounded-lg border"
      style={{
        width: size,
        height: size,
        borderColor: 'var(--daily-line)',
        background: tone === 'shell' ? 'var(--daily-surface)' : 'var(--daily-shell)',
        color: 'var(--daily-accent)',
        padding: inset,
      }}>
      <AgentMark softwareId={softwareId} />
    </span>
  )
}
