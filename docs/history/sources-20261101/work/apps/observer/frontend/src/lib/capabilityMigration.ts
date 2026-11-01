// WUI-08 · the capability-migration chain, as far as a read-only projection may say.
//
// The taskpack's acceptance is a six-step chain: 源评价 → 用户选择目标 → 差异损失 → 隔离试用 → 目标验证 →
// 获准部署读回恢复. Four of those steps have NO field anywhere in `workflow/snapshot/v3`: no producer writes
// a migration target, a loss diff, a trial record or a target verification today. This module therefore does
// two things and refuses a third. It states what IS projected (the source evaluation ladder, and the write
// policy that decides whether a deployment readback is even reachable from here), and it names every missing
// step with the producer that would have to emit it. The third thing it refuses is the tempting one: rendering
// a step as 未开始 or 0 would turn "nobody projected this" into a claim about the world.
//
// The rule that shapes the whole file: 源成功不代替目标成功. A source client whose ladder is fully MET does
// not move a single downstream step forward -- the ladder belongs to the source, and `steps()` keeps them
// separate by construction, which is what the negative test attacks.
import type { AdapterCapabilityCard } from '@/types'
import { establishedFacts } from '@/lib/capabilityAssets'

export type MigrationStageId = 'sourceEvaluation' | 'targetChosen' | 'differenceLoss'
                                             | 'isolatedTrial' | 'targetVerification' | 'deployReadback'

export type MigrationStageState = 'PROJECTED' | 'NOT_PROJECTED'

export interface MigrationStage {
  id: MigrationStageId
  label: string
  state: MigrationStageState
  /** what proves the state: a field path, or the producer that would have to emit one */
  basis: string
  /** the owning producer for a gap, or the owning projection for a projected fact */
  owner: string
  /** rendered detail -- a gap says what is missing, a projected step says what was read */
  detail: string
}

export const MIGRATION_STAGES: { id: MigrationStageId, label: string }[] = [
  { id: 'sourceEvaluation', label: '源评价' },
  { id: 'targetChosen', label: '用户选择目标' },
  { id: 'differenceLoss', label: '差异损失' },
  { id: 'isolatedTrial', label: '隔离试用' },
  { id: 'targetVerification', label: '目标验证' },
  { id: 'deployReadback', label: '获准部署读回恢复' },
]

const GAP = (id: MigrationStageId, label: string, basis: string, owner: string, detail: string): MigrationStage =>
  ({ id, label, state: 'NOT_PROJECTED', basis, owner, detail })

/**
 * The chain for one client. `cards` is the adapter-card projection the lane already renders, so the
 * evaluation step cannot disagree with the ladder the user sees two sections above.
 */
export function migrationChain(card: AdapterCapabilityCard | null): MigrationStage[] {
  const labels = new Map(MIGRATION_STAGES.map((stage) => [stage.id, stage.label]))
  const label = (id: MigrationStageId) => labels.get(id) ?? id

  if (card === null) {
    return MIGRATION_STAGES.map((stage) => GAP(stage.id, stage.label,
                                               'snap.adapterCapabilities',
                                               'packages/client-neutral-core/scripts/adapter_capability_projection.py',
                                               '能力卡未投影（来源不可读或无适配器注册），整条链无可判定的起点'))
  }

  const facts = establishedFacts(card)
  const source: MigrationStage = {
    id: 'sourceEvaluation',
    label: label('sourceEvaluation'),
    state: 'PROJECTED',
    basis: 'snap.adapterCapabilities[].layers / .verbEvidence',
    owner: 'packages/client-neutral-core/scripts/adapter_capability_projection.py',
    detail: `来源侧已确立 ${facts.metLayers.length} / ${card.layers.length} 层，`
          + `最高到 ${facts.highestMetLayer ?? '无'}，`
          + `原生状态 ${card.nativeStatus}；这是「${card.displayName}」自身的评价，不是任何目标的验证`,
  }

  // The write policy is the only part of the last step that is real today: with an OBSERVE ownership default
  // or a non-write policy, a deployment readback cannot exist because nothing may be written from here.
  const observablePolicy = card.writePolicy || card.configOwnershipDefault?.mode || 'unknown'
  const deploy: MigrationStage = {
    id: 'deployReadback',
    label: label('deployReadback'),
    state: 'PROJECTED',
    basis: 'snap.adapterCapabilities[].writePolicy / .configOwnershipDefault.mode',
    owner: 'config/config-ownership.json (经 adapter registry 投影)',
    detail: `本仓对该客户端的写入策略为 ${observablePolicy}`
          + (card.configOwnershipDefault?.mode === 'OBSERVE'
              ? '：只观察，不写入，因此不存在可读回的部署'
              : '：部署与否仍须由目标侧验证读回判定，此处不代为断言'),
  }

  return [
    source,
    GAP('targetChosen', label('targetChosen'), 'snap.adapterCapabilities[].migrationTarget',
        'Workflow 侧的能力迁移合同（尚未有生产者）',
        '快照里没有任何字段说明这次迁移要去哪个目标；选择是用户的一次决定，需要有生产者把它记下来才可判'),
    GAP('differenceLoss', label('differenceLoss'), 'migration diff 投影',
        'Workflow 侧差异比较（源能力集 vs 目标能力集）',
        '差异损失需要两侧能力集同时在场；目标未定即无从比较，此处给出任何数字都是编造'),
    GAP('isolatedTrial', label('isolatedTrial'), 'trial record 投影',
        'WUI-21 的隔离试用三页及其读模型合同',
        '没有试用记录被投影，因此不能说「未试用」——只能说本仓没有看过'),
    GAP('targetVerification', label('targetVerification'), 'target verification 投影',
        '目标侧证据生产者（外部软件自己执行，WORK-LAB 只读回）',
        '快照里没有目标验证字段：来源侧评价再高也不能推进这一步，它只能来自目标侧的读回证据'),
    deploy,
  ]
}

export function chainCounts(stages: MigrationStage[]): { projected: number, notProjected: number } {
  return {
    projected: stages.filter((stage) => stage.state === 'PROJECTED').length,
    notProjected: stages.filter((stage) => stage.state === 'NOT_PROJECTED').length,
  }
}
