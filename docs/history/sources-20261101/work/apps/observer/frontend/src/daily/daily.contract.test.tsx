// 2026-10-24 TRAE 交接包 · 日常壳与 HUD 四态的契约测试。
// 钉住提示词 §13 的真实回归问题：四主入口＋设置底置、UNKNOWN 不补 0、
// 不同方法/工具对应各自记录、预览＝复制＝导出同一材料、反馈是内存态并明说刷新丢失。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act, fireEvent, within } from '@testing-library/react'

const mockSnap = {
  schemaVersion: 'workflow/snapshot/v3',
  revision: 7,
  generatedAt: '2026-10-24T00:00:00Z',
  sourceWatermark: '2026-10-24T00:00:00Z',
  transport: { transportState: 'LIVE', freshnessState: 'FRESH', connectedSince: null, eventsUrl: null },
  coverage: { numerator: 1, denominator: 1, scope: 'unit' },
  governance: {
    state: 'CLEAN',
    families: {
      rules: { state: 'CLEAN', current: null, drift: 0 },
      skills: { state: 'CLEAN', current: null, drift: 0 },
      memory: { state: 'CLEAN', current: null, drift: 0 },
      adapters: { state: 'CLEAN', current: null, drift: 0 },
    },
  },
  workspace: {},
  projects: [
    {
      projectId: 'proj-a', displayName: '示例项目甲', agentPlatform: 'qoder', identityState: 'MATCHED',
      activityState: 'ACTIVE', attentionState: 'NONE', activeExecutionCount: 1, workingAreas: [],
      visibility: 'private', quality: 'REAL', lastStrongEvidenceAt: '2026-10-24T00:00:00Z',
      repositories: [], git: { localSha: null, remoteSha: null, matchState: 'NO_LOCAL_CLAIM', branch: null, dirtyCount: null, observedAt: null, quality: null, freshness: null, sourceRef: null, sourceProjectId: null },
      token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
      ci: [], executionIds: ['e1'], sourceRefs: [],
    },
    {
      projectId: 'proj-b', displayName: '示例项目乙', agentPlatform: 'codex', identityState: 'MATCHED',
      activityState: 'REGISTERED', attentionState: 'NONE', activeExecutionCount: 0, workingAreas: [],
      visibility: 'private', quality: 'REAL', lastStrongEvidenceAt: null,
      repositories: [], git: { localSha: null, remoteSha: null, matchState: 'NO_LOCAL_CLAIM', branch: null, dirtyCount: null, observedAt: null, quality: null, freshness: null, sourceRef: null, sourceProjectId: null },
      token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
      ci: [], executionIds: [], sourceRefs: [],
    },
  ],
  executions: [
    { executionId: 'e1', anchorProjectId: 'proj-a', workingArea: null, state: 'WAITING_USER', stateQuality: 'REAL', agent: 'qoder', sessionId: null, sourceRef: null },
  ],
  tasks: {},
  tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
  git: { localSha: null, remoteSha: null, ciSha: null, matchState: 'NO_LOCAL_CLAIM' },
  ci: [],
  sourceRefs: [],
  issues: [
    {
      schemaVersion: 'workflow/issue/v1', fingerprint: 'fp-aaa', class: 'SOURCE_FAILURE', projectId: 'proj-a',
      subject: '示例问题：采集器连续失败', origin: 'collector', evidenceRef: 'telemetry_events', priority: 'P1',
      priorityRule: 'P1: source failure', firstSeenAt: '2026-10-23T00:00:00Z', lastSeenAt: '2026-10-24T00:00:00Z',
      occurrences: 3, status: 'OPEN', softwareId: null, softwareVersion: null, softwareVersionSource: 'source-names-no-software',
    },
  ],
  issuesSummary: {
    schemaVersion: 'worklab/issues-summary/v1', sourcesRead: 2, sourcesAbsent: 0, rowsScanned: 10,
    distinctIssueCount: 1, emittedCount: 1, omittedCount: 0, foldedOccurrences: 3, cap: 200, truncated: false,
    complete: true, softwareAttribution: { attributed: 0, unmatched: 0, ambiguous: 0, unattributable: 1, versionKnown: 0, identitySourceAbsent: false },
  },
  adapterCapabilities: [
    {
      clientId: 'qoder', displayName: 'Qoder', supportLevel: 'MANAGE', declaredOperations: ['read'], matrixOperations: ['read'],
      operationsDrift: false, registryStatus: 'ACTIVE', writePolicy: 'READ_ONLY', risk: 'LOW', runtimeAdapter: null,
      configOwnershipDefault: null, declaredVersion: '1.2.0', versionReadbackMethod: null, versionObservedAt: null,
      versionSource: null, detectionMode: null, detectionEvidenceState: 'REAL', protocolConformance: {},
      observedAt: '2026-10-24T00:00:00Z', layers: [], nativeStatus: 'NOT_PROBED',
      // Declared, not guessed: the HUD strip monitors agent runtimes by this field, so a fixture that left it
      // out would be a source-gap snapshot, and the HUD tests would then be asserting geometry on an empty panel.
      role: 'agent_runtime',
      entryProbe: { status: 'PASS', entryPoint: 'qoder', argv: [], exitCode: 0, probedAt: '2026-10-24T00:00:00Z' },
    },
    {
      clientId: 'codex', displayName: 'Codex', supportLevel: 'MANAGE', declaredOperations: [], matrixOperations: [],
      operationsDrift: false, registryStatus: 'ACTIVE', writePolicy: 'READ_ONLY', risk: 'LOW', runtimeAdapter: null,
      configOwnershipDefault: null, declaredVersion: null, versionReadbackMethod: null, versionObservedAt: null,
      versionSource: null, detectionMode: null, detectionEvidenceState: 'NO_EVIDENCE', protocolConformance: {},
      observedAt: null, layers: [], nativeStatus: 'NOT_PROBED', entryProbe: null,
      role: 'agent_runtime',
    },
  ],
} as never

const liveSnapshot: { current: unknown } = { current: mockSnap }

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => ({ snap: liveSnapshot.current as never, source: 'live', live: true, error: null, dataUpdatedAt: 0 }) }
})

vi.mock('@/lib/repairPack', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/repairPack')>()
  return {
    ...actual,
    makeHttpRepairPackReader: () => async () => ({
      kind: 'RESULT',
      httpStatus: 200,
      endpoint: 'test',
      view: {
        schemaVersion: 'worklab/repair-packs-view/v1', status: 'OK', reason: '测试', generatedAt: '2026-10-24T00:00:00Z',
        issuesSummary: null,
        packs: [{
          schemaVersion: 'worklab/repair-pack/v1', packId: 'pack-1', generatedAt: '2026-10-24T00:00:00Z',
          status: 'DRAFT', readiness: { state: 'READY', reasons: [] },
          target: { kind: 'project', projectId: 'proj-a', projectName: '示例项目甲', projectRoot: '/tmp', adapter: null, declaredOperations: [], operation: 'fix', routingSource: 'test' },
          binds: { issueFingerprints: ['fp-aaa'], evidenceRefs: [], classes: [], priorities: [], issueCount: 1, softwareIds: [], unattributedCount: 0 },
          verification: { known: false, command: '', basis: '' },
          handoff: { mode: 'manual_copy', copyable: true, sent: false, dispatched: false, requiresOwnerAction: '' },
          handoffText: '后端渲染的交接文本（PACK-1）',
        }],
        summary: { openIssueCount: 1, packCount: 1 },
      },
    }),
  }
})

const solutionA = {
  solutionId: 'sol-a', revision: 3, title: '方法甲：检查更新后的构建产物', status: 'VALIDATED', recommended: true,
  software: { softwareId: 'work-lab' }, versionHint: { state: 'SAME', message: '记录版本一致' },
  limits: ['仅适用于本机构建链'], steps: ['步骤甲一', '步骤甲二'], verificationSteps: ['验证甲'],
  preconditions: ['前提甲'], risks: [], invalidWhen: ['构建脚本变更后失效'],
  issueRefs: [], evidenceRefs: [], source: {}, score: 5, matchedTerms: [], issueMatch: false,
}
const solutionB = {
  solutionId: 'sol-b', revision: 1, title: '方法乙：回退到上一个可用版本', status: 'CANDIDATE', recommended: false,
  software: { softwareId: 'design-lab-project' }, versionHint: { state: 'UNKNOWN', message: '无版本记录' },
  limits: [], steps: ['步骤乙一'], verificationSteps: [], preconditions: [], risks: ['会丢弃本地改动'],
  invalidWhen: [], issueRefs: ['fp-aaa'], evidenceRefs: [], source: {}, score: 0, matchedTerms: [], issueMatch: true,
}

vi.mock('@/daily/solutionsClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/daily/solutionsClient')>()
  return {
    ...actual,
    fetchSolutions: async () => ({
      kind: 'RESULT',
      view: {
        schemaVersion: 'worklab/solution-search/v1', status: 'OK', reason: '测试', query: '',
        results: [solutionA, solutionB],
        summary: { mode: 'BROWSE' },
      },
    }),
  }
})

import App from '@/App'
import { HudDaily } from '@/daily/HudDaily'
import { buildHandoverMaterial, dailyToolRows } from '@/daily/dailyData'
import { DAILY_NAV } from '@/daily/DailyChrome'
import { DAILY_CARRIED_VIEWS } from '@/daily/DailyApp'

beforeEach(() => {
  window.history.replaceState(null, '', '/index.html?shell=daily')
})
afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', window.location.pathname)
})

describe('日常壳（?shell=daily）', () => {
  it('一级导航就是 DAILY_NAV 那张表，设置仍然底置（导航末位）', () => {
    render(<App />)
    const nav = screen.getByRole('navigation', { name: '主导航' })
    const buttons = Array.from(nav.querySelectorAll('button')).map((b) => b.textContent)
    // The expectation is read from the declaration the rail renders from, so the claim left standing is
    // "the rail is the table, and 设置 is last" rather than a hand-copied list that can drift.
    expect(buttons).toEqual([...DAILY_NAV.map((n) => n.label), '设置'])
    // The sign-off pack's promised delta is +1 nav entry over the three it started from.
    expect(DAILY_NAV.length).toBe(4)
  })

  it('治理与诊断把五张承接卡接进日常壳，且每一项都有可复用的组件', () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=governance')
    render(<App />)
    const section = document.querySelector('[data-landmark="daily-governance"]') as HTMLElement
    expect(section).not.toBeNull()
    // The order is the sign-off pack's card order, so a reordering is a decision, not a slip.
    expect(Array.from(section.querySelectorAll('[data-carried]')).map((n) => n.getAttribute('data-carried')))
      .toEqual(['trust', 'monitoring', 'collectors', 'privacy', 'audit'])
    // A declared id with no component would print the refusal instead of a view; that is a gap, not a
    // rendering, and it must not pass as one.
    expect(section.textContent).not.toContain('这一项还没有可复用的视图组件')
  })

  it('第 4 卡在日常壳不长出会点的外观控件（降级为徽章是签字包定的）', () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=governance')
    render(<App />)
    const card = document.querySelector('[data-carried="privacy"]') as HTMLElement
    expect(card).not.toBeNull()
    // The professional view renders these only when the shell passes onTheme/onLayout/onPalette. The daily
    // shell passes none, so a control appearing here would be a button that looks live and does nothing.
    expect(card.querySelectorAll('[data-setting]').length).toBe(0)
    expect(card.textContent).toContain('深色')
  })

  it('无快照时治理屏不补 0：三个槽位回落 UNKNOWN，而它们在有快照时确实会被回答', () => {
    // The five mounted views each carry the no-fabrication rule in the professional shell. What is proven
    // here is that the daily mount does not paper over it: `snap` reaches them as null and no wrapper
    // invents a zero or a rate. The data render is the positive control -- without it, a string the panel
    // always prints would pass the null assertion and guard nothing.
    const painted = () =>
      (screen.getByRole('heading', { name: '治理与诊断' }).closest('section') as HTMLElement).textContent ?? ''
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=governance')

    render(<App />)
    const withData = painted()
    cleanup()

    liveSnapshot.current = null
    let noData = ''
    try {
      render(<App />)
      noData = painted()
    } finally {
      liveSnapshot.current = mockSnap
    }
    for (const slot of ['传输状态', '新鲜度', '覆盖度']) {
      expect(withData).not.toContain(`${slot}UNKNOWN`)
      expect(noData).toContain(`${slot}UNKNOWN`)
    }
    expect(noData).not.toMatch(/全部干净|\d+%/)
  })

  it('被日常壳承接的视图不再出现在设置页的专业链接里（一件事一个入口）', () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=settings')
    render(<App />)
    const links = Array.from(document.querySelectorAll('a[href^="/index.html?view="]'))
      .map((a) => a.getAttribute('href'))
    for (const id of DAILY_CARRIED_VIEWS.map((v) => v.id)) {
      expect(links.filter((h) => h === `/index.html?view=${id}`)).toEqual([])
    }
    // Non-vacuity: the list still carries the views the daily shell does not surface.
    expect(links.length).toBeGreaterThanOrEqual(7)
    expect(links).toContain('/index.html?view=work')
  })

  it('无数据不补 0：概览页显示待确认/UNKNOWN 而不是编造的百分比', () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-b')
    render(<App />)
    expect(screen.getByText(/确认时间：UNKNOWN/)).toBeTruthy()
    expect(screen.queryByText(/%/)).toBeNull()
  })

  it('等待用户决定的状态由真实执行行推出（proj-a 有 WAITING_USER）', () => {
    render(<App />)
    expect(screen.getByText('需要关注')).toBeTruthy()
    expect(screen.getByText('状态待确认')).toBeTruthy()
  })

  it('不同方法打开各自记录：抽屉内容随 methodId 变化', async () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a')
    render(<App />)
    const openA = (await screen.findAllByText('查看该方法详情 →'))[0]
    await act(async () => { openA.click() })
    expect((await screen.findAllByText(/方法甲：检查更新后的构建产物/)).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/步骤甲一/).length).toBeGreaterThan(0)
    // 切到方法乙：整张抽屉内容替换，不再有甲的步骤
    await act(async () => { screen.getByLabelText('关闭抽屉').click() })
    const homeBtn = screen.getByRole('button', { name: '项目' })
    await act(async () => { homeBtn.click() })
    // 通过搜索直接打开 sol-b：方法抽屉由 URL 驱动，这里直接改地址后重挂
    cleanup()
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a&dm=sol-b')
    render(<App />)
    expect((await screen.findAllByText(/方法乙：回退到上一个可用版本/)).length).toBeGreaterThan(0)
    expect(screen.queryByText(/步骤甲一/)).toBeNull()
    expect(screen.getByText(/会丢弃本地改动/)).toBeTruthy()
  })

  it('步骤手风琴：带风险提示的项冷启动即展开，没有提示的步骤不长出假的展开控件', async () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a&dm=sol-a')
    render(<App />)
    expect((await screen.findAllByText(/方法甲：检查更新后的构建产物/)).length).toBeGreaterThan(0)
    expect(document.querySelectorAll('ol > li > button[aria-expanded]')).toHaveLength(0)
    cleanup()

    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a&dm=sol-b')
    render(<App />)
    const toggle = await screen.findByRole('button', { name: /步骤乙一/ })
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText(/会丢弃本地改动/)).toBeTruthy()
    await act(async () => { toggle.click() })
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(screen.queryByText(/会丢弃本地改动/)).toBeNull()
  })

  it('预览、复制与导出来自同一材料；复制失败给出可选择文本而不是假成功', async () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a&dm=sol-a')
    render(<App />)
    const preview = await screen.findByLabelText('交接材料预览') as HTMLTextAreaElement
    expect(preview.value).toContain('方法甲：检查更新后的构建产物')
    expect(preview.value).toContain('适用限制')
    // jsdom 没有可用的剪贴板/ execCommand：必须报告失败而不是 Toast 假成功
    const copyBtn = screen.getByRole('button', { name: '复制给外部工具' })
    await act(async () => { copyBtn.click() })
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.getByRole('alert').textContent).toContain('可手动选择复制')
  })

  // E2 adds a display-filter chip row above the list, and the chips carry the same tool names as the
  // rows. A global getAllByText(name)[0] therefore lands on a chip (which toggles ?tools=) instead of
  // the row (which selects the tool), so both claims below are read out of the list itself.
  const toolList = () => screen.getByRole('list', { name: '工具列表' })

  it('我的工具：切换工具整个详情同步替换', async () => {
    render(<App />)
    await act(async () => { screen.getByRole('button', { name: '我的工具' }).click() })
    expect((await screen.findAllByText('Qoder')).length).toBeGreaterThan(0)
    expect(screen.getByText('声明操作：read（READ_ONLY）')).toBeTruthy()
    await act(async () => { fireEvent.click(within(toolList()).getAllByText('Codex')[0]) })
    expect(screen.getByText('无已声明操作记录')).toBeTruthy()
    expect(screen.getByText('未连接（无入口探测记录）')).toBeTruthy()
    expect(screen.queryByText('声明操作：read（READ_ONLY）')).toBeNull()
  })

  it('工具列表按声明的角色分组：路由与未声明条目不混进 agent 运行时', async () => {
    const cards = (mockSnap as unknown as { adapterCapabilities: Record<string, unknown>[] }).adapterCapabilities
    const routerLike = { ...cards[0], clientId: 'cc-switch', displayName: 'CC Switch',
      declaredOperations: ['detect', 'capabilities', 'observe'], writePolicy: 'unavailable',
      registryStatus: 'legacy_observe', role: 'provider_router' }
    const agentLike = { ...cards[0], clientId: 'hermes', displayName: 'Hermes',
      declaredOperations: ['apply', 'invoke', 'observe'], writePolicy: 'approval_required',
      registryStatus: 'active', role: 'agent_runtime' }
    // The undeclared group needs its own member now that the two fixture cards declare a role: the claim
    // being tested is that a row with no declaration is not pulled into either named group.
    const undeclaredLike = { ...cards[0], clientId: 'mystery', displayName: 'Mystery Tool',
      registryStatus: 'active', writePolicy: 'approval_required', role: undefined }
    cards.push(routerLike, agentLike, undeclaredLike)
    try {
      render(<App />)
      await act(async () => { screen.getByRole('button', { name: '我的工具' }).click() })
      const labels = (await screen.findAllByText(/agent 运行时|供应商路由|角色未声明/))
        .filter((node) => node.hasAttribute('data-group-label'))
      expect(labels.map((node) => node.getAttribute('data-role'))).toEqual(
        ['agent_runtime', 'provider_router', 'UNKNOWN'])
      const hermes = within(toolList()).getAllByText('Hermes')[0]
      const router = within(toolList()).getAllByText('CC Switch')[0]
      const mystery = within(toolList()).getAllByText('Mystery Tool')[0]
      // DOM order is the claim: a router must not sit among the agents, and an undeclared row must not
      // be silently promoted into either group.
      expect(hermes.compareDocumentPosition(router) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(router.compareDocumentPosition(mystery) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(screen.getByText(/LEGACY_OBSERVE/)).toBeTruthy()
    } finally {
      cards.length = 2
    }
  })

  it('role 从卡片自己的声明字段读出，缺声明就是 UNKNOWN，不从名字猜', () => {
    const rows = dailyToolRows({
      adapterCapabilities: [
        { clientId: 'cc-switch', displayName: 'CC Switch', registryStatus: 'legacy_observe',
          writePolicy: 'unavailable', declaredOperations: [], role: 'provider_router' },
        { clientId: 'mystery', displayName: 'Mystery Tool', registryStatus: 'active',
          writePolicy: 'approval_required', declaredOperations: ['apply'] },
      ],
      projects: [],
    } as never)
    expect(rows.map((r) => [r.clientId, r.role])).toEqual([
      ['cc-switch', 'provider_router'],
      ['mystery', 'UNKNOWN'],
    ])
  })

  it('反馈是内存态：显示“你反馈”，并明确提示刷新后丢失，不宣称系统已验证', async () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=issues')
    render(<App />)
    const row = await screen.findByRole('button', { name: /示例问题：采集器连续失败/ })
    await act(async () => { row.click() })
    const restored = await screen.findByRole('button', { name: '已恢复' })
    await act(async () => { restored.click() })
    expect(screen.getByText('你反馈：已恢复')).toBeTruthy()
    expect(screen.getByText(/反馈仅保存在本页内存中，刷新后丢失/)).toBeTruthy()
    expect(screen.queryByText(/系统已验证/)).toBeNull()
  })
})

describe('HUD 四态（?hud=daily）', () => {
  it('H01 窄面板：两个工具各自成行，额度一律 UNKNOWN，不出现虚构百分比', () => {
    window.history.replaceState(null, '', '/index.html?layout=compact&hud=daily&hs=h01')
    render(<App />)
    // Each row is bound to the client it monitors, and draws a figure rather than the first two letters of
    // the display name -- two identical "QO"/"CO" pills were the thing that made the rows indistinguishable.
    const bound = Array.from(document.querySelectorAll('[data-hud-agent]'))
      .map((node) => node.getAttribute('data-hud-agent'))
    expect(bound).toEqual(['qoder', 'codex'])
    expect(document.querySelectorAll('[data-hud-agent] svg').length).toBe(2)
    expect(screen.queryByText('QO')).toBeNull()
    expect(screen.queryByText('CO')).toBeNull()
    expect(screen.getAllByText('额度 UNKNOWN').length).toBe(2)
    expect(screen.queryByText(/79%|12%/)).toBeNull()
  })

  it('页脚齿轮换下状态卡，而不是接在下面把自己顶出视口', () => {
    window.history.replaceState(null, '', '/index.html?layout=compact&hud=daily&hs=h01')
    render(<HudDaily snap={mockSnap as never} nativeStrip />)
    const frame = document.querySelector('[data-hud-frame]') as HTMLElement
    expect(frame.querySelector('[data-landmark="h01"]')).not.toBeNull()
    expect(frame.querySelector('[data-landmark="hud-settings"]')).toBeNull()
    fireEvent.click(screen.getByLabelText('HUD 设置'))
    expect(frame.querySelector('[data-landmark="hud-settings"]')).not.toBeNull()
    // The swap is the claim: appended, this block painted at y=508 of a 480px window (measured by
    // scripts/audit/hud_strip_geometry_via_cdp.py), i.e. opened and invisible.
    expect(frame.querySelector('[data-landmark="h01"]')).toBeNull()
    expect(screen.getByLabelText('HUD 设置').getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(screen.getByRole('button', { name: '收起' }))
    expect(frame.querySelector('[data-landmark="h01"]')).not.toBeNull()
    expect(frame.querySelector('[data-landmark="hud-settings"]')).toBeNull()
    expect(screen.getByLabelText('HUD 设置').getAttribute('aria-expanded')).toBe('false')
  })

  it('H03 工具详情不画虚构柱状图；H04 提醒不冒充系统确认', () => {
    window.history.replaceState(null, '', '/index.html?layout=compact&hud=daily&hs=h03')
    const { unmount } = render(<App />)
    expect(screen.getByText(/不绘制柱状图/)).toBeTruthy()
    unmount()
    window.history.replaceState(null, '', '/index.html?layout=compact&hud=daily&hs=h04')
    render(<App />)
    expect(screen.getByText(/外部回复不等于系统确认/)).toBeTruthy()
    expect(screen.getByText(/摘要保持 待确认/)).toBeTruthy()
  })

  it('状态切换写回 ?hs=（URL 可分享）', () => {
    window.history.replaceState(null, '', '/index.html?layout=compact&hud=daily')
    render(<App />)
    const btn = screen.getByRole('button', { name: 'H03' })
    btn.click()
    expect(window.location.search).toContain('hs=h03')
  })
})

describe('方法抽屉的修复包材料接口', () => {
  it('方法 issueRefs 对上修复包指纹时，材料用后端 handoffText 并标注来源', async () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a&dm=sol-b')
    render(<App />)
    const preview = await screen.findByLabelText('交接材料预览') as HTMLTextAreaElement
    expect(preview.value).toContain('后端渲染的交接文本（PACK-1）')
    expect(preview.value).not.toContain('步骤乙一')
    expect(screen.getByText(/来源：修复包 pack-1 · 后端渲染 · 未发送/)).toBeTruthy()
  })

  it('没有对上修复包的方法沿用方案库材料并标注方案来源', async () => {
    window.history.replaceState(null, '', '/index.html?shell=daily&dv=overview&dp=proj-a&dm=sol-a')
    render(<App />)
    const preview = await screen.findByLabelText('交接材料预览') as HTMLTextAreaElement
    expect(preview.value).toContain('方法甲：检查更新后的构建产物')
    expect(screen.getByText(/来源：方案库方法/)).toBeTruthy()
  })
})

describe('交接材料生成器', () => {
  it('pack 材料原样携带后端 handoffText；方法材料含项目/问题/步骤/限制', () => {
    const packMaterial = buildHandoverMaterial({
      projectName: '示例项目甲', issueTitle: null, method: null, pack: {
        schemaVersion: 'worklab/repair-pack/v1', packId: 'pack-1', generatedAt: '2026-10-24T00:00:00Z',
        status: 'DRAFT', readiness: { state: 'READY', reasons: [] },
        target: { kind: 'project', projectId: 'proj-a', projectName: '示例项目甲', projectRoot: '/tmp', adapter: null, declaredOperations: [], operation: 'fix', routingSource: 'test' },
        binds: { issueFingerprints: ['fp'], evidenceRefs: [], classes: [], priorities: [], issueCount: 1, softwareIds: [], unattributedCount: 0 },
        verification: { known: false, command: '', basis: '' },
        handoff: { mode: 'manual_copy', copyable: true, sent: false, dispatched: false, requiresOwnerAction: '' },
        handoffText: '后端渲染的交接文本',
      }, targetTool: 'Qoder',
    })
    expect(packMaterial.text).toContain('后端渲染的交接文本')
    expect(packMaterial.text).toContain('示例项目甲')
    const methodMaterial = buildHandoverMaterial({
      projectName: '示例项目乙', issueTitle: '某问题', method: solutionA as never, pack: null, targetTool: '',
    })
    expect(methodMaterial.text).toContain('项目：示例项目乙')
    expect(methodMaterial.text).toContain('问题：某问题')
    expect(methodMaterial.text).toContain('1. 步骤甲一')
    expect(methodMaterial.text).toContain('适用限制')
  })
})

describe('CL-08 默认桌面入口（2026-10-24 owner「完成全部前后端任务」）', () => {
  // 主窗口是 borderless（decorations:false），默认入口现在是日常壳：
  // 标题控件簇与拖动面必须在原生壳里真渲染、在浏览器壳里真缺席——
  // 两侧都断言，否则这条守卫永远无法判红。
  it('原生壳（__TAURI_INTERNALS__ 存在）渲染窗口控件与拖动面', async () => {
    ;(window as unknown as { __TAURI_INTERNALS__: unknown }).__TAURI_INTERNALS__ = { probe: true }
    try {
      render(<App />)
      expect(document.querySelector('.winctl')).toBeTruthy()
      expect(document.querySelector('[data-tauri-drag-region]')).toBeTruthy()
    } finally {
      delete (window as unknown as { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
    }
  })

  it('浏览器壳不渲染窗口控件（同一地址，差一个垫片；拖动属性本身与壳无关，浏览器里是空操作）', () => {
    render(<App />)
    expect(document.querySelector('.winctl')).toBeNull()
    expect(document.querySelector('[data-tauri-drag-region]')).toBeTruthy()
  })

  it('旧深链 ?view=evidence 仍落到专业投影壳，不静默改道', () => {
    window.history.replaceState(null, '', '/index.html?view=evidence')
    render(<App />)
    expect(document.querySelector('[data-shell="daily"]')).toBeNull()
    expect(document.querySelector('nav[aria-label="主导航"]')).toBeNull()
  })
})

describe('CL-12 原生窄窗 surface（?surface=hud）', () => {
  it('URL 写回不冲掉 surface 标记：窄窗保持窄窗，不回落到专业壳', () => {
    // 实测过的缺陷：写回白名单漏了 surface，快照到达后的 replaceState 把地址改写成
    // 不带 surface 的形式，下一次渲染就在 150px 里画出专业导航。
    window.history.replaceState(null, '', '/index.html?surface=hud')
    render(<App />)
    expect(new URLSearchParams(window.location.search).get('surface')).toBe('hud')
    expect(document.querySelector('[data-hud-frame="native-strip"]')).toBeTruthy()
    expect(document.querySelector('[data-shell="daily"]')).toBeNull()
  })

  it('窄窗只渲染 HUD 本体，四态切换器留给面板（切换器是调试面，不占常驻窄窗）', () => {
    window.history.replaceState(null, '', '/index.html?surface=hud')
    render(<App />)
    expect(document.querySelector('[aria-label="工具额度窄面板"]')).toBeTruthy()
    expect(document.querySelector('[aria-label="HUD 状态切换"]')).toBeNull()
  })
})

describe('CL-12 原生窄窗的 H02 可达性', () => {
  // 隐藏四态切换器后，H02（悬停摘要）在窄窗里就没有别的入口了。参考把它画成悬停行旁的
  // 内联小胶囊，所以挂在**被悬停的那一行**上：指针天然留在展开区内，也不会像追加整张高卡
  // 那样把常驻页脚顶出 480px 视口、或要求用户滚动去看自己刚唤出的内容。
  it('悬停某一行只展开那一行的内联摘要，H01 与其余行不受影响', () => {
    window.history.replaceState(null, '', '/index.html?surface=hud')
    render(<HudDaily snap={mockSnap as never} nativeStrip />)
    expect(screen.queryByLabelText('悬停摘要')).toBeNull()
    const li = screen.getByLabelText('工具额度窄面板').querySelector('li')!
    fireEvent.mouseEnter(li)
    const summary = screen.getByLabelText('悬停摘要')
    expect(summary.textContent).toContain('UNKNOWN')
    expect(li.contains(summary)).toBe(true)
    // 参考的 H02 还会把被悬停那一行本身点亮（琥珀环），只出现摘要不算还原。
    // 2026-10-27 起环色是主题令牌而不是字面量（写死时窄窗在两个主题下逐字节相同），所以这里钉两件事：
    // 环说得出自己演的是哪个角色（data-ring-role，窄窗几何门读同一个属性），且点亮行与未点亮行
    // 引用的是**不同**的令牌——两个角色若共用一个令牌，琥珀就再也点不亮任何东西。
    const ring = li.querySelector('circle')!
    expect(ring.getAttribute('data-ring-role')).toBe('active')
    expect(ring.style.stroke).toBe('var(--daily-warn-mark)')
    const other = screen.getByLabelText('工具额度窄面板').querySelectorAll('li')[1]
    const otherRing = other.querySelector('circle')!
    expect(otherRing.getAttribute('data-ring-role')).toBe('idle')
    expect(otherRing.style.stroke).toBe('var(--daily-line)')
    expect(otherRing.style.stroke).not.toBe(ring.style.stroke)
    expect(screen.getAllByLabelText('悬停摘要')).toHaveLength(1)
    expect(screen.getByLabelText('工具额度窄面板')).toBeTruthy()
  })

  it('键盘聚焦同样展开（悬停不是唯一通道），移开即收起', () => {
    window.history.replaceState(null, '', '/index.html?surface=hud')
    render(<HudDaily snap={mockSnap as never} nativeStrip />)
    const li = screen.getByLabelText('工具额度窄面板').querySelector('li')!
    fireEvent.focus(li)
    expect(screen.getByLabelText('悬停摘要')).toBeTruthy()
    fireEvent.blur(li)
    expect(screen.queryByLabelText('悬停摘要')).toBeNull()
  })

  it('面板层不内联展开（切换器仍在，再挂一层会重复）', () => {
    window.history.replaceState(null, '', '/index.html?layout=compact&hud=daily')
    render(<HudDaily snap={mockSnap as never} />)
    const li = screen.getByLabelText('工具额度窄面板').querySelector('li')!
    fireEvent.mouseEnter(li)
    expect(screen.queryByLabelText('悬停摘要')).toBeNull()
    expect(screen.getByLabelText('HUD 状态切换')).toBeTruthy()
  })
})
