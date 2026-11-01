// WUI-13 · the legacy routes, each with a recorded disposition. The population is whatever the table below
// holds — no count is restated in prose, because this file's own header claimed "23" for a table that had
// already grown to 26, which is the drift the note below this header warns about.
//
// The owner's seed table is `docs/history/owner-inputs/20261009/final-readable/inputs/
// frontend_route_mapping.proposed.csv`. It is a SEED, not a migrated fact, and the route doc is explicit
// that a design-page id may not simply replace an old id. So this module records, per seed row, where the
// old address actually lands today, which object parameters must survive, who still links to it, and which
// test proves it. `legacyRoutes.contract.test.tsx` then reads the CSV itself and fails if this ledger and
// the seed table stop agreeing — a hand-copied list of 23 would otherwise drift the first time a lane is
// renamed, and the drift would look like a successful migration.
//
// Two rules every row obeys:
// * an old id is never silently repurposed. Merging means the old address renders the destination AND
//   says so; it never means "show whatever is newest";
// * the object namespaces stay separate: `taskId`, `executionId`, `projectId` and the evidence byte-range
//   params are four different addresses, and no row may fold one into another.
import { VIEW_BY_ID, OVERVIEW_ID } from './viewRegistry'
import { OFF_DEFAULT_NAV_IDS } from './navigation'
import { EVIDENCE_PARAM_NAMES } from './evidenceRange'

export type LegacyDisposition =
  /** folded into the landing destination; the old id still resolves */
  | 'merged-into-home'
  /** the old id IS a destination page today */
  | 'destination'
  /** still a real lane, reachable from the rail in its compatibility group */
  | 'compat-lane'
  /** left the default nav; deep link, palette entry and implementation all intact */
  | 'demoted'

export interface LegacyRouteRow {
  seedId: string
  disposition: LegacyDisposition
  /** the lane id the old address resolves to today */
  resolvesTo: string
  /** object parameters that must survive the address */
  params: readonly string[]
  consumers: string
  policy: string
  evidence: string
}

const RECORD_PARAMS = ['taskId', 'executionId'] as const
const PROJECT_PARAMS = ['projectId'] as const

export const LEGACY_ROUTE_ROWS: LegacyRouteRow[] = [
  {
    seedId: 'overview', disposition: 'merged-into-home', resolvesTo: OVERVIEW_ID, params: [],
    consumers: 'Tauri 主窗默认入口、历史收藏的 ?view=overview',
    policy: '同一泳道承载 项目监控 首页；不建第二首页，旧地址渲染新首页并在标题上说明它是项目监控。',
    evidence: 'src/homeIa.contract.test.tsx（默认落地 + 未知泳道不静默跳）',
  },
  {
    seedId: 'projects', disposition: 'compat-lane', resolvesTo: 'projects', params: PROJECT_PARAMS,
    consumers: '旧项目列表深链',
    policy: '保留为兼容只读入口；日用语义并入首页项目集合，projectId 深链改指 project-detail。',
    evidence: 'src/lib/projectIdentity.test.ts + homeIa 同名不合并用例',
  },
  {
    seedId: 'agents', disposition: 'compat-lane', resolvesTo: 'agents', params: [],
    consumers: '旧"智能体"泳道链接',
    policy: '软件视角并入 软件环境 目的地；旧车道保留，不变成单一 Chat Bot 页。',
    evidence: 'src/views/views.test.tsx + 状态矩阵 sweep 覆盖全部车道',
  },
  {
    seedId: 'software', disposition: 'compat-lane', resolvesTo: 'software', params: [],
    consumers: 'S31/32 安装身份面板链接',
    policy: '目的地 软件环境 组合本车道（整段复用，不复制实现）；本 id 仍是兼容入口。',
    evidence: 'src/views/softwareEnvironment.contract.test.tsx',
  },
  {
    seedId: 'work', disposition: 'compat-lane', resolvesTo: 'work', params: RECORD_PARAMS,
    consumers: 'D3 工作闭环深链、Inspector 链接',
    policy: '兼容只读入口；不再作为默认任务中心，taskId/executionId 语义不变。',
    evidence: 'src/views/WorkView.behavior.test.tsx',
  },
  {
    seedId: 'executions', disposition: 'compat-lane', resolvesTo: 'executions', params: RECORD_PARAMS,
    consumers: '执行列表深链',
    policy: '低频只读；选定项目/问题后进入，不改选别的执行。',
    evidence: 'src/views/views.test.tsx + recordFocus 拒绝用例',
  },
  {
    seedId: 'execution-detail', disposition: 'compat-lane', resolvesTo: 'execution-detail', params: ['executionId'],
    consumers: 'L10 执行详情深链',
    policy: '深链兼容；地址未命中时给明确缺失，绝不静默改选最新一条。',
    evidence: 'src/lib/recordFocus.test.ts + 本文件 stale-id 用例',
  },
  {
    seedId: 'evidence', disposition: 'compat-lane', resolvesTo: 'evidence', params: EVIDENCE_PARAM_NAMES,
    consumers: 'REQ-RANGE-20261007 证据区间地址',
    policy: '按需只读；身份/权限/区间校验保留，参数只在证据车道存活。',
    evidence: 'src/views/EvidenceView.test.tsx + App URL 写回用例',
  },
  {
    seedId: 'task-packs', disposition: 'compat-lane', resolvesTo: 'task-packs', params: [],
    consumers: '本仓工程诊断链接',
    policy: '低频；不要求被观察项目登记任务包。',
    evidence: 'src/views/views.test.tsx',
  },
  {
    seedId: 'delivery', disposition: 'compat-lane', resolvesTo: 'delivery', params: [],
    consumers: '交付/回执状态链接',
    policy: '按需；回执状态与接受状态分开显示，不合并成一个成功。',
    evidence: 'src/laneTruth.sweep.test.tsx',
  },
  {
    seedId: 'tools', disposition: 'compat-lane', resolvesTo: 'tools', params: [],
    consumers: '旧工具清单链接',
    policy: '目的地 能力资产 承载来源/评价/迁移语义；本车道保留为兼容入口，不承诺完整运行器。',
    evidence: 'src/views/capabilityAssets.contract.test.tsx',
  },
  {
    seedId: 'integrations', disposition: 'compat-lane', resolvesTo: 'integrations', params: [],
    consumers: 'MCP/插件连接链接',
    policy: '连接详情属规则与适配语境；不建知识主库。',
    evidence: 'src/views/views.test.tsx',
  },
  {
    seedId: 'models', disposition: 'compat-lane', resolvesTo: 'models', params: [],
    consumers: '模型/用量链接',
    policy: '计量并入 用量缓存 目的地；连接配置属规则语境，不另起模型平台。',
    evidence: 'src/views/usageCache.contract.test.tsx',
  },
  {
    seedId: 'monitoring', disposition: 'compat-lane', resolvesTo: 'monitoring', params: [],
    consumers: '采集健康链接',
    policy: '作辅助视图，不做第二个总览。',
    evidence: 'src/laneStateMatrix.sweep.test.tsx',
  },
  {
    seedId: 'memory', disposition: 'compat-lane', resolvesTo: 'memory', params: [],
    consumers: '旧记忆车道链接',
    policy: '只显示获准的 AAOS 连接/版本解释；未接入如实说明，不建本地记忆主库。',
    evidence: 'src/views/views.test.tsx',
  },
  {
    seedId: 'rules-policy', disposition: 'compat-lane', resolvesTo: 'rules-policy', params: [],
    consumers: 'L7 治理车道链接',
    policy: '目的地 规则适配 承载五阶段与三方差异；本车道保留原判据，两页同源不互猜。',
    evidence: 'src/views/ruleAdaptation.contract.test.tsx',
  },
  {
    seedId: 'approvals', disposition: 'compat-lane', resolvesTo: 'approvals', params: [],
    consumers: '审批投影链接',
    policy: '按对象展示本方/受委托决定；不设三项目上级审批中心。',
    evidence: 'src/views/permissionContract.test.tsx',
  },
  {
    seedId: 'audit', disposition: 'compat-lane', resolvesTo: 'audit', params: [],
    consumers: '历史定位链接',
    policy: '历史可定位，不作为默认指令源。',
    evidence: 'src/views/views.test.tsx',
  },
  {
    seedId: 'trust', disposition: 'compat-lane', resolvesTo: 'trust', params: [],
    consumers: '证据质量链接',
    policy: '质量是解释，不是独立总控制页。',
    evidence: 'src/laneTransportTruth.sweep.test.tsx',
  },
  {
    seedId: 'workflows', disposition: 'compat-lane', resolvesTo: 'workflows', params: [],
    consumers: 'L10 模板车道',
    policy: '作能力资产的有效模板参考；不承诺编排引擎。',
    evidence: 'src/views/l10-views.test.tsx',
  },
  {
    seedId: 'workflow-editor', disposition: 'demoted', resolvesTo: 'workflow-editor', params: [],
    consumers: '实验页深链与命令面板',
    policy: '退出默认导航：不在 rail，实现/深链/面板入口保留，到页显示退出原因与未接通说明。',
    evidence: 'src/homeIa.contract.test.tsx（demoted lane 用例）+ lib/viewRegistry.test.ts 不变量',
  },
  {
    seedId: 'observer', disposition: 'compat-lane', resolvesTo: 'observer', params: [],
    consumers: 'L10 观察者车道',
    policy: '与项目监控/采集诊断合并语义，不重复提供同一组状态。',
    evidence: 'src/views/l10-views.test.tsx',
  },
  {
    seedId: 'settings', disposition: 'compat-lane', resolvesTo: 'settings', params: [],
    consumers: '设置链接',
    policy: '低频底部入口；外观/存储/隐私/连接说明，不复制业务页。采集生命周期属 隐私与采集 车道。',
    evidence: 'src/views/settingsPrivacy.contract.test.tsx',
  },
]

export const LEGACY_SEED_IDS: string[] = LEGACY_ROUTE_ROWS.map((row) => row.seedId)

/** Where an old address lands today. `undefined` means the ledger does not know that id — never a fallback. */
export function resolveLegacyRoute(seedId: string): LegacyRouteRow | undefined {
  return LEGACY_ROUTE_ROWS.find((row) => row.seedId === seedId)
}

/** The lane a seed id actually renders. Same resolution rule the shell uses, exposed for the contract. */
export function laneForSeed(seedId: string): string | undefined {
  const row = resolveLegacyRoute(seedId)
  if (!row) return undefined
  return row.resolvesTo === OVERVIEW_ID ? OVERVIEW_ID : (VIEW_BY_ID[row.resolvesTo] ? row.resolvesTo : undefined)
}

/** Self-check the ledger against the registry: every row must point at a lane that exists. */
export function legacyRouteViolations(): string[] {
  const problems: string[] = []
  const seen = new Set<string>()
  for (const row of LEGACY_ROUTE_ROWS) {
    if (seen.has(row.seedId)) problems.push(`duplicate seed row ${row.seedId}`)
    seen.add(row.seedId)
    if (row.resolvesTo !== OVERVIEW_ID && !VIEW_BY_ID[row.resolvesTo]) {
      problems.push(`seed ${row.seedId} points at unknown lane ${row.resolvesTo}`)
    }
    if (row.disposition === 'demoted' && !OFF_DEFAULT_NAV_IDS.includes(row.resolvesTo)) {
      problems.push(`seed ${row.seedId} claims demoted but ${row.resolvesTo} is still on the default nav`)
    }
    if (row.disposition !== 'demoted' && OFF_DEFAULT_NAV_IDS.includes(row.resolvesTo)) {
      problems.push(`seed ${row.seedId} claims ${row.disposition} but ${row.resolvesTo} left the default nav`)
    }
    for (const field of ['consumers', 'policy', 'evidence'] as const) {
      if (!row[field].trim()) problems.push(`seed ${row.seedId} has no ${field}`)
    }
  }
  const demotedSeeds = LEGACY_ROUTE_ROWS.filter((row) => row.disposition === 'demoted').map((row) => row.seedId)
  for (const id of OFF_DEFAULT_NAV_IDS) {
    if (!demotedSeeds.includes(id)) problems.push(`lane ${id} left the default nav with no seed row explaining it`)
  }
  return problems
}
