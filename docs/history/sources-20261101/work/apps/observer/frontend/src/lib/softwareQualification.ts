// WUI-06 · 软件环境资格 — pure reads over the v3 snapshot, no probing of its own.
//
// The acceptance line for WUI-06 is: 版本/形态/适配器/字段绑定资格；有限支持与更新待复验明确；
// 原生启动可观察，不强制本方派工. Read literally against the two producers, that is a list of four
// claims this page must be able to answer *separately*, plus the wording it must not use.
//
// What the producers actually emit (verified by reading them, not inferred):
//
//   * `software[]` is always present in production and may be `[]` — the builder returns `[]` when the
//     discovery module failed to import (composition_root.py:83-84) and on any exception mid-probe
//     (composition_root.py:156-159). So `[]` cannot distinguish "nothing is declared" from "the probe
//     crashed"; the page says so instead of picking one reading.
//   * `updateAvailable` is hardcoded null (composition_root.py:143 — "NOT in resolver; not probed ->
//     never fabricate"). null means 未探测, never 否 and never 是.
//   * A registry entry with no discovery observation is emitted as locationStatus:"UNKNOWN" +
//     discoverySource:"unavailable" (composition_root.py:108-126) — the source is unavailable, which is
//     a SOURCE_GAP, while a row whose probe ran but returned no status (`composition_root.py:130`
//     defaults `location_status` to "UNKNOWN") is a field that was read and came back empty: NULL_FIELD.
//     Those two read the same and mean different things, so this module keeps them apart.
//   * `adapterCapabilities` is either absent (the producer could not read its declared inputs — see the
//     conditional spread in snapshot_api.py:106-108) or a non-empty list; `[]` is never produced. Absent
//     is therefore "没有读成", NOT "0 个 adapter".
//   * The ladder is hardcoded: REGISTERED is always MET/SYNTHETIC (adapter_capability_projection.py:310-312)
//     and layers 3-7 are always NOT_PROBED/NO_EVIDENCE (:315-319). INSTALLED is the only upper rung that
//     can legitimately move, and only from a measured install identity or a live entry readback
//     (:115-141). `nativeStatus` is a constant NOT_IMPLEMENTED (:350). So nothing above REGISTERED may be
//     presented as achieved unless the card's own row says MET — and this module only ever reads the rows.
//   * `verbEvidence` / `verbEvidenceCounts` / `verbEvidenceProbedAt` are added only when rows exist
//     (:352-358): an absent key is "did not look", `[]` would be "looked, declared nothing".
//   * The card's join to a software row is a NAME-level alias match (`softwareId` ↔ `clientId` with the
//     `-`/`_` swap, adapter_capability_projection.py:125-127). There is no foreign key anywhere in the
//     payload, so this module mirrors that exact alias set rather than inventing a looser match.
//
// `entryProbe` and `versionDrift` are typed now (types.ts EntryProbeFact + the two optional card fields),
// but the payload is JSON produced by `_card_probe` (adapter_capability_projection.py:93-112), where
// entryPoint / exitCode / detail arrive as null whenever the probe record had no such key. Each field is
// therefore read defensively and a missing one stays missing: substituting a value here is exactly the
// fabrication this module exists to refuse.
import type {
  AdapterCapabilityCard, CapabilityLayerState, SoftwareIdentity, SnapshotV3,
} from '@/types'

/** Same three-origin discipline as the Inspector's `Dim` (views/RecordInspector.tsx:8-16, 214-243):
 *  a projected value, a field the source read as empty, and a dimension the contract never carried are
 *  three different statements and may not be collapsed into each other. */
export type QualificationOrigin = 'PROJECTED' | 'NULL_FIELD' | 'SOURCE_GAP'

export interface QualificationClaim {
  key: string
  label: string
  origin: QualificationOrigin
  /** the value as the projection states it, raw tokens included — never laundered into a verdict */
  value: string | null
  /** which projected field this rests on, as a handle a reader can go check */
  source: string | null
  note: string
}

/** The four dimensions WUI-06's acceptance names, plus the two the page must not bury. */
export const SOFTWARE_ACCEPTANCE_KEYS = ['version', 'form', 'adapter', 'fieldBinding'] as const
export const SOFTWARE_QUALIFICATION_KEYS = [...SOFTWARE_ACCEPTANCE_KEYS, 'update', 'drift', 'native'] as const

const claim = (
  key: string, label: string, origin: QualificationOrigin,
  value: string | null, source: string | null, note: string,
): QualificationClaim => ({ key, label, origin, value, source, note })

const projected = (key: string, label: string, value: string, source: string, note: string) =>
  claim(key, label, 'PROJECTED', value, source, note)

const nullField = (key: string, label: string, note: string, source: string | null = null) =>
  claim(key, label, 'NULL_FIELD', null, source, note)

const sourceGap = (key: string, label: string, note: string, source: string | null = null) =>
  claim(key, label, 'SOURCE_GAP', null, source, note)

/** A gap can still carry the word the page must print — the update dimension's origin is "never asked",
 *  and the honest rendering of that is 未探测, not a blank cell. */
const gapWith = (key: string, label: string, value: string, source: string | null, note: string) =>
  claim(key, label, 'SOURCE_GAP', value, source, note)

/** '' and null are different from the string 'UNKNOWN' the producer writes on purpose, so normalize
 *  conservatively: only absence and blank become "nothing was said". */
const said = (value: string | null | undefined): string | null => {
  if (value === null || value === undefined) return null
  const trimmed = value.trim()
  return trimmed === '' ? null : trimmed
}

const rowHandle = (softwareId: string) => `software[${softwareId}]`

/** The adapter source trio the cards are built from, named the way AdapterCapabilityCards names it, so a
 *  reader who sees the gap anywhere on this page gets the same three file handles. */
export const ADAPTER_DECLARED_SOURCES
  = 'config/adapter-registry.json / config/capability-matrix.json / config/capability-conformance.json'

// ---------------------------------------------------------------------------
// list access: absent key vs read-but-empty
// ---------------------------------------------------------------------------

/** `null` = the snapshot carries no `software` key at all (snapshot_api.py:51 defaults it to None and
 *  :106 only spreads it when it is not None). An empty array is a different, also real, statement. */
export function softwareRowsOf(snap: SnapshotV3 | null | undefined): SoftwareIdentity[] | null {
  if (!snap) return null
  return Array.isArray(snap.software) ? snap.software : null
}

/** `null` = absent key = the producer could not read its declared inputs. Never "no adapters". */
export function adapterCardsOf(snap: SnapshotV3 | null | undefined): AdapterCapabilityCard[] | null {
  if (!snap) return null
  const cards = snap.adapterCapabilities
  return Array.isArray(cards) ? cards : null
}

/** The producer's own alias set, in the same direction it uses it. */
export function clientIdAliases(softwareId: string): string[] {
  const id = softwareId.trim()
  return [...new Set([id, id.replace(/-/g, '_'), id.replace(/_/g, '-')])]
}

/** The card that answers for this software row, or `null`. Callers must check `adapterCardsOf` first:
 *  "no match in a list that was read" and "the list was never read" are different claims. */
export function cardForSoftware(
  cards: AdapterCapabilityCard[] | null, softwareId: string,
): AdapterCapabilityCard | null {
  if (!cards) return null
  const aliases = clientIdAliases(softwareId)
  return cards.find((card) => aliases.includes(card.clientId)) ?? null
}

// ---------------------------------------------------------------------------
// card extras: typed by types.ts now, still read as the JSON that they are
// ---------------------------------------------------------------------------

/** `EntryProbeFact` as the payload really arrives: every field optional-or-null, so the reading keeps the
 *  nulls instead of promising a string the producer never wrote. */
export interface EntryProbeReading {
  status: string | null
  entryPoint: string | null
  argv: string[] | null
  exitCode: number | null
  outputDigest: string | null
  detail: string | null
  probedAt: string | null
}

export interface AdapterCardExtras {
  entryProbe: EntryProbeReading | null
  versionDrift: boolean | null
}

const textField = (value: unknown): string | null => (typeof value === 'string' ? said(value) : null)

/** Read `entryProbe` / `versionDrift` without assuming anything the payload did not send. A missing key
 *  stays missing, because "no readback" IS the answer the page has to show. */
export function readCardExtras(card: AdapterCapabilityCard | null | undefined): AdapterCardExtras {
  if (!card) return { entryProbe: null, versionDrift: null }
  const probe = card.entryProbe ?? null
  const raw = probe as unknown as Record<string, unknown> | null
  const entryProbe: EntryProbeReading | null = raw === null || typeof raw !== 'object'
    ? null
    : {
        status: textField(raw.status),
        entryPoint: textField(raw.entryPoint),
        argv: Array.isArray(raw.argv) ? raw.argv.map((part) => String(part)) : null,
        exitCode: typeof raw.exitCode === 'number' ? raw.exitCode : null,
        outputDigest: textField(raw.outputDigest),
        detail: textField(raw.detail),
        probedAt: textField(raw.probedAt),
      }
  return {
    entryProbe,
    versionDrift: typeof card.versionDrift === 'boolean' ? card.versionDrift : null,
  }
}

/** The entry readback states that prove an executable answered (`adapter_capability_projection.py:90`). */
const LIVE_ENTRY_STATUSES = ['LIVE_VERIFIED', 'VERSION_MOVED']

// ---------------------------------------------------------------------------
// update availability: what null means
// ---------------------------------------------------------------------------

export type UpdateAvailabilityState = 'NOT_PROBED' | 'AVAILABLE' | 'NONE'

export interface UpdateAvailabilityFact {
  state: UpdateAvailabilityState
  /** false whenever nothing was asked — the whole point of the field */
  probed: boolean
  raw: boolean | null
  /** the word the page renders: 未探测 / 是 / 否 — never collapsed */
  text: string
  meaning: string
}

export function updateAvailability(row: Pick<SoftwareIdentity, 'softwareId' | 'updateAvailable'>): UpdateAvailabilityFact {
  if (row.updateAvailable === true) {
    return {
      state: 'AVAILABLE', probed: true, raw: true, text: '是',
      meaning: `${rowHandle(row.softwareId)}.updateAvailable=true —— 有来源问过更新权威并回报有可用更新。`,
    }
  }
  if (row.updateAvailable === false) {
    return {
      state: 'NONE', probed: true, raw: false, text: '否',
      meaning: `${rowHandle(row.softwareId)}.updateAvailable=false —— 有来源问过更新权威并回报没有更新。`,
    }
  }
  return {
    // The shape the producer always emits today (composition_root.py:143). Rendering it as 否 would tell
    // the reader the machine is up to date, which is exactly the fabricated all-clear this page exists to
    // refuse; 是 would tell them to go update. So: 未探测, and the reason.
    state: 'NOT_PROBED', probed: false, raw: null, text: '未探测',
    meaning: 'updateAvailable=null 是"没有向任何更新权威问过"（services/orchestration/composition_root.py:143 '
      + '把该字段硬编码为 null，resolver 里没有更新事实），既不是"没有更新"也不是"有更新"。',
  }
}

// ---------------------------------------------------------------------------
// the ladder: only what the card itself marks MET
// ---------------------------------------------------------------------------

/** Layers the card's own row says MET. Ordering is the ladder's own order, so a caller can see the rungs. */
export function establishedLayers(card: AdapterCapabilityCard | null): CapabilityLayerState[] {
  if (!card) return []
  return card.layers.filter((layer) => layer.state === 'MET')
}

/** A MET rung with no named source is a contract violation, not an achievement: surface it as such
 *  instead of counting it (the same refusal the verb validator makes at adapter_capability_projection.py:216-218). */
export function uncreditableMetLayers(card: AdapterCapabilityCard | null): CapabilityLayerState[] {
  return establishedLayers(card).filter((layer) => !said(layer.source))
}

export function layerClaimText(layer: CapabilityLayerState): string {
  const source = said(layer.source)
  return source ? `${layer.state} · ${layer.evidenceLevel} · 来源 ${source}` : `${layer.state} · ${layer.evidenceLevel} · 无来源`
}

/** Whether the UI may present a rung as reached for this card — strictly the row's own state, so no
 *  neighbouring success can lift it. */
export function layerIsClaimed(card: AdapterCapabilityCard | null, layer: string): boolean {
  return establishedLayers(card).some((entry) => entry.layer === layer)
}

/** `nativeStatus` is a constant NOT_IMPLEMENTED today (adapter_capability_projection.py:350). Anything that
 *  reads like a pass — including a future NATIVELY_VERIFIED — is only creditable with the last rung MET. */
export function nativeStatusWording(card: AdapterCapabilityCard | null): string {
  if (!card) return '无能力卡，原生状态无从谈起（见适配器维度）'
  if (card.nativeStatus === 'NOT_IMPLEMENTED') {
    return 'nativeStatus=NOT_IMPLEMENTED —— 生产者写的是常量（adapter_capability_projection.py:350），'
      + '这条路没有实现，因此不给任何层级提供证据'
  }
  if (card.nativeStatus === 'NOT_PROBED') return 'nativeStatus=NOT_PROBED —— 未做过原生探测'
  return layerIsClaimed(card, 'OBSERVED_IN_EXECUTION')
    ? 'nativeStatus=NATIVELY_VERIFIED · 与 OBSERVED_IN_EXECUTION 一致'
    : 'nativeStatus=NATIVELY_VERIFIED 但 OBSERVED_IN_EXECUTION 未成立 —— 不采信，两处声明都原样留着'
}

// ---------------------------------------------------------------------------
// limited support / needs revalidation, driven by real fields only
// ---------------------------------------------------------------------------

/** supportLevel vocabulary in the tracked registry is deep | experimental | manifest-only;
 *  registryStatus in the matrix is active | quarantined | legacy_observe | blocked | NOT_IN_MATRIX. */
const FULL_SUPPORT_LEVELS = ['deep']
const LIMITED_LEVEL_WORDING: Record<string, string> = {
  experimental: 'supportLevel=experimental：按实验客户端声明的范围使用',
  'manifest-only': 'supportLevel=manifest-only：只有清单，没有可用适配器的实测',
}
const STATUS_WORDING: Record<string, string> = {
  quarantined: 'registryStatus=quarantined：已隔离，不作为可用来源',
  legacy_observe: 'registryStatus=legacy_observe：只观察，不写入',
  blocked: 'registryStatus=blocked：被拦在外，未进入可用集合',
  NOT_IN_MATRIX: 'registryStatus=NOT_IN_MATRIX：capability-matrix 里没有这个客户端的条目',
}

export interface SupportVerdict {
  isLimited: boolean
  /** the sentence the page renders; '' when nothing in the payload limits support */
  wording: string
  reasons: string[]
}

/** 有限支持 must come from declared fields, never from a mood: support level, matrix status, whether writes
 *  are available at all, whether a runtime adapter exists, and the ownership mode. */
export function limitedSupport(card: AdapterCapabilityCard | null): SupportVerdict {
  if (!card) {
    return {
      isLimited: true,
      wording: '适配器声明源未给出这个客户端的卡片，支持范围无从判定（见适配器维度）',
      reasons: ['没有能力卡'],
    }
  }
  const reasons: string[] = []
  const level = said(card.supportLevel)
  if (level && !FULL_SUPPORT_LEVELS.includes(level)) {
    reasons.push(LIMITED_LEVEL_WORDING[level] ?? `supportLevel=${level}：不是 deep，按有限处理`)
  }
  const status = said(card.registryStatus)
  if (status && status !== 'active') reasons.push(STATUS_WORDING[status] ?? `registryStatus=${status}：非 active`)
  if (card.writePolicy === 'unavailable') reasons.push('writes=unavailable：写路径不可用')
  if (!said(card.runtimeAdapter)) reasons.push('runtime_adapter=null：没有运行时适配器')
  const mode = card.configOwnershipDefault?.mode
  if (mode === 'OBSERVE') reasons.push('配置归属默认 mode=OBSERVE：只观察，不由本方写入')
  return {
    isLimited: reasons.length > 0,
    wording: reasons.join('；'),
    // An unqualified "deep · active" still must not read as "capable": the ladder says the rungs above
    // REGISTERED were never probed, and that limit comes from a field, not from an opinion.
    reasons: reasons.length
      ? reasons
      : [`声明为 deep · active，写策略 ${card.writePolicy}；阶梯上 REGISTERED 之上仍未探测`],
  }
}

export interface RevalidationVerdict {
  required: boolean
  wording: string
  reasons: string[]
}

/** 更新待复验 — one reason per field that says "this was not settled this round". Nothing here invents a
 *  due date: the payload carries no revalidation schedule, so the reason is always a field handle. */
export function needsRevalidation(
  row: SoftwareIdentity, card: AdapterCapabilityCard | null,
): RevalidationVerdict {
  const reasons: string[] = []
  const update = updateAvailability(row)
  if (!update.probed) reasons.push('更新状态未探测（updateAvailable=null），待有来源问过更新权威后复验')
  if (said(row.discoverySource) === 'unavailable') reasons.push('本轮没有实测发现（discoverySource=unavailable），待发现模块可用后复验')
  if (!said(row.lastVerified)) reasons.push('没有核验时间戳（lastVerified=null），身份判定停留在未核验')
  if (!said(row.discoveredVersion)) reasons.push('没有发现版本（discoveredVersion=null），版本资格未成立')
  const extras = readCardExtras(card)
  if (extras.versionDrift === true) reasons.push('入口读回版本与 registry 声明不一致（versionDrift=true，state=VERSION_MOVED），两个版本串都待复验')
  if (card && card.operationsDrift) reasons.push('registry 与 capability-matrix 的动词集合不一致（operationsDrift=true），待复验')
  if (card && said(card.detectionEvidenceState) === 'UNVERIFIED') reasons.push('检测证据态 UNVERIFIED：声明的探测未经复核')
  return { required: reasons.length > 0, wording: reasons.join('；'), reasons }
}

// ---------------------------------------------------------------------------
// per-row qualification: version / form / adapter / field-binding (+ update / drift / native)
// ---------------------------------------------------------------------------

/** `true` when the row's own status says the installation identity moved or doubled. Surfaced as-is —
 *  these are the two states the panel must never re-label as fine. */
export function isDriftedLocation(row: SoftwareIdentity): boolean {
  return row.locationStatus === 'LOCATION_DRIFT'
    || row.locationStatus === 'DUAL_INSTALLATION'
    || row.locationStatus === 'MISSING_EXPECTED_INSTALL'
}

export function versionQualification(row: SoftwareIdentity): QualificationClaim {
  const version = said(row.discoveredVersion)
  const source = `${rowHandle(row.softwareId)} discoverySource=${said(row.discoverySource) ?? 'UNKNOWN'}`
  if (version) {
    const channel = said(row.releaseChannel)
    const verified = said(row.lastVerified)
    // composition_root.py:142 — release_channel is "usually None from resolver": a missing channel is a
    // field that came back empty, and the note says so instead of dropping the row.
    return projected('version', '版本资格',
      `${version} · 渠道 ${channel ?? '无记录（null）'} · 核验 ${verified ?? '无记录（null）'}`,
      source,
      channel
        ? '发现模块读回的版本串；渠道与核验时间各说各的，不合并成一个"最新"'
        : 'releaseChannel=null 是 resolver 没给（composition_root.py:142），不是"没有渠道这件事"')
  }
  if (said(row.discoverySource) === 'unavailable') {
    return gapWith('version', '版本资格', 'UNKNOWN',
      source,
      '发现模块本轮不可用（composition_root.py:108-126 走 UNKNOWN/unavailable 分支），没有可引用的版本读回')
  }
  return nullField('version', '版本资格',
    '发现跑到了这台机器，但这一条没有读回版本串（discoveredVersion=null）—— 未读到不等于没有版本',
    source)
}

export function formQualification(row: SoftwareIdentity): QualificationClaim {
  const source = `${rowHandle(row.softwareId)} locationStatus=${row.locationStatus} duplicateInstallation=${String(row.duplicateInstallation)}`
  const expected = said(row.expectedLocation)
  const observed = said(row.observedLocation)
  const detail = expected || observed
    ? `预期 ${expected ?? '无记录'} · 观测 ${observed ?? '无记录'}`
    : '预期与观测位置都没有记录'
  if (row.locationStatus === 'UNKNOWN') {
    if (said(row.discoverySource) === 'unavailable') {
      return gapWith('form', '形态资格', 'UNKNOWN', source,
        `本轮没有实测发现（discoverySource=unavailable），安装形态无从判定：${detail}`)
    }
    // composition_root.py:130 defaults an empty `location_status` to "UNKNOWN" — the probe ran and said
    // nothing, which is a read-but-empty field, not an unavailable source.
    return nullField('form', '形态资格',
      `发现跑过了，但这一条的 location_status 是空的（生产者落成 UNKNOWN）：${detail}`, source)
  }
  // Every other status is shown with its raw token, drift and duplicate included. There is deliberately no
  // "Healthy" branch here: SINGLE_VERIFIED is stated as what it is (one verified root) and nothing else.
  return projected('form', '形态资格', `${row.locationStatus} · ${detail}`, source,
    isDriftedLocation(row)
      ? '这是实测到的冲突，原样展示；Observer 不迁移、不删除、不合并实例'
      : '形态只说安装位置的形状，不代表可执行、不代表已连接、不代表已资格判定')
}

export function adapterQualification(
  row: SoftwareIdentity, cards: AdapterCapabilityCard[] | null, card: AdapterCapabilityCard | null,
): QualificationClaim {
  const aliasNote = `按 softwareId↔clientId 名字匹配（别名集 ${clientIdAliases(row.softwareId).join(' | ')}，同 adapter_capability_projection.py:125-127），v3 没有外键`
  if (!cards) {
    return sourceGap('adapter', '适配器资格',
      `快照没有 adapterCapabilities 字段 —— 生产者未能读取 ${ADAPTER_DECLARED_SOURCES}。`
        + '缺席说的是"没读成"，本页因此对适配器数量不作任何断言',
      `snapshot_api.py:106-108 的条件展开`)
  }
  if (!card) {
    return nullField('adapter', '适配器资格',
      `adapterCapabilities 已投影（${cards.length} 张卡），其中没有匹配 ${row.softwareId} 的 clientId —— `
        + '读过而没有，是声明源的缺失，不是本机没装。' + aliasNote)
  }
  return projected('adapter', '适配器资格',
    `${card.clientId} · supportLevel=${card.supportLevel} · registryStatus=${card.registryStatus} · writes=${card.writePolicy} · risk=${card.risk}`,
    `adapterCapabilities[${card.clientId}]`, aliasNote)
}

export function fieldBindingQualification(
  row: SoftwareIdentity, cards: AdapterCapabilityCard[] | null, card: AdapterCapabilityCard | null,
): QualificationClaim {
  if (!cards) {
    return sourceGap('fieldBinding', '字段绑定资格',
      `能力卡不存在（读取 ${ADAPTER_DECLARED_SOURCES} 失败），没有任何字段归属可引用`,
      'snapshot_api.py:106-108')
  }
  if (!card) {
    return nullField('fieldBinding', '字段绑定资格',
      `已投影的能力卡里没有 ${row.softwareId} 的条目，字段归属无声明可引`, `adapterCapabilities 共 ${cards.length} 张`)
  }
  const ownership = card.configOwnershipDefault
  if (!ownership) {
    // Real today for deepseek-harness (config/capability-matrix.json clients[].config_ownership_default is
    // null): no declared default is not "no fields" and not "everything writable".
    return nullField('fieldBinding', '字段绑定资格',
      `adapterCapabilities[${card.clientId}].configOwnershipDefault=null —— 该客户端没有声明归属默认；`
        + '这不是"没有字段"，也不是"全部可写"',
      `config/capability-matrix.json#clients[id=${card.clientId}].config_ownership_default`)
  }
  return projected('fieldBinding', '字段绑定资格',
    `${ownership.layer ?? 'UNKNOWN'} / ${ownership.mode ?? 'UNKNOWN'} / preserve_unknown=${String(ownership.preserve_unknown ?? 'UNKNOWN')}`,
    `adapterCapabilities[${card.clientId}].configOwnershipDefault`,
    '这是整客户端的默认归属声明，逐字段表未进入快照（见来源缺口 fieldLevelOwnership）；声明≠已写入≠已加载')
}

export function driftQualification(
  row: SoftwareIdentity, card: AdapterCapabilityCard | null,
): QualificationClaim {
  const extras = readCardExtras(card)
  if (!card) {
    return sourceGap('drift', '声明 × 实测差异',
      `没有能力卡就没有可比对的两边（读取 ${ADAPTER_DECLARED_SOURCES} 未成功）`, 'snapshot_api.py:106-108')
  }
  const pieces: string[] = []
  const declared = said(card.declaredVersion)
  const discovered = said(row.discoveredVersion)
  if (extras.versionDrift === true) {
    pieces.push('入口读回标 VERSION_MOVED：registry 声明串与本机读回串不同，两个都留着')
  }
  if (declared && discovered) pieces.push(declared === discovered ? `版本两边一致：${declared}` : `版本两边不同：声明 ${declared} · 发现 ${discovered}`)
  else if (declared || discovered) pieces.push(`版本只有一边有值：声明 ${declared ?? 'null'} · 发现 ${discovered ?? 'null'}`)
  else pieces.push('两边都没有版本串')
  if (card.operationsDrift) pieces.push('operationsDrift=true：registry 与 capability-matrix 的动词集合不一致，两处都原样展示')
  pieces.push(extras.entryProbe
    ? `入口读回 ${extras.entryProbe.status ?? 'UNKNOWN'}${extras.entryProbe.entryPoint ? ` · ${extras.entryProbe.entryPoint}` : ''}`
    : '没有入口读回（entryProbe=null）')
  return projected('drift', '声明 × 实测差异', pieces.join(' ｜ '),
    `adapterCapabilities[${card.clientId}] + ${rowHandle(row.softwareId)}`,
    '漂移是两份声明的对照结果，不选一个赢家；判定哪个是真值属所有者决定')
}

export function nativeQualification(card: AdapterCapabilityCard | null): QualificationClaim {
  if (!card) {
    return sourceGap('native', '原生状态', '没有能力卡，原生状态无字段可读', 'snapshot_api.py:106-108')
  }
  const met = establishedLayers(card).map((layer) => layer.layer)
  return projected('native', '原生状态',
    `${nativeStatusWording(card)} ｜ 该卡自己标 MET 的层：${met.length ? met.join(' · ') : '无'}`,
    `adapterCapabilities[${card.clientId}].nativeStatus + layers`,
    '层级只按卡片自己的行呈现，任何一层都不因邻层成立而晋级')
}

export interface ParticipatingProjects {
  projectIds: string[]
  executionIds: string[]
  /** why this is a candidate list and not an ownership fact */
  basis: string
}

/** 参与项目 — the closest the payload comes is a name-level agent match. snapshot_api.py:255 derives
 *  `agentPlatform` from the project's executions, so both sides speak agent names; neither speaks
 *  `softwareId`, which is why this is labelled a candidate and never an attribution. */
export function participatingProjects(
  snap: SnapshotV3 | null | undefined, softwareId: string,
): ParticipatingProjects {
  const aliases = clientIdAliases(softwareId)
  const projectIds: string[] = []
  for (const project of snap?.projects ?? []) {
    const platform = said(project.agentPlatform)
    if (platform && aliases.includes(platform) && !projectIds.includes(project.projectId)) projectIds.push(project.projectId)
  }
  const executionIds: string[] = []
  for (const execution of snap?.executions ?? []) {
    const agent = said(execution.agent)
    if (agent && aliases.includes(agent) && execution.executionId) executionIds.push(execution.executionId)
  }
  return {
    projectIds, executionIds,
    basis: '名字级匹配（projects[].agentPlatform / executions[].agent ↔ softwareId 别名），'
      + 'v3 没有 softwareId↔projectId 外键，因此这是候选集合，不构成归属；未匹配到的项目也不会被剔除身份',
  }
}

export interface SoftwareQualification {
  softwareId: string
  displayName: string | null
  row: SoftwareIdentity
  card: AdapterCapabilityCard | null
  claims: QualificationClaim[]
  update: UpdateAvailabilityFact
  limitedSupport: SupportVerdict
  needsRevalidation: RevalidationVerdict
  /** rung names the card itself marks MET */
  established: string[]
  uncreditableMet: string[]
  participating: ParticipatingProjects
}

export function qualifySoftwareRow(row: SoftwareIdentity, snap: SnapshotV3 | null | undefined): SoftwareQualification {
  const cards = adapterCardsOf(snap)
  const card = cardForSoftware(cards, row.softwareId)
  const claims: QualificationClaim[] = [
    versionQualification(row),
    formQualification(row),
    adapterQualification(row, cards, card),
    fieldBindingQualification(row, cards, card),
  ]
  const update = updateAvailability(row)
  claims.push(update.probed
    ? projected('update', '更新可用', update.text, `${rowHandle(row.softwareId)}.updateAvailable`, update.meaning)
    : gapWith('update', '更新可用', update.text, `${rowHandle(row.softwareId)}.updateAvailable`, update.meaning))
  claims.push(driftQualification(row, card))
  claims.push(nativeQualification(card))
  const met = establishedLayers(card)
  return {
    softwareId: row.softwareId,
    displayName: said(row.displayName),
    row,
    card,
    claims,
    update,
    limitedSupport: limitedSupport(card),
    needsRevalidation: needsRevalidation(row, card),
    established: met.map((layer) => layer.layer),
    uncreditableMet: uncreditableMetLayers(card).map((layer) => layer.layer),
    participating: participatingProjects(snap, row.softwareId),
  }
}

// ---------------------------------------------------------------------------
// page-level summary
// ---------------------------------------------------------------------------

export interface SoftwareEnvironmentSummary {
  softwareKeyPresent: boolean
  softwareRowCount: number
  /** `[]` cannot be read as "nothing declared" — see composition_root.py:83-84 / 156-159 */
  softwareListAmbiguous: boolean
  cardsKeyPresent: boolean
  cardCount: number
  /** rows whose softwareId found no card, while the card list was read */
  rowsWithoutCard: string[]
  driftedSoftwareIds: string[]
  unprobedUpdateSoftwareIds: string[]
  /** every rung name any card marks MET above REGISTERED, with the owning client */
  claimedAboveRegistered: { clientId: string; layer: string }[]
  qualifications: SoftwareQualification[]
}

export function summarizeSoftwareEnvironment(snap: SnapshotV3 | null | undefined): SoftwareEnvironmentSummary {
  const rows = softwareRowsOf(snap)
  const cards = adapterCardsOf(snap)
  const qualifications = (rows ?? []).map((row) => qualifySoftwareRow(row, snap))
  const claimed: { clientId: string; layer: string }[] = []
  for (const card of cards ?? []) {
    for (const layer of establishedLayers(card)) {
      if (layer.layer !== 'REGISTERED') claimed.push({ clientId: card.clientId, layer: layer.layer })
    }
  }
  return {
    softwareKeyPresent: rows !== null,
    softwareRowCount: rows?.length ?? 0,
    softwareListAmbiguous: rows !== null && rows.length === 0,
    cardsKeyPresent: cards !== null,
    cardCount: cards?.length ?? 0,
    rowsWithoutCard: rows && cards
      ? rows.filter((row) => !cardForSoftware(cards, row.softwareId)).map((row) => row.softwareId)
      : [],
    driftedSoftwareIds: (rows ?? []).filter(isDriftedLocation).map((row) => row.softwareId),
    unprobedUpdateSoftwareIds: (rows ?? []).filter((row) => !updateAvailability(row).probed).map((row) => row.softwareId),
    claimedAboveRegistered: claimed,
    qualifications,
  }
}

// ---------------------------------------------------------------------------
// first-run qualification (母版 15_first_run: 已授权发现 → 资格与字段 → 差异 → 低风险真实活动 → 回读)
// ---------------------------------------------------------------------------

export type StageAnswer = 'ANSWERABLE' | 'PARTIAL' | 'SOURCE_GAP'

export interface FirstRunStageRow {
  key: string
  label: string
  answer: StageAnswer
  /** what this snapshot does answer for the stage, with field handles */
  answers: string
  /** what it cannot answer, named rather than implied */
  gap: string
}

export const FIRST_RUN_STAGE_KEYS = [
  'authorizedDiscovery', 'qualificationAndFields', 'declaredVsObservedDiff',
  'lowRiskRealActivity', 'entryReadback',
] as const

export function firstRunQualification(snap: SnapshotV3 | null | undefined): FirstRunStageRow[] {
  const rows = softwareRowsOf(snap)
  const cards = adapterCardsOf(snap)
  const discovered = (rows ?? []).filter((row) => said(row.discoverySource) && said(row.discoverySource) !== 'unavailable')
  const probedEntries = (cards ?? []).filter((card) => {
    const probe = readCardExtras(card).entryProbe
    return probe !== null && LIVE_ENTRY_STATUSES.includes(probe.status ?? '')
  })
  const answeredVerbs = (cards ?? []).filter((card) => (card.verbEvidence ?? []).some((verb) => verb.state === 'MET'))

  const discoveryAnswer: StageAnswer = !rows
    ? 'SOURCE_GAP'
    : rows.length === 0
      ? 'SOURCE_GAP'
      : discovered.length === rows.length && rows.length > 0
        ? 'ANSWERABLE'
        : 'PARTIAL'
  const diffAnswer: StageAnswer = !cards
    ? 'SOURCE_GAP'
    : cards.length === 0
      ? 'PARTIAL'
      : probedEntries.length > 0 ? 'ANSWERABLE' : 'PARTIAL'
  const readbackAnswer: StageAnswer = probedEntries.length > 0 || answeredVerbs.length > 0 ? 'ANSWERABLE' : 'SOURCE_GAP'

  return [
    {
      key: 'authorizedDiscovery',
      label: '① 已授权发现',
      answer: discoveryAnswer,
      answers: rows
        ? `${rows.length} 行软件身份；其中 ${discovered.length} 行带实测发现源（discoverySource ≠ unavailable），`
          + `${rows.filter((row) => said(row.lastVerified)).length} 行带核验时间戳`
        : '本页能看到快照是否携带 software 字段',
      gap: !rows
        ? '快照没有 software 字段：发现层没有产出可读的东西，接入第一步就无从判断'
        : rows.length === 0
          ? 'software=[] 无法区分"注册表里没有条目"与"构建过程崩了"（composition_root.py:83-84 与 :156-159 两条路径都返回 []）'
          : discovered.length === rows.length
            ? '发现只回答"这台机器上有什么"，不回答"是否获准采集更多来源"；扩大范围属所有者决定'
            : `有 ${rows.length - discovered.length} 行是 discoverySource=unavailable 的未实测行，形态与版本都停在 UNKNOWN`,
    },
    {
      key: 'qualificationAndFields',
      label: '② 资格与字段',
      answer: 'PARTIAL',
      answers: cards
        ? `声明级可回答：${cards.length} 张能力卡带 supportLevel / registryStatus / writes / configOwnershipDefault；`
          + '阶梯里只有卡片自己标 MET 的行计入'
        : '声明级也无从回答（能力卡缺席）',
      gap: '实测级回答不了：REGISTERED 恒为 MET/SYNTHETIC，3–7 层在生产者里硬编码 NOT_PROBED'
        + '（adapter_capability_projection.py:310-319），逐字段归属表也没有进入快照',
    },
    {
      key: 'declaredVsObservedDiff',
      label: '③ 差异（声明 × 实测）',
      answer: diffAnswer,
      answers: cards
        ? `可比对：registry 声明版本 × 发现版本、registry 动词 × matrix 动词（operationsDrift）、`
          + `入口读回状态（VERSION_MOVED 即版本漂移）${probedEntries.length ? ` · 已读回 ${probedEntries.length} 个入口` : ''}`
        : `读不到声明源（${ADAPTER_DECLARED_SOURCES}），两边都缺，没有可比对的两份声明`,
      gap: probedEntries.length > 0
        ? '入口读回只证明"可执行文件答过一次"，不证明会话、加载或行为'
        : '没有入口读回（entryProbe=null）：只能比对两份声明文本，不能声明本机行为差异',
    },
    {
      key: 'lowRiskRealActivity',
      label: '④ 低风险真实活动',
      answer: 'SOURCE_GAP',
      answers: '本页只能观察：executions[].agent 是名字，可与 softwareId 做候选匹配（不构成归属）',
      gap: '快照没有 softwareId↔execution 的绑定，也没有"该客户端在本次执行里被真实使用"的 receipt/readback；'
        + '而且本页不派工、不启动、不重试（Observer 只读法），原生启动的可观察性属执行侧合同',
    },
    {
      key: 'entryReadback',
      label: '⑤ 回读',
      answer: readbackAnswer,
      answers: readbackAnswer === 'ANSWERABLE'
        ? `${probedEntries.length} 个入口有 LIVE_VERIFIED/VERSION_MOVED 读回 · ${answeredVerbs.length} 张卡有 MET 动词行`
        : '本阶段没有可引用的回读事实',
      gap: readbackAnswer === 'ANSWERABLE'
        ? '回读只覆盖被探针问过的那一次，不覆盖更新状态（updateAvailable=null）与其他层级'
        : '回读需要一次真实问话：docs/audits/EXECUTOR_LIVE_PROBE_2026-10-08.json 的记录不在快照里时，'
          + 'entryProbe 为 null、verbEvidence 键整个缺席，本界面不代为发起',
    },
  ]
}

// ---------------------------------------------------------------------------
// what this projection cannot answer, named
// ---------------------------------------------------------------------------

export interface SoftwareSourceGap {
  key: string
  question: string
  /** what the producer actually does, so the reader can tell a gap from a design choice */
  reason: string
  /** the reason is a read-only boundary this project keeps on purpose, not a missing wire-up */
  byDesign?: boolean
}

export const SOFTWARE_SOURCE_GAPS: SoftwareSourceGap[] = [
  {
    key: 'updateProbe',
    question: '这个软件有没有可用更新？',
    reason: 'composition_root.py:143 把 updateAvailable 硬编码为 null（resolver 不提供更新事实）。'
      + '未探测不是"没有更新"，也不是"有更新"；更新权威属软件自身与其更新源。',
  },
  {
    key: 'softwareListAmbiguity',
    question: 'software=[] 是"没声明任何软件"还是"发现过程失败了"？',
    reason: 'composition_root.py:83-84（发现模块导入失败）与 :156-159（探测中途异常）都返回 []，'
      + '两条路径与空注册表在 payload 里不可分辨。本页因此把 [] 报成"无法区分"，而不是报成一个数量。',
  },
  {
    key: 'adapterCapabilitiesAbsent',
    question: '有哪些适配器、各自支持到什么程度？',
    reason: `snapshot_api.py:106-108 只在读成功时展开 adapterCapabilities；键缺席意味着生产者没读成 `
      + `${ADAPTER_DECLARED_SOURCES}。缺席是来源缺口，本页因此不对适配器数量作任何断言。`,
  },
  {
    key: 'layerLadder',
    question: '这个客户端是否已加载/已资格判定/已按任务启用/有原生投影/在执行中被观察过？',
    reason: 'adapter_capability_projection.py:310-319：REGISTERED 恒为 MET/SYNTHETIC，3–7 层恒为 '
      + 'NOT_PROBED/NO_EVIDENCE。INSTALLED 只可能来自实测安装身份或入口读回（:115-141）。'
      + '所以本页不得把 REGISTERED 之上的任何一层呈现为达成。',
  },
  {
    key: 'nativeVerification',
    question: '这个客户端原生验证过了吗？',
    reason: 'adapter_capability_projection.py:350 把 nativeStatus 写成常量 NOT_IMPLEMENTED。'
      + '它是"这条路没实现"，不是通过，也不是失败。',
  },
  {
    key: 'fieldLevelOwnership',
    question: '具体哪些配置字段由本方管理、哪些只观察？',
    reason: '能力卡只带整客户端的 configOwnershipDefault；逐字段表在 config/config-ownership.json，'
      + '未进入 v3 快照合同。因此这里能回答"声明的默认"，不能回答"逐字段绑定"。',
  },
  {
    key: 'verbEvidenceAbsent',
    question: '合同声明的动词里，这个客户端实际答了哪几个？',
    reason: 'adapter_capability_projection.py:352-358：只有存在行时才加 verbEvidence / verbEvidenceCounts / '
      + 'verbEvidenceProbedAt 三个键。键缺席=没看；空列表=看了但什么都没声明。两者都不是"支持"。',
  },
  {
    key: 'sourceLoadProvenance',
    question: '本轮实际读回了哪两个获准来源、什么时候读的？',
    reason: 'workspace.sources 只登记 PLAN / STATIC_BASELINE / HISTORY 三类（workspace_evidence.py:199-224），'
      + '软件注册表、平台发现与 adapter 声明源没有加载记录。本页只能按字段在/不在判断读取与否，'
      + '说不出来源名与读取时刻，因此"两个获准来源读回"要由审计侧的探针记录提供。',
  },
  {
    key: 'authSurface',
    question: '这个软件的鉴权/凭据面状态如何？',
    reason: '只读边界禁止读取凭据、auth store、令牌与私有会话（AGENTS.md Safety；apps/observer/AGENTS.md）。'
      + '母版 03_software 列出的"鉴权"维度本页故意不采集，不是漏接。',
    byDesign: true,
  },
  {
    key: 'privateSessions',
    question: '客户端里的私人会话、浏览器数据、模型权重是什么？',
    reason: 'WUI-06 验收明写"不探读私人会话和浏览器"，项目安全规则同样禁止。本页不读取、不缓存、不转述。',
    byDesign: true,
  },
  {
    key: 'softwareProjectBinding',
    question: '这个软件被哪些项目使用（归属，不是候选）？',
    reason: 'projects[].agentPlatform 由执行 agent 推出（snapshot_api.py:255），payload 里没有 '
      + 'softwareId↔projectId 外键。本页给出的是名字级候选集合，标签始终是"候选"。',
  },
  {
    key: 'revalidationSchedule',
    question: '什么时候必须复验、上次复验通过了什么？',
    reason: '快照只带 lastVerified / versionObservedAt / observedAt 这些时间戳，没有复验周期、没有复验结论。'
      + '"待复验"只能由字段缺失推出，不能由到期推出。',
  },
]

/** Which of the listed gaps bite for THIS snapshot. The static list is the contract; this is the state. */
export function bitingSourceGaps(snap: SnapshotV3 | null | undefined): string[] {
  const rows = softwareRowsOf(snap)
  const cards = adapterCardsOf(snap)
  const keys: string[] = ['updateProbe', 'layerLadder', 'nativeVerification', 'fieldLevelOwnership',
    'authSurface', 'privateSessions', 'softwareProjectBinding', 'revalidationSchedule', 'sourceLoadProvenance']
  if (rows !== null && rows.length === 0) keys.push('softwareListAmbiguity')
  if (!cards) keys.push('adapterCapabilitiesAbsent')
  if (cards && cards.length > 0 && cards.every((card) => card.verbEvidence === undefined)) keys.push('verbEvidenceAbsent')
  return keys
}
