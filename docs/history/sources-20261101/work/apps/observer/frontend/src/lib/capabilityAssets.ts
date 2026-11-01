// WUI-07 · 能力资产与评价详情 — the read model behind the destination page.
//
// The page has to answer two master sheets (05_assets / 06_asset_detail): an asset inventory and, per
// asset, 来源身份、版本、许可、依赖、适用条件、失败反例、用户判断、迁移状态. Read literally against the
// producer (packages/client-neutral-core/scripts/adapter_capability_projection.py), most of those words
// ARE NOT FIELDS in the v3 snapshot. This module therefore does three things and nothing else:
//
// 1. groups the cards by what the projection can actually key them by — clientId — and says out loud
//    that the five provenance classes (原创/定制/收藏/第三方/客户端形成) cannot be assigned, because
//    no field carries them. The grouping is explicitly "类别未知", never a silent merge;
// 2. derives per card "what has actually been established" — the MET ladder layers (each standing on
//    its own evidence, never promoted by a neighbour) and the orthogonally-projected verb answers,
//    with the three shapes of the verb dimension (absent key / empty list / rows) kept distinct:
//    absent means "没看", empty means "看了·声明为零", and only rows carry answers;
// 3. names the source gaps (CAPABILITY_SOURCE_GAPS) as data the pages render, so an unanswerable
//    question reads as a gap with a reason instead of an empty tab or an invented value.
//
// Producer facts pinned here (verified 2026-10-09, do not re-derive at render time):
//   * `adapterCapabilities` is ABSENT when the producer could not read its declared sources and
//     otherwise NON-EMPTY — `[]` is never produced, so absent must never render as a zero count;
//   * REGISTERED is always MET with evidenceLevel SYNTHETIC（登记来自仓库声明文件，是声明不是探测）;
//     `_installed_layer` is the only other computed layer; layers 3–7 are hardcoded NOT_PROBED —
//     hence PRODUCER_CEILING below;
//   * `nativeStatus` is the constant 'NOT_IMPLEMENTED';
//   * `configOwnershipDefault` is copied from config/capability-matrix.json, NOT from
//     config/config-ownership.json — the label has to say so (OWNERSHIP_DEFAULT_SOURCE_PATH).
import type { AdapterCapabilityCard, CapabilityLayer, SnapshotV3 } from '@/types'

/**
 * The five classes WUI-07's acceptance names. They are the QUESTION, not a taxonomy the UI may apply:
 * no field in AdapterCapabilityCard carries an asset's provenance class, so no card may be labelled
 * with one of these. Exported so the gap text and the tests share one vocabulary.
 */
export const PROVENANCE_CLASSES = ['原创', '定制', '收藏', '第三方', '客户端形成'] as const

export interface ProvenanceGroup {
  key: 'PROVENANCE_UNKNOWN'
  label: string
  /** why the classes cannot be assigned — rendered next to the group, not hidden behind it */
  reason: string
  cards: AdapterCapabilityCard[]
}

/**
 * The honest grouping: one group, 类别未知, carrying every card. A second grouping key would have to
 * come from a snapshot field; there is none, so inventing one (e.g. by registryStatus or source_kind)
 * would launder a declaration into a provenance claim.
 */
export function groupAssetsByProvenance(cards: AdapterCapabilityCard[]): ProvenanceGroup[] {
  return [{
    key: 'PROVENANCE_UNKNOWN',
    label: '资产来源类别未投影 · 全部条目停在「类别未知」',
    reason: `v3 卡的合同里没有来源类别字段，${PROVENANCE_CLASSES.join(' / ')} 中的哪一个都无法由投影判定；`
      + 'adapter-registry.json 的 provenance.source_kind 说的是适配器版本身份从哪里读回，不是这件能力资产从何而来，'
      + '且它也没有被投影为卡字段。这里不猜测归类，也不把支持等级当作来源。',
    cards,
  }]
}

/** Ladder order, for display and for the ceiling check. */
export const LADDER_ORDER: CapabilityLayer[] = [
  'REGISTERED', 'INSTALLED', 'LOADED_CONNECTED', 'QUALIFIED',
  'ENABLED_FOR_TASK', 'NATIVE_PROJECTION', 'OBSERVED_IN_EXECUTION',
]

/**
 * The highest layer the producer can currently ever mark MET: REGISTERED is declared-SYNTHETIC and
 * `_installed_layer` is computed; layers 3–7 are hardcoded NOT_PROBED in the projection script. A MET
 * above this ceiling is therefore an out-of-contract shape: render it verbatim and flag it, but never
 * let it promote a neighbouring layer.
 */
export const PRODUCER_CEILING: CapabilityLayer = 'INSTALLED'

const LADDER_RANK: Record<CapabilityLayer, number> = {
  REGISTERED: 1, INSTALLED: 2, LOADED_CONNECTED: 3, QUALIFIED: 4,
  ENABLED_FOR_TASK: 5, NATIVE_PROJECTION: 6, OBSERVED_IN_EXECUTION: 7,
}

/** The three shapes of the verb dimension. Absent and empty are DIFFERENT statements. */
export type VerbDimensionShape = 'ABSENT_KEY' | 'EMPTY_LIST' | 'ROWS'

export interface EstablishedFacts {
  clientId: string
  /** layers the projection itself marked MET, in ladder order — never augmented, never trimmed */
  metLayers: CapabilityLayer[]
  highestMetLayer: CapabilityLayer | null
  /** MET layers above PRODUCER_CEILING: an anomaly to state, not to hide and not to propagate */
  aboveCeilingMet: CapabilityLayer[]
  verbShape: VerbDimensionShape
  /** verbs answered from a named read-only call (only meaningful when verbShape === 'ROWS') */
  verbsAnswered: string[]
  /** NOT_PROBED with attempted=true: the call ran and the answer was not creditable */
  verbsAttemptedUncredited: string[]
  /** NOT_PROBED with attempted=false: the probe refused to run it at all */
  verbsNeverAttempted: string[]
  /** NOT_SUPPORTED: a named declaration, not a measurement */
  verbsDeclaredUnsupported: string[]
  /** strict equality with NATIVELY_VERIFIED — the constant NOT_IMPLEMENTED is never a pass */
  nativeVerified: boolean
}

/**
 * "What has actually been established" for one card. A verb row never promotes a layer, so the layer
 * half reads ONLY card.layers; the verb half only card.verbEvidence, in its three shapes.
 */
export function establishedFacts(card: AdapterCapabilityCard): EstablishedFacts {
  const metLayers = card.layers
    .filter((layer) => layer.state === 'MET')
    .map((layer) => layer.layer)
    .sort((a, b) => LADDER_RANK[a] - LADDER_RANK[b])
  const ceilingRank = LADDER_RANK[PRODUCER_CEILING]
  const rows = card.verbEvidence
  const shape: VerbDimensionShape = rows === undefined ? 'ABSENT_KEY' : rows.length === 0 ? 'EMPTY_LIST' : 'ROWS'
  const verb = (state: string, attempted?: (row: { attempted: boolean }) => boolean) =>
    (rows ?? []).filter((row) => row.state === state && (attempted ? attempted(row) : true)).map((row) => row.verb)
  return {
    clientId: card.clientId,
    metLayers,
    highestMetLayer: metLayers.length ? metLayers[metLayers.length - 1] : null,
    aboveCeilingMet: metLayers.filter((layer) => LADDER_RANK[layer] > ceilingRank),
    verbShape: shape,
    verbsAnswered: verb('MET'),
    verbsAttemptedUncredited: verb('NOT_PROBED', (row) => row.attempted),
    verbsNeverAttempted: verb('NOT_PROBED', (row) => !row.attempted),
    verbsDeclaredUnsupported: verb('NOT_SUPPORTED'),
    nativeVerified: card.nativeStatus === 'NATIVELY_VERIFIED',
  }
}

export interface CapabilitySourceGap {
  key: string
  /** the question WUI-07 asks… */
  question: string
  /** …and why the v3 snapshot cannot answer it — rendered verbatim, never a blank tab */
  reason: string
}

/** Every asset-detail question with NO FIELD in the snapshot. Seven, named, with their reasons. */
export const CAPABILITY_SOURCE_GAPS: CapabilitySourceGap[] = [
  {
    key: 'provenanceClass',
    question: '这件资产属于哪一来源类别：原创 / 定制 / 收藏 / 第三方 / 客户端形成？',
    reason: 'AdapterCapabilityCard 没有任何来源类别字段；registry 的 provenance.source_kind 描述适配器版本身份的读回出处，'
      + '不是资产来源，且该键也未投影进快照。界面只能整组标为类别未知。',
  },
  {
    key: 'licence',
    question: '这件资产的许可文本是什么？',
    reason: '许可文本不在 v3 快照的任何字段里；Observer 是只读投影，不会替页面去仓库文件或网络抓取 LICENSE 来补值。',
  },
  {
    key: 'dependencies',
    question: '这件资产声明了哪些依赖？',
    reason: '卡上没有依赖清单字段。protocolConformance 说的是接口协议的符合性声明，不是资产的依赖列表，不能代用。',
  },
  {
    key: 'applicability',
    question: '这个能力在什么条件下适用？',
    reason: '卡携带的是逐层探测状态与动词回答，没有任何字段表达「在哪些场景/前提下成立」；适用条件属声明内容，未投影。',
  },
  {
    key: 'failureCounterExamples',
    question: '这个能力有哪些已知的失败反例？',
    reason: 'verb 行的 NOT_PROBED(attempted=true) 只说明那一次调用结果未被采信，不构成设计意义上的失败反例；快照没有反例字段。',
  },
  {
    key: 'userJudgement',
    question: '用户是否判断这件能力有价值、是否接受？',
    reason: '判断发生在人那一侧，v3 合同没有承载「接受 / 评价结论」的字段；本页只投影声明与探测，不推断意图。',
  },
  {
    key: 'migrationStatus',
    question: '这件能力是否已迁移、待迁移、或准备迁移到哪个目标？',
    reason: '迁移合同属 WUI-08（源评价→目标选择→差异损失→隔离试用→验证→部署读回），快照尚未投影源↔目标映射与迁移状态。',
  },
]

/** Where configOwnershipDefault actually comes from — the matrix, not the runtime ownership file. */
export const OWNERSHIP_DEFAULT_SOURCE_PATH = 'config/capability-matrix.json'
export const OWNERSHIP_DEFAULT_NOT_SOURCE_PATH = 'config/config-ownership.json'

/** The repo-declared files the capability cards are built from (naming them is a claim the pages can check). */
export const CAPABILITY_DECLARED_SOURCES = [
  'config/adapter-registry.json',
  'config/capability-matrix.json',
  'config/capability-conformance.json',
] as const

export interface WorkspaceSourceRow {
  path: string | null
  evidenceKind: string | null
  loadedAt: string | null
  generatedAt: string | null
}

/**
 * `workspace.sources` is the sidecar's own loaded-surface ledger (one row per surface it appended).
 * Absent is "this snapshot projected no ledger at all", empty is "the ledger is empty" — the same
 * absent/empty split as every other optional list, so it stays three distinguishable shapes here.
 */
export type WorkspaceSourceFacts =
  | { kind: 'ABSENT' }
  | { kind: 'EMPTY' }
  | { kind: 'ROWS'; rows: WorkspaceSourceRow[] }

export function workspaceSourceFacts(snap: SnapshotV3 | null): WorkspaceSourceFacts {
  const sources = snap?.workspace?.sources
  if (sources === undefined) return { kind: 'ABSENT' }
  if (sources.length === 0) return { kind: 'EMPTY' }
  return {
    kind: 'ROWS',
    rows: sources.map((row) => ({
      path: row.path ?? null,
      evidenceKind: row.evidenceKind ?? null,
      loadedAt: row.loadedAt ?? null,
      generatedAt: row.generatedAt ?? null,
    })),
  }
}

/** Which capability-declared source files the workspace ledger genuinely shows as loaded. */
export function capabilityDeclarationsInSources(facts: WorkspaceSourceFacts): string[] {
  if (facts.kind !== 'ROWS') return []
  const shown = new Set(facts.rows.map((row) => row.path).filter((p): p is string => !!p))
  return CAPABILITY_DECLARED_SOURCES.filter((path) => shown.has(path))
}

/** The declared sources the ledger does NOT show — with the current sidecar allow-list this is all of them. */
export function capabilityDeclarationsMissingFromSources(facts: WorkspaceSourceFacts): string[] {
  if (facts.kind !== 'ROWS') return [...CAPABILITY_DECLARED_SOURCES]
  return CAPABILITY_DECLARED_SOURCES.filter((path) => !capabilityDeclarationsInSources(facts).includes(path))
}
