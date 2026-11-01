// WUI-01/WUI-02 (taskpack 20261009) · the information-architecture model.
//
// Before this module the rail's grouping lived inside Sidebar.tsx as a literal, so "which lanes are
// daily destinations" was only answerable by reading a component, and the owner's route mapping
// (docs/history/owner-inputs/20261009/final-readable/inputs/frontend_route_mapping.proposed.csv) had no
// place to be encoded. This file is the single source: the rail, the command palette and the contract
// tests all read it, and the invariants are functions rather than magic numbers — the taskpack's rule is
// to repair the stale seven-group count assertion instead of pinning a permanent five.
//
// Two separations the product keeps insisting on:
//
// * DEFAULT NAVIGATION vs REGISTRY. A lane can leave the rail (workflow-editor: 退出默认导航) without
//   losing its deep link or its working implementation. `OFF_DEFAULT_NAV_IDS` is that statement, and it
//   is the only way a lane disappears from the rail.
// * DESTINATION vs LANE. The five destinations are a suggestion (WUI-01 says so explicitly), so they are
//   named here as data with their member lanes, and nothing in the app asserts "exactly five".
import { VIEW_REGISTRY, OVERVIEW_ID } from './viewRegistry'

export interface NavGroup {
  key: string
  label: string
  /** lane ids rendered in this rail section, in reading order */
  ids: string[]
  /** `auxiliary` marks the low-frequency section the owner's pack calls 辅助入口 (诊断 / 隐私). It is
   *  data, not a comment: the command palette's section name and the reachability assertions read it, so
   *  a lane cannot be "auxiliary" in one surface and primary in another. */
  role?: 'primary' | 'auxiliary'
}

/** The landing destination: 项目监控 (master page 01_projects). It rides the existing synthetic
 *  overview lane rather than a new id, because the owner's route table maps `overview` INTO 项目监控
 *  ("复用可用摘要") and 不建立双首页 — a second home id would be two homes with one name. */
export const HOME_LANE_ID = OVERVIEW_ID

/** The five suggested destinations + low-frequency settings, in rail order. WUI-05..09 gave each
 *  destination its own lane, so these ids are the destination pages and the legacy lanes below them in
 *  the same group are the compatibility entries to the same projection. */
export const DAILY_DESTINATION_IDS: readonly string[] = [
  HOME_LANE_ID, 'environment', 'capabilities', 'usage', 'rules-adaptation', 'settings',
]

/** Lanes that leave the default rail but keep their implementation, their deep link and a palette entry
 *  marked as an experimental entry. Removing a lane from the registry would delete a working surface,
 *  which WUI-13 forbids. */
export const OFF_DEFAULT_NAV_IDS: readonly string[] = ['workflow-editor']

/** Why an off-rail lane is off-rail, shown on the page it still renders. An unexplained missing entry
 *  looks identical to a lost feature. */
export const OFF_NAV_NOTES: Record<string, string> = {
  'workflow-editor':
    '实验入口：工作流编辑器已退出默认导航（20261009 路线表），实现与本深链保留；'
    + '编排运行器未接通，Observer 不发起执行，本页不产生任务。',
}

/** The key of the section the owner's pack calls 辅助入口. Named as a constant because a test must be able
 *  to ask "is this lane in the auxiliary section?" without re-typing a string that can drift. */
export const AUXILIARY_GROUP_KEY = 'auxiliary'

/** Rail sections. Every registry lane belongs to exactly one section (or is off-nav), asserted by
 *  navInvariantViolations() and by the registry contract test. Section captions are deliberately not
 *  the same words as their member lane labels — two identical strings in the rail read as one control
 *  that does nothing. */
export const NAV_GROUPS: NavGroup[] = [
  { key: 'home', label: '首页', ids: [HOME_LANE_ID, 'projects', 'project-detail'] },
  { key: 'environment', label: '软件与环境',
    ids: ['environment', 'software', 'agents', 'observer'] },
  { key: 'capability', label: '能力',
    ids: ['capabilities', 'tools', 'workflows', 'integrations', 'memory'] },
  { key: 'metering', label: '计量', ids: ['usage', 'models'] },
  { key: 'rules', label: '规则', ids: ['rules-adaptation', 'rules-policy', 'approvals', 'task-packs'] },
  // WUI-21 (20261012): the isolated-trial surfaces. Three read-only lanes over one component, and they
  // are NOT in 记录 because they are not compatibility surfaces: they report work this repository can answer
  // about a trial, with every stage carrying the basis it was read from.
  { key: 'trial', label: '隔离试用', ids: ['trial-plan', 'trial-failure', 'trial-readback'] },
  { key: 'records', label: '按需记录（兼容只读）',
    ids: ['work', 'executions', 'execution-detail', 'evidence', 'delivery', 'audit', 'trust'] },
  { key: 'preferences', label: '设置', ids: ['settings'] },
  // 入册材料 WL-REC-0103 §2 asks for 诊断 and 隐私 as AUXILIARY entries rather than destinations. They are
  // not new surfaces: `monitoring` is the bounded-diagnostics lane WUI-11 shipped and `privacy` is the
  // collection-lifecycle page WUI-12 shipped, so this section groups two existing projections and adds
  // nothing to read. Moving them here is what makes the word 诊断 findable -- it is in the section name the
  // palette filters on, while neither lane's own label contains it.
  { key: AUXILIARY_GROUP_KEY, label: '诊断与隐私', role: 'auxiliary', ids: ['monitoring', 'privacy'] },
]

const REGISTRY_IDS = new Set(VIEW_REGISTRY.map((entry) => entry.id))

/** Every id the navigation model knows about: registry lanes plus the synthetic home. */
export function knownLaneIds(): Set<string> {
  return new Set<string>([...REGISTRY_IDS, OVERVIEW_ID])
}

/** The lanes the rail actually renders — registry lanes minus the off-nav set, plus the home. */
export function railLaneIds(): string[] {
  return NAV_GROUPS.flatMap((group) => group.ids).filter((id) => !OFF_DEFAULT_NAV_IDS.includes(id))
}

export function isOnDefaultNav(id: string): boolean {
  return !OFF_DEFAULT_NAV_IDS.includes(id) && NAV_GROUPS.some((group) => group.ids.includes(id))
}

export function groupOfLane(id: string): NavGroup | undefined {
  return NAV_GROUPS.find((group) => group.ids.includes(id))
}

/**
 * The palette's section for one lane. The command palette is the surface that keeps an off-rail lane
 * reachable, so it names WHY that entry is not in the rail instead of listing it like any other.
 */
export function paletteGroupForLane(id: string): string {
  if (OFF_DEFAULT_NAV_IDS.includes(id)) return '实验入口（不在默认导航）'
  const group = groupOfLane(id)
  if (group?.role === 'auxiliary') return `辅助入口（${group.label}）`
  if (DAILY_DESTINATION_IDS.includes(id)) return '日用目的地'
  return '其他入口'
}

/** The lanes the pack calls 辅助入口, straight off the group role so no second list can drift. */
export function auxiliaryLaneIds(): string[] {
  return NAV_GROUPS.filter((group) => group.role === 'auxiliary').flatMap((group) => group.ids)
}

/**
 * The IA self-check, as data so a test can fail with the named violation instead of with a count that
 * nobody can interpret. Returns one string per broken rule; empty means the model is coherent.
 */
export function navInvariantViolations(): string[] {
  const known = knownLaneIds()
  const problems: string[] = []
  const flat = NAV_GROUPS.flatMap((group) => group.ids)
  const seen = new Set<string>()

  for (const group of NAV_GROUPS) {
    if (!group.label.trim()) problems.push(`group ${group.key} has no label`)
    for (const id of group.ids) {
      if (!known.has(id)) problems.push(`group ${group.key} references unknown lane ${id}`)
      if (OFF_DEFAULT_NAV_IDS.includes(id)) problems.push(`lane ${id} is both on- and off-default-nav`)
      if (seen.has(id)) problems.push(`lane ${id} appears in more than one group`)
      seen.add(id)
    }
  }
  if (new Set(NAV_GROUPS.map((group) => group.key)).size !== NAV_GROUPS.length) {
    problems.push('group keys must be unique')
  }
  for (const id of known) {
    if (!seen.has(id) && !OFF_DEFAULT_NAV_IDS.includes(id)) {
      problems.push(`lane ${id} is reachable but in no nav group`)
    }
  }
  for (const id of OFF_DEFAULT_NAV_IDS) {
    if (!REGISTRY_IDS.has(id)) problems.push(`off-nav id ${id} is not a registry lane`)
  }
  for (const id of DAILY_DESTINATION_IDS) {
    if (!known.has(id)) problems.push(`daily destination ${id} is not a known lane`)
    if (OFF_DEFAULT_NAV_IDS.includes(id)) problems.push(`daily destination ${id} is off the default nav`)
  }
  if (!DAILY_DESTINATION_IDS.includes(HOME_LANE_ID)) problems.push('the home lane is not a daily destination')
  return problems
}
