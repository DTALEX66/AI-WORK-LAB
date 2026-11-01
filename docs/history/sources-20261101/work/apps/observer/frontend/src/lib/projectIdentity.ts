// WUI-04 · project identity as the projection can actually answer it.
//
// The acceptance line says: 非Git/多目录/worktree/同名不合并. Read literally against the producer, that
// is a statement about what the UI may NOT do, because the v3 snapshot answers identity with exactly one
// key. Verified in `packages/client-neutral-core/scripts/snapshot_api.py` and
// `services/orchestration/composition_root.py`:
//
//   * `projectId` is the canonical store's primary key — the only unique identity that reaches the UI;
//   * `displayName` is NOT unique and is defaulted to the id when absent, so two rows can legitimately
//     carry the same name and three can carry the same directory;
//   * `identityState` only ever arrives as RESOLVED or UNRESOLVED — the resolver's CONFLICT state
//     (`project_identity_resolver.py:48`) is never projected;
//   * `repositories` is read with a default of `[]` from a row builder that never sets it, so an empty
//     list is a producer gap, NOT "this project has no repositories";
//   * `workingAreas` is aggregated from executions, so `[]` means no execution recorded one;
//   * there is no worktree id, no repository id and no per-project observation state in the payload.
//
// So this module does two things: it keys everything by `projectId`, and it names the identity questions
// the projection cannot answer as data the pages render — which is the only way the UI can say
// "同名不合并" truthfully instead of implying a resolution it never received.
import type { Project, SnapshotV3 } from '@/types'

/** The one addressable identity. Nothing in the UI may construct a looser key. */
export function identityKeyOf(project: Pick<Project, 'projectId'>): string {
  return project.projectId
}

export interface IdentityGap {
  key: string
  question: string
  /** what the producer actually does, so the reader can tell a gap from a design choice */
  reason: string
}

/** Identity questions WUI-04 asks and the v3 snapshot does not answer. Rendered, not hidden. */
export const PROJECT_IDENTITY_GAPS: IdentityGap[] = [
  {
    key: 'repositories',
    question: '这个项目关联哪些仓库？',
    reason: 'snapshot_api.py 以 `project.get("repositories", [])` 读取，而 composition_root.py 的 _project_rows 从不写该键：空数组是生产者缺口，不等于「无仓库」。',
  },
  {
    key: 'worktree',
    question: '同一仓库的哪个 worktree？',
    reason: 'payload 无 worktreeId / repositoryId；project_identity_resolver.py 有这两个概念，但未被快照消费。',
  },
  {
    key: 'conflict',
    question: '身份是否冲突？',
    reason: 'identityState 只会被投影为 RESOLVED 或 UNRESOLVED，解析器的 CONFLICT 态从未进入快照。',
  },
  {
    key: 'perProjectObservation',
    question: '这个项目本身的观测连通状态？',
    reason: '观测时间戳与连通状态只有快照级 transport，没有按项目的观测轴；页面顶部的传输状态覆盖整个快照，不针对单项目。',
  },
]

/**
 * Display names shared by more than one `projectId`. A duplicate is not an error to hide: it is the
 * exact case where a name-based link could open the wrong project, so the pages surface it and keep the
 * id visible.
 */
export function duplicateDisplayNames(projects: Project[]): Set<string> {
  const byName = new Map<string, number>()
  for (const project of projects) {
    const name = project.displayName ?? ''
    if (!name) continue
    byName.set(name, (byName.get(name) ?? 0) + 1)
  }
  return new Set([...byName].filter(([, count]) => count > 1).map(([name]) => name))
}

/** Working areas are aggregated from executions, so an empty list is a stated absence, never "no directory". */
export function workingAreaFacts(project: Project): { areas: string[]; aggregatedFromExecutions: true } {
  return { areas: project.workingAreas ?? [], aggregatedFromExecutions: true }
}

/** Distinct participating software across the project and its executions, `null` names dropped not zeroed. */
export function participantsOf(snap: SnapshotV3 | null, project: Project): string[] {
  const names = new Set<string>()
  if (project.agentPlatform) names.add(project.agentPlatform)
  for (const execution of snap?.executions ?? []) {
    if (execution.anchorProjectId !== project.projectId) continue
    if (execution.agent) names.add(execution.agent)
  }
  return [...names]
}
