// WUI-09 (20261009) · 规则适配与三方差异 —— 只读真值层。
//
// 这一层只做一件事：把 v3 快照里**确实存在**的规则/配置治理字段读出来，并把 WUI-09 验收清单里
// 那些**不存在**的字段点名成为来源缺口，附带生产者侧的原因。它不是视图层，不碰 DOM、不读
// window、不写任何存储，因此 `ruleProjectionTruth.test.ts` 能脱离渲染逐条判定。
//
// 生产者事实（不是推测，逐行读过）：
//
// * `packages/client-neutral-core/scripts/snapshot_api.py:82` 把 governance 交给
//   `_governance_projection(governance)`；`snapshot_api.py:44` 的 `governance` 形参默认 `None`，
//   而唯一的生产调用 `services/orchestration/composition_root.py:460` 不带 `governance=`
//   （仓库里唯一传参的调用点是 `tests/workflow-assistance/test_snapshot_sse_live.py:104`）。
//   所以**出厂快照必然走 snapshot_api.py:296-304 那个 UNKNOWN 常量块**：四个家族全部
//   `{state:"UNKNOWN", current:null, drift:null}`。
// * 若哪天真传入 governance，家族记录仍然只有三键（`snapshot_api.py:316`），
//   且 `DRIFT` 只在 `drift > 0` 时写出（`snapshot_api.py:312-315`）；`current`/`drift` 双 null 才是
//   UNKNOWN。这就是本页允许出现的最大表达力：一个家族级状态 + 一个可空的整数计数。
// * `workspace.governance`（`packages/client-neutral-core/scripts/workspace_evidence.py:143-156`）
//   是另一条真实投影：`contracts` 取 `CURRENT_STATE.json` 的 `contracts.count`
//   （`workspace_evidence.py:148`），是个计数，不是规则明细。
//
// 由此得到本文件的三条纪律：
//   1. UNKNOWN 就渲染成 UNKNOWN。`drift: null` 不是 0，也不是「无漂移」。
//   2. 意图 / 投影生成 / 写入 / 原生加载 / 行为验证 **没有阶段状态位**，三方比较（前态 /
//      本方发布态 / 原生现态）**没有对应字段**，恢复范围与冲突检测同样没有。它们渲染为具名缺口 +
//      生产者原因，绝不渲染成空表、绝不借家族 CLEAN/DRIFT 冒充某一阶段通过。
//   3. Observer 永久只读（`apps/observer/AGENTS.md`）：本页不自授写资格。快照里的任何值——
//      CLEAN 家族、drift=0、契约计数、能力卡 `writePolicy`——都不改变 `canWrite: false`。
//
// 三态口径与 `src/views/RecordInspector.tsx` 的 `Dim` / `renderDimension` 完全一致
// （PROJECTED / NULL_FIELD / SOURCE_GAP），本文件产出的行对象可直接交给它渲染。
import type { AdapterCapabilityCard, FamilyState, GovernanceFamily, SnapshotV3 } from '@/types'

export type RuleTruthOrigin = 'PROJECTED' | 'NULL_FIELD' | 'SOURCE_GAP'

/** 一行可渲染的真值。与 `InspectorDimension` 结构同形，故 RecordInspector 的 renderDimension 直接吃它。 */
export interface RuleTruthRow {
  key: string
  label: string
  origin: RuleTruthOrigin
  /** 只有 PROJECTED 才有值；缺口与 null 字段一律 null，渲染层因此不可能显示一个编造出来的字符串 */
  value: string | null
  note: string
}

const projected = (key: string, label: string, value: string): RuleTruthRow =>
  ({ key, label, origin: 'PROJECTED', value, note: '' })

const nullField = (key: string, label: string, note: string): RuleTruthRow =>
  ({ key, label, origin: 'NULL_FIELD', value: null, note })

const gap = (key: string, label: string, note: string): RuleTruthRow =>
  ({ key, label, origin: 'SOURCE_GAP', value: null, note })

/** 生产者位置，供页面「出处」块与测试逐条引用；改生产者就改这里，不散落在 JSX 里。 */
export const PRODUCER = {
  snapshotGovernance: 'packages/client-neutral-core/scripts/snapshot_api.py:82 → :289-317',
  noGovernanceArg: 'services/orchestration/composition_root.py:460 的 build_snapshot(...) 不传 governance=（snapshot_api.py:44 默认 None；全仓唯一传参处是 tests/workflow-assistance/test_snapshot_sse_live.py:104）',
  unknownBlock: 'snapshot_api.py:296-304：_governance_projection(None) 直接返回四个 {state:"UNKNOWN",current:null,drift:null}',
  familyThreeKeys: 'snapshot_api.py:316：每个家族只写 {state,current,drift} 三键',
  driftRule: 'snapshot_api.py:312-315：只有 drift>0 才写 DRIFT，current/drift 双 null 才是 UNKNOWN',
  workspaceContracts: 'packages/client-neutral-core/scripts/workspace_evidence.py:143-156（contracts 取 CURRENT_STATE.json 的 contracts.count，见 :148）',
  ownershipAuthority: 'config/config-ownership.json（workflow/config-ownership/v2，字段级归属唯一权威）',
  writeOwner: 'services/policy + services/control 的受管 config 事务（WUI-10）',
} as const

// ---------------------------------------------------------------------------
// 1. 四大家族：状态带就是快照里的状态带
// ---------------------------------------------------------------------------

export const RULE_FAMILY_KEYS = ['rules', 'skills', 'memory', 'adapters'] as const
export type RuleFamilyKey = (typeof RULE_FAMILY_KEYS)[number]

/** 家族可见名 —— 导出是因为 RulesPolicyView 用同一组词，两处漂移就是两个车道各说各话。 */
export const RULE_FAMILY_LABELS: Record<RuleFamilyKey, string> = {
  rules: '规则', skills: '技能', memory: '记忆', adapters: '适配器',
}

export interface RuleFamilyTruth {
  key: RuleFamilyKey
  label: string
  /** 快照给的原始状态，未做任何提升：生产快照恒为 'UNKNOWN' */
  state: FamilyState
  drift: number | null
  current: unknown | null
  /** drift 的可见文本。null → 未知，绝不是 '0' */
  driftText: string
  currentText: string
  /** 该家族是否携带任何明细（与 RulesPolicyView 的 hasFamilyData 同一判据） */
  hasEvidence: boolean
  /** 无明细时的原因，带生产者位置；有明细时为空串 */
  note: string
}

function isRuleFamilyKey(v: string): v is RuleFamilyKey {
  return (RULE_FAMILY_KEYS as readonly string[]).includes(v)
}

function familyOf(snap: SnapshotV3 | null, key: RuleFamilyKey): GovernanceFamily | null {
  const families = snap?.governance?.families
  if (!families) return null
  const raw: GovernanceFamily | undefined = families[key]
  return raw && typeof raw === 'object' ? raw : null
}

function unknownFamily(key: RuleFamilyKey, note: string): RuleFamilyTruth {
  return {
    key, label: RULE_FAMILY_LABELS[key], state: 'UNKNOWN', drift: null, current: null,
    driftText: '未知（快照未给数，不是 0）', currentText: '未投影', hasEvidence: false, note,
  }
}

/** 家族记录的「无明细」原因：把生产调用不带 governance 这件事说清楚，而不是留一行空白。 */
const NO_GOVERNANCE_NOTE =
  `快照未传入治理数据源 —— ${PRODUCER.noGovernanceArg}，因此 ${PRODUCER.unknownBlock} 原样出厂。`

export function ruleFamilies(snap: SnapshotV3 | null): RuleFamilyTruth[] {
  return RULE_FAMILY_KEYS.map((key) => {
    if (!snap) return unknownFamily(key, '快照未到达（数据源未接入），家族状态无从判定，保持 UNKNOWN。')
    const family = familyOf(snap, key)
    if (!family) return unknownFamily(key, `快照的 governance.families 里没有 ${key} 这一族（生产者未投影该族）。`)

    const state: FamilyState = family.state === 'CLEAN' || family.state === 'DRIFT' ? family.state : 'UNKNOWN'
    const drift = typeof family.drift === 'number' && !Number.isNaN(family.drift) ? family.drift : null
    const hasEvidence = state !== 'UNKNOWN' || drift !== null || family.current != null
    if (!hasEvidence) return unknownFamily(key, NO_GOVERNANCE_NOTE)
    return {
      key,
      label: RULE_FAMILY_LABELS[key],
      state,
      drift,
      current: family.current ?? null,
      driftText: drift === null ? '未知（快照未给数，不是 0）' : `${drift} 项（生产者给出的家族级计数）`,
      currentText: family.current == null
        ? '未投影（current 为 null；不猜内容）'
        : '携带 current，但本页不展开为规则明细（详见阶段与三方差异块）',
      hasEvidence: true,
      note: '',
    }
  })
}

export interface FamilySummary {
  /** 快照顶层 governance.state 字符串原样；snap 为 null 时是 null */
  governanceState: string | null
  anyEvidence: boolean
  /** 任一家族 drift>0 —— 这是本页能拿到的最强不一致证据，仍不是三方比较 */
  anyDrift: boolean
  driftedLabels: string[]
}

export function familySummary(snap: SnapshotV3 | null): FamilySummary {
  const families = ruleFamilies(snap)
  const drifted = families.filter((f) => f.state === 'DRIFT' || (typeof f.drift === 'number' && f.drift > 0))
  return {
    governanceState: snap?.governance?.state ?? null,
    anyEvidence: families.some((f) => f.hasEvidence),
    anyDrift: drifted.length > 0,
    driftedLabels: drifted.map((f) => f.label),
  }
}

/** 供测试钉住的单族查询；未知 key 返回 null 而不是伪造一行 UNKNOWN。 */
export function ruleFamily(snap: SnapshotV3 | null, key: string): RuleFamilyTruth | null {
  return isRuleFamilyKey(key) ? ruleFamilies(snap).find((f) => f.key === key) ?? null : null
}

// ---------------------------------------------------------------------------
// 2. 五个阶段：意图 / 投影生成 / 写入 / 原生加载 / 行为验证
// ---------------------------------------------------------------------------

export type RuleStageKey = 'intent' | 'projection' | 'write' | 'nativeLoad' | 'behaviour'

export interface RuleStageDefinition {
  key: RuleStageKey
  label: string
  /** 这一行要变成 PROJECTED，快照必须携带的字段名（本页只认这个位置，不自造第二套 schema） */
  requiredField: string
  /** 缺口的生产者原因 */
  reason: string
}

/** 阶段清单本身也是契约：删掉一条就是 WUI-09 少答了一问，测试逐条走这张表。 */
export const RULE_STAGE_GAPS: readonly RuleStageDefinition[] = [
  {
    key: 'intent',
    label: '意图 · 谁在哪一层声明了哪条规则',
    requiredField: 'governance.families.rules.current[intent]',
    reason: `规则意图住在 ${PRODUCER.ownershipAuthority} 的 layers/operation_modes 与各客户端声明里，快照只投 governance.{state,families}（${PRODUCER.familyThreeKeys}），没有任何 intent 字段。`,
  },
  {
    key: 'projection',
    label: '投影生成 · 意图 → 客户端可写文件/字段',
    requiredField: 'governance.families.rules.current[projection]',
    reason: `投影产物是同步脚本生成的计划与暂存（sync_hermes_workflow_assets.py 一类的 backup-before-publish  staging），快照的 governance 块里没有计划/摘要字段（${PRODUCER.familyThreeKeys}）；workspace 侧只带计数与清单名（${PRODUCER.workspaceContracts}）。`,
  },
  {
    key: 'write',
    label: '写入 · 受管事务实际落盘',
    requiredField: 'governance.families.rules.current[write]',
    reason: `写入结论由 ${PRODUCER.writeOwner} 在唯一事务账本里判定，快照没有任何写入/回执字段（${PRODUCER.unknownBlock} 与 ${PRODUCER.familyThreeKeys} 里都没有），本页因此不能显示"已写入"。`,
  },
  {
    key: 'nativeLoad',
    label: '原生加载 · 客户端真实读到哪一版',
    requiredField: 'governance.families.rules.current[nativeLoad]',
    reason: `原生加载要回读客户端生效状态；快照能给的最强证据是家族级 drift 整数（${PRODUCER.driftRule}），它说的是"有几项不一致"，不是"客户端读到了哪一版"。`,
  },
  {
    key: 'behaviour',
    label: '行为验证 · 规则在真实执行里生效',
    requiredField: 'governance.families.rules.current[behaviour]',
    reason: `行为验证需要一条规则与一次执行之间的外键；快照的执行面只到 state/agent/session/sourceRef（types.ts 的 Execution），governance 块与执行面之间没有连接键，所以不冒充验证通过。`,
  },
] as const

/** 阶段状态唯一可能到货的位置：`GovernanceFamily.current`（types.ts 里声明为 `unknown | null`）。
 *  生产者从不填它；填了也只接受"对象 + 该阶段键"，其余一律按缺口/空字段处理。 */
function stageCarrier(snap: SnapshotV3 | null): Record<string, unknown> | null {
  const current = familyOf(snap, 'rules')?.current
  if (current && typeof current === 'object' && !Array.isArray(current)) {
    return current as Record<string, unknown>
  }
  return null
}

function stageValueText(key: RuleStageKey, raw: unknown): string | null {
  if (typeof raw === 'string' && raw.trim() !== '') return `${key}=${raw}`
  if (typeof raw === 'boolean') return `${key}=${raw ? 'true' : 'false'}`
  if (typeof raw === 'number' && !Number.isNaN(raw)) return `${key}=${raw}`
  return null
}

export function stageRows(snap: SnapshotV3 | null): RuleTruthRow[] {
  const carrier = stageCarrier(snap)
  return RULE_STAGE_GAPS.map((stage) => {
    const key = `stage.${stage.key}`
    if (!snap) {
      return gap(key, stage.label, `快照未到达（数据源未接入），阶段状态无从判定；${stage.reason}`)
    }
    if (!carrier || !Object.prototype.hasOwnProperty.call(carrier, stage.key)) {
      return gap(key, stage.label,
        `快照不携带 ${stage.requiredField}；${stage.reason}（家族 CLEAN/DRIFT 不推进本阶段。）`)
    }
    const raw = carrier[stage.key]
    if (raw === null) {
      return nullField(key, stage.label,
        `生产者查询过 ${stage.requiredField} 并如实回报 null —— 未知不等于失败，也不等于通过`)
    }
    const text = stageValueText(stage.key, raw)
    if (text === null) {
      return nullField(key, stage.label,
        `${stage.requiredField} 携带的值不是可显示标量（${typeof raw}），原样不解读、不改写成通过`)
    }
    return projected(key, stage.label, `${text}（来自 governance.families.rules.current，生产者给出的阶段事实）`)
  })
}

/** 阶段块是否有任何一行真的是 PROJECTED —— 视图用它决定是否显示「本阶段没有一行来自投影字段」的提示。 */
export function stageProjectedCount(snap: SnapshotV3 | null): number {
  return stageRows(snap).filter((r) => r.origin === 'PROJECTED').length
}

// ---------------------------------------------------------------------------
// 3. 三方差异：前态 / 本方发布态 / 原生现态 —— 具名缺口，不是空表
// ---------------------------------------------------------------------------

export interface ThreeWaySide {
  key: 'prior' | 'published' | 'native'
  label: string
  reason: string
}

export const THREE_WAY_GAP: {
  summary: string
  nearestTruth: string
  sides: readonly ThreeWaySide[]
} = {
  summary: '三方比较（前态 / 本方发布态 / 原生现态）在 v3 快照里没有对应字段，因此下面三行全部是具名来源缺口：'
    + '不渲染成空表，不写成「无漂移」，也不写成「一致」。',
  nearestTruth: `本页能读到的最接近的东西是家族级 drift 计数（${PRODUCER.driftRule}）：drift>0 只说明存在不一致，`
    + '不说明是哪一条规则、哪一侧、什么时候不一致，所以它不能填满任何一格。',
  sides: [
    {
      key: 'prior',
      label: '前态 · 写入之前客户端原样',
      reason: `写入前态只存在于受管事务的计划/回执里（${PRODUCER.writeOwner}，config-ownership.json 的 apply_only_actual_managed_drift 与 apply_readback_required 说的就是这一对），`
        + `快照的 governance 块既无 prior/before 字段也无时间戳（${PRODUCER.familyThreeKeys}）。`,
    },
    {
      key: 'published',
      label: '本方发布态 · WORK-LAB 发布的目标内容与摘要',
      reason: `发布态内容是 packages/client-neutral-core/skills/**、config/SOUL.md 与 bin/ 的受管资产，快照只投 governance.{state,families}（${PRODUCER.snapshotGovernance}）；`
        + `workspace 侧只带 contracts/skills 的计数与清单名（${PRODUCER.workspaceContracts}），没有任何发布正文摘要字段。`,
    },
    {
      key: 'native',
      label: '原生现态 · 客户端当前真实状态',
      reason: `原生现态需要回读客户端实时配置；快照不读实时配置（apps/observer/AGENTS.md 的只读边界），governance 三键里没有现态正文、版本或读取时刻（${PRODUCER.driftRule}）。`,
    },
  ] as const,
}

export function threeWayRows(snap: SnapshotV3 | null): RuleTruthRow[] {
  return THREE_WAY_GAP.sides.map((side) => {
    const key = `threeway.${side.key}`
    if (!snap) return gap(key, side.label, `快照未到达（数据源未接入），本侧更无从取值；${side.reason}`)
    return gap(key, side.label, side.reason)
  })
}

/** drift 读回行：真实存在时才显示，并明确它不是三方比较的替代品。 */
export function driftReadbackRow(snap: SnapshotV3 | null): RuleTruthRow {
  const label = '快照实际携带的不一致证据（家族级计数，非三方比较）'
  if (!snap) return gap('threeway.drift', label, '快照未到达，连计数也没有。')
  const parts = ruleFamilies(snap).map((f) => `${f.label} ${f.drift === null ? '未知' : f.drift}`)
  const summary = familySummary(snap)
  if (!summary.anyDrift) {
    return gap('threeway.drift', label,
      `四个家族的 drift 全为 null 或 0（${parts.join(' · ')}）——「读不到」与「读到且为 0」在本页都显示 UNKNOWN，`
      + `因为生产者从未传入 governance（${PRODUCER.noGovernanceArg}），UNKNOWN 不是被证明的一致状态。`)
  }
  return projected('threeway.drift', label,
    `${parts.join(' · ')} —— drift>0 的家族：${summary.driftedLabels.join('/')}。这是家族级计数，`
    + `不指名规则、不指认哪一侧，因此不构成前态/发布态/原生现态的差异。`)
}

// ---------------------------------------------------------------------------
// 4. 归属范围：只读快照真正携带的那些字段
// ---------------------------------------------------------------------------

/** `workspace.governance.contracts` 是唯一确定投影的归属范围数字（workspace_evidence.py:148）。 */
export function contractsRow(snap: SnapshotV3 | null): RuleTruthRow {
  const label = '治理契约计数 · workspace.governance.contracts'
  if (!snap) return gap('ownership.contracts', label, '快照未到达（数据源未接入），不预填任何计数。')
  const governance = (snap.workspace as { governance?: Record<string, unknown> } | undefined)?.governance
  if (!governance || typeof governance !== 'object') {
    return gap('ownership.contracts', label,
      `快照未携带 workspace.governance —— ${PRODUCER.workspaceContracts} 没读到 CURRENT_STATE.json 时整块缺席，与「读到但计数为空」是两件事。`)
  }
  const raw = governance.contracts
  if (raw === undefined) {
    return gap('ownership.contracts', label,
      `workspace.governance 存在但没有 contracts 键（${PRODUCER.workspaceContracts} 取的是 contracts.count，缺键即未投影）。`)
  }
  if (raw === null) {
    return nullField('ownership.contracts', label,
      '生产者读了 CURRENT_STATE.json，contracts.count 本身就是 null —— 这是事实，不是 0，也不是缺源。')
  }
  if (typeof raw === 'number' && !Number.isNaN(raw)) {
    return projected('ownership.contracts', label, `${raw} 项（来自 ${PRODUCER.workspaceContracts}）`)
  }
  return nullField('ownership.contracts', label, `contracts 携带的是非数字（${typeof raw}），原样不解读、不换算成计数。`)
}

export interface ClientOwnershipTruth {
  clientId: string
  displayName: string
  layer: string | null
  mode: string | null
  preserveUnknown: boolean | null
  writePolicy: string | null
}

function ownershipOf(card: AdapterCapabilityCard): ClientOwnershipTruth {
  const declared = card.configOwnershipDefault
  return {
    clientId: card.clientId,
    displayName: card.displayName || card.clientId,
    layer: declared?.layer ?? null,
    mode: declared?.mode ?? null,
    preserveUnknown: typeof declared?.preserve_unknown === 'boolean' ? declared.preserve_unknown : null,
    writePolicy: card.writePolicy ?? null,
  }
}

/** 能力卡携带的客户端级归属默认 —— 真实存在，但它是客户端级，不是字段级。 */
export function clientOwnership(snap: SnapshotV3 | null): ClientOwnershipTruth[] {
  const cards = snap?.adapterCapabilities
  if (!cards || !Array.isArray(cards)) return []
  return cards.map(ownershipOf)
}

/** 字段级清单行的标题。导出是为了页面与测试共用一个字符串，而不是在两处各拼一遍再对不上。 */
export const OWNERSHIP_FIELD_LABEL = '字段级归属清单 · MANAGE / OBSERVE / IGNORE / FORBIDDEN'

export function ownershipRows(snap: SnapshotV3 | null): RuleTruthRow[] {
  const rows: RuleTruthRow[] = [contractsRow(snap)]

  const cards = snap?.adapterCapabilities
  if (!cards || !Array.isArray(cards)) {
    rows.push(gap('ownership.clients', '客户端级归属默认 · adapterCapabilities[].configOwnershipDefault',
      '快照未携带 adapterCapabilities（生产者未投影能力卡），连客户端级的 layer/mode/preserve_unknown 默认也读不到 —— 与「投影了但没有客户端」是两件事。'))
  } else if (cards.length === 0) {
    rows.push(projected('ownership.clients', '客户端级归属默认 · adapterCapabilities[].configOwnershipDefault',
      '0 张能力卡（已投影，结果为空）。不因此推断任何客户端的归属。'))
  } else {
    for (const card of cards) {
      const own = ownershipOf(card)
      const declared = [
        `layer ${own.layer ?? '未声明'}`,
        `mode ${own.mode ?? '未声明'}`,
        `preserve_unknown ${own.preserveUnknown === null ? '未声明' : String(own.preserveUnknown)}`,
      ].join(' · ')
      rows.push(own.layer || own.mode || own.preserveUnknown !== null
        ? projected(`ownership.client.${own.clientId}`,
            `客户端 ${own.displayName} 的声明默认（客户端级，非字段级）`,
            `${declared}；writePolicy ${own.writePolicy ?? '未声明'} —— 这是生产者声明，不是本页的写资格。`)
        : nullField(`ownership.client.${own.clientId}`,
            `客户端 ${own.displayName} 的声明默认（客户端级，非字段级）`,
            '能力卡存在但 configOwnershipDefault 为 null/空 —— 未声明不等于 OBSERVE，也不等于可写。'))
    }
  }

  rows.push(gap('ownership.fields', OWNERSHIP_FIELD_LABEL,
    `字段级唯一权威是 ${PRODUCER.ownershipAuthority}（layers × operation_modes × adapter_defaults + preserve_unknown），`
    + `它不进入快照投影：snapshot_api.py 只投 governance.{state,families}，workspace.governance 只带计数与清单名（${PRODUCER.workspaceContracts}）。`
    + '因此"这一条规则归哪一层、是什么模式"不是本页能逐条回答的问题。'))
  rows.push(gap('ownership.userEdit', '用户编辑是否被覆盖（保护现态）',
    `config-ownership.json 声明 default_unknown=OBSERVE_QUARANTINE 与各适配器 preserve_unknown: true —— 保护意图在权威文件里，`
    + `生效与否要读回客户端现态，快照不携带（${PRODUCER.familyThreeKeys}）。本页只声明这条边界，不声称保护已经发生。`))
  rows.push(gap('ownership.restoreScope', '恢复范围 · 仅恢复本次范围',
    `恢复是一次受管写事务，范围（哪条规则 / 哪一层 / 哪台机器）由 ${PRODUCER.writeOwner} 的事务账本决定；`
    + `快照无 restore_scope 与上一次写入范围（${PRODUCER.unknownBlock}），所以本页连"本次范围是什么"都读不到，只声明边界。`))
  rows.push(gap('ownership.conflict', '冲突检测 · 用户编辑与本方发布是否冲突',
    `快照无 conflict / user_edit_override 字段（${PRODUCER.familyThreeKeys}），冲突裁决属 ${PRODUCER.writeOwner} 的事务前置检查（WUI-10）。`
    + '本页不显示"无冲突"，因为那需要两边正文，而两边正文都不在契约里。'))
  return rows
}

// ---------------------------------------------------------------------------
// 5. 写资格：本页不自授
// ---------------------------------------------------------------------------

export const READ_ONLY_STATEMENT = {
  qualification: '本界面不能授予写权限',
  qualificationWhy: `写资格由服务端判定（${PRODUCER.writeOwner}：主体 / 范围 / 前态 / 版本 / 幂等），Observer 与 sidecar 永久只读。`
    + '快照里的任何值——CLEAN 家族、drift=0、契约计数、能力卡 writePolicy——都不构成本页的写资格，'
    + '本页也不提供"看起来已经接上"的写控件。',
  realAnswer: `真实答案住在两处：字段归属看 ${PRODUCER.ownershipAuthority}；能否写、写到哪、失败怎么回退看 ${PRODUCER.writeOwner} 的事务读回（WUI-10）。`,
  restore: '仅恢复本次范围',
  restoreWhy: '本页不执行恢复，也不显示可点的恢复控件：恢复属于服务端事务，且范围只能由那条事务界定。'
    + '快照既不携带前态也不携带上一次写入范围（见上面三行缺口），所以"恢复"在本页是一个边界声明，不是一个动作。',
  userEdit: '用户编辑不覆盖',
  userEditWhy: '保护来自 preserve_unknown / default_unknown=OBSERVE_QUARANTINE 的字段级权威，'
    + '本页只显示能力卡携带的客户端级声明，并把它标成"声明"而不是"结果"。',
} as const

export interface WriteQualification {
  canWrite: false
  /** 唯一可能的来源：服务端资格判定，本页没有它的投影字段 */
  grantedBy: string
  statement: string
}

/** 恒定 false：`canWrite` 的字面类型就是 `false`，任何快照值都无法把它翻过来 —— 想授写得改生产者，改不了这个返回值。 */
export function writeQualification(_snap: SnapshotV3 | null): WriteQualification {
  return { canWrite: false, grantedBy: PRODUCER.writeOwner, statement: READ_ONLY_STATEMENT.qualification }
}
