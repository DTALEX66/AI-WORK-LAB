// P1-03 behaviour tests for the Agent capability cards.
//
// The point of these cards is that a reader can tell declaration from observation. So the tests are
// written around the failure they exist to prevent: a card that reads as "installed/native" without
// evidence, and a missing source silently rendering as an empty shelf.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AdapterCapabilityCards } from '@/views/AdapterCapabilityCards'
import { AgentsView } from '@/views/Views'
import type { AdapterCapabilityCard, AdapterVerbEvidenceRow, SnapshotV3 } from '@/types'

function snapshotWith(cards?: AdapterCapabilityCard[]): SnapshotV3 {
  const s = {} as unknown as SnapshotV3
  s.schemaVersion = 'workflow/snapshot/v3'
  s.revision = 1
  s.generatedAt = '2026-10-08T00:00:00Z'
  s.sourceWatermark = null
  s.transport = { transportState: 'LIVE', freshnessState: 'FRESH', connectedSince: null, eventsUrl: null }
  s.coverage = { numerator: null, denominator: null, scope: null }
  s.governance = { state: 'CLEAN', families: {} } as SnapshotV3['governance']
  s.workspace = {}
  s.projects = []
  s.executions = []
  s.tasks = {}
  s.tokenSummary = { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' }
  s.git = { localSha: null, remoteSha: null, ciSha: null, matchState: 'NO_LOCAL_CLAIM' }
  s.ci = []
  s.sourceRefs = []
  if (cards !== undefined) s.adapterCapabilities = cards
  return s
}

function card(over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard {
  const layers = [
    { layer: 'REGISTERED', state: 'MET', evidenceLevel: 'SYNTHETIC',
      source: 'config/adapter-registry.json#entries[id=hermes]', reason: '登记来自仓库声明文件' },
    { layer: 'INSTALLED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
      reason: '软件安装身份投影里没有该客户端的行' },
    { layer: 'LOADED_CONNECTED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
      reason: 'adapter 的 invoke/observe 动词仍返回 NOT_IMPLEMENTED' },
    { layer: 'QUALIFIED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
      reason: '没有逐能力资格判定' },
    { layer: 'ENABLED_FOR_TASK', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
      reason: '派发未实现' },
    { layer: 'NATIVE_PROJECTION', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
      reason: '原生侧状态尚未进入 v3 快照合同' },
    { layer: 'OBSERVED_IN_EXECUTION', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
      reason: '需要真实执行链上的 receipt/readback' },
  ] as AdapterCapabilityCard['layers']
  return {
    clientId: 'hermes', displayName: 'Hermes', supportLevel: 'deep',
    declaredOperations: ['detect', 'capabilities', 'invoke'],
    matrixOperations: ['detect', 'capabilities', 'invoke'],
    operationsDrift: false,
    registryStatus: 'active', writePolicy: 'approval_required', risk: 'high',
    runtimeAdapter: 'HermesAdapter',
    configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE', preserve_unknown: true },
    clientNote: null,
    declaredVersion: '0.21.5+6948.gedd2476', versionReadbackMethod: 'install-stamp-readback',
    versionObservedAt: '2026-10-07', versionSource: 'install-stamp.json',
    detectionMode: 'isolated', detectionEvidenceState: 'UNVERIFIED',
    protocolConformance: { acp: 'STATIC_PASS', skills: 'STATIC_PASS', mcp: 'STATIC_UNVERIFIED' },
    observedAt: '2026-10-08T00:00:00Z',
    layers,
    nativeStatus: 'NOT_IMPLEMENTED',
    ...over,
  }
}

describe('AdapterCapabilityCards', () => {
  it('a missing field is a source gap, not "no clients"', () => {
    const { container } = render(<AdapterCapabilityCards snap={snapshotWith()} />)
    expect(screen.getByText(/来源缺口/)).toBeTruthy()
    expect(container.textContent).not.toMatch(/没有任何 adapter 条目/)
    expect(screen.getByText(/这里不画一张没有源的卡/)).toBeTruthy()
  })

  it('an empty list is the other statement', () => {
    render(<AdapterCapabilityCards snap={snapshotWith([])} />)
    expect(screen.getByText(/声明源里没有任何 adapter 条目/)).toBeTruthy()
    expect(screen.queryByText(/来源缺口/)).toBeNull()
  })

  it('shows exactly one layer as 成立 and names the gap of the other six', () => {
    const { container } = render(<AdapterCapabilityCards snap={snapshotWith([card()])} />)
    expect(container.textContent).toContain('阶梯 1/7 层成立')
    expect(screen.getAllByText('成立').length).toBe(1)
    expect(screen.getAllByText('未探测').length).toBe(6)
    expect(screen.getByText(/invoke\/observe 动词仍返回 NOT_IMPLEMENTED/)).toBeTruthy()
    expect(screen.getByText(/派发未实现/)).toBeTruthy()
  })

  it('never lets a card read as native: the native status is printed as NOT_IMPLEMENTED', () => {
    render(<AdapterCapabilityCards snap={snapshotWith([card()])} />)
    expect(screen.queryByText(/NATIVELY_VERIFIED/)).toBeNull()
    // NOT_IMPLEMENTED legitimately appears twice: the card's own native status and the layer reason
    expect(screen.getAllByText(/NOT_IMPLEMENTED/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText(/声明 ≠ 检测 ≠ 可用 ≠ 调用 ≠ 原生验证/)).toBeTruthy()
  })

  it('carries the detection evidence state without laundering it', () => {
    render(<AdapterCapabilityCards snap={snapshotWith([card()])} />)
    expect(screen.getByText(/isolated \/ UNVERIFIED/)).toBeTruthy()
  })

  it('shows both verb lists and names the drift instead of picking a winner', () => {
    const drifted = card({
      declaredOperations: ['detect', 'capabilities', 'invoke', 'observe'],
      matrixOperations: ['detect', 'capabilities'],
      operationsDrift: true,
    })
    render(<AdapterCapabilityCards snap={snapshotWith([drifted])} />)
    expect(screen.getByText(/不一致：registry 与 capability-matrix/)).toBeTruthy()
    expect(screen.getByText('detect · capabilities')).toBeTruthy()
    expect(screen.getByText('detect · capabilities · invoke · observe')).toBeTruthy()
  })

  it('keeps a legacy-observe client labelled as such', () => {
    render(<AdapterCapabilityCards snap={snapshotWith([card({
      clientId: 'cc-switch', displayName: 'CC Switch', registryStatus: 'legacy_observe',
      writePolicy: 'unavailable', supportLevel: 'deep',
    })])} />)
    expect(screen.getByText('legacy_observe')).toBeTruthy()
    expect(screen.getByText(/writes=unavailable/)).toBeTruthy()
  })

  it('renders no interactive control: the Agents lane stays a projection', () => {
    const { container } = render(<AdapterCapabilityCards snap={snapshotWith([card()])} />)
    expect(container.innerHTML).not.toContain('<button')
    expect(container.innerHTML).not.toContain('<input')
    expect(container.innerHTML).not.toContain('<textarea')
    expect(container.querySelectorAll('a')).toHaveLength(0)
  })

  it('AgentsView keeps its execution table while gaining the cards', () => {
    const s = snapshotWith([card()])
    s.executions = [{
      executionId: 'ex-1', anchorProjectId: 'work-lab', workingArea: '/repo',
      state: 'RUNNING', stateQuality: 'strong', agent: 'hermes', sessionId: 'sess-9', sourceRef: null,
    } as SnapshotV3['executions'][number]]
    render(<AgentsView snap={s} />)
    // 'hermes' legitimately appears twice — the card's clientId and the execution table's agent column
    expect(screen.getAllByText('hermes').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('sess-9')).toBeTruthy()
    expect(screen.getByText(/阶梯 1\/7 层成立/)).toBeTruthy()
  })
})

function verbRow(over: Partial<AdapterVerbEvidenceRow> = {}): AdapterVerbEvidenceRow {
  return {
    verb: 'detect', state: 'MET', evidenceLevel: 'INTEGRATED',
    source: 'read-only version readback: hermes.exe --version', reason: null, attempted: true,
    command: ['hermes.exe', '--version'], exitCode: 0,
    outputDigest: '95f01c44a4b1f5c0d1e2a3b4c5d6e7f80123456789abcdef0123456789abcdef',
    probedAt: '2026-10-08T03:00:00+0800',
    ...over,
  }
}

describe('AdapterCapabilityCards verb evidence dimension', () => {
  it('an absent verbEvidence key is the probe-record gap, never zero rows', () => {
    const { container } = render(<AdapterCapabilityCards snap={snapshotWith([card()])} />)
    expect(screen.getByText(/动词证据来源缺口/)).toBeTruthy()
    expect(screen.getByText(/未探测 ≠ 不支持任何动词/)).toBeTruthy()
    // the honest gap must not be dressed up as a measured count of verbs
    expect(container.textContent).not.toMatch(/已作答/)
  })

  it('an empty verbEvidence list is the same gap, not "declares nothing"', () => {
    // The producer never emits this shape (absent is a missing key), but a renderer that turned [] into a
    // zero-row summary would be the exact lie requirement 4 forbids, so the card must still show the gap.
    render(<AdapterCapabilityCards snap={snapshotWith([card({ verbEvidence: [] })])} />)
    expect(screen.getByText(/动词证据来源缺口/)).toBeTruthy()
    expect(screen.queryByText(/已作答/)).toBeNull()
  })

  it('shows the re-runnable proof of a MET verb and the refusal of a never-attempted one', () => {
    const rows: AdapterVerbEvidenceRow[] = [
      verbRow({ verb: 'detect' }),
      verbRow({
        verb: 'apply', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null, reason: '拒绝尝试：apply 会写入真实用户配置。',
        attempted: false, command: undefined, exitCode: undefined, outputDigest: undefined,
      }),
    ]
    const { container } = render(
      <AdapterCapabilityCards snap={snapshotWith([card({ verbEvidence: rows, verbEvidenceCounts: { MET: 1, NOT_PROBED: 1, NOT_SUPPORTED: 0 } })])} />)
    // MET names the call, the exit code and a digest — that is what makes it re-runnable evidence
    expect(container.textContent).toContain('$ hermes.exe --version')
    expect(container.textContent).toContain('exit=0')
    expect(container.textContent).toContain('digest=95f01c44a4b1')
    expect(screen.getByText('已作答')).toBeTruthy()
    // a refused write verb says so and never wears the MET label
    expect(screen.getByText('未尝试')).toBeTruthy()
    expect(container.textContent).toContain('拒绝尝试：apply')
  })

  it('attempted-and-uncredited is a different statement from never-attempted', () => {
    const rows: AdapterVerbEvidenceRow[] = [
      verbRow({ verb: 'observe', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '已调用 adapter.observe() 但 events=[] 且 observed_at=null，自报完成不予采信。', attempted: true }),
      verbRow({ verb: 'apply', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '拒绝尝试：apply 会写入真实用户配置。', attempted: false }),
    ]
    render(<AdapterCapabilityCards snap={snapshotWith([card({ verbEvidence: rows })])} />)
    expect(screen.getByText('已尝试·未采信')).toBeTruthy()
    expect(screen.getByText('未尝试')).toBeTruthy()
    // neither of them is credited as an answer
    expect(screen.queryByText('已作答')).toBeNull()
  })

  it('a NOT_SUPPORTED verb is shown as a declaration, not a measurement', () => {
    const rows: AdapterVerbEvidenceRow[] = [
      verbRow({ verb: 'rollback', state: 'NOT_SUPPORTED', evidenceLevel: 'SYNTHETIC',
        source: 'config/adapter-registry.json#entries[hermes].operations 不含 rollback', reason: '声明缺失',
        attempted: false, command: undefined, exitCode: undefined, outputDigest: undefined }),
    ]
    const { container } = render(<AdapterCapabilityCards snap={snapshotWith([card({ verbEvidence: rows })])} />)
    expect(screen.getByText('声明不支持')).toBeTruthy()
    // SYNTHETIC also marks the ladder's REGISTERED row, so assert containment, not a unique hit
    expect(container.textContent).toContain('SYNTHETIC')
    expect(container.textContent).toContain('config/adapter-registry.json')
  })

  it('the verb dimension never moves the ladder or the native status', () => {
    const rows: AdapterVerbEvidenceRow[] = ['detect', 'capabilities', 'plan', 'apply', 'invoke', 'observe', 'rollback']
      .map((verb) => verbRow({ verb }))
    const { container } = render(
      <AdapterCapabilityCards snap={snapshotWith([card({ verbEvidence: rows })])} />)
    // the ladder still reports 1/7 — seven answered verbs do not climb a single rung
    expect(screen.getByText(/阶梯 1\/7 层成立/)).toBeTruthy()
    expect(container.textContent).not.toMatch(/NATIVELY_VERIFIED/)
  })

  it('the verb rows add no interactive control: the Agents lane stays a projection', () => {
    const rows: AdapterVerbEvidenceRow[] = [verbRow(), verbRow({ verb: 'apply', state: 'NOT_PROBED',
      evidenceLevel: 'NO_EVIDENCE', source: null, reason: '拒绝尝试', attempted: false })]
    const { container } = render(
      <AdapterCapabilityCards snap={snapshotWith([card({ verbEvidence: rows })])} />)
    expect(container.innerHTML).not.toContain('<button')
    expect(container.innerHTML).not.toContain('<input')
    expect(container.innerHTML).not.toContain('<textarea')
    expect(container.querySelectorAll('a')).toHaveLength(0)
  })
})
