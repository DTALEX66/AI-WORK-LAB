// WUI-06 · the software-qualification module's own truth tests.
//
// Every case here is written around a lie the page could tell: `null` read as "no update", an absent card
// list read as "no adapters", a drift status softened into a verdict, a rung above REGISTERED lifted
// because its neighbour was MET, an unprobed dimension left blank instead of named. The positive cases
// exist to prove the module does report what the fields say, not only what they forbid.
import { describe, it, expect } from 'vitest'
import {
  ADAPTER_DECLARED_SOURCES, FIRST_RUN_STAGE_KEYS, SOFTWARE_ACCEPTANCE_KEYS, SOFTWARE_QUALIFICATION_KEYS,
  SOFTWARE_SOURCE_GAPS,
  adapterCardsOf, adapterQualification, bitingSourceGaps, cardForSoftware, clientIdAliases, driftQualification,
  establishedLayers, fieldBindingQualification, firstRunQualification, formQualification, isDriftedLocation,
  layerIsClaimed, limitedSupport, nativeQualification, nativeStatusWording, needsRevalidation,
  participatingProjects, qualifySoftwareRow, readCardExtras, softwareRowsOf, summarizeSoftwareEnvironment,
  uncreditableMetLayers, updateAvailability, versionQualification,
} from '@/lib/softwareQualification'
import type { AdapterCapabilityCard, CapabilityLayerState, SoftwareIdentity, SnapshotV3 } from '@/types'
import { mkSnap } from '@/test/snapshotFixture'

/** One row exactly as composition_root.py:135-151 emits it: updateAvailable null, discoverySource real. */
function mkRow(over: Partial<SoftwareIdentity> = {}): SoftwareIdentity {
  return {
    softwareId: 'hermes', displayName: 'Hermes',
    installRoot: 'C:\\Users\\ALEX\\AppData\\Local\\Programs\\Hermes',
    executableRealpath: 'C:\\Users\\ALEX\\AppData\\Local\\Programs\\Hermes\\Hermes.exe',
    discoveredVersion: '0.21.5+6948.gedd2476', releaseChannel: null,
    updateAvailable: null, duplicateInstallation: false,
    expectedLocation: 'C:\\Users\\ALEX\\AppData\\Local\\Programs\\Hermes',
    observedLocation: 'C:\\Users\\ALEX\\AppData\\Local\\Programs\\Hermes',
    locationStatus: 'SINGLE_VERIFIED', lastVerified: '2026-10-08T01:00:00Z',
    discoverySource: 'real-platform-probe',
    ...over,
  }
}

const FRESH_LAYERS = (): AdapterCapabilityCard['layers'] => ([
  { layer: 'REGISTERED', state: 'MET', evidenceLevel: 'SYNTHETIC',
    source: 'config/adapter-registry.json#entries[id=hermes]', reason: '登记来自仓库声明文件，是声明不是探测' },
  { layer: 'INSTALLED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
    reason: '软件安装身份投影里没有该客户端的行（发现模块不可用或未登记）' },
  { layer: 'LOADED_CONNECTED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
    reason: '没有已接通的原生会话读回：adapter 的 invoke/observe 动词仍返回 NOT_IMPLEMENTED（AG-06/G06）' },
  { layer: 'QUALIFIED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
    reason: '没有逐能力资格判定：资格需要真实调用与产物，目前没有可引用的判定记录' },
  { layer: 'ENABLED_FOR_TASK', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
    reason: '没有任务级启用记录：派发未实现，没有任何任务把该客户端启用为执行器' },
  { layer: 'NATIVE_PROJECTION', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
    reason: '没有原生投影：原生侧状态（会话/模型/子代理）尚未进入 v3 快照合同' },
  { layer: 'OBSERVED_IN_EXECUTION', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
    reason: '没有执行中观察：需要真实执行链上的 receipt/readback 关联到该客户端' },
]) as CapabilityLayerState[]

/** Lift exactly one rung to MET the way the producer would, leaving the other six rows untouched. */
function met(
  layers: AdapterCapabilityCard['layers'], layerName: CapabilityLayerState['layer'],
  source: string | null, evidenceLevel: CapabilityLayerState['evidenceLevel'] = 'INTEGRATED',
): AdapterCapabilityCard['layers'] {
  return layers.map((layer) => (layer.layer === layerName
    ? { ...layer, state: 'MET', evidenceLevel, source }
    : layer))
}

/** A card exactly as project_adapter_capabilities() emits it for a fresh projection
 *  (adapter_capability_projection.py:321-351): no verbEvidence key, nativeStatus constant. */
function mkCard(over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard {
  return {
    clientId: 'hermes', displayName: 'Hermes', supportLevel: 'deep',
    declaredOperations: ['detect', 'capabilities', 'plan', 'apply', 'invoke', 'observe', 'rollback'],
    matrixOperations: ['detect', 'capabilities', 'plan', 'apply', 'invoke', 'observe', 'rollback'],
    operationsDrift: false, registryStatus: 'active', writePolicy: 'approval_required', risk: 'high',
    runtimeAdapter: 'HermesAdapter',
    configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE', preserve_unknown: true },
    clientNote: null,
    declaredVersion: '0.21.5+6948.gedd2476', versionReadbackMethod: 'install-stamp-readback',
    versionObservedAt: '2026-10-07', versionSource: 'install-stamp.json',
    detectionMode: 'isolated', detectionEvidenceState: 'UNVERIFIED',
    protocolConformance: { acp: 'STATIC_PASS', skills: 'STATIC_PASS', mcp: 'STATIC_UNVERIFIED' },
    observedAt: '2026-10-08T00:00:00Z',
    layers: FRESH_LAYERS(),
    nativeStatus: 'NOT_IMPLEMENTED',
    ...over,
  }
}

/** `software` / `adapterCapabilities` are only ever set when the caller asks, because "key absent" and
 *  "key present and empty" are the two statements this module keeps apart. */
function snapWith(over: { software?: SoftwareIdentity[] | null, cards?: AdapterCapabilityCard[] | null } = {}): SnapshotV3 {
  const snap = mkSnap()
  if (over.software !== undefined && over.software !== null) snap.software = over.software
  if (over.cards !== undefined && over.cards !== null) snap.adapterCapabilities = over.cards
  return snap
}

describe('list access: absent key vs read-but-empty', () => {
  it('a missing software key is null, an empty list is an empty list', () => {
    expect(softwareRowsOf(snapWith())).toBeNull()
    expect(softwareRowsOf(snapWith({ software: [] }))).toEqual([])
    expect(softwareRowsOf(null)).toBeNull()
    expect(softwareRowsOf(undefined)).toBeNull()
  })

  it('a missing adapterCapabilities key is null, never an empty adapter list', () => {
    expect(adapterCardsOf(snapWith())).toBeNull()
    expect(adapterCardsOf(snapWith({ cards: [] }))).toEqual([])
    expect(adapterCardsOf(snapWith({ cards: [mkCard()] }))).toHaveLength(1)
  })
})

describe('the softwareId ↔ clientId join is the producer\'s alias set', () => {
  it('matches the three forms the projection itself tries', () => {
    expect(clientIdAliases('cc-switch')).toEqual(['cc-switch', 'cc_switch'])
    expect(clientIdAliases('a_b')).toContain('a-b')
    const cards = [mkCard({ clientId: 'cc-switch' })]
    expect(cardForSoftware(cards, 'cc-switch')?.clientId).toBe('cc-switch')
    expect(cardForSoftware(cards, 'cc_switch')?.clientId).toBe('cc-switch')
  })

  it('returns null for an unmatched id and for an unread list, and the two mean different things', () => {
    expect(cardForSoftware([mkCard()], 'github')).toBeNull()
    expect(cardForSoftware(null, 'github')).toBeNull()
    const unread = adapterQualification(mkRow({ softwareId: 'github' }), null, null)
    const readButMissing = adapterQualification(mkRow({ softwareId: 'github' }), [mkCard()], null)
    expect(unread.origin).toBe('SOURCE_GAP')
    expect(readButMissing.origin).toBe('NULL_FIELD')
  })

  it('the gap wording names the declared sources instead of counting adapters', () => {
    const gap = adapterQualification(mkRow(), null, null)
    expect(gap.note).toContain(ADAPTER_DECLARED_SOURCES)
    expect(gap.note).toContain('没读成')
    expect(gap.note).not.toMatch(/0 个适配器/)
  })

  it('a matched card is projected with its own fields, and the note admits the join is name-level', () => {
    const card = mkCard()
    const claim = adapterQualification(mkRow(), [card], card)
    expect(claim.origin).toBe('PROJECTED')
    expect(claim.value).toContain('supportLevel=deep')
    expect(claim.value).toContain('registryStatus=active')
    expect(claim.note).toContain('没有外键')
  })
})

describe('updateAvailable: what null means', () => {
  it('null is 未探测 — nothing was asked, so neither 是 nor 否 is available to render', () => {
    const fact = updateAvailability(mkRow({ updateAvailable: null }))
    expect(fact.state).toBe('NOT_PROBED')
    expect(fact.probed).toBe(false)
    expect(fact.text).toBe('未探测')
    expect(fact.meaning).toContain('composition_root.py:143')
    // the sentence must not read as either verdict
    expect(fact.text).not.toBe('否')
    expect(fact.text).not.toBe('是')
  })

  it('a real false means 否 and a real true means 是 — the field is only unavailable when it was never asked', () => {
    expect(updateAvailability(mkRow({ updateAvailable: false }))).toMatchObject({ state: 'NONE', probed: true, text: '否' })
    expect(updateAvailability(mkRow({ updateAvailable: true }))).toMatchObject({ state: 'AVAILABLE', probed: true, text: '是' })
    expect(updateAvailability(mkRow({ updateAvailable: false })).meaning).toContain('问过更新权威')
  })

  it('every produced row is unprobed today, and the summary says so per row', () => {
    const summary = summarizeSoftwareEnvironment(snapWith({ software: [mkRow(), mkRow({ softwareId: 'codex' })], cards: [] }))
    expect(summary.unprobedUpdateSoftwareIds).toEqual(['hermes', 'codex'])
  })
})

describe('version qualification', () => {
  it('a discovered version is projected with its source handle, and a null channel stays a null channel', () => {
    const claim = versionQualification(mkRow())
    expect(claim.origin).toBe('PROJECTED')
    expect(claim.value).toContain('0.21.5+6948.gedd2476')
    expect(claim.value).toContain('渠道 无记录（null）')
    expect(claim.source).toContain('discoverySource=real-platform-probe')
    expect(claim.note).toContain('releaseChannel=null')
  })

  it('a row with no observation is a source gap, not a blank cell', () => {
    // composition_root.py:108-126 — registry entry with no discovery observation
    const claim = versionQualification(mkRow({ discoveredVersion: null, discoverySource: 'unavailable', lastVerified: null }))
    expect(claim.origin).toBe('SOURCE_GAP')
    expect(claim.value).toBe('UNKNOWN')
    expect(claim.note).toContain('composition_root.py:108-126')
  })

  it('a probe that ran but returned no version string is NULL_FIELD, which is a third statement', () => {
    const claim = versionQualification(mkRow({ discoveredVersion: null, discoverySource: 'real-platform-probe' }))
    expect(claim.origin).toBe('NULL_FIELD')
    expect(claim.note).toContain('未读到不等于没有版本')
  })
})

describe('form qualification: drift and duplicates stay as typed', () => {
  it('LOCATION_DRIFT is emitted as the raw token with both locations', () => {
    const row = mkRow({ locationStatus: 'LOCATION_DRIFT', expectedLocation: 'D:\\All projects\\DSH', observedLocation: 'C:\\Program Files\\DSH' })
    const claim = formQualification(row)
    expect(claim.origin).toBe('PROJECTED')
    expect(claim.value).toContain('LOCATION_DRIFT')
    expect(claim.value).toContain('D:\\All projects\\DSH')
    expect(claim.value).toContain('C:\\Program Files\\DSH')
    expect(claim.note).toContain('不迁移')
  })

  it('DUAL_INSTALLATION keeps its token and its duplicateInstallation flag', () => {
    const row = mkRow({ locationStatus: 'DUAL_INSTALLATION', duplicateInstallation: true })
    const claim = formQualification(row)
    expect(claim.value).toContain('DUAL_INSTALLATION')
    expect(claim.source).toContain('duplicateInstallation=true')
  })

  it('SINGLE_VERIFIED is stated as a location shape and never as capability', () => {
    const claim = formQualification(mkRow({ locationStatus: 'SINGLE_VERIFIED' }))
    expect(claim.note).toContain('不代表可执行')
    expect(claim.note).toContain('不代表已连接')
    expect(claim.note).not.toMatch(/正常|健康|Healthy/)
  })

  it('UNKNOWN from an unavailable source is a gap, UNKNOWN from a live probe is an empty field', () => {
    expect(formQualification(mkRow({ locationStatus: 'UNKNOWN', discoverySource: 'unavailable' })).origin).toBe('SOURCE_GAP')
    const read = formQualification(mkRow({ locationStatus: 'UNKNOWN', discoverySource: 'real-platform-probe' }))
    expect(read.origin).toBe('NULL_FIELD')
    expect(read.note).toContain('location_status')
  })

  it('isDriftedLocation covers exactly the three conflict states and no others', () => {
    expect(isDriftedLocation(mkRow({ locationStatus: 'LOCATION_DRIFT' }))).toBe(true)
    expect(isDriftedLocation(mkRow({ locationStatus: 'DUAL_INSTALLATION' }))).toBe(true)
    expect(isDriftedLocation(mkRow({ locationStatus: 'MISSING_EXPECTED_INSTALL' }))).toBe(true)
    expect(isDriftedLocation(mkRow({ locationStatus: 'SINGLE_VERIFIED' }))).toBe(false)
    expect(isDriftedLocation(mkRow({ locationStatus: 'OS_MANAGED' }))).toBe(false)
    expect(isDriftedLocation(mkRow({ locationStatus: 'UNKNOWN' }))).toBe(false)
  })

  it('NOT_INSTALLED / OS_MANAGED / RELOCATION_REQUESTED render their own tokens', () => {
    for (const status of ['NOT_INSTALLED', 'OS_MANAGED', 'RELOCATION_REQUESTED'] as const) {
      expect(formQualification(mkRow({ locationStatus: status })).value).toContain(status)
    }
  })
})

describe('field-binding qualification', () => {
  it('a declared ownership default is projected as a default, and the note refuses to call it per-field', () => {
    const card = mkCard()
    const claim = fieldBindingQualification(mkRow(), [card], card)
    expect(claim.origin).toBe('PROJECTED')
    expect(claim.value).toContain('USER_OVERLAY / MANAGE / preserve_unknown=true')
    expect(claim.note).toContain('声明≠已写入≠已加载')
  })

  it('a client that declares no default is NULL_FIELD, never "no fields" and never "all writable"', () => {
    // the real case: config/capability-matrix.json → deepseek-harness.config_ownership_default is null
    const card = mkCard({ clientId: 'deepseek-harness', configOwnershipDefault: null })
    const claim = fieldBindingQualification(mkRow({ softwareId: 'deepseek-harness' }), [card], card)
    expect(claim.origin).toBe('NULL_FIELD')
    expect(claim.note).toContain('不是"没有字段"')
    expect(claim.note).toContain('也不是"全部可写"')
  })

  it('an OBSERVE default is not laundered into MANAGE', () => {
    const card = mkCard({ clientId: 'cc-switch', configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'OBSERVE', preserve_unknown: true } })
    const claim = fieldBindingQualification(mkRow({ softwareId: 'cc-switch' }), [card], card)
    expect(claim.value).toContain('/ OBSERVE /')
  })
})

describe('declared × observed drift', () => {
  it('VERSION_MOVED from the entry readback is shown, and both strings stay visible', () => {
    const card = mkCard({ declaredVersion: '0.2.0-rc.2' })
    ;(card as AdapterCapabilityCard & { versionDrift?: boolean }).versionDrift = true
    ;(card as AdapterCapabilityCard & { entryProbe?: unknown }).entryProbe = {
      status: 'VERSION_MOVED', entryPoint: 'DeepSeek Harness.exe', argv: ['DeepSeek Harness.exe', '--version'],
      exitCode: 0, outputDigest: 'a'.repeat(64), detail: '0.2.0-rc.3', probedAt: '2026-10-08T03:00:00Z',
    }
    const claim = driftQualification(mkRow({ softwareId: 'deepseek-harness', discoveredVersion: '0.2.0-rc.3' }), card)
    expect(claim.origin).toBe('PROJECTED')
    expect(claim.value).toContain('VERSION_MOVED')
    expect(claim.value).toContain('0.2.0-rc.2')
    expect(claim.value).toContain('0.2.0-rc.3')
    expect(claim.note).toContain('不选一个赢家')
  })

  it('operationsDrift is reported without picking which list is truth', () => {
    const card = mkCard({ declaredOperations: ['detect'], matrixOperations: ['detect', 'observe'], operationsDrift: true })
    const claim = driftQualification(mkRow(), card)
    expect(claim.value).toContain('operationsDrift=true')
    expect(claim.note).toContain('属所有者决定')
  })

  it('no entry readback is stated as absent, not as a failed readback', () => {
    const claim = driftQualification(mkRow(), mkCard())
    expect(claim.value).toContain('没有入口读回（entryProbe=null）')
  })

  it('without a card there is nothing to compare, which is a named gap', () => {
    const claim = driftQualification(mkRow(), null)
    expect(claim.origin).toBe('SOURCE_GAP')
    expect(claim.note).toContain(ADAPTER_DECLARED_SOURCES)
  })
})

describe('card extras the producer emits before types.ts carries them', () => {
  it('absent keys stay null — the reader never sees a substituted value', () => {
    expect(readCardExtras(mkCard())).toEqual({ entryProbe: null, versionDrift: null })
    expect(readCardExtras(null).entryProbe).toBeNull()
  })

  it('an entry probe is read field by field and an off-type value is not coerced into a verdict', () => {
    // the payload is JSON, so the read stays defensive even though types.ts now declares both fields
    const card = {
      ...mkCard(),
      entryProbe: {
        status: 'LIVE_VERIFIED', entryPoint: 'hermes.exe', argv: ['hermes.exe', '--version'],
        exitCode: 0, outputDigest: 'b'.repeat(64), detail: null, probedAt: '2026-10-08T03:00:00Z',
      },
      versionDrift: 'yes',
    } as unknown as AdapterCapabilityCard
    const extras = readCardExtras(card)
    expect(extras.entryProbe?.status).toBe('LIVE_VERIFIED')
    expect(extras.entryProbe?.argv).toEqual(['hermes.exe', '--version'])
    expect(extras.entryProbe?.detail).toBeNull()
    // a non-boolean versionDrift is not coerced into true or false
    expect(extras.versionDrift).toBeNull()
  })

  it('a probe record with no entry readback keeps entryProbe null rather than an empty object', () => {
    expect(readCardExtras(mkCard({ entryProbe: null })).entryProbe).toBeNull()
    const sparse = mkCard({ entryProbe: { status: 'NO_ENTRY', entryPoint: null, argv: [], exitCode: null, probedAt: null } })
    const extras = readCardExtras(sparse)
    expect(extras.entryProbe?.status).toBe('NO_ENTRY')
    expect(extras.entryProbe?.entryPoint).toBeNull()
    expect(extras.entryProbe?.exitCode).toBeNull()
  })
})

describe('the ladder is read, never climbed', () => {
  it('a fresh card marks exactly one rung MET and it is REGISTERED', () => {
    const card = mkCard()
    expect(establishedLayers(card).map((layer) => layer.layer)).toEqual(['REGISTERED'])
    expect(layerIsClaimed(card, 'REGISTERED')).toBe(true)
    for (const layer of ['INSTALLED', 'LOADED_CONNECTED', 'QUALIFIED', 'ENABLED_FOR_TASK', 'NATIVE_PROJECTION', 'OBSERVED_IN_EXECUTION']) {
      expect(layerIsClaimed(card, layer)).toBe(false)
    }
  })

  it('a card whose INSTALLED rung really is MET keeps it, and nothing else lifts', () => {
    const card = mkCard({ layers: met(FRESH_LAYERS(), 'INSTALLED', 'software[hermes] locationStatus=SINGLE_VERIFIED root=C:\\x') })
    expect(establishedLayers(card).map((layer) => layer.layer)).toEqual(['REGISTERED', 'INSTALLED'])
    expect(layerIsClaimed(card, 'QUALIFIED')).toBe(false)
  })

  it('a MET rung with no named source is surfaced as uncreditable instead of counted', () => {
    const card = mkCard({ layers: met(FRESH_LAYERS(), 'QUALIFIED', null, 'REAL') })
    expect(uncreditableMetLayers(card).map((layer) => layer.layer)).toEqual(['QUALIFIED'])
    expect(establishedLayers(card)).toHaveLength(2)
  })

  it('nativeStatus NOT_IMPLEMENTED is worded as an unimplemented path, not as a pass', () => {
    const card = mkCard()
    expect(nativeStatusWording(card)).toContain('NOT_IMPLEMENTED')
    expect(nativeStatusWording(card)).toContain('常量')
    expect(nativeStatusWording(card)).not.toMatch(/VERIFIED|通过|成功/)
    const claim = nativeQualification(card)
    expect(claim.origin).toBe('PROJECTED')
    expect(claim.value).toContain('该卡自己标 MET 的层：REGISTERED')
  })

  it('a NATIVELY_VERIFIED claim without the last rung is refused, with both statements kept', () => {
    const card = mkCard({ nativeStatus: 'NATIVELY_VERIFIED' })
    expect(nativeStatusWording(card)).toContain('不采信')
    expect(nativeStatusWording(card)).toContain('OBSERVED_IN_EXECUTION 未成立')
    const layers = met(FRESH_LAYERS(), 'OBSERVED_IN_EXECUTION', 'receipt', 'REAL')
    expect(nativeStatusWording(mkCard({ nativeStatus: 'NATIVELY_VERIFIED', layers }))).toContain('一致')
  })

  it('no card means no native status to report, which is a gap not a verdict', () => {
    expect(nativeQualification(null).origin).toBe('SOURCE_GAP')
    expect(nativeQualification(null).note).toContain('无字段可读')
  })
})

describe('limited support and revalidation wording come from fields', () => {
  it('deep + active with a runtime adapter and MANAGE default carries no field-level limit, and still says the ladder is unprobed', () => {
    const verdict = limitedSupport(mkCard())
    expect(verdict.isLimited).toBe(false)
    expect(verdict.wording).toBe('')
    expect(verdict.reasons[0]).toContain('REGISTERED 之上仍未探测')
  })

  it('experimental / manifest-only / quarantined / legacy_observe / blocked each name the field that limits', () => {
    expect(limitedSupport(mkCard({ supportLevel: 'experimental' })).wording).toContain('supportLevel=experimental')
    expect(limitedSupport(mkCard({ supportLevel: 'manifest-only' })).wording).toContain('只有清单')
    expect(limitedSupport(mkCard({ registryStatus: 'quarantined' })).wording).toContain('已隔离')
    expect(limitedSupport(mkCard({ registryStatus: 'legacy_observe' })).wording).toContain('只观察，不写入')
    expect(limitedSupport(mkCard({ registryStatus: 'blocked' })).wording).toContain('被拦在外')
  })

  it('writes=unavailable, a null runtime adapter and an OBSERVE default are all limits', () => {
    expect(limitedSupport(mkCard({ writePolicy: 'unavailable' })).wording).toContain('写路径不可用')
    expect(limitedSupport(mkCard({ runtimeAdapter: null })).wording).toContain('没有运行时适配器')
    expect(limitedSupport(mkCard({ configOwnershipDefault: { layer: 'PLATFORM_INTERNAL', mode: 'OBSERVE', preserve_unknown: true } }))
      .wording).toContain('只观察，不由本方写入')
  })

  it('a missing card is limited by absence of evidence, and says which dimension that is', () => {
    const verdict = limitedSupport(null)
    expect(verdict.isLimited).toBe(true)
    expect(verdict.wording).toContain('支持范围无从判定')
  })

  it('needsRevalidation fires on every unsettled field and only on those', () => {
    const reasons = needsRevalidation(mkRow(), mkCard()).reasons
    expect(reasons.some((line) => line.includes('updateAvailable=null'))).toBe(true)
    expect(reasons.some((line) => line.includes('UNVERIFIED'))).toBe(true)
    expect(reasons).toHaveLength(2)
  })

  it('an unobserved row adds its own reasons instead of being reported as verified', () => {
    const row = mkRow({ discoveredVersion: null, lastVerified: null, discoverySource: 'unavailable', locationStatus: 'UNKNOWN' })
    const verdict = needsRevalidation(row, null)
    expect(verdict.required).toBe(true)
    expect(verdict.reasons).toHaveLength(4)
    expect(verdict.reasons.join('')).toContain('discoverySource=unavailable')
    expect(verdict.reasons.join('')).toContain('lastVerified=null')
    expect(verdict.reasons.join('')).toContain('discoveredVersion=null')
    expect(verdict.wording).toBe(verdict.reasons.join('；'))
  })

  it('versionDrift and operationsDrift both demand revalidation', () => {
    const card = mkCard()
    ;(card as AdapterCapabilityCard & { versionDrift?: boolean }).versionDrift = true
    ;(card as AdapterCapabilityCard & { operationsDrift?: boolean }).operationsDrift = true
    const reasons = needsRevalidation(mkRow({ lastVerified: '2026-10-08T00:00:00Z' }), card).reasons
    expect(reasons.some((line) => line.includes('VERSION_MOVED'))).toBe(true)
    expect(reasons.some((line) => line.includes('动词集合不一致'))).toBe(true)
  })
})

describe('participating projects are candidates, never attribution', () => {
  it('matches projects and executions by agent name and says the payload has no foreign key', () => {
    const result = participatingProjects(mkSnap(), 'codex')
    expect(result.projectIds).toEqual(['work-lab', 'design-lab'])
    expect(result.basis).toContain('名字级匹配')
    expect(result.basis).toContain('外键')
    expect(result.executionIds).toEqual([])
  })

  it('an unmatched softwareId yields an empty candidate list, not a guess', () => {
    expect(participatingProjects(mkSnap(), 'openhuman').projectIds).toEqual([])
  })

  it('a project without agentPlatform is skipped and never counted as this software', () => {
    const snap = mkSnap({ projects: [{ ...mkSnap().projects[0], agentPlatform: null }] })
    expect(participatingProjects(snap, 'codex').projectIds).toEqual([])
  })

  it('executions match on agent name and keep their own ids', () => {
    const snap = mkSnap({ executions: [
      { executionId: 'ex-1', agent: 'codex', anchorProjectId: 'work-lab', workingArea: null, state: 'RUNNING', stateQuality: 'strong', sessionId: null, sourceRef: null },
      { executionId: 'ex-2', agent: 'hermes', anchorProjectId: 'work-lab', workingArea: null, state: 'RUNNING', stateQuality: 'strong', sessionId: null, sourceRef: null },
    ] as SnapshotV3['executions'] })
    expect(participatingProjects(snap, 'codex').executionIds).toEqual(['ex-1'])
  })
})

describe('qualifySoftwareRow assembles the four acceptance dimensions plus the rest', () => {
  it('every declared key is present exactly once, in order', () => {
    const qualification = qualifySoftwareRow(mkRow(), snapWith({ software: [mkRow()], cards: [mkCard()] }))
    expect(qualification.claims.map((claim) => claim.key)).toEqual([...SOFTWARE_QUALIFICATION_KEYS])
    for (const key of SOFTWARE_ACCEPTANCE_KEYS) {
      expect(qualification.claims.some((claim) => claim.key === key)).toBe(true)
    }
  })

  it('the update claim keeps 未探测 as its value even though its origin is a gap', () => {
    const qualification = qualifySoftwareRow(mkRow(), snapWith({ software: [mkRow()], cards: [mkCard()] }))
    const update = qualification.claims.find((claim) => claim.key === 'update')!
    expect(update.origin).toBe('SOURCE_GAP')
    expect(update.value).toBe('未探测')
    expect(update.note).toContain('composition_root.py:143')
  })

  it('a row without a card reports the adapter dimension as NULL_FIELD while the list was read', () => {
    const qualification = qualifySoftwareRow(mkRow({ softwareId: 'github' }), snapWith({ software: [mkRow()], cards: [mkCard()] }))
    expect(qualification.card).toBeNull()
    expect(qualification.claims.find((claim) => claim.key === 'adapter')!.origin).toBe('NULL_FIELD')
    expect(qualification.established).toEqual([])
  })

  it('established layers are only ever the card\'s own MET rows', () => {
    const withInstalled = mkCard({ layers: met(FRESH_LAYERS(), 'INSTALLED', 'executor_live_probe[hermes] LIVE_VERIFIED entry=hermes.exe') })
    const snap = mkSnap({ software: [mkRow()], adapterCapabilities: [withInstalled] })
    expect(qualifySoftwareRow(mkRow(), snap).established).toEqual(['REGISTERED', 'INSTALLED'])
  })
})

describe('page summary', () => {
  it('an empty software list is flagged ambiguous, never as "nothing installed"', () => {
    const summary = summarizeSoftwareEnvironment(snapWith({ software: [], cards: [mkCard()] }))
    expect(summary.softwareKeyPresent).toBe(true)
    expect(summary.softwareListAmbiguous).toBe(true)
    expect(summary.softwareRowCount).toBe(0)
    expect(summary.qualifications).toEqual([])
  })

  it('an absent software key is a different state from an empty one', () => {
    const summary = summarizeSoftwareEnvironment(mkSnap())
    expect(summary.softwareKeyPresent).toBe(false)
    expect(summary.softwareListAmbiguous).toBe(false)
    expect(summary.cardsKeyPresent).toBe(false)
    expect(summary.cardCount).toBe(0)
  })

  it('drifted rows and rows without a card are named by id', () => {
    const summary = summarizeSoftwareEnvironment(snapWith({
      software: [mkRow(), mkRow({ softwareId: 'deepseek-harness', locationStatus: 'LOCATION_DRIFT' }), mkRow({ softwareId: 'openhuman', locationStatus: 'DUAL_INSTALLATION' })],
      cards: [mkCard({ clientId: 'deepseek-harness' })],
    }))
    expect(summary.driftedSoftwareIds).toEqual(['deepseek-harness', 'openhuman'])
    expect(summary.rowsWithoutCard).toEqual(['hermes', 'openhuman'])
  })

  it('nothing above REGISTERED is reported as claimed for fresh cards', () => {
    const summary = summarizeSoftwareEnvironment(snapWith({ software: [mkRow()], cards: [mkCard(), mkCard({ clientId: 'codex' })] }))
    expect(summary.claimedAboveRegistered).toEqual([])
  })
})

describe('first-run stages', () => {
  it('walks the five stages of 母版 15_first_run in order', () => {
    const stages = firstRunQualification(mkSnap())
    expect(stages.map((stage) => stage.key)).toEqual([...FIRST_RUN_STAGE_KEYS])
    for (const stage of stages) expect(stage.answers.length).toBeGreaterThan(0)
    for (const stage of stages) expect(stage.gap.length).toBeGreaterThan(0)
  })

  it('low-risk real activity is never answerable from this projection', () => {
    const stages = firstRunQualification(snapWith({ software: [mkRow()], cards: [mkCard()] }))
    const activity = stages.find((stage) => stage.key === 'lowRiskRealActivity')!
    expect(activity.answer).toBe('SOURCE_GAP')
    expect(activity.gap).toContain('不派工')
  })

  it('qualification and fields are partial by construction: declaration yes, measurement no', () => {
    const stages = firstRunQualification(snapWith({ software: [mkRow()], cards: [mkCard()] }))
    const fields = stages.find((stage) => stage.key === 'qualificationAndFields')!
    expect(fields.answer).toBe('PARTIAL')
    expect(fields.gap).toContain('adapter_capability_projection.py:310-319')
  })

  it('discovery is SOURCE_GAP without the key and PARTIAL with unprobed rows mixed in', () => {
    expect(firstRunQualification(mkSnap()).find((s) => s.key === 'authorizedDiscovery')!.answer).toBe('SOURCE_GAP')
    expect(firstRunQualification(snapWith({ software: [] })).find((s) => s.key === 'authorizedDiscovery')!.answer).toBe('SOURCE_GAP')
    expect(firstRunQualification(snapWith({ software: [mkRow()], cards: [] })).find((s) => s.key === 'authorizedDiscovery')!.answer).toBe('ANSWERABLE')
    const mixed = firstRunQualification(snapWith({ software: [mkRow(), mkRow({ softwareId: 'codex', discoverySource: 'unavailable' })], cards: [] }))
    expect(mixed.find((s) => s.key === 'authorizedDiscovery')!.answer).toBe('PARTIAL')
    expect(mixed.find((s) => s.key === 'authorizedDiscovery')!.gap).toContain('停在 UNKNOWN')
  })

  it('readback needs a real entry probe or a MET verb row, and says what it lacks otherwise', () => {
    expect(firstRunQualification(snapWith({ software: [mkRow()], cards: [mkCard()] })).find((s) => s.key === 'entryReadback')!.answer).toBe('SOURCE_GAP')
    const probed = mkCard({
      entryProbe: { status: 'LIVE_VERIFIED', entryPoint: 'hermes.exe', argv: ['hermes.exe', '--version'], exitCode: 0, probedAt: '2026-10-08T03:00:00Z' },
    })
    const stage = firstRunQualification(snapWith({ software: [mkRow()], cards: [probed] })).find((s) => s.key === 'entryReadback')!
    expect(stage.answer).toBe('ANSWERABLE')
    expect(stage.answers).toContain('1 个入口')
    const declared = mkCard({
      verbEvidence: [{
        verb: 'detect', state: 'MET', evidenceLevel: 'INTEGRATED', source: 'hermes.exe --version',
        reason: null, attempted: true,
      }],
    })
    expect(firstRunQualification(snapWith({ software: [mkRow()], cards: [declared] })).find((s) => s.key === 'entryReadback')!.answer).toBe('ANSWERABLE')
  })

  it('the diff stage is a gap when the cards were never read', () => {
    expect(firstRunQualification(snapWith({ software: [mkRow()] })).find((s) => s.key === 'declaredVsObservedDiff')!.answer).toBe('SOURCE_GAP')
  })
})

describe('SOFTWARE_SOURCE_GAPS: what the projection cannot answer, by name', () => {
  it('every entry is a question with a producer-grounded reason and a unique key', () => {
    const keys = SOFTWARE_SOURCE_GAPS.map((gap) => gap.key)
    expect(new Set(keys).size).toBe(keys.length)
    for (const gap of SOFTWARE_SOURCE_GAPS) {
      expect(gap.question.length).toBeGreaterThan(4)
      expect(gap.reason.length).toBeGreaterThan(20)
    }
  })

  it('covers the update probe, the ladder, native status, field-level ownership and the readback provenance', () => {
    const keys = SOFTWARE_SOURCE_GAPS.map((gap) => gap.key)
    for (const key of ['updateProbe', 'softwareListAmbiguity', 'adapterCapabilitiesAbsent', 'layerLadder',
      'nativeVerification', 'fieldLevelOwnership', 'verbEvidenceAbsent', 'sourceLoadProvenance',
      'authSurface', 'privateSessions', 'softwareProjectBinding', 'revalidationSchedule']) {
      expect(keys).toContain(key)
    }
  })

  it('the read-only boundary gaps are marked as deliberate, so they are not filed as bugs', () => {
    const byDesign = SOFTWARE_SOURCE_GAPS.filter((gap) => gap.byDesign).map((gap) => gap.key)
    expect(byDesign).toEqual(['authSurface', 'privateSessions'])
    expect(SOFTWARE_SOURCE_GAPS.find((gap) => gap.key === 'authSurface')!.reason).toContain('凭据')
    expect(SOFTWARE_SOURCE_GAPS.find((gap) => gap.key === 'privateSessions')!.reason).toContain('浏览器')
  })

  it('biting gaps switch on the snapshot: an unread adapter list and missing verb evidence are named, an empty software list only when it is empty', () => {
    expect(bitingSourceGaps(mkSnap())).toContain('adapterCapabilitiesAbsent')
    expect(bitingSourceGaps(snapWith({ cards: [mkCard()] }))).not.toContain('adapterCapabilitiesAbsent')
    expect(bitingSourceGaps(snapWith({ software: [], cards: [mkCard()] }))).toContain('softwareListAmbiguity')
    expect(bitingSourceGaps(snapWith({ software: [mkRow()], cards: [mkCard()] }))).not.toContain('softwareListAmbiguity')
    expect(bitingSourceGaps(snapWith({ cards: [mkCard()] }))).toContain('verbEvidenceAbsent')
    const withVerbs = mkCard({ verbEvidence: [{ verb: 'detect', state: 'MET', evidenceLevel: 'INTEGRATED', source: 'x', reason: null, attempted: true }] })
    expect(bitingSourceGaps(snapWith({ cards: [withVerbs] }))).not.toContain('verbEvidenceAbsent')
  })

  it('the boundary and ladder gaps bite in every snapshot, because they are contract limits not wiring limits', () => {
    for (const snap of [mkSnap(), snapWith({ software: [mkRow()], cards: [mkCard()] })]) {
      const biting = bitingSourceGaps(snap)
      expect(biting).toContain('updateProbe')
      expect(biting).toContain('layerLadder')
      expect(biting).toContain('authSurface')
      expect(biting).toContain('privateSessions')
      expect(biting).toContain('sourceLoadProvenance')
    }
  })
})
