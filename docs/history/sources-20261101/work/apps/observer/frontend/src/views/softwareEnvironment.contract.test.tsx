// WUI-06 · render-level contract tests for 软件环境页.
//
// These assert the five things the taskpack names, at the DOM level, because each one is a lie a reader
// could act on: an absent adapter list read as "no adapters", an unasked update field read as "up to date",
// a drifted or duplicated installation read as fine, a rung above REGISTERED read as achieved, and the
// constant NOT_IMPLEMENTED read as a pass. The page composes SoftwareView and AdapterCapabilityCards rather
// than re-drawing them, so a test also proves the reused surfaces are the ones that rendered.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SoftwareEnvironmentView } from '@/views/SoftwareEnvironmentView'
import type { AdapterCapabilityCard, CapabilityLayerState, SoftwareIdentity, SnapshotV3 } from '@/types'
import { mkSnap } from '@/test/snapshotFixture'

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

/** The ladder exactly as adapter_capability_projection.py:310-319 builds it for a fresh card. */
function freshLayers(): AdapterCapabilityCard['layers'] {
  return [
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
  ] as CapabilityLayerState[]
}

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
    layers: freshLayers(),
    nativeStatus: 'NOT_IMPLEMENTED',
    ...over,
  }
}

function snapWith(over: { software?: SoftwareIdentity[] | null, cards?: AdapterCapabilityCard[] | null } = {}): SnapshotV3 {
  const snap = mkSnap()
  if (over.software) snap.software = over.software
  if (over.cards) snap.adapterCapabilities = over.cards
  return snap
}

const claimIn = (container: HTMLElement, softwareId: string, key: string): Element | null =>
  container.querySelector(`[data-software-qualification="${softwareId}"] [data-qualification-claim="${key}"]`)

const originOf = (container: HTMLElement, softwareId: string, key: string): string | null =>
  container.querySelector(`[data-software-qualification="${softwareId}"] [data-qualification-claim="${key}"]`)?.getAttribute('data-origin') ?? null

describe('the page composes the working surfaces instead of redrawing them', () => {
  it('renders SoftwareView and AdapterCapabilityCards, both with their own headers', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()], cards: [mkCard()] })} />)
    expect(container.querySelector('[data-testid="section-install-identity"]')).toBeTruthy()
    expect(container.querySelector('[data-testid="section-adapter-cards"]')).toBeTruthy()
    expect(screen.getByText('软件安装身份（只读投影）')).toBeTruthy()
    // the reused cards surface renders its ladder count, which only its own component produces
    expect(screen.getByText(/阶梯 1\/7 层成立/)).toBeTruthy()
    // the install-identity rows themselves come from the reused panel
    expect(screen.getByText('安装位置')).toBeTruthy()
    expect(screen.getByText('发现版本')).toBeTruthy()
  })

  it('a null snapshot renders the page shell and names both missing keys rather than crashing', () => {
    const { container } = render(<SoftwareEnvironmentView snap={null} />)
    expect(screen.getByText('软件环境 · 接入资格')).toBeTruthy()
    expect(container.querySelector('[data-testid="summary-software"]')?.textContent).toContain('software 键缺席')
    expect(container.querySelector('[data-testid="summary-adapters"]')?.textContent).toContain('adapterCapabilities 键缺席')
  })
})

describe('absent adapterCapabilities is the named source gap, never "no adapters"', () => {
  it('the summary, the per-row adapter claim and the reused cards section all say 来源缺口', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()] })} />)
    const summary = container.querySelector('[data-testid="summary-adapters"]')!
    expect(summary.textContent).toContain('来源缺口')
    expect(summary.textContent).toContain('config/adapter-registry.json')
    expect(originOf(container, 'hermes', 'adapter')).toBe('SOURCE_GAP')
    expect(claimIn(container, 'hermes', 'adapter')?.textContent).toContain('没读成')
    // the reused component's own gap wording is present too
    expect(screen.getByText(/来源缺口：快照没有 adapterCapabilities 字段/)).toBeTruthy()
    expect(screen.getByText('原生能力卡')).toBeTruthy()
  })

  it('no part of the page states an adapter count when the key is absent', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()] })} />)
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/0 个适配器|适配器 0|adapterCapabilities[：:]\s*0/)
    expect(text).not.toMatch(/无适配器/)
    // and the gap entry for it is marked as biting this round
    const gap = container.querySelector('[data-gap-key="adapterCapabilitiesAbsent"]')!
    expect(gap.getAttribute('data-biting')).toBe('yes')
  })

  it('a read list whose softwareId has no entry is a different statement: NULL_FIELD, not a gap', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow({ softwareId: 'github' })], cards: [mkCard()] })} />)
    expect(originOf(container, 'github', 'adapter')).toBe('NULL_FIELD')
    expect(originOf(container, 'github', 'fieldBinding')).toBe('NULL_FIELD')
    expect(claimIn(container, 'github', 'adapter')?.textContent).toContain('读过而没有')
    expect(container.querySelector('[data-testid="summary-rows-without-card"]')?.textContent).toContain('github')
  })
})

describe('updateAvailable null renders 未探测 and never 是 / 否', () => {
  it('the update claim carries the unprobed word and its origin is the never-asked gap', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow({ updateAvailable: null })], cards: [mkCard()] })} />)
    const claim = claimIn(container, 'hermes', 'update')!
    expect(claim.textContent).toContain('未探测')
    expect(claim.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(claim.textContent).toContain('composition_root.py:143')
    // neither verdict exists as a standalone value for this dimension
    expect(claim.querySelector('[data-testid="origin-update"]')?.textContent).toBe('SOURCE_GAP')
    const values = [...claim.querySelectorAll('div')].map((node) => node.textContent?.trim())
    expect(values).not.toContain('是')
    expect(values).not.toContain('否')
  })

  it('no line on the page reads the update field as a verdict', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow(), mkRow({ softwareId: 'codex', displayName: 'Codex' })], cards: [mkCard()] })} />)
    expect((container.textContent ?? '').replace(/\s+/g, '')).not.toMatch(/更新可用[：:].{0,3}(是|否)/)
    expect(container.querySelector('[data-testid="summary-software"]')?.textContent).toContain('更新未探测 2 行')
  })

  it('a real boolean does get its verdict word, so the unprobed case is a distinction and not a blanket', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow({ updateAvailable: false })], cards: [mkCard()] })} />)
    const claim = claimIn(container, 'hermes', 'update')!
    expect(claim.getAttribute('data-origin')).toBe('PROJECTED')
    expect([...claim.querySelectorAll(':scope > div')].some((node) => node.textContent?.trim() === '否')).toBe(true)
    expect(container.querySelector('[data-testid="summary-software"]')?.textContent).toContain('更新未探测 0 行')
  })
})

describe('LOCATION_DRIFT and DUAL_INSTALLATION stay as typed', () => {
  it('both raw enum tokens reach the DOM and no wording launders them', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({
      software: [
        mkRow({ locationStatus: 'LOCATION_DRIFT', expectedLocation: 'D:\\All projects\\DSH', observedLocation: 'C:\\Users\\ALEX\\AppData\\Local\\Programs\\DeepSeek Harness' }),
        mkRow({ softwareId: 'cc-switch', displayName: 'CC Switch', locationStatus: 'DUAL_INSTALLATION', duplicateInstallation: true }),
      ],
      cards: [mkCard({ clientId: 'cc-switch', registryStatus: 'legacy_observe', writePolicy: 'unavailable' })],
    })} />)
    const text = container.textContent ?? ''
    expect(text).toContain('LOCATION_DRIFT')
    expect(text).toContain('DUAL_INSTALLATION')
    expect(text).not.toContain('正常')
    expect(originOf(container, 'hermes', 'form')).toBe('PROJECTED')
    expect(claimIn(container, 'hermes', 'drift-flag')?.textContent).toContain('预期 D:\\All projects\\DSH')
    expect(claimIn(container, 'cc-switch', 'drift-flag')?.textContent).toContain('duplicateInstallation=true')
    // the reused SoftwareView keeps its own error-level reading of the same two states
    expect(screen.getAllByText('位置漂移').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('双安装').length).toBeGreaterThanOrEqual(1)
  })

  it('the drift-flag element only exists for the three conflict states', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({
      software: [mkRow(), mkRow({ softwareId: 'codex', displayName: 'Codex', locationStatus: 'SINGLE_UNVERIFIED' }), mkRow({ softwareId: 'github', displayName: 'GitHub', locationStatus: 'MISSING_EXPECTED_INSTALL' })],
      cards: [],
    })} />)
    expect(container.querySelector('[data-software-qualification="hermes"] [data-qualification-claim="drift-flag"]')).toBeNull()
    expect(container.querySelector('[data-software-qualification="codex"] [data-qualification-claim="drift-flag"]')).toBeNull()
    expect(container.querySelector('[data-software-qualification="github"] [data-qualification-claim="drift-flag"]')).toBeTruthy()
  })

  it('an unobserved registry entry reports UNKNOWN honestly instead of a location claim', () => {
    // composition_root.py:108-126 — the no-observation shape
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow({
      installRoot: null, executableRealpath: null, discoveredVersion: null, locationStatus: 'UNKNOWN',
      expectedLocation: null, observedLocation: null, lastVerified: null, discoverySource: 'unavailable',
    })], cards: [mkCard()] })} />)
    expect(originOf(container, 'hermes', 'form')).toBe('SOURCE_GAP')
    expect(originOf(container, 'hermes', 'version')).toBe('SOURCE_GAP')
    expect(claimIn(container, 'hermes', 'form')?.textContent).toContain('discoverySource=unavailable')
    expect(claimIn(container, 'hermes', 'form')?.textContent).toContain('UNKNOWN')
  })
})

describe('nothing above REGISTERED is presented as achieved', () => {
  it('a fresh card yields exactly one MET rung badge per card, and the page reports no higher claim', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({
      software: [mkRow(), mkRow({ softwareId: 'codex', displayName: 'Codex' })],
      cards: [mkCard(), mkCard({ clientId: 'codex', displayName: 'Codex' })],
    })} />)
    // one 成立 badge per card = REGISTERED only; six 未探测 rungs per card from the ladder
    expect(screen.getAllByText('成立')).toHaveLength(2)
    expect(screen.getAllByText('未探测').length).toBeGreaterThanOrEqual(12)
    expect(container.querySelector('[data-testid="summary-ladder"]')?.textContent).toContain('无 ——')
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/已资格判定[^]{0,12}(成立|达成)/)
    expect(claimIn(container, 'hermes', 'native')?.textContent).toContain('自己标 MET 的层：REGISTERED')
  })

  it('answered verbs in the reused cards never lift a rung, and this page says so in its own words', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({
      software: [mkRow()],
      cards: [mkCard({
        verbEvidence: ['detect', 'capabilities'].map((verb) => ({
          verb, state: 'MET' as const, evidenceLevel: 'INTEGRATED' as const,
          source: `read-only call ${verb}`, reason: null, attempted: true,
        })),
      })],
    })} />)
    expect(screen.getAllByText('成立')).toHaveLength(1)
    expect(screen.getAllByText('已作答')).toHaveLength(2)
    expect(container.querySelector('[data-testid="summary-ladder"]')?.textContent).toContain('本页不把任何更高层级说成达成')
  })

  it('a card whose INSTALLED rung really is MET reports it, and stops there', () => {
    const installed = mkCard({
      layers: freshLayers().map((layer) => (layer.layer === 'INSTALLED'
        ? {
            ...layer,
            state: 'MET' as const,
            evidenceLevel: 'INTEGRATED' as const,
            source: 'software[hermes] locationStatus=SINGLE_VERIFIED root=C:\\x',
          }
        : layer)),
    })
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()], cards: [installed] })} />)
    expect(container.querySelector('[data-testid="summary-ladder"]')?.textContent).toContain('hermes:INSTALLED')
    expect(screen.getAllByText('成立')).toHaveLength(2)
    expect(container.querySelector('[data-testid="summary-ladder"]')?.textContent).not.toContain('QUALIFIED')
  })
})

describe('nativeStatus is NOT_IMPLEMENTED wording, not a pass', () => {
  it('the native claim prints the constant with the reason and never a verification success', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()], cards: [mkCard()] })} />)
    const claim = claimIn(container, 'hermes', 'native')!
    expect(claim.textContent).toContain('NOT_IMPLEMENTED')
    expect(claim.textContent).toContain('常量')
    expect(claim.textContent).not.toContain('NATIVELY_VERIFIED')
    const text = container.textContent ?? ''
    expect(text).not.toMatch(/原生验证(已|通过|成功)/)
    expect(text).not.toContain('NATIVELY_VERIFIED')
    // the reused card prints the same constant, so the two surfaces cannot disagree
    expect(screen.getAllByText(/NOT_IMPLEMENTED/).length).toBeGreaterThanOrEqual(2)
  })

  it('without any card the native dimension is a gap, not a silent blank', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()] })} />)
    expect(originOf(container, 'hermes', 'native')).toBe('SOURCE_GAP')
    expect(claimIn(container, 'hermes', 'native')?.textContent).toContain('无字段可读')
  })

  it('limited support comes from the card fields and is labelled with them', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({
      software: [mkRow({ softwareId: 'deepseek-harness', displayName: 'DeepSeek Harness' })],
      cards: [mkCard({ clientId: 'deepseek-harness', displayName: 'DeepSeek Harness', supportLevel: 'experimental', registryStatus: 'active', runtimeAdapter: 'DeepSeekHarnessAdapter', writePolicy: 'approval_required', risk: 'medium', configOwnershipDefault: null })],
    })} />)
    const block = container.querySelector('[data-software-qualification="deepseek-harness"]')!
    expect(block.textContent).toContain('有限支持')
    expect(block.textContent).toContain('supportLevel=experimental')
    expect(block.textContent).toContain('configOwnershipDefault=null')
  })
})

describe('first-run stages say which stages this snapshot can answer', () => {
  it('renders five stages and keeps the low-risk-activity stage a gap', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()], cards: [mkCard()] })} />)
    const stages = [...container.querySelectorAll('[data-stage]')]
    expect(stages.filter((node) => node.getAttribute('data-stage') !== 'boundary')).toHaveLength(5)
    expect(container.querySelector('[data-stage="lowRiskRealActivity"]')?.getAttribute('data-answer')).toBe('SOURCE_GAP')
    expect(container.querySelector('[data-stage="lowRiskRealActivity"]')?.textContent).toContain('不派工')
    expect(container.querySelector('[data-stage="qualificationAndFields"]')?.getAttribute('data-answer')).toBe('PARTIAL')
    expect(container.querySelector('[data-stage="entryReadback"]')?.getAttribute('data-answer')).toBe('SOURCE_GAP')
  })

  it('an entry readback in the card flips only the readback stage', () => {
    const probed = mkCard({
      entryProbe: { status: 'LIVE_VERIFIED', entryPoint: 'hermes.exe', argv: ['hermes.exe', '--version'], exitCode: 0, probedAt: '2026-10-08T03:00:00Z' },
    })
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [mkRow()], cards: [probed] })} />)
    expect(container.querySelector('[data-stage="entryReadback"]')?.getAttribute('data-answer')).toBe('ANSWERABLE')
    expect(container.querySelector('[data-stage="declaredVsObservedDiff"]')?.getAttribute('data-answer')).toBe('ANSWERABLE')
    expect(container.querySelector('[data-stage="lowRiskRealActivity"]')?.getAttribute('data-answer')).toBe('SOURCE_GAP')
    expect(container.textContent).toContain('hermes.exe')
  })

  it('an empty software list is reported as indistinguishable, never as "nothing installed"', () => {
    const { container } = render(<SoftwareEnvironmentView snap={snapWith({ software: [], cards: [mkCard()] })} />)
    const empty = container.querySelector('[data-testid="qualification-empty"]')!
    expect(empty.textContent).toContain('无法区分')
    expect(empty.textContent).toContain(':83-84')
    expect(empty.textContent).not.toMatch(/这台机器没有(安装|任何)/)
    expect(container.querySelector('[data-gap-key="softwareListAmbiguity"]')?.getAttribute('data-biting')).toBe('yes')
  })
})

describe('the page stays a projection: no control, no sub-12px text', () => {
  const full = () => render(<SoftwareEnvironmentView snap={snapWith({
    software: [mkRow(), mkRow({ softwareId: 'deepseek-harness', displayName: 'DeepSeek Harness', locationStatus: 'LOCATION_DRIFT' })],
    cards: [mkCard(), mkCard({ clientId: 'deepseek-harness', displayName: 'DeepSeek Harness', supportLevel: 'experimental' })],
  })} />)

  it('renders no button, input, select, textarea or link at all', () => {
    const { container } = full()
    for (const tag of ['button', 'input', 'select', 'textarea', 'a', 'form']) {
      expect(container.querySelectorAll(tag)).toHaveLength(0)
    }
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('names the forbidden actions as things it does not do, and never offers them', () => {
    const { container } = full()
    const boundary = container.querySelector('[data-stage="boundary"]')!
    expect(boundary.textContent).toContain('不安装')
    expect(boundary.textContent).toContain('不更新')
    expect(boundary.textContent).toContain('不启动')
    expect(boundary.textContent).toContain('不重新探测')
  })

  it('every explicit text-[] size utility on the page is at least 12px', () => {
    const { container } = full()
    const offenders: string[] = []
    let scanned = 0
    for (const node of Array.from(container.querySelectorAll<HTMLElement>('*'))) {
      const className = node.getAttribute('class') ?? ''
      for (const token of className.split(/\s+/)) {
        const size = /^text-\[(\d+(?:\.\d+)?)px\]$/.exec(token)
        if (size) {
          scanned += 1
          if (Number(size[1]) < 12) offenders.push(`${token} on ${node.tagName}`)
        }
      }
    }
    expect(offenders).toEqual([])
    // the guard is only worth having if the page actually carries sized text to check
    expect(scanned).toBeGreaterThan(20)
  })

  it('marks the read-only boundary gaps as deliberate so they are not read as missing wiring', () => {
    const { container } = full()
    expect(container.querySelector('[data-gap-key="authSurface"]')?.textContent).toContain('按只读边界故意不采')
    expect(container.querySelector('[data-gap-key="privateSessions"]')?.textContent).toContain('浏览器')
    expect(container.querySelector('[data-gap-key="fieldLevelOwnership"]')?.textContent).toContain('config-ownership.json')
    expect(container.querySelector('[data-gap-key="verbEvidenceAbsent"]')?.getAttribute('data-biting')).toBe('yes')
  })

  it('renders all declared qualification keys per row', () => {
    const { container } = full()
    for (const key of ['version', 'form', 'adapter', 'fieldBinding', 'update', 'drift', 'native']) {
      expect(container.querySelector(`[data-software-qualification="hermes"] [data-qualification-claim="${key}"]`)).toBeTruthy()
    }
    expect(container.querySelector('[data-testid="summary-claim-keys"]')?.textContent).toContain('version · form · adapter · fieldBinding · update · drift · native')
  })
})
