import * as React from 'react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { VIEW_REGISTRY, OVERVIEW_ID, OVERVIEW_LABEL, OVERVIEW_ICON } from '@/lib/viewRegistry'
// WUI-01/WUI-02: the grouping is data now, and it lives in `lib/navigation` next to the statement of
// which lanes are daily destinations and which left the default nav. The rail renders that model; it no
// longer owns it, because a grouping that only a component can read cannot be asserted, searched or
// reused by the command palette.
import { NAV_GROUPS, DAILY_DESTINATION_IDS, isOnDefaultNav } from '@/lib/navigation'

/**
 * L10b (2026-09-27): B10 sidebar — the verbatim B10 DOM:
 *
 *   <aside class="sidebar">
 *     <div class="brand">
 *       <div class="brand-mark"></div>
 *       <div><h1>WORK-LAB</h1><small>AI WORKFLOW CONTROL PLANE</small></div>
 *     </div>
 *     <div class="nav">
 *       <button><svg class="lucide-activity"></svg><span>总览</span></button>
 *       …
 *     </div>
 *     <div class="sidebar-footer">
 *       <div class="avatar">A</div>
 *       <div><strong>Alex</strong><small>Personal Workspace</small></div>
 *     </div>
 *   </aside>
 *
 * `.sidebar` (280px gradient rail) / `.brand` / `.brand-mark` (B10's 48px gradient
 * tile, overridden in src/skins/l10b-shell.css to the 91x48 cut-out logo mark — the
 * pinned skin itself stays verbatim per decision D-11) / `.nav button` (+ `.active` gradient + `::before` cyan→blue edge bar) /
 * `.nav-dot` / `.sidebar-footer` / `.avatar` are all B10-verbatim in
 * src/skins/b10.css. Since 2026-10-29 the rail mounts each lane's own registry glyph in place of the
 * decorative `.nav-dot`; the rule stays in the pinned sheet untouched, and no lane's name was hidden to
 * make room — that trade is exactly what `apps/observer/frontend/DESIGN.md` gap 10 records as the failed
 * first attempt. This component only supplies the data (the lanes) — the
 * groups from `lib/navigation` render as the B10 buttons, each group with its
 * own labelled disclosure block so every lane on the default nav stays one click away.
 *
 * Read-only contract: the rail is pure navigation — no write, approve or
 * configuration affordance exists here.
 */
interface LaneDef {
  id: string
  label: string
  // WUI-03 gap 10: the glyph comes from the registry row, not from a table kept here. A picture the rail
  // invents is a second source, and the two sources drift exactly the way the three 总览 literals did (N-1).
  icon: LucideIcon
}

// The rail renders every lane in NAV_GROUPS that is still on the default nav. `workflow-editor` is the
// one registry lane that left it (20261009 route table: 退出默认导航) — its component, its deep link and
// its palette entry all stay, so an experimental surface is demoted rather than deleted.
// Read-only contract: navigation only. No write, approve or configuration affordance exists here; those
// must be blocked by the backend contract, not merely hidden from this rail.


function buildLanes(): Map<string, LaneDef> {
  const map = new Map<string, LaneDef>([[OVERVIEW_ID,
    { id: OVERVIEW_ID, label: OVERVIEW_LABEL, icon: OVERVIEW_ICON }]])
  for (const e of VIEW_REGISTRY) {
    if (e.component) map.set(e.id, { id: e.id, label: e.label, icon: e.icon })
  }
  return map
}

export interface SidebarProps {
  activeView: string
  onSelect: (id: string) => void
}

function Brand() {
  return (
    <div className="brand">
      {/* Decorative on purpose: the h1 below already spells WORK-LAB, so an aria-label here would make
          a screen reader announce the brand twice per render. The glyph is the artwork cut from the
          project logo (see src/assets/brand/work-lab-mark.png); it replaces the "WL" text the pinned
          skin used to show, and the override that sizes it lives in skins/l10b-shell.css. */}
      <div className="brand-mark" aria-hidden="true" />
      <div>
        <h1>WORK-LAB</h1>
        <small>AI WORKFLOW CONTROL PLANE</small>
      </div>
    </div>
  )
}

function Nav({
  activeView,
  onSelect,
}: {
  activeView: string
  onSelect: (id: string) => void
}) {
  const lanes = React.useMemo(buildLanes, [])
  const groups = React.useMemo(
    () =>
      NAV_GROUPS.map((g) => ({
        ...g,
        items: g.ids.filter(isOnDefaultNav).map((id) => lanes.get(id)).filter(Boolean) as LaneDef[],
      })).filter((g) => g.items.length > 0),
    [lanes],
  )
  // Scrolling makes a long rail reachable; collapsing is what keeps it short enough to read. The rail is
  // its own scroll box since `36f9a297`, which is necessary but not sufficient — ARIA APG Disclosure
  // Navigation expects each section to be a disclosure button as well, which is the shape Rancher's
  // per-group nav implements and the shape the 23-item rail needs at a 600px-tall window.
  const [collapsed, setCollapsed] = React.useState<ReadonlySet<string>>(() => new Set())
  const toggles = React.useRef<Record<string, HTMLButtonElement | null>>({})
  const setToggleRef = (key: string) => (node: HTMLButtonElement | null) => {
    toggles.current[key] = node
  }
  const toggleGroup = (key: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const onKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== 'Escape') return
    const group = groups.find((g) => g.ids.some((id) => id === activeView))
    const target = event.target as HTMLElement | null
    if (!group || !target || !event.currentTarget.contains(target)) return
    if (target === toggles.current[group.key]) return
    setCollapsed((prev) => (prev.has(group.key) ? prev : new Set(prev).add(group.key)))
    toggles.current[group.key]?.focus()
  }

  return (
    <nav className="nav" onKeyDown={onKeyDown}>
      {groups.map((g) => {
        const open = !collapsed.has(g.key)
        return (
          <div key={g.key} className="flex flex-col gap-1.5 pb-1.5">
            {/* group label (B07 IA matrix) — a disclosure button, so the caption is also the control
                that hides its own items; the muted B10 caption styling is kept in the skin layer */}
            <button
              type="button"
              ref={setToggleRef(g.key)}
              className="nav-group-toggle px-3.5 pt-1 text-[12px] font-semibold uppercase tracking-[0.12em] text-muted"
              aria-expanded={open}
              aria-controls={`nav-group-${g.key}`}
              title={open ? `收起 ${g.label}` : `展开 ${g.label}`}
              onClick={() => toggleGroup(g.key)}
            >
              <span className="nav-group-caret" aria-hidden="true" />
              <span className="truncate">{g.label}</span>
            </button>
            {open && (
              <div id={`nav-group-${g.key}`} className="flex flex-col gap-1.5">
                {g.items.map((l) => {
                  const active = activeView === l.id
                  return (
                    <button
                      key={l.id}
                      type="button"
                      onClick={() => onSelect(l.id)}
                      data-lane={l.id}
                      // The five suggested destinations + settings are marked rather than counted, so a
                      // contract can assert "these are the daily entries" without pinning the number 5.
                      data-daily={DAILY_DESTINATION_IDS.includes(l.id) ? 'true' : undefined}
                      title={l.label}
                      aria-current={active ? 'page' : undefined}
                      className={cn(active && 'active')}
                    >
                      {/* WUI-03 gap 10: the lane's own glyph, declared in the registry and until 2026-10-29
                          carried no consumer — the rail painted 31 identical `.nav-dot` circles. It replaces
                          the dot instead of joining it, because a second 15px box pushes more labels into
                          `.truncate`, and a truncated label is the information the gap said not to remove. */}
                      <l.icon size={15} strokeWidth={2} aria-hidden="true" data-lane-icon={l.id} />
                      <span className="truncate">{l.label}</span>
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </nav>
  )
}

function SidebarFooter() {
  return (
    <div className="sidebar-footer">
      <div className="avatar">A</div>
      <div>
        <strong>Alex</strong>
        <small>Personal Workspace</small>
      </div>
    </div>
  )
}

export function Sidebar({ activeView, onSelect }: SidebarProps) {
  return (
    <aside className="sidebar sidebar-slot" aria-label="侧边导航">
      <Brand />
      <Nav activeView={activeView} onSelect={onSelect} />
      <SidebarFooter />
    </aside>
  )
}
