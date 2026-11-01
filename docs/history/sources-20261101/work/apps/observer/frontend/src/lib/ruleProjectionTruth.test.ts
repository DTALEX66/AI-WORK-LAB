/** WUI-09 · 规则投影真值层的逐条判定（纯函数，不碰 DOM）。
 *
 * 这一文件守的是四条会被"顺手优化"掉的红线：
 *
 *  1. 生产快照的四个家族必然是 UNKNOWN —— 因为 `services/orchestration/composition_root.py:460`
 *     调用 `build_snapshot` 时不带 `governance=`（`snapshot_api.py:44` 默认 None），投影直接返回
 *     `snapshot_api.py:296-304` 的 UNKNOWN 常量块。任何把它渲染成 CLEAN 的代码都是造假。
 *  2. `drift: null` 不是 0。0 是"读到了、结果为空"，null 是"没读"。
 *  3. `drift > 0` 必须真的显示成漂移（`snapshot_api.py:312-315`），否则这一路计数就白投影了。
 *  4. 五阶段与三方比较在 v3 里没有字段：家族 CLEAN 不能推进任何阶段，缺口必须带生产者原因，
 *     而不是被折叠成空表或"无差异"。
 *
 * 每条都写正反两面：正面对真实存在的字段（契约计数、drift>0、能力卡的客户端级默认、
 * current 里真到货的阶段键），反面对生产形状与 hostile 形状（writePolicy 声称可写也不给资格）。
 */
import { describe, it, expect } from 'vitest'

import {
  clientOwnership, contractsRow, driftReadbackRow, familySummary, OWNERSHIP_FIELD_LABEL, PRODUCER,
  READ_ONLY_STATEMENT, RULE_FAMILY_KEYS, RULE_FAMILY_LABELS, RULE_STAGE_GAPS, ruleFamilies, ruleFamily,
  stageProjectedCount, stageRows, THREE_WAY_GAP, threeWayRows, writeQualification, ownershipRows,
} from '@/lib/ruleProjectionTruth'
import { mkSnap, UNKNOWN_GOVERNANCE } from '@/test/snapshotFixture'
import type { AdapterCapabilityCard, GovernanceFamily, SnapshotGovernance, SnapshotV3 } from '@/types'

/** The snapshot as it actually ships: the UNKNOWN constant block, no governance argument. */
const production = (over: Partial<SnapshotV3> = {}): SnapshotV3 =>
  mkSnap({ governance: UNKNOWN_GOVERNANCE, ...over })

const family = (over: Partial<GovernanceFamily> = {}): GovernanceFamily =>
  ({ state: 'UNKNOWN', current: null, drift: null, ...over })

const governanceOf = (rules: GovernanceFamily, rest: Partial<SnapshotGovernance['families']> = {}): SnapshotGovernance =>
  ({
    state: rules.state === 'UNKNOWN' ? 'UNKNOWN' : rules.state,
    families: { rules, skills: rest.skills ?? family(), memory: rest.memory ?? family(), adapters: rest.adapters ?? family() },
  })

const card = (over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard =>
  ({
    clientId: 'hermes', displayName: 'Hermes', supportLevel: 'MANAGED', declaredOperations: [],
    matrixOperations: [], operationsDrift: false, registryStatus: 'REGISTERED', writePolicy: 'READ_ONLY',
    risk: 'LOW', runtimeAdapter: null, configOwnershipDefault: null, declaredVersion: null,
    versionReadbackMethod: null, versionObservedAt: null, versionSource: null, detectionMode: null,
    detectionEvidenceState: 'NO_EVIDENCE', protocolConformance: {}, observedAt: null, layers: [],
    nativeStatus: 'NOT_IMPLEMENTED',
    ...over,
  }) as AdapterCapabilityCard

describe('ruleFamilies · 出厂快照的四个家族', () => {
  it('恰好四族，顺序与 governance.families 的键一致', () => {
    expect(ruleFamilies(production()).map((f) => f.key)).toEqual([...RULE_FAMILY_KEYS])
    expect(ruleFamilies(null).map((f) => f.key)).toEqual([...RULE_FAMILY_KEYS])
  })

  it('生产形状（governance=None 的常量块）四族全 UNKNOWN，无一族被渲染成 CLEAN', () => {
    const families = ruleFamilies(production())
    expect(families).toHaveLength(4)
    for (const f of families) {
      expect(f.state).toBe('UNKNOWN')
      expect(f.hasEvidence).toBe(false)
      expect(f.current).toBeNull()
      expect(f.drift).toBeNull()
    }
    expect(families.some((f) => f.state === 'CLEAN')).toBe(false)
    expect(families.some((f) => f.state === 'DRIFT')).toBe(false)
    expect(familySummary(production()).anyEvidence).toBe(false)
  })

  it('UNKNOWN 的原因说明点名生产者位置，而不是留一句"暂无数据"', () => {
    for (const f of ruleFamilies(production())) {
      expect(f.note).toContain('snapshot_api.py:296-304')
      expect(f.note).toContain('composition_root.py:460')
    }
  })

  it('快照未到达时仍是 UNKNOWN，并说明是数据源问题', () => {
    const families = ruleFamilies(null)
    expect(families.every((f) => f.state === 'UNKNOWN')).toBe(true)
    expect(families.every((f) => f.note.includes('快照未到达'))).toBe(true)
    expect(familySummary(null).governanceState).toBeNull()
  })

  it('缺某一族（families 里没有 adapters）报该族缺投影，不借用邻族状态', () => {
    const snap = mkSnap({
      governance: {
        state: 'CLEAN',
        families: { rules: family({ state: 'CLEAN', drift: 0 }), skills: family({ state: 'CLEAN', drift: 0 }), memory: family({ state: 'CLEAN', drift: 0 }) } as SnapshotGovernance['families'],
      },
    })
    const adapters = ruleFamily(snap, 'adapters')
    expect(adapters?.state).toBe('UNKNOWN')
    expect(adapters?.note).toContain('没有 adapters 这一族')
  })

  it('未知键不伪造一行：ruleFamily(snap, "prompts") 返回 null', () => {
    expect(ruleFamily(production(), 'prompts')).toBeNull()
    expect(RULE_FAMILY_LABELS.rules).toBe('规则')
  })

  it('drift:null 渲染文本里出现"未知"，绝不出现单独的 0', () => {
    for (const f of ruleFamilies(production())) {
      expect(f.driftText).toContain('未知')
      expect(f.driftText).not.toBe('0')
      expect(f.driftText).not.toMatch(/^0/)
    }
  })

  it('drift>0 真的渲染成 DRIFT，并带上计数的来源措辞', () => {
    const snap = mkSnap({ governance: governanceOf(family({ state: 'DRIFT', drift: 2 })) })
    const rules = ruleFamily(snap, 'rules')
    expect(rules?.state).toBe('DRIFT')
    expect(rules?.drift).toBe(2)
    expect(rules?.driftText).toContain('2 项')
    expect(rules?.hasEvidence).toBe(true)
    expect(rules?.note).toBe('')
    expect(familySummary(snap).anyDrift).toBe(true)
    expect(familySummary(snap).driftedLabels).toEqual(['规则'])
  })

  it('drift=0 是"读到且为空"，与 null 的"没读"分得开', () => {
    const snap = mkSnap({ governance: governanceOf(family({ state: 'CLEAN', drift: 0, current: 'x' })) })
    const rules = ruleFamily(snap, 'rules')
    expect(rules?.drift).toBe(0)
    expect(rules?.driftText).toMatch(/^0 项/)
    expect(rules?.currentText).toContain('不展开为规则明细')
  })

  it('生产者状态字符串不在状态带之外被解读', () => {
    const snap = mkSnap({ governance: governanceOf(family({ state: 'DRIFT', drift: 3 })) })
    expect(familySummary(snap).governanceState).toBe('DRIFT')
  })
})

describe('stageRows · 五阶段（意图/投影生成/写入/原生加载/行为验证）', () => {
  it('清单恰好五阶段，顺序即验收顺序', () => {
    expect(RULE_STAGE_GAPS.map((s) => s.key))
      .toEqual(['intent', 'projection', 'write', 'nativeLoad', 'behaviour'])
  })

  it('每条缺口的原因都点名"快照里没有这个字段"及生产者位置', () => {
    for (const stage of RULE_STAGE_GAPS) {
      expect(stage.requiredField).toContain('governance.families.rules.current')
      expect(stage.reason.length).toBeGreaterThan(30)
    }
  })

  it('生产形状：五行全 SOURCE_GAP，没有一行是 pass', () => {
    const rows = stageRows(production())
    expect(rows).toHaveLength(5)
    expect(rows.every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
    expect(rows.every((r) => r.value === null)).toBe(true)
    expect(stageProjectedCount(production())).toBe(0)
  })

  it('家族 CLEAN + drift=0 不推进任何阶段（邻居成功不算本阶段成功）', () => {
    const snap = mkSnap({ governance: governanceOf(family({ state: 'CLEAN', drift: 0 })) })
    expect(snap.governance.families.rules.state).toBe('CLEAN')
    expect(stageRows(snap).every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
    expect(stageProjectedCount(snap)).toBe(0)
  })

  it('current 真带阶段键时该行才 PROJECTED，同族其它行仍是缺口', () => {
    const snap = mkSnap({
      governance: governanceOf(family({ state: 'DRIFT', drift: 1, current: { write: 'APPLIED', nativeLoad: null } })),
    })
    const rows = stageRows(snap)
    const write = rows.find((r) => r.key === 'stage.write')
    const load = rows.find((r) => r.key === 'stage.nativeLoad')
    const intent = rows.find((r) => r.key === 'stage.intent')
    expect(write?.origin).toBe('PROJECTED')
    expect(write?.value).toContain('APPLIED')
    // current 里明确出现 null：查询过、如实回报空 —— 这是第三种状态，既不是缺口也不是通过
    expect(load?.origin).toBe('NULL_FIELD')
    expect(load?.value).toBeNull()
    expect(intent?.origin).toBe('SOURCE_GAP')
    expect(stageProjectedCount(snap)).toBe(1)
  })

  it('current 是数组/标量等非对象时不接受"看起来像阶段"的值', () => {
    const snap = mkSnap({ governance: governanceOf(family({ state: 'DRIFT', drift: 1, current: 'write=APPLIED' })) })
    expect(stageRows(snap).every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
  })

  it('current 里的非可显示值（对象）渲染为 NULL_FIELD 而不是被序列化成通过', () => {
    const snap = mkSnap({ governance: governanceOf(family({ current: { write: { nested: 1 } } })) })
    const write = stageRows(snap).find((r) => r.key === 'stage.write')
    expect(write?.origin).toBe('NULL_FIELD')
    expect(write?.value).toBeNull()
    expect(write?.note).toContain('不是可显示标量')
  })

  it('快照未到达 → 五行仍全 SOURCE_GAP', () => {
    expect(stageRows(null).every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
    expect(stageRows(null)[0].note).toContain('快照未到达')
  })
})

describe('contractsRow · workspace.governance.contracts（唯一真实的归属范围数字）', () => {
  it('有计数时 PROJECTED，且值就是快照里的数字', () => {
    const row = contractsRow(production({ workspace: { governance: { contracts: 3 } } }))
    expect(row.origin).toBe('PROJECTED')
    expect(row.value).toContain('3')
    expect(row.value).toContain('workspace_evidence.py:143-156')
  })

  it('0 是投影出来的 0，不是缺口', () => {
    const row = contractsRow(production({ workspace: { governance: { contracts: 0 } } }))
    expect(row.origin).toBe('PROJECTED')
    expect(row.value).toMatch(/^0 项/)
  })

  it('count 本身为 null 是第三种状态，既不写 0 也不写缺源', () => {
    // 生产者真会给出 null（workspace_evidence.py:148 `(current.get("contracts") or {}).get("count")`
    // 在 CURRENT_STATE.json 缺 contracts 块时返回 None），而 types.ts 把该字段声明成 `contracts?: number`，
    // 少写了 null 这一支。这里用窄化 cast 表达生产者真相，types.ts 由他人持有，不改。
    const row = contractsRow(production({ workspace: { governance: { contracts: null as unknown as number } } }))
    expect(row.origin).toBe('NULL_FIELD')
    expect(row.value).toBeNull()
    expect(row.note).toContain('不是 0')
  })

  it('整块 workspace.governance 缺席才是 SOURCE_GAP', () => {
    const row = contractsRow(production({ workspace: {} }))
    expect(row.origin).toBe('SOURCE_GAP')
    expect(row.note).toContain('两件事')
  })

  it('governance 存在但没有 contracts 键 → SOURCE_GAP（未投影），不当作 null 字段', () => {
    const row = contractsRow(production({ workspace: { governance: { modules: [] } } }))
    expect(row.origin).toBe('SOURCE_GAP')
    expect(row.note).toContain('没有 contracts 键')
  })

  it('快照未到达 → SOURCE_GAP，不预填计数', () => {
    const row = contractsRow(null)
    expect(row.origin).toBe('SOURCE_GAP')
    expect(row.value).toBeNull()
  })
})

describe('THREE_WAY_GAP · 前态 / 本方发布态 / 原生现态', () => {
  it('恰好三侧，身份可寻址', () => {
    expect(THREE_WAY_GAP.sides.map((s) => s.key)).toEqual(['prior', 'published', 'native'])
    expect(threeWayRows(production()).map((r) => r.key))
      .toEqual(['threeway.prior', 'threeway.published', 'threeway.native'])
  })

  it('三侧全是 SOURCE_GAP，且各自带原因（不是同一句复制三遍）', () => {
    const rows = threeWayRows(production())
    expect(rows.every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
    expect(rows.every((r) => r.value === null)).toBe(true)
    const notes = rows.map((r) => r.note)
    expect(new Set(notes).size).toBe(3)
    expect(rows[0].note).toContain('受管事务')
    expect(rows[1].note).toContain('计数')
    expect(rows[2].note).toContain('实时配置')
  })

  it('家族 CLEAN / drift>0 都填不进任何一格', () => {
    const clean = mkSnap({ governance: governanceOf(family({ state: 'CLEAN', drift: 0 })) })
    expect(threeWayRows(clean).every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
    const drift = mkSnap({ governance: governanceOf(family({ state: 'DRIFT', drift: 4 })) })
    expect(threeWayRows(drift).every((r) => r.origin === 'SOURCE_GAP')).toBe(true)
  })

  it('drift>0 时读回行是 PROJECTED，并明说它是家族级计数、不指名规则与侧别', () => {
    const snap = mkSnap({ governance: governanceOf(family({ state: 'DRIFT', drift: 4 })) })
    const row = driftReadbackRow(snap)
    expect(row.origin).toBe('PROJECTED')
    expect(row.value).toContain('4')
    expect(row.value).toContain('家族级计数')
    expect(row.value).toContain('不构成前态/发布态/原生现态的差异')
  })

  it('生产形状的读回行仍是缺口，并解释 UNKNOWN 不等于一致', () => {
    const row = driftReadbackRow(production())
    expect(row.origin).toBe('SOURCE_GAP')
    expect(row.note).toContain('UNKNOWN 不是被证明的一致状态')
    expect(row.note).toContain('composition_root.py:460')
  })

  it('摘要与最近真值两段散文各点名一次位置', () => {
    expect(THREE_WAY_GAP.summary).toContain('没有对应字段')
    expect(THREE_WAY_GAP.nearestTruth).toContain('snapshot_api.py:312-315')
  })
})

describe('ownershipRows · 归属范围只报快照携带的', () => {
  it('顺序固定：契约计数 → 客户端级默认 → 字段级缺口 → 编辑保护 → 恢复范围 → 冲突检测', () => {
    expect(ownershipRows(production()).map((r) => r.key)).toEqual([
      'ownership.contracts', 'ownership.clients', 'ownership.fields',
      'ownership.userEdit', 'ownership.restoreScope', 'ownership.conflict',
    ])
  })

  it('能力卡缺席是"没投影"，空数组是"投影了但没有客户端"', () => {
    const absent = ownershipRows(production()).find((r) => r.key === 'ownership.clients')
    expect(absent?.origin).toBe('SOURCE_GAP')
    expect(absent?.note).toContain('两件事')

    const empty = ownershipRows(production({ adapterCapabilities: [] })).find((r) => r.key === 'ownership.clients')
    expect(empty?.origin).toBe('PROJECTED')
    expect(empty?.value).toContain('0 张能力卡')
  })

  it('卡片带声明默认时逐客户端成行，并标成"客户端级，非字段级"', () => {
    const snap = production({
      adapterCapabilities: [
        card({ clientId: 'hermes', displayName: 'Hermes', configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE', preserve_unknown: true }, writePolicy: 'STAGED_READBACK' }),
        card({ clientId: 'open-design', displayName: 'Open Design', configOwnershipDefault: null, writePolicy: 'NONE' }),
      ],
    })
    const rows = ownershipRows(snap)
    expect(rows.filter((r) => r.key.startsWith('ownership.client.'))).toHaveLength(2)
    const hermes = rows.find((r) => r.key === 'ownership.client.hermes')
    expect(hermes?.origin).toBe('PROJECTED')
    expect(hermes?.value).toContain('USER_OVERLAY')
    expect(hermes?.value).toContain('MANAGE')
    expect(hermes?.value).toContain('preserve_unknown true')
    expect(hermes?.value).toContain('不是本页的写资格')
    expect(hermes?.label).toContain('非字段级')
    // 有能力卡但默认三字段皆空 → NULL_FIELD，不猜成 OBSERVE
    const od = rows.find((r) => r.key === 'ownership.client.open-design')
    expect(od?.origin).toBe('NULL_FIELD')
    expect(od?.note).toContain('未声明不等于 OBSERVE')
    expect(clientOwnership(snap).map((c) => c.clientId)).toEqual(['hermes', 'open-design'])
    expect(clientOwnership(production())).toEqual([])
  })

  it('字段级清单恒为缺口，并点名 config-ownership.json 为唯一权威', () => {
    const row = ownershipRows(production()).find((r) => r.key === 'ownership.fields')
    expect(row?.origin).toBe('SOURCE_GAP')
    expect(row?.note).toContain('config/config-ownership.json')
    expect(row?.label).toBe(OWNERSHIP_FIELD_LABEL)
    // 即使契约计数与能力卡都到货，字段级仍然不是本页能逐条回答的
    const full = ownershipRows(production({
      workspace: { governance: { contracts: 9 } },
      adapterCapabilities: [card({ configOwnershipDefault: { layer: 'PROJECT_OVERLAY', mode: 'MANAGE', preserve_unknown: true } })],
    })).find((r) => r.key === 'ownership.fields')
    expect(full?.origin).toBe('SOURCE_GAP')
  })

  it('恢复范围与冲突检测各自成行、各自带快照里没有该字段的理由', () => {
    const rows = ownershipRows(production())
    const restore = rows.find((r) => r.key === 'ownership.restoreScope')
    const conflict = rows.find((r) => r.key === 'ownership.conflict')
    const userEdit = rows.find((r) => r.key === 'ownership.userEdit')
    expect(restore?.origin).toBe('SOURCE_GAP')
    expect(restore?.note).toContain('restore_scope')
    expect(conflict?.origin).toBe('SOURCE_GAP')
    expect(conflict?.note).toContain('snapshot_api.py:316')
    expect(userEdit?.origin).toBe('SOURCE_GAP')
    expect(userEdit?.note).toContain('preserve_unknown')
  })
})

describe('writeQualification · 本页不自授写资格', () => {
  it('快照未到达 / 生产形状 / 全 CLEAN：都判 false', () => {
    for (const snap of [null, production(), mkSnap({ governance: governanceOf(family({ state: 'CLEAN', drift: 0 })) })]) {
      expect(writeQualification(snap).canWrite).toBe(false)
    }
  })

  it('hostile 形状（契约计数 + 能力卡声称可写 + 家族 CLEAN）也不构成资格', () => {
    const snap = mkSnap({
      governance: governanceOf(family({ state: 'CLEAN', drift: 0 })),
      workspace: { governance: { contracts: 42 } },
      adapterCapabilities: [card({ writePolicy: 'ALLOW_ALL_WRITES', configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE' } })],
    })
    const verdict = writeQualification(snap)
    expect(verdict.canWrite).toBe(false)
    expect(verdict.grantedBy).toBe(PRODUCER.writeOwner)
    expect(verdict.statement).toBe(READ_ONLY_STATEMENT.qualification)
  })

  it('声明文本给出"本界面不能授予写权限"与"仅恢复本次范围"，并指向真实答案所在', () => {
    expect(READ_ONLY_STATEMENT.qualification).toBe('本界面不能授予写权限')
    expect(READ_ONLY_STATEMENT.restore).toBe('仅恢复本次范围')
    expect(READ_ONLY_STATEMENT.qualificationWhy).toContain('永久只读')
    expect(READ_ONLY_STATEMENT.realAnswer).toContain('services/policy')
    expect(READ_ONLY_STATEMENT.realAnswer).toContain('config-ownership.json')
    expect(READ_ONLY_STATEMENT.restoreWhy).toContain('不执行恢复')
  })
})
