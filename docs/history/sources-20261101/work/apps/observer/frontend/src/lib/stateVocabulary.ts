// WUI-11 · the eight states the UI must be able to tell apart.
//
// The taskpack line is: 无数据 / 未连接 / 不支持 / 隐藏 / 延迟 / 局部故障 / 权限不足 / 不存在分别解释.
// "分别解释" is the whole requirement: a single "no data" component reused for all eight is what makes a
// reader believe the product is empty when it is actually refusing, or healthy when the source is merely
// behind. This module is the one place that says which of the eight the v3 snapshot can actually produce,
// from which field, and what the reader may then do.
//
// Two of the eight have NO producer signal, verified against the projection code: hidden-by-policy and
// insufficient-permission. The sidecar refuses reads by reason code (`outside-declared-surface`,
// sensitive-name counters) but never projects a permission state, and nothing in the payload says a field
// was suppressed for privacy. Those two render as affordances the UI *can* be asked to show by a caller
// that genuinely knows (an evidence-range refusal, a future Control answer) — never as a default, and
// never inferred from an absence. That distinction lives here so no view invents it locally.
import type { SnapshotV3 } from '@/types'

export type ProductState =
  | 'no-data' | 'not-connected' | 'unsupported' | 'hidden-by-policy'
  | 'delayed' | 'partial-failure' | 'insufficient-permission' | 'not-existing'

export interface StateDefinition {
  id: ProductState
  label: string
  /** what the state asserts, in the reader's terms */
  meaning: string
  /** the projected field(s) that can produce it, or the honest statement that none can */
  signal: string
  /** whether the snapshot can answer it at all today */
  projectable: boolean | 'partly'
  /** the next thing the reader can actually do, per the master page's 空态和异常的可行操作 list */
  nextAction: string
}

export const STATE_DEFINITIONS: StateDefinition[] = [
  {
    id: 'no-data',
    label: '无数据',
    meaning: '已查询，结果为空：这与「没查」和「查不到」是三件事。',
    signal: '字段存在且为空列表 / 为 null，例如 coverage 为 0 或 projects 为空数组',
    projectable: true,
    nextAction: '放宽时间范围或换筛选条件；空集合本身是答案。',
  },
  {
    id: 'not-connected',
    label: '未连接',
    meaning: '读路径不通，数值全部保持 UNKNOWN。',
    signal: 'transport.transportState=OFFLINE / 快照请求失败；eventStreamConnected=false',
    projectable: true,
    nextAction: '进入接入资格说明；不要通过切换页面期待它变好。',
  },
  {
    id: 'unsupported',
    label: '不支持',
    meaning: '该来源或客户端不声明这个能力，不是它失败了。',
    signal: 'adapterCapabilities[].supportLevel、layers[].state=NOT_SUPPORTED、verbEvidence[].state=NOT_SUPPORTED',
    projectable: true,
    nextAction: '查看字段限制说明，改用受支持的来源。',
  },
  {
    id: 'hidden-by-policy',
    label: '隐私隐藏',
    meaning: '内容存在但按策略不进入只读投影。',
    signal: '快照无此状态字段；只有调用方明确告知时才可显示（例如 evidence-range 的 SENSITIVE_NAME 拒绝）',
    projectable: false,
    nextAction: '解释当前策略与所需授权范围；不得由空值推断。',
  },
  {
    id: 'delayed',
    label: '延迟',
    meaning: '数据可读但比源端落后，last-good 带时间。',
    signal: 'transport.transportState=DELAYED、freshnessState=STALE、SSE resync_required',
    projectable: true,
    nextAction: '保留上次良好值并显示其时间；不请求更多源端采集。',
  },
  {
    id: 'partial-failure',
    label: '局部故障',
    meaning: '一个来源失败，其他来源与已投影事实保留。',
    signal: 'coverage{numerator,denominator,scope}、单泳道 ErrorBoundary、artifactHandlesSummary.refused',
    projectable: true,
    nextAction: '只处理该适配器；不清空其他来源。',
  },
  {
    id: 'insufficient-permission',
    label: '权限不足',
    meaning: '请求被拒，因为当前主体没有该范围的授权。',
    signal: '快照无权限态；只有服务端返回的拒绝原因可支撑（sidecar 的拒绝码不投影为权限状态）',
    projectable: false,
    nextAction: '说明所需范围与申请路径；Observer 不自授权，也不重试。',
  },
  {
    id: 'not-existing',
    label: '不存在',
    meaning: '被点名的对象身份不在投影里，原 ID 保留。',
    signal: '按 projectId / taskId / executionId 解析未命中；software locationStatus=MISSING_EXPECTED_INSTALL',
    projectable: true,
    nextAction: '保留原 ID 供复制，并提供返回路径；绝不改选「最新」或同名他项。',
  },
]

export const STATE_BY_ID: Record<ProductState, StateDefinition> =
  Object.fromEntries(STATE_DEFINITIONS.map((definition) => [definition.id, definition])) as Record<ProductState, StateDefinition>

/** The states the shipped snapshot cannot answer — kept as data so a test can fail if a view starts
 *  using one of them as a default. */
export const NON_PROJECTABLE_STATES: ProductState[] = STATE_DEFINITIONS
  .filter((definition) => definition.projectable === false)
  .map((definition) => definition.id)

/**
 * The transport word this surface may claim about itself. Absent data is UNKNOWN, a failed read is
 * OFFLINE, and a snapshot that arrived but is behind is DELAYED — three different answers that a single
 * "no data" branch would collapse into one lie. `'unknown'` means "nothing needs explaining here": a
 * healthy snapshot is not a state, and calling it one is how a page starts reporting 无数据 over real data.
 */
export function snapshotStateOf(snap: SnapshotV3 | null, error: string | null): ProductState | 'unknown' {
  if (!snap) return error ? 'not-connected' : 'unknown'
  const transport = snap.transport
  if (transport?.transportState === 'OFFLINE') return 'not-connected'
  if (transport?.transportState === 'DELAYED' || transport?.freshnessState === 'STALE') return 'delayed'
  const coverage = snap.coverage
  if (coverage && coverage.denominator != null && coverage.numerator != null
    && coverage.numerator < coverage.denominator) return 'partial-failure'
  if ((snap.projects?.length ?? 0) === 0) return 'no-data'
  return 'unknown'
}
