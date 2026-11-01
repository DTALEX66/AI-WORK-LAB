/** WUI-09 · 规则适配与三方差异界面的渲染层契约。
 *
 * 这里验的是"页面上看得见的东西"，与 `src/lib/ruleProjectionTruth.test.ts` 分工不同：真值层证明判定函数
 * 不会被骗，本文件证明 JSX 没有把判定结果重新涂白。逐条对应任务包 WUI-09 的验收：
 *
 *  - 出厂形状（生产调用不带 governance=，快照必然带 snapshot_api.py:296-304 的 UNKNOWN 常量块）下，
 *    四族全部可见为「未知」，页面上不出现「干净」，也不出现把 null 当成 0 的读数；整页没有一行 PROJECTED；
 *  - `drift > 0` 的快照确实画出「漂移」，否则 UNKNOWN 的纪律只是单向造假；
 *  - 五阶段各一行、各带 origin，没有任何一行在没有投影字段时显示为通过；
 *  - 三方比较（前态 / 本方发布态 / 原生现态）渲染为具名缺口，而不是空表、不是「无漂移」「一致」；
 *  - 契约计数携带时可见其值、缺席时是缺口；客户端级声明默认与字段级清单分得很开；
 *  - 页面上没有任何写控件（button / input / select / textarea / form / [role=button] 全为 0），
 *    出路只有链接，且链接地址里没有写语义；
 *  - 「本界面不能授予写权限」「仅恢复本次范围」两句真的在 DOM 里。
 *
 * 断言同时钉 `data-origin` 与可见文本：只钉标记等于承认"用户看不见差别"。
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'

import { RuleAdaptationView } from '@/views/RuleAdaptationView'
import { EMPTY_FOCUS } from '@/lib/recordFocus'
import { mkSnap, UNKNOWN_GOVERNANCE } from '@/test/snapshotFixture'
import type {
  AdapterCapabilityCard, GovernanceFamily, SnapshotGovernance, SnapshotV3,
} from '@/types'

afterEach(cleanup)

const UNKNOWN_FAM: GovernanceFamily = { state: 'UNKNOWN', current: null, drift: null }
const fam = (over: Partial<GovernanceFamily> = {}): GovernanceFamily => ({ ...UNKNOWN_FAM, ...over })
const gov = (rules: GovernanceFamily, rest: Partial<SnapshotGovernance['families']> = {}): SnapshotGovernance => ({
  state: rules.state,
  families: {
    rules,
    skills: rest.skills ?? fam(),
    memory: rest.memory ?? fam(),
    adapters: rest.adapters ?? fam(),
  },
})

/** 出厂快照：governance = snapshot_api.py:296-304 的常量块，workspace 不携带 governance 块。 */
const production = (over: Partial<SnapshotV3> = {}): SnapshotV3 =>
  mkSnap({ governance: UNKNOWN_GOVERNANCE, ...over })

const mkCleanSnap = (): SnapshotV3 => mkSnap({
  governance: gov(fam({ state: 'CLEAN', drift: 0 }), {
    skills: fam({ state: 'CLEAN', drift: 0 }),
    memory: fam({ state: 'CLEAN', drift: 0 }),
    adapters: fam({ state: 'CLEAN', drift: 0 }),
  }),
})

const mkDriftSnap = (drift: number): SnapshotV3 =>
  mkSnap({ governance: gov(fam({ state: 'DRIFT', drift })) })

const mkStageSnap = (current: Record<string, unknown>): SnapshotV3 =>
  mkSnap({ governance: gov(fam({ state: 'DRIFT', drift: 1, current })) })

const card = (over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard => ({
  clientId: 'hermes', displayName: 'Hermes', supportLevel: 'MANAGED', declaredOperations: [],
  matrixOperations: [], operationsDrift: false, registryStatus: 'REGISTERED', writePolicy: 'READ_ONLY',
  risk: 'LOW', runtimeAdapter: null, configOwnershipDefault: null, declaredVersion: null,
  versionReadbackMethod: null, versionObservedAt: null, versionSource: null, detectionMode: null,
  detectionEvidenceState: 'NO_EVIDENCE', protocolConformance: {}, observedAt: null, layers: [],
  nativeStatus: 'NOT_IMPLEMENTED',
  ...over,
} as AdapterCapabilityCard)

/** 最"乐观"的快照：家族全 CLEAN、契约计数 42、能力卡把 writePolicy 写成允许 —— 仍不构成本页的写资格。 */
const mkHostileSnap = (): SnapshotV3 => ({
  ...mkCleanSnap(),
  workspace: { governance: { contracts: 42 } },
  adapterCapabilities: [card({
    writePolicy: 'ALLOW_ALL_WRITES',
    configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE', preserve_unknown: true },
  })],
} as SnapshotV3)

const dimsOf = (container: HTMLElement, prefix: string): HTMLElement[] =>
  Array.from(container.querySelectorAll<HTMLElement>(`[data-dim^="${prefix}"]`))

const originsOf = (rows: HTMLElement[]): (string | undefined)[] => rows.map((r) => r.dataset.origin)

const sideRows = (container: HTMLElement): HTMLElement[] =>
  dimsOf(container, 'threeway.').filter((r) => r.dataset.dim !== 'threeway.drift')

describe('治理家族状态带 · 出厂快照', () => {
  it('四族都在，全为 UNKNOWN，页面上不出现「干净」，也没有一行来自投影', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const rows = Array.from(container.querySelectorAll<HTMLElement>('[data-family]'))
    expect(rows.map((r) => r.dataset.family)).toEqual(['rules', 'skills', 'memory', 'adapters'])
    expect(rows.every((r) => r.dataset.state === 'UNKNOWN')).toBe(true)
    expect(rows.every((r) => r.dataset.evidence === 'gap')).toBe(true)
    expect(screen.getAllByText('未知')).toHaveLength(4)
    expect(screen.queryByText('干净')).toBeNull()
    expect(screen.queryByText('漂移')).toBeNull()
    expect(container.textContent).not.toContain('全部干净')
    expect(container.querySelectorAll('[data-origin="PROJECTED"]')).toHaveLength(0)
    expect(container.textContent).toContain('无明细（UNKNOWN）')
  })

  it('每条 UNKNOWN 都点名生产者位置，而不是留一句"暂无数据"', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const rules = container.querySelector('[data-family="rules"]')
    expect(rules?.textContent).toContain('snapshot_api.py:296-304')
    expect(rules?.textContent).toContain('composition_root.py:460')
  })

  it('drift 为 null 时显示「未知」，绝不显示成 0', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    for (const row of Array.from(container.querySelectorAll('[data-family]'))) {
      expect(row.textContent).toMatch(/漂移计数：未知/)
      expect(row.textContent).not.toMatch(/漂移计数：\s*0/)
    }
  })

  it('drift>0 的快照确实渲染为「漂移」并带计数', () => {
    const { container } = render(<RuleAdaptationView snap={mkDriftSnap(2)} />)
    const rules = container.querySelector('[data-family="rules"]')
    expect(rules?.getAttribute('data-state')).toBe('DRIFT')
    expect(rules?.textContent).toContain('2 项')
    expect(screen.getByText('漂移')).toBeInTheDocument()
  })

  it('快照未到达时仍是四行 UNKNOWN，不预选任何状态', () => {
    const { container } = render(<RuleAdaptationView snap={null} />)
    const rows = Array.from(container.querySelectorAll<HTMLElement>('[data-family]'))
    expect(rows).toHaveLength(4)
    expect(rows.every((r) => r.dataset.state === 'UNKNOWN')).toBe(true)
    expect(container.textContent).toContain('数据源未接入')
    expect(container.querySelectorAll('[data-origin="PROJECTED"]')).toHaveLength(0)
  })
})

describe('五阶段 · 意图 / 投影生成 / 写入 / 原生加载 / 行为验证', () => {
  it('五行齐全、顺序即验收顺序，且没有一行是 PROJECTED', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const rows = dimsOf(container, 'stage.')
    expect(rows.map((r) => r.dataset.dim)).toEqual([
      'stage.intent', 'stage.projection', 'stage.write', 'stage.nativeLoad', 'stage.behaviour',
    ])
    expect(originsOf(rows).every((o) => o === 'SOURCE_GAP')).toBe(true)
    const text = container.textContent ?? ''
    for (const label of ['意图', '投影生成', '写入', '原生加载', '行为验证']) {
      expect(text).toContain(label)
    }
    expect(container.textContent).toContain('无一行来自投影字段')
  })

  it('家族全 CLEAN（drift=0）不把任何阶段涂成通过 —— 邻族成功不算本阶段成功', () => {
    const { container } = render(<RuleAdaptationView snap={mkCleanSnap()} />)
    expect(container.querySelector('[data-family="rules"]')?.getAttribute('data-state')).toBe('CLEAN')
    expect(dimsOf(container, 'stage.').filter((r) => r.dataset.origin === 'PROJECTED')).toHaveLength(0)
  })

  it('current 真带阶段键时才出现那一行 PROJECTED，同族的 null 字段是第三种状态', () => {
    const { container } = render(<RuleAdaptationView snap={mkStageSnap({ write: 'APPLIED', nativeLoad: null })} />)
    const projected = dimsOf(container, 'stage.').filter((r) => r.dataset.origin === 'PROJECTED')
    expect(projected).toHaveLength(1)
    expect(projected[0].dataset.dim).toBe('stage.write')
    expect(projected[0].textContent).toContain('APPLIED')
    const load = container.querySelector('[data-dim="stage.nativeLoad"]')
    expect(load?.getAttribute('data-origin')).toBe('NULL_FIELD')
    expect(load?.textContent).toContain('投影为 null')
    expect(container.querySelector('[data-dim="stage.intent"]')?.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(container.textContent).toContain('1 / 5 行来自投影')
  })

  it('每条缺口都写着「当前 v3 快照未携带」，不折叠成空白单元格', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    for (const row of dimsOf(container, 'stage.')) {
      expect(row.textContent).toContain('来源缺口（当前 v3 快照未携带')
    }
  })
})

describe('三方差异 · 前态 / 本方发布态 / 原生现态', () => {
  it('三侧都在，全是具名缺口，页面明说这不是空表', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const sides = sideRows(container)
    expect(sides.map((r) => r.dataset.dim))
      .toEqual(['threeway.prior', 'threeway.published', 'threeway.native'])
    expect(originsOf(sides).every((o) => o === 'SOURCE_GAP')).toBe(true)
    const text = container.textContent ?? ''
    for (const label of ['前态', '本方发布态', '原生现态']) expect(text).toContain(label)
    expect(text).toContain('具名来源缺口')
  })

  it('三个原因互不相同，各自点名缺的是哪一面', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const notes = sideRows(container).map((r) => r.textContent)
    expect(new Set(notes).size).toBe(3)
    expect(notes[0]).toContain('受管事务')
    expect(notes[1]).toContain('计数')
    expect(notes[2]).toContain('实时配置')
  })

  it('家族 CLEAN 或 drift>0 都填不进任何一格；读回行只说"家族级计数"', () => {
    const { container } = render(<RuleAdaptationView snap={mkDriftSnap(4)} />)
    expect(originsOf(sideRows(container)).includes('PROJECTED')).toBe(false)
    const drift = container.querySelector('[data-dim="threeway.drift"]')
    expect(drift?.getAttribute('data-origin')).toBe('PROJECTED')
    expect(drift?.textContent).toContain('家族级计数')
    expect(drift?.textContent).not.toContain('无漂移')
    expect(drift?.textContent).not.toContain('三方一致')
  })

  it('出厂形状的读回行仍是缺口，并说明 UNKNOWN 不等于被证明的一致', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const drift = container.querySelector('[data-dim="threeway.drift"]')
    expect(drift?.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(drift?.textContent).toContain('UNKNOWN 不是被证明的一致状态')
  })

  it('四种数据形状下都不出现成品结论', () => {
    for (const snap of [production(), mkCleanSnap(), mkDriftSnap(1), null] as (SnapshotV3 | null)[]) {
      const { container } = render(<RuleAdaptationView snap={snap} />)
      expect(screen.queryByText('无漂移')).toBeNull()
      expect(container.textContent).not.toContain('三方一致')
      expect(container.textContent).not.toContain('已合并')
      cleanup()
    }
  })
})

describe('归属范围 · 只报快照携带的字段', () => {
  it('契约计数携带时可见其值', () => {
    const { container } = render(
      <RuleAdaptationView snap={production({ workspace: { governance: { contracts: 3 } } })} />,
    )
    const row = container.querySelector('[data-dim="ownership.contracts"]')
    expect(row?.getAttribute('data-origin')).toBe('PROJECTED')
    expect(row?.textContent).toContain('3 项')
  })

  it('契约计数为 0 时是投影出来的 0，不是缺口', () => {
    const { container } = render(
      <RuleAdaptationView snap={production({ workspace: { governance: { contracts: 0 } } })} />,
    )
    const row = container.querySelector('[data-dim="ownership.contracts"]')
    expect(row?.getAttribute('data-origin')).toBe('PROJECTED')
    expect(row?.textContent).toContain('0 项')
  })

  it('契约块缺席时是具名缺口，不写成 0', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const row = container.querySelector('[data-dim="ownership.contracts"]')
    expect(row?.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(row?.textContent).not.toContain('0 项')
    expect(row?.textContent).toContain('两件事')
  })

  it('能力卡缺席报"未投影"；投影了但没有客户端是另一句话', () => {
    const { container: absent } = render(<RuleAdaptationView snap={production()} />)
    const gapRow = absent.querySelector('[data-dim="ownership.clients"]')
    expect(gapRow?.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(gapRow?.textContent).toContain('两件事')

    const { container: empty } = render(<RuleAdaptationView snap={production({ adapterCapabilities: [] })} />)
    const projected = empty.querySelector('[data-dim="ownership.clients"]')
    expect(projected?.getAttribute('data-origin')).toBe('PROJECTED')
    expect(projected?.textContent).toContain('0 张能力卡')
  })

  it('卡片带声明默认时逐客户端成行，并标成"客户端级，非字段级"', () => {
    const snap = production({
      adapterCapabilities: [
        card({ configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE', preserve_unknown: true } }),
        card({ clientId: 'open-design', displayName: 'Open Design', configOwnershipDefault: null }),
      ],
    })
    const { container } = render(<RuleAdaptationView snap={snap} />)
    const hermes = container.querySelector('[data-dim="ownership.client.hermes"]')
    expect(hermes?.getAttribute('data-origin')).toBe('PROJECTED')
    expect(hermes?.textContent).toContain('USER_OVERLAY')
    expect(hermes?.textContent).toContain('MANAGE')
    expect(hermes?.textContent).toContain('非字段级')
    const od = container.querySelector('[data-dim="ownership.client.open-design"]')
    expect(od?.getAttribute('data-origin')).toBe('NULL_FIELD')
    expect(od?.textContent).toContain('未声明不等于 OBSERVE')
  })

  it('字段级归属清单始终是缺口，并点名 config-ownership.json 为唯一权威', () => {
    const { container } = render(<RuleAdaptationView snap={mkHostileSnap()} />)
    const row = container.querySelector('[data-dim="ownership.fields"]')
    expect(row?.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(row?.textContent).toContain('config/config-ownership.json')
  })

  it('恢复范围 / 冲突检测 / 用户编辑三行都是缺口', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    for (const key of ['ownership.restoreScope', 'ownership.conflict', 'ownership.userEdit']) {
      expect(container.querySelector(`[data-dim="${key}"]`)?.getAttribute('data-origin')).toBe('SOURCE_GAP')
    }
    expect(container.querySelector('[data-dim="ownership.restoreScope"]')?.textContent).toContain('restore_scope')
    expect(container.querySelector('[data-dim="ownership.conflict"]')?.textContent).toContain('snapshot_api.py:316')
  })
})

describe('写边界 · 本界面不能自授', () => {
  it('页面上没有任何写控件（按钮 / 表单 / 输入全为 0）', () => {
    const { container } = render(<RuleAdaptationView snap={mkHostileSnap()} />)
    expect(container.querySelectorAll('button, input, select, textarea, form, [role="button"]')).toHaveLength(0)
    expect(container.textContent).toContain('本界面不能授予写权限')
    // Deliberately NOT asserted: the phrase 此界面只读. `laneStateMatrix.sweep.test.tsx` reserves that
    // permission affordance for lanes that refuse an action a row actually offered; this lane has no
    // action to refuse, so printing it would advertise a decision point that does not exist. The
    // boundary is still stated — in the qualification sentence above and the owner sentence below.
    expect(container.textContent).toContain('Observer 与 sidecar 永久只读')
  })

  it('「仅恢复本次范围」在 DOM 里，且明说本页不执行恢复', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    expect(container.textContent).toContain('仅恢复本次范围')
    expect(container.textContent).toContain('本页不执行恢复')
    expect(container.querySelector('[data-boundary="restore-scope"]')).not.toBeNull()
    expect(container.querySelector('[data-boundary="user-edit"]')?.textContent).toContain('用户编辑不覆盖')
    expect(container.querySelector('[data-boundary="conflict"]')?.textContent).toContain('本页不显示「无冲突」')
  })

  it('真实答案的去处被写进页面，而不是留一个死胡同', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const text = container.textContent ?? ''
    for (const expect_ of ['services/policy', 'services/control', 'WUI-10', 'config-ownership.json']) {
      expect(text).toContain(expect_)
    }
  })

  it('唯一的链接是清除定位，地址里不含写语义，点击只清定位', () => {
    const onFocus = vi.fn()
    const { container } = render(
      <RuleAdaptationView snap={production()}
        focus={{ taskId: null, executionId: null, projectId: 'work-lab' }} onFocus={onFocus} />,
    )
    const links = Array.from(container.querySelectorAll<HTMLAnchorElement>('a[href]'))
    expect(links.length).toBeGreaterThan(0)
    for (const link of links) {
      expect(link.getAttribute('href')).not.toMatch(/apply|write|restore|rollback|delete|promote/i)
    }
    fireEvent.click(links[0])
    expect(onFocus).toHaveBeenCalledWith(EMPTY_FOCUS)
    expect(container.textContent).toContain('快照没有 project↔rule 外键')
  })

  it('hostile 快照（契约 42 + 能力卡声称可写 + 家族全 CLEAN）不新增控件或通过行', () => {
    const { container } = render(<RuleAdaptationView snap={mkHostileSnap()} />)
    expect(container.querySelectorAll('button, input, select, textarea, form')).toHaveLength(0)
    expect(dimsOf(container, 'stage.').filter((r) => r.dataset.origin === 'PROJECTED')).toHaveLength(0)
    expect(container.textContent).toContain('本界面不能授予写权限')
    expect(container.querySelector('[data-dim="ownership.contracts"]')?.textContent).toContain('42 项')
  })

  it('地址被拒绝的定位逐条显示，不静默丢弃', () => {
    const { container } = render(
      <RuleAdaptationView snap={production()}
        focusRejected={['projectId · 定位标识包含非法字符，已拒绝']} />,
    )
    expect(container.textContent).toContain('定位被拒绝')
    expect(screen.getByText('projectId · 定位标识包含非法字符，已拒绝')).toBeInTheDocument()
  })
})

describe('可读性与出处', () => {
  it('正文不小于 12px（不出现 9/10/11px 类）', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    expect(container.innerHTML).not.toMatch(/text-\[(9|10|11)px\]/)
  })

  it('出处块把每条生产者位置写全，读者可复核', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    const text = container.textContent ?? ''
    for (const cite of [
      'snapshot_api.py:82', 'composition_root.py:460', 'snapshot_api.py:296-304',
      'snapshot_api.py:316', 'snapshot_api.py:312-315', 'workspace_evidence.py:143-156',
      'config/config-ownership.json', 'services/policy',
    ]) {
      expect(text).toContain(cite)
    }
    expect(container.querySelector('[data-block="provenance"]')).not.toBeNull()
  })

  it('六个块都在同一页上（家族 / 阶段 / 三方 / 归属 / 边界 / 出处）', () => {
    const { container } = render(<RuleAdaptationView snap={production()} />)
    expect(Array.from(container.querySelectorAll<HTMLElement>('[data-block]')).map((e) => e.dataset.block))
      .toEqual(['families', 'stages', 'three-way', 'ownership', 'boundary', 'provenance'])
  })
})
