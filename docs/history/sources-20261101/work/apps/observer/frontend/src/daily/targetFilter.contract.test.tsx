// 2026-10-26 E2 · 监控对象显示筛选（?targets=）的契约测试。
// 钉四件事：地址是唯一载体（往返可复现、刷新不丢）、空结果说清是筛选造成的、
// 每个被筛的数都带范围、整条链路零写入（不发请求、不碰 web storage、不动侧车状态）。
// 夹具沿用 daily.contract.test.tsx 的形状：两个监控对象（proj-a ACTIVE＋1 条问题、
// proj-b 无问题），一条执行 WAITING_USER。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import {
  TARGETS_PARAM, readTargetSelection, encodeTargetSelection, toggleTargetToken, selectTargets,
  partitionIssuesByTargets, projectCountSentence, issueCountSentence, targetMissSentence,
} from '@/daily/dailyData'

const mockSnap = {
  schemaVersion: 'workflow/snapshot/v3',
  revision: 7,
  generatedAt: '2026-10-26T00:00:00Z',
  sourceWatermark: '2026-10-26T00:00:00Z',
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
      visibility: 'private', quality: 'REAL', lastStrongEvidenceAt: '2026-10-26T00:00:00Z',
      repositories: [], git: { localSha: null, remoteSha: null, matchState: 'NO_LOCAL_CLAIM', branch: null, dirtyCount: null, observedAt: null, quality: null, freshness: null, sourceRef: null, sourceProjectId: null },
      token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
      ci: [], executionIds: ['e1'], sourceRefs: [],
    },
    {
      projectId: 'proj-b', displayName: '示例项目乙', agentPlatform: 'codex', identityState: 'MATCHED',
      activityState: 'IDLE', attentionState: 'NONE', activeExecutionCount: 0, workingAreas: [],
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
  // 全机只有 1 条问题，而且挂在 proj-a：proj-b 被单独筛出来时它必须「消失但不归零」。
  issues: [
    {
      schemaVersion: 'workflow/issue/v1', fingerprint: 'fp-aaa', class: 'SOURCE_FAILURE', projectId: 'proj-a',
      subject: '示例问题：采集器连续失败', origin: 'collector', evidenceRef: 'telemetry_events', priority: 'P1',
      priorityRule: 'P1: source failure', firstSeenAt: '2026-10-25T00:00:00Z', lastSeenAt: '2026-10-26T00:00:00Z',
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
      observedAt: '2026-10-26T00:00:00Z', layers: [], nativeStatus: 'NOT_PROBED',
      entryProbe: { status: 'PASS', entryPoint: 'qoder', argv: [], exitCode: 0, probedAt: '2026-10-26T00:00:00Z' },
    },
  ],
} as never

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => ({ snap: mockSnap, source: 'live', live: true, error: null, dataUpdatedAt: 0 }) }
})

// 与筛选无关的两条读取路一律给空结果：本文件的 fetch 计数才只回答「筛选自己有没有写出去」。
vi.mock('@/lib/repairPack', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/repairPack')>()
  return {
    ...actual,
    makeHttpRepairPackReader: () => async () => ({
      kind: 'RESULT', httpStatus: 200, endpoint: 'test',
      view: {
        schemaVersion: 'worklab/repair-packs-view/v1', status: 'OK', reason: '测试', generatedAt: '2026-10-26T00:00:00Z',
        issuesSummary: null, packs: [], summary: { openIssueCount: 0, packCount: 0 },
      },
    }),
  }
})

vi.mock('@/daily/solutionsClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/daily/solutionsClient')>()
  return {
    ...actual,
    fetchSolutions: async () => ({
      kind: 'RESULT',
      view: {
        schemaVersion: 'worklab/solution-search/v1', status: 'OK', reason: '测试', query: '',
        results: [], summary: { mode: 'BROWSE' },
      },
    }),
  }
})

import App from '@/App'
import { HudDaily } from '@/daily/HudDaily'

const CARDS = '[data-landmark="project-card"]'

function setUrl(search: string) {
  window.history.replaceState(null, '', `/index.html${search}`)
}
function currentTargets(): string | null {
  return new URLSearchParams(window.location.search).get(TARGETS_PARAM)
}
function cardsShown(): number {
  return document.querySelectorAll(CARDS).length
}
/** 页脚计数按"用户读到的一行一行"断言，而不是把两行拼成一个字符串：拼起来读不出
 *  「数字被挤到下一行单独悬着」这类排版问题，而那正是分成两行的原因。 */
function countLines(testId: string): string[] {
  const el = screen.getByTestId(testId)
  return Array.from(el.querySelectorAll('span')).map((line) => line.textContent ?? '')
}
/** 把被动效果与 Promise 回调这一轮全部落地后再断言：地址写回走的是 App.tsx 的 useEffect，
 *  按真实时序读地址，而不是按理想时序。 */
async function settle() {
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
}

beforeEach(() => { setUrl('?shell=daily') })
afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', window.location.pathname)
  window.localStorage.clear()
})

describe('E2 · ?targets= 的编解码（纯函数层）', () => {
  it('缺席＝全部；空值＝全部；多值按序去重；token 认 projectId 也认显示名', () => {
    expect(readTargetSelection('')).toBeNull()
    expect(readTargetSelection('shell=daily')).toBeNull()
    expect(readTargetSelection(`${TARGETS_PARAM}=`)).toBeNull()
    expect(readTargetSelection(`${TARGETS_PARAM}=,,`)).toBeNull()
    expect(readTargetSelection(`${TARGETS_PARAM}=proj-a,proj-b,proj-a`)).toEqual(['proj-a', 'proj-b'])
    expect(readTargetSelection(`${TARGETS_PARAM}= PROJ-A ,bogus`)).toEqual(['PROJ-A', 'bogus'])
    expect(encodeTargetSelection(null)).toBeNull()
    expect(encodeTargetSelection([])).toBeNull()
    expect(encodeTargetSelection(['proj-a', 'proj-b'])).toBe('proj-a,proj-b')
  })

  it('点一下的取舍：未筛选时点某项＝只看它；再加一项；移回空集＝删参数而不是写空值', () => {
    expect(toggleTargetToken(null, 'proj-a')).toEqual(['proj-a'])
    expect(toggleTargetToken(['proj-a'], 'proj-b')).toEqual(['proj-a', 'proj-b'])
    expect(toggleTargetToken(['proj-a', 'proj-b'], 'proj-a')).toEqual(['proj-b'])
    expect(toggleTargetToken(['proj-a'], 'proj-a')).toBeNull()
  })

  it('子集派生：命中/未命中/被排除都点名，未命中绝不静默回退成全部', () => {
    const items = [
      { projectId: 'proj-a', displayName: '示例项目甲' },
      { projectId: 'proj-b', displayName: '示例项目乙' },
    ]
    const none = selectTargets(items, null)
    expect([none.active, none.shown.length, none.total, none.unmatchedTokens]).toEqual([false, 2, 2, []])

    const one = selectTargets(items, ['proj-b'])
    expect(one.active).toBe(true)
    expect(one.shown.map((c) => c.projectId)).toEqual(['proj-b'])
    expect(one.excluded.map((c) => c.projectId)).toEqual(['proj-a'])
    expect(one.matchedProjectIds).toEqual(['proj-b'])

    const byName = selectTargets(items, [' 示例项目甲 '])
    expect(byName.shown.map((c) => c.projectId)).toEqual(['proj-a'])
    expect(byName.unmatchedTokens).toEqual([])

    const miss = selectTargets(items, ['nope'])
    expect(miss.shown).toHaveLength(0)
    expect(miss.unmatchedTokens).toEqual(['nope'])
    expect(miss.total).toBe(2)
  })

  it('问题归属：被筛掉的对象的问题 counted 得见，无项目归属的也 counted 得见', () => {
    const rows = [
      { projectId: 'proj-a' }, { projectId: 'proj-a' }, { projectId: 'proj-b' }, { projectId: null },
    ]
    const subset = selectTargets(
      [{ projectId: 'proj-a', displayName: '示例项目甲' }, { projectId: 'proj-b', displayName: '示例项目乙' }],
      ['proj-a'],
    )
    const scope = partitionIssuesByTargets(rows, subset)
    expect(scope.shown.length).toBe(2)
    expect(scope.total).toBe(4)
    expect(scope.hiddenByFilter).toBe(1)
    expect(scope.unattributed).toBe(1)
    // 未筛选时不谎称有筛选：全部行都在，hiddenByFilter 恒 0。
    const all = partitionIssuesByTargets(rows, selectTargets(
      [{ projectId: 'proj-a', displayName: '示例项目甲' }], null))
    expect([all.shown.length, all.hiddenByFilter, all.unattributed]).toEqual([4, 0, 1])
  })

  it('计数句自带范围，未命中句自带「不是没有对象」', () => {
    const items = [
      { projectId: 'proj-a', displayName: '示例项目甲' },
      { projectId: 'proj-b', displayName: '示例项目乙' },
    ]
    expect(projectCountSentence(selectTargets(items, null))).toBe('2 个已注册项目')
    const filtered = projectCountSentence(selectTargets(items, ['proj-a']))
    expect(filtered).toContain('筛选显示 1／2 个已注册项目')
    // 这句只钉「未显示的数量被点名」这个属性，不钉措辞：项目侧与工具侧共用同一个子句生成器，
    // 词序改过一版（「未显示 1 个」→「另有 1 项未显示」），两种都算兑现了范围声明。
    expect(filtered).toMatch(/(未显示 1 个|另有 1 项未显示)/)
    expect(filtered).toContain('只限显示，不改数据')

    const scope = partitionIssuesByTargets(
      [{ projectId: 'proj-a' }, { projectId: 'proj-b' }], selectTargets(items, ['proj-b']))
    const sentence = issueCountSentence(scope, true, 1)
    expect(sentence).toContain('筛选内 1／1 条')
    expect(sentence).toContain('全机 2 条问题')
    expect(sentence).toContain('1 条属未显示的监控对象')

    const miss = targetMissSentence(['nope'], 2)
    expect(miss).toContain('nope')
    expect(miss).toContain('这不是「没有项目」')
  })
})

describe('E2 · 日常壳里的显示筛选（URL 往返与如实空态）', () => {
  it('往返：无参数显示全部 → 点控件写地址 → 重解析同一子集 → 重新挂载仍然复现', async () => {
    setUrl('?shell=daily')
    render(<App />)
    await settle()
    expect(currentTargets()).toBeNull()
    expect(cardsShown()).toBe(2)

    await act(async () => { screen.getByTestId('target-filter-option-proj-a').click() })
    expect(currentTargets()).toBe('proj-a')
    expect(cardsShown()).toBe(1)
    expect(document.querySelector(`${CARDS} h2`)?.textContent).toBe('示例项目甲')
    // 地址是唯一的载体：从地址重解析，得到的还是同一个子集。
    expect(readTargetSelection(window.location.search.slice(1))).toEqual(['proj-a'])
    expect(screen.getByTestId('target-filter-option-proj-a').getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByTestId('target-filter-option-proj-b').getAttribute('aria-pressed')).toBe('false')

    // 刷新＝用同一个地址重新挂载（不靠内存态、不靠 web storage）。
    const addr = window.location.search
    cleanup()
    setUrl(addr)
    render(<App />)
    await settle()
    expect(currentTargets()).toBe('proj-a')
    expect(cardsShown()).toBe(1)

    // 「全部」= 删参数，回到默认。
    await act(async () => { screen.getByTestId('target-filter-all').click() })
    expect(currentTargets()).toBeNull()
    expect(cardsShown()).toBe(2)
  })

  it('共享深链不被上层写回冲掉：?targets 在挂载后仍留在地址里', async () => {
    setUrl('?shell=daily&targets=proj-b')
    render(<App />)
    await settle()
    expect(currentTargets()).toBe('proj-b')
    expect(cardsShown()).toBe(1)
    expect(document.querySelector(`${CARDS} h2`)?.textContent).toBe('示例项目乙')
  })

  it('筛选把唯一的问题源排除时，计数写明子集与全机两个数，空列表不读成「没有问题」', async () => {
    setUrl('?shell=daily&dv=issues&targets=proj-b')
    render(<App />)
    await settle()
    expect(document.querySelectorAll('[data-landmark="issue-row"]').length).toBe(0)
    const scope = screen.getByTestId('issues-count-scope').textContent ?? ''
    expect(scope).toContain('筛选内 0')
    expect(scope).toContain('全机 1 条问题')
    expect(scope).toContain('1 条属未显示的监控对象')
    const empty = screen.getByTestId('issues-empty').textContent ?? ''
    expect(empty).toContain('不是「没有问题」')
    expect(empty).toContain('全机仍有 1 条问题')
    // 未筛选时那句「实测，非推断」不得被复用成筛选态的结论。
    expect(empty).not.toContain('当前没有打开的问题')
    // 全机来源统计也要说明自己不受筛选影响。
    expect(screen.getByTestId('issues-summary-scope').textContent).toContain('全机来源统计')
  })

  it('筛选未命中任何对象：明说空来自筛选，并保留未命中的 token', async () => {
    setUrl('?shell=daily&targets=ghost')
    render(<App />)
    await settle()
    expect(cardsShown()).toBe(0)
    expect(screen.getByTestId('home-empty-miss').textContent).toContain('这不是「没有项目」')
    expect(screen.getByTestId('target-filter-unmatched').textContent).toContain('ghost')
    expect(screen.getByTestId('target-filter-scope').textContent).toContain('筛选显示 0／2 个已注册项目')
    expect(currentTargets()).toBe('ghost')
    // 仍然给得出一条回到全部的路，而不是把地址改写了事。
    await act(async () => { screen.getByTestId('target-filter-all').click() })
    expect(currentTargets()).toBeNull()
    expect(cardsShown()).toBe(2)
  })

  it('筛选态下首页每个数都带范围；未筛选态措辞不变', async () => {
    setUrl('?shell=daily')
    render(<App />)
    await settle()
    expect(screen.getByTestId('target-filter-scope').textContent).toBe('2 个已注册项目')
    expect(screen.getByTestId('home-caption').textContent).not.toContain('不代表全机')

    await act(async () => { screen.getByTestId('target-filter-option-proj-a').click() })
    expect(screen.getByTestId('target-filter-scope').textContent).toContain('筛选显示 1／2')
    expect(screen.getByTestId('home-caption').textContent).toContain('不代表全机')
    // 对象自己的问题数属于该对象，不加「全机」这种范围词，避免把 per-target 数读成总量。
    expect(document.querySelector('[data-testid="target-filter"]')?.textContent).toContain('监控对象显示筛选')
  })

  it('筛选态下「我的工具」把两个维度各自的参数说清楚', async () => {
    setUrl('?shell=daily&dv=tools&targets=proj-a')
    render(<App />)
    await settle()
    expect(currentTargets()).toBe('proj-a')
    const scope = screen.getByTestId('tools-target-scope').textContent ?? ''
    // 只钉「两个参数都被点名」这个属性：范围声明缺任何一个都会让读者把一维筛选读成全局筛选。
    expect(scope).toContain('?targets')
    expect(scope).toContain('?tools')
    cleanup()
    setUrl('?shell=daily&dv=tools')
    render(<App />)
    await settle()
    expect(screen.queryByTestId('tools-target-scope')).toBeNull()
  })

  it('零写入：筛选只改地址，不发请求、不碰 web storage', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    setUrl('?shell=daily')
    render(<App />)
    await settle()
    fetchSpy.mockClear()
    await act(async () => { screen.getByTestId('target-filter-option-proj-a').click() })
    await act(async () => { screen.getByTestId('target-filter-option-proj-b').click() })
    await act(async () => { screen.getByTestId('target-filter-all').click() })
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(window.localStorage.length).toBe(0)
    expect(window.sessionStorage.length).toBe(0)
    fetchSpy.mockRestore()
  })

  it('窄窗在筛选态点名自己的计数范围，未筛选态一字不加', async () => {
    setUrl('?surface=hud&targets=proj-a')
    const { unmount } = render(<App />)
    await settle()
    // 两个计数是两行，每行一个完整的「名词＋数」：断言按行读，才不会被"数字被挤到下一行"这种排版骗过。
    expect(countLines('hud-project-counts')).toEqual(['全机 运行中项目 1', '待审 1'])
    expect(screen.getByTestId('hud-count-scope').textContent).toContain('不随主窗口 ?targets 显示筛选变化')
    expect(currentTargets()).toBe('proj-a')
    unmount()
    cleanup()

    setUrl('?surface=hud')
    render(<App />)
    await settle()
    expect(currentTargets()).toBeNull()
    expect(screen.queryByTestId('hud-count-scope')).toBeNull()
    expect(countLines('hud-project-counts')).toEqual(['运行中项目 1', '待审 1'])
  })

  it('窄窗不自己发明第二套显示状态：筛选控件只在日常壳里', async () => {
    setUrl('?surface=hud&targets=proj-a')
    render(<HudDaily snap={mockSnap as never} nativeStrip />)
    expect(screen.queryByTestId('target-filter')).toBeNull()
  })
})
