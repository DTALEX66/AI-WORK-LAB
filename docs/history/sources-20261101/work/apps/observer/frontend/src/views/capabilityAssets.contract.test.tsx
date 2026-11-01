// WUI-07 render-contract tests — the lies this page exists to prevent.
//
// Each test names a producer truth and pins how it must read: absent ≠ empty ≠ rows; a verb answer
// never climbs the ladder; the nativeStatus constant never passes; ABSENT is not conformance; the five
// provenance classes are the question, never an assigned label; and no control pretends to act.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CapabilityAssetsView } from '@/views/CapabilityAssetsView'
import { CAPABILITY_SOURCE_GAPS, PROVENANCE_CLASSES } from '@/lib/capabilityAssets'
import { mkSnap } from '@/test/snapshotFixture'
import type { AdapterCapabilityCard, AdapterVerbEvidenceRow } from '@/types'

/** A fresh card exactly as adapter_capability_projection.py emits one today. */
function freshCard(over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard {
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
    protocolConformance: { acp: 'STATIC_PASS', mcp: 'ABSENT' },
    observedAt: '2026-10-09T00:00:00Z',
    layers: [
      { layer: 'REGISTERED', state: 'MET', evidenceLevel: 'SYNTHETIC',
        source: 'config/adapter-registry.json#entries[id=hermes]',
        reason: '登记来自仓库声明文件，是声明不是探测' },
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
    ],
    nativeStatus: 'NOT_IMPLEMENTED',
    ...over,
  } as AdapterCapabilityCard
}

function verbRow(over: Partial<AdapterVerbEvidenceRow> = {}): AdapterVerbEvidenceRow {
  return {
    verb: 'detect', state: 'MET', evidenceLevel: 'INTEGRATED',
    source: 'read-only version readback: hermes.exe --version', reason: null, attempted: true,
    command: ['hermes.exe', '--version'], exitCode: 0, ...over,
  }
}

describe('CapabilityAssetsView · inventory source shapes', () => {
  it('absent adapterCapabilities renders the named gap and never a zero count', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap()} />)
    expect(screen.getByTestId('assets-absent-gap').textContent).toContain('没有 adapterCapabilities 字段')
    expect(screen.getByTestId('assets-absent-gap').textContent).toContain('config/adapter-registry.json')
    expect(container.textContent).not.toMatch(/0\s*[项件张个]\s*资产/)
    expect(container.textContent).not.toMatch(/共\s*0/)
    expect(container.querySelectorAll('[data-asset-row]')).toHaveLength(0)
    // and it is not merged with the empty-list sentence
    expect(screen.queryByTestId('assets-empty-shape')).toBeNull()
  })

  it('the empty list is the OTHER statement — both shapes render differently', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [] })} />)
    const empty = screen.getByTestId('assets-empty-shape').textContent!
    expect(empty).toContain('空列表')
    expect(empty).toContain('已读取声明源')
    expect(empty).not.toContain('没有 adapterCapabilities 字段')
    expect(screen.queryByTestId('assets-absent-gap')).toBeNull()
    expect(container.querySelectorAll('[data-asset-row]')).toHaveLength(0)
  })

  it('a null snapshot is 快照未到达 — no count, no inventory, no fake zero', () => {
    const { container } = render(<CapabilityAssetsView snap={null} />)
    expect(screen.getByText('快照未到达')).toBeTruthy()
    expect(container.textContent).not.toMatch(/0\s*[项件张个]\s*资产/)
    expect(container.querySelectorAll('[data-asset-row]')).toHaveLength(0)
  })

  it('cards build the inventory: one row per clientId under the explicit 类别未知 group', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard(), freshCard({ clientId: 'codex', displayName: 'Codex' })],
    })} />)
    const rows = container.querySelectorAll('[data-asset-row]')
    expect(rows).toHaveLength(2)
    expect(rows[0].getAttribute('data-asset-row')).toBe('hermes')
    expect(rows[1].getAttribute('data-asset-row')).toBe('codex')
    expect(screen.getByText('资产来源类别未投影 · 全部条目停在「类别未知」')).toBeTruthy()
  })
})

describe('CapabilityAssetsView · the ladder keeps its ceiling', () => {
  it('a fresh card shows MET for nothing above REGISTERED/INSTALLED', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    const ladderRows = container.querySelectorAll('[data-ladder] [data-layer]')
    expect(ladderRows).toHaveLength(7)
    const met = container.querySelectorAll('[data-ladder] [data-layer][data-state="MET"]')
    expect(met).toHaveLength(1)
    expect(met[0].getAttribute('data-layer')).toBe('REGISTERED')
    for (const layer of ['LOADED_CONNECTED', 'QUALIFIED', 'ENABLED_FOR_TASK', 'NATIVE_PROJECTION', 'OBSERVED_IN_EXECUTION']) {
      expect(container.querySelector(`[data-layer="${layer}"][data-state="MET"]`)).toBeNull()
    }
    // the REGISTERED MET is stated as declared, with its SYNTHETIC evidence level
    expect(met[0].textContent).toContain('SYNTHETIC')
    expect(met[0].textContent).toContain('登记来自仓库声明文件')
  })

  it('seven answered verbs climb zero rungs — the verb dimension stays orthogonal', () => {
    const rows = ['detect', 'capabilities', 'plan', 'apply', 'invoke', 'observe', 'rollback']
      .map((verb) => verbRow({ verb }))
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard({ verbEvidence: rows, verbEvidenceCounts: { MET: 7, NOT_PROBED: 0, NOT_SUPPORTED: 0 } })],
    })} />)
    expect(container.querySelectorAll('[data-ladder] [data-layer][data-state="MET"]')).toHaveLength(1)
    expect(container.textContent).toContain('动词行永不晋级任何层')
    // but the answers themselves are shown, with their re-runnable proof
    expect(container.textContent).toContain('$ hermes.exe --version')
  })

  it('the four claims stay four separate blocks', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    for (const claim of ['DISCOVERED', 'INSTALLED', 'LOADED', 'INVOKED']) {
      expect(container.querySelector(`[data-claim="${claim}"]`)).toBeTruthy()
    }
    expect(container.textContent).toContain('四类宣称分开成立')
  })

  it('a MET above the producer ceiling is projected verbatim and flagged, not hidden or spread', () => {
    const card = freshCard({
      layers: freshCard().layers.map((l) =>
        l.layer === 'QUALIFIED' ? { ...l, state: 'MET', evidenceLevel: 'REAL', source: 'out-of-contract', reason: '' } : l),
    })
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [card] })} />)
    expect(screen.getByText(/合同外形态/)).toBeTruthy()
    // the anomaly does NOT drag the other unprobed layers into MET
    expect(container.querySelector('[data-layer="LOADED_CONNECTED"][data-state="MET"]')).toBeNull()
  })
})

describe('CapabilityAssetsView · constants are not verdicts', () => {
  it('nativeStatus NOT_IMPLEMENTED never reads as a pass', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    const line = container.querySelector('[data-native-status]')!
    expect(line.getAttribute('data-native-status')).toBe('NOT_IMPLEMENTED')
    expect(line.textContent).toContain('恒值')
    expect(line.textContent).not.toContain('成立')
    expect(container.textContent).not.toContain('NATIVELY_VERIFIED')
  })

  it('protocolConformance ABSENT is stated as unlisted, never as conformance', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    const mcp = container.querySelector('[data-protocol="mcp"]')!
    expect(mcp.getAttribute('data-status')).toBe('ABSENT')
    expect(mcp.textContent).toContain('未列入符合性声明 ≠ 符合')
    expect(mcp.textContent).not.toMatch(/mcp\s*=/)
    const acp = container.querySelector('[data-protocol="acp"]')!
    expect(acp.textContent).toBe('acp=STATIC_PASS')
  })
})

describe('CapabilityAssetsView · verb dimension shapes render as different sentences', () => {
  it('absent key says 没看', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    const block = container.querySelector('[data-verb-shape]')!
    expect(block.getAttribute('data-verb-shape')).toBe('ABSENT_KEY')
    expect(block.textContent).toContain('没有 verbEvidence 键')
    expect(block.textContent).toContain('没看')
    expect(block.textContent).not.toContain('声明的动词行为零')
  })

  it('an empty list says 看了 · 声明为零 — different text, different shape marker', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard({ verbEvidence: [] })],
    })} />)
    const block = container.querySelector('[data-verb-shape]')!
    expect(block.getAttribute('data-verb-shape')).toBe('EMPTY_LIST')
    expect(block.textContent).toContain('为空列表')
    expect(block.textContent).toContain('声明的动词行为零')
    expect(block.textContent).not.toContain('没有 verbEvidence 键')
  })

  it('rows carry per-verb states, keeping attempted/uncredited apart from never-attempted', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard({ verbEvidence: [
        verbRow(),
        verbRow({ verb: 'apply', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
          reason: '拒绝尝试：apply 会写入真实用户配置。', attempted: false, command: undefined, exitCode: undefined }),
      ] })],
    })} />)
    expect(screen.getByText('已作答')).toBeTruthy()
    expect(screen.getByText('未尝试')).toBeTruthy()
    expect(container.textContent).toContain('拒绝尝试：apply')
  })
})

describe('CapabilityAssetsView · no-field questions are gaps, not tabs', () => {
  it('all seven gaps render named, each with its reason', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    for (const gap of CAPABILITY_SOURCE_GAPS) {
      const el = container.querySelector(`[data-capability-gap="${gap.key}"]`)
      expect(el, gap.key).toBeTruthy()
      expect(el!.textContent).toContain(gap.question)
      expect(el!.textContent).toContain('来源缺口')
    }
  })

  it('the five provenance classes are never invented onto an asset row', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard(), freshCard({ clientId: 'codex', displayName: 'Codex', registryStatus: 'quarantined' })],
    })} />)
    const rows = container.querySelectorAll('[data-asset-row]')
    expect(rows.length).toBeGreaterThan(0)
    for (const row of rows) {
      for (const cls of PROVENANCE_CLASSES) {
        expect(row.textContent).not.toContain(cls)
      }
    }
    // the classes exist ONLY as the unanswered question inside the named gap
    const gap = container.querySelector('[data-capability-gap="provenanceClass"]')!
    for (const cls of PROVENANCE_CLASSES) expect(gap.textContent).toContain(cls)
  })

  it('configOwnershipDefault names capability-matrix.json as its source, not config-ownership.json', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    const row = container.querySelector('[data-ownership-source]')!
    expect(row.getAttribute('data-ownership-source')).toBe('config/capability-matrix.json')
    expect(row.textContent).toContain('config/capability-matrix.json')
    expect(row.textContent).toContain('不是 config/config-ownership.json 的读取')
    expect(row.textContent).toContain('USER_OVERLAY / MANAGE')
  })

  it('migration status is stated as a gap — the page does not pretend a WUI-08 answer', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    expect(container.querySelector('[data-capability-gap="migrationStatus"]')!.textContent).toContain('WUI-08')
    expect(screen.getByText(/迁移评价（源→目标、差异损失、隔离试用、验证）属于 WUI-08/)).toBeTruthy()
  })
})

describe('CapabilityAssetsView · address and source context', () => {
  it('focus ids are echoed as context and never select or filter a card', () => {
    const { container } = render(<CapabilityAssetsView
      snap={mkSnap({ adapterCapabilities: [freshCard()] })}
      focus={{ taskId: 'WL-900', executionId: null, projectId: null }}
      focusRejected={[]} />)
    const note = container.querySelector('[data-focus-note]')!
    expect(note.textContent).toContain('taskId=WL-900')
    expect(note.textContent).toContain('不按记录 id 筛选')
    expect(container.querySelectorAll('[data-asset-row]')).toHaveLength(1)
  })

  it('rejected ids are reported', () => {
    render(<CapabilityAssetsView snap={mkSnap()} focusRejected={['taskId · 定位标识包含非法字符，已拒绝']} />)
    expect(screen.getByText('地址被拒绝')).toBeTruthy()
    expect(screen.getByText(/定位标识包含非法字符/)).toBeTruthy()
  })

  it('workspace.sources rows show what the ledger genuinely carries — and do not claim capability files unless shown', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard()],
      workspace: { sources: [
        { path: 'taskpacks/current/error-ledger.json', evidenceKind: 'HISTORY', loadedAt: '2026-10-09T00:00:00Z' },
      ] },
    })} />)
    expect(container.querySelector('[data-workspace-sources-shape="ROWS"]')!.textContent)
      .toContain('taskpacks/current/error-ledger.json')
    expect(container.textContent).toContain('当前加载台账未列出其中任何一个')
  })

  it('an absent ledger is its own named statement', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap()} />)
    const block = container.querySelector('[data-workspace-sources-shape="ABSENT"]')!
    expect(block.textContent).toContain('workspace.sources 键不存在')
    expect(block.textContent).toContain('不等于「什么都没加载」')
  })

  it('entryProbe absent / null / fact are three renderings', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [
        freshCard(),
        freshCard({ clientId: 'codex', entryProbe: null }),
        freshCard({ clientId: 'dsh', entryProbe: {
          status: 'ENTRY_ANSWERED', entryPoint: 'DeepSeek Harness.exe', argv: ['--version'],
          exitCode: 0, probedAt: '2026-10-08T03:00:00Z', detail: null,
        } }),
      ],
    })} />)
    expect(container.querySelector('[data-entry-probe-shape="ABSENT_KEY"]')!.textContent).toContain('未携带 entryProbe 键')
    expect(container.querySelector('[data-entry-probe-shape="NULL"]')!.textContent).toContain('不存在任何探针记录')
    const fact = container.querySelector('[data-entry-probe-shape="FACT"]')!
    expect(fact.textContent).toContain('ENTRY_ANSWERED')
    expect(fact.textContent).toContain('不等于活跃会话')
  })

  it('version drift keeps both strings visible without naming a winner', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard({ versionDrift: true })],
    })} />)
    expect(container.querySelector('[data-version-drift="true"]')).toBeTruthy()
    expect(container.textContent).toContain('0.21.5+6948.gedd2476')
    expect(container.textContent).toContain('registry 不是真值')
  })
})

describe('CapabilityAssetsView · read-only boundary', () => {
  it('no control pretends to act: no form controls, no disabled buttons, only in-page anchors', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({
      adapterCapabilities: [freshCard({ verbEvidence: [verbRow()] })],
    })} />)
    expect(container.querySelectorAll('button, input, select, textarea, form')).toHaveLength(0)
    expect(container.querySelectorAll('[disabled]')).toHaveLength(0)
    for (const a of Array.from(container.querySelectorAll('a'))) {
      expect(a.getAttribute('href')!.startsWith('#asset-')).toBe(true)
    }
    // the boundary lives in words, with the owner of the write named
    expect(screen.getByText(/Observer 是严格只读投影/)).toBeTruthy()
    expect(screen.getByText(/单独的 Task Grant/)).toBeTruthy()
  })

  it('meaningful text never drops below 12px', () => {
    const { container } = render(<CapabilityAssetsView snap={mkSnap({ adapterCapabilities: [freshCard()] })} />)
    expect(container.innerHTML).not.toMatch(/text-\[1?[01](\.\d+)?px\]/)
    expect(container.innerHTML).not.toMatch(/\bfont-size:\s*(9|10|11)(\.\d+)?px/)
  })
})
