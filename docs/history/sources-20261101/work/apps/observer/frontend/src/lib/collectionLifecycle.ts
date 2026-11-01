// WUI-12 · what this surface may say about collection, retention and the four different "stops".
//
// Verified against the producer before writing: the v3 snapshot carries NO collector defaults, NO field
// whitelist, NO retention policy and NO storage bounds. `_expected_collector_names`
// (`services/orchestration/sidecar.py:274`) and `EVENT_RETENTION`
// (`packages/client-neutral-core/scripts/sse_hub.py:53`) are code constants that never reach the payload,
// and `config/config-ownership.json` is the ownership authority but is likewise not projected. So a
// settings page that printed a whitelist would be printing the repository's intent as if it were the
// running client's state — the exact substitution this project keeps having to relearn.
//
// The second thing the page has to keep apart is the four "stops". 暂停滚动 is a view-local reading
// affordance; 停止采集 belongs to the collector owner in `packages/client-neutral-core`; 关闭窗口 is the
// desktop shell's; 停止原生软件 is the managed software's own lifecycle. Collapsing them into one toggle
// would let a UI gesture claim authority over a running tool.
import type { PaletteId } from '@/theme/tokens'

export interface AppearanceFacts {
  theme: 'dark' | 'light'
  layout: 'full' | 'compact'
  palette: PaletteId
}

export const APPEARANCE_ROWS: {
  key: keyof AppearanceFacts
  label: string
  /** where the choice lives, because "it is remembered" would be a lie: web storage is forbidden */
  travels: string
}[] = [
  { key: 'theme', label: '明暗模式', travels: '地址参数 ?theme=；裸地址回到深色（设计语言），不是丢失' },
  { key: 'palette', label: '配色主题', travels: '地址参数 ?palette=；默认不写参数，现行配色保持默认' },
  { key: 'layout', label: '主窗 / 紧凑 HUD', travels: '地址参数 ?layout=；HUD 是桌面浮窗，不是手机端' },
]

export interface CollectionGap {
  key: string
  question: string
  reason: string
}

/** What WUI-12 asks and the projection does not answer. Rendered, with the producer named. */
export const COLLECTION_GAPS: CollectionGap[] = [
  {
    key: 'defaults',
    question: '当前实际生效的采集默认是什么？',
    reason: 'v3 快照不投影采集默认；`services/orchestration/sidecar.py:274` 的 `_expected_collector_names` 是代码常量，不进 payload。',
  },
  {
    key: 'whitelist',
    question: '字段白名单逐条状态（采了什么、没采什么）？',
    reason: '字段级唯一权威是 `config/config-ownership.json`（workflow/config-ownership/v2），它不是快照投影；本页能说的是仓库声明，不能说是运行态。',
  },
  {
    key: 'retention',
    question: '事件与投影实际保留多久？',
    reason: '`packages/client-neutral-core/scripts/sse_hub.py:53` 的 EVENT_RETENTION 只存在于代码，快照无保留期字段。',
  },
  {
    key: 'storage',
    question: '后台存储与队列上限是多少、当前占用多少？',
    reason: '快照无 storage/queue 边界字段；有界性属 WUI-18 的实测项，未测就保持未测。',
  },
  {
    key: 'diagnostics-scope',
    question: '一次限定诊断的范围（项目/问题/时间/保留）如何申请与显示？',
    reason: '申请与批准都在受管事务侧（WUI-10），Observer 只读，不发起也不代理诊断请求。',
  },
]

export interface LifecycleAction {
  key: string
  label: string
  /** what actually changes in the world */
  effect: string
  owner: string
  /** whether this surface can do it — the honest answer is no for three of the four */
  here: string
}

/** The four stops, kept four apart (taskpack: 暂停滚动 / 停采集 / 关窗 / 停原生软件分开). */
export const LIFECYCLE_ACTIONS: LifecycleAction[] = [
  {
    key: 'pause-scroll',
    label: '暂停滚动',
    effect: '只停止本页跟随新事件重排，读数不再被顶走。',
    owner: '本视图（阅读辅助），状态走地址参数，不落 storage。',
    here: '本页不代替泳道提供该开关；它属于具体列表的读态，不是一份全局设置。',
  },
  {
    key: 'stop-collection',
    label: '停止采集',
    effect: '源端不再产生新事件，观测轴随后显示断连或延迟。',
    owner: '采集属主 `packages/client-neutral-core`（Workflow Assistance）。',
    here: 'Observer 与 sidecar 永久只读：本页不发起停采，也不显示可点的停采开关。',
  },
  {
    key: 'close-window',
    label: '关闭观察窗口',
    effect: '桌面窗口消失；采集与原生软件是否继续，取决于各自属主，不由窗口推断。',
    owner: '桌面壳 `apps/observer/src-tauri`。',
    here: '本页不控制窗口；窗口生命周期与采集生命周期分开。',
  },
  {
    key: 'stop-native-software',
    label: '停止被观察的原生软件',
    effect: '那个工具自己退出，它参与的项目随之失去来源。',
    owner: '被管理的原生客户端本身。',
    here: '本仓不派工、不终止外部软件；断连也不推出「软件已停止」。',
  },
]

/** Privacy statements this surface may make because they are about the surface itself. */
export const READ_ONLY_PRIVACY: string[] = [
  '本页不读取凭据、.env、认证库、私人会话库、提示词/回复正文、工具参数、子 Agent 完整轨迹与模型权重。',
  '投影里没有的字段一律显示为具名缺口并附生产者位置，不补 0、不补空串、不用相邻字段反推。',
  '外观选择只写在地址里：任何 web storage 使用都会被 `apps/observer/tests/test_production_surface_static_contract.js` 判失败。',
]
