// 2026-10-26 E2 · 工具（软件）这一维的显示筛选（?tools=）与「另有 N 项未显示」补句的契约测试。
// 与 targetFilter.contract.test.tsx（?targets 那一维）分文件：这一维管的是适配器能力卡，
// 那一维管的是监控对象（项目）。两维各自一个参数，各自的空态成因也必须各自说得出来。
// 钉四件事：①参数只进地址、刷新后还在；②筛选生效且「另有 N 项未显示」的 N 与实测行数一致；
// ③全显（含未筛选、以及地址把对象列全）时那句话不出现；④零写入——不发请求、不碰 web storage。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import { mkSnap } from '@/test/snapshotFixture'
import {
  TOOLS_PARAM, TARGETS_PARAM, readToolSelection, encodeToolSelection, toggleToolToken,
  selectTools, toolCountSentence, notShownClause, projectCountSentence, selectTargets,
} from '@/daily/dailyData'

const card = (clientId: string, displayName: string) => ({
  clientId, displayName, supportLevel: 'MANAGE', declaredOperations: ['read'], matrixOperations: ['read'],
  operationsDrift: false, registryStatus: 'ACTIVE', writePolicy: 'READ_ONLY', risk: 'LOW',
  runtimeAdapter: null, configOwnershipDefault: null, declaredVersion: '1.0.0', versionReadbackMethod: null,
  versionObservedAt: null, versionSource: null, detectionMode: null, detectionEvidenceState: 'REAL',
  protocolConformance: {}, observedAt: '2026-10-26T00:00:00Z', layers: [], nativeStatus: 'NOT_PROBED',
  entryProbe: { status: 'PASS', entryPoint: clientId, argv: [], exitCode: 0, probedAt: '2026-10-26T00:00:00Z' },
})

const snap = mkSnap({
  // 三张能力卡：只有 3 个对象时才分得清「筛掉 2 个」「筛掉 1 个」「一个都没筛掉」三种句子。
  adapterCapabilities: [
    card('qoder', 'Qoder') as never,
    card('codex', 'Codex') as never,
    card('dsatharness', 'DeepSeek Harness') as never,
  ],
  issues: [],
})

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => ({ snap, source: 'live', live: true, error: null, dataUpdatedAt: 0 }) }
})
vi.mock('@/lib/repairPack', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/repairPack')>()
  return { ...actual, makeHttpRepairPackReader: () => async () => ({ kind: 'UNREACHABLE' as const, detail: '测试环境不读取' }) }
})
vi.mock('@/daily/solutionsClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/daily/solutionsClient')>()
  return { ...actual, fetchSolutions: async () => ({ kind: 'UNREACHABLE' as const, detail: '测试环境不读取' }) }
})

import App from '@/App'

const TOOLS_URL = `?shell=daily&dv=tools`
function setUrl(search: string) {
  window.history.replaceState(null, '', `/index.html${search}`)
}
function paramOf(name: string): string | null {
  return new URLSearchParams(window.location.search).get(name)
}
/** 工具列表里的真实行数：空态那条 li 里没有按钮，所以用行内按钮计数，不用 li 计数。 */
function toolRowsShown(): number {
  return document.querySelectorAll('ul[aria-label="工具列表"] > li > button').length
}
function hiddenFromSentence(text: string): number | null {
  const m = /另有 (\d+) 项未显示/.exec(text)
  return m ? Number(m[1]) : null
}
async function settle() {
  await act(async () => { await Promise.resolve(); await Promise.resolve() })
}

beforeEach(() => { setUrl(TOOLS_URL) })
afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', window.location.pathname)
  window.localStorage.clear()
})

describe('E2 · ?tools= 的编解码与补句（纯函数层）', () => {
  it('缺席＝全部；空值＝全部；多值按序去重；token 认 clientId 也认显示名', () => {
    expect(readToolSelection('')).toBeNull()
    expect(readToolSelection(`${TOOLS_PARAM}=`)).toBeNull()
    expect(readToolSelection(`${TOOLS_PARAM}=,,`)).toBeNull()
    expect(readToolSelection(`${TOOLS_PARAM}= QODER ,codex,codex`)).toEqual(['QODER', 'codex'])
    expect(encodeToolSelection(null)).toBeNull()
    expect(encodeToolSelection([])).toBeNull()
    expect(encodeToolSelection(['qoder', 'codex'])).toBe('qoder,codex')
    expect(toggleToolToken(null, 'qoder')).toEqual(['qoder'])
    expect(toggleToolToken(['qoder', 'codex'], 'qoder')).toEqual(['codex'])
    expect(toggleToolToken(['qoder'], 'qoder')).toBeNull()
  })

  it('补句只在 N>0 时出现：N＝总数 − 显示数，两维共用同一个生成器', () => {
    expect(notShownClause(3, 1)).toBe('另有 2 项未显示')
    expect(notShownClause(3, 3)).toBe('')
    expect(notShownClause(0, 0)).toBe('')
    const rows = [
      { clientId: 'qoder', displayName: 'Qoder' },
      { clientId: 'codex', displayName: 'Codex' },
      { clientId: 'dsatharness', displayName: 'DeepSeek Harness' },
    ]
    const one = toolCountSentence(selectTools(rows, ['qoder']))
    expect(one).toContain('筛选显示 1／3 个已登记工具')
    expect(one).toContain('另有 2 项未显示')
    // 地址把三个对象全列了一遍：仍是筛选态，但没有东西被藏起来，这句话就不该出现。
    expect(toolCountSentence(selectTools(rows, ['qoder', 'codex', 'dsatharness'])))
      .not.toContain('另有')
    // 未筛选态不谎报有筛选。
    expect(toolCountSentence(selectTools(rows, null))).toBe('3 个已登记工具')
    // 项目那一维同一条规则。
    const items = [{ projectId: 'proj-a', displayName: '甲' }, { projectId: 'proj-b', displayName: '乙' }]
    expect(projectCountSentence(selectTargets(items, ['proj-a']))).toContain('另有 1 项未显示')
    expect(projectCountSentence(selectTargets(items, ['proj-a', 'proj-b']))).not.toContain('另有')
  })

  it('能力卡缺席是来源缺失，不补 0、不画百分比', () => {
    const none = selectTools<{ clientId: string; displayName: string }>([], ['qoder'])
    expect(toolCountSentence(none)).toContain('来源缺失，不是 0 个工具')
    expect(toolCountSentence(none)).not.toMatch(/0％|0%|\d+％|\d+%/);
    expect(none.unmatchedTokens).toEqual(['qoder'])
  })
})

describe('E2 · 「我的工具」屏上的 ?tools= 显示筛选', () => {
  it('状态只走地址：点控件写参数，用同一地址重新挂载仍得同一子集', async () => {
    render(<App />)
    await settle()
    expect(paramOf(TOOLS_PARAM)).toBeNull()
    expect(toolRowsShown()).toBe(3)

    await act(async () => { screen.getByTestId('tool-filter-option-qoder').click() })
    expect(paramOf(TOOLS_PARAM)).toBe('qoder')
    expect(toolRowsShown()).toBe(1)
    expect(screen.getByTestId('tool-filter-option-qoder').getAttribute('aria-pressed')).toBe('true')
    // 地址是唯一载体：从地址读回的 token 与界面一致（没有 web storage 兜底）。
    expect(readToolSelection(window.location.search.slice(1))).toEqual(['qoder'])
    expect(window.localStorage.length).toBe(0)
    expect(window.sessionStorage.length).toBe(0)

    // 刷新＝用同一个地址重新挂载。
    const addr = window.location.search
    cleanup()
    setUrl(addr)
    render(<App />)
    await settle()
    expect(paramOf(TOOLS_PARAM)).toBe('qoder')
    expect(toolRowsShown()).toBe(1)

    // 「全部」＝删参数，回到默认，而不是写一个空值。
    await act(async () => { screen.getByTestId('tool-filter-all').click() })
    expect(paramOf(TOOLS_PARAM)).toBeNull()
    expect(toolRowsShown()).toBe(3)
  })

  it('冷启动直接带参数：第一帧就是子集，不被上层写回冲掉', async () => {
    setUrl(`${TOOLS_URL}&${TOOLS_PARAM}=codex,dsatharness`)
    render(<App />)
    await settle()
    expect(paramOf(TOOLS_PARAM)).toBe('codex,dsatharness')
    expect(toolRowsShown()).toBe(2)
    // 主题按钮只在设置屏渲染（DailyApp 的 SettingsView），而整串 URL 的重建发生在 App.tsx，
    // 所以这一例必须真的走到那一个屏上按它：参数要活过一次上层写回，再回到工具屏仍是子集。
    await act(async () => { screen.getByRole('button', { name: '设置' }).click() })
    await settle()
    await act(async () => { screen.getByTestId('daily-theme-toggle').click() })
    await settle()
    expect(paramOf(TOOLS_PARAM)).toBe('codex,dsatharness')
    expect(paramOf(TARGETS_PARAM)).toBeNull()
    await act(async () => { screen.getByRole('button', { name: '我的工具' }).click() })
    await settle()
    expect(paramOf(TOOLS_PARAM)).toBe('codex,dsatharness')
    expect(toolRowsShown()).toBe(2)
  })

  it('「另有 N 项未显示」的 N 与实测行数一致；全显时这句话不出现', async () => {
    setUrl(`${TOOLS_URL}&${TOOLS_PARAM}=qoder`)
    render(<App />)
    await settle()
    const shown = toolRowsShown()
    const scope = screen.getByTestId('tool-filter-scope').textContent ?? ''
    expect(shown).toBe(1)
    expect(hiddenFromSentence(scope)).toBe(3 - shown)
    expect(scope).toContain('另有 2 项未显示')
    cleanup()

    // 三个都列进地址：显示 3／3，N=0，句子整句消失（不是「另有 0 项未显示」）。
    setUrl(`${TOOLS_URL}&${TOOLS_PARAM}=qoder,codex,dsatharness`)
    render(<App />)
    await settle()
    expect(toolRowsShown()).toBe(3)
    const all = screen.getByTestId('tool-filter-scope').textContent ?? ''
    expect(all).toContain('筛选显示 3／3 个已登记工具')
    expect(hiddenFromSentence(all)).toBeNull()
    expect(all).not.toContain('另有 0 项未显示')
    cleanup()

    // 未筛选态同样不出现。
    setUrl(TOOLS_URL)
    render(<App />)
    await settle()
    expect(toolRowsShown()).toBe(3)
    expect(screen.getByTestId('tool-filter-scope').textContent).toBe('3 个已登记工具')
  })

  it('筛选未命中任何能力卡：明说空来自筛选，不静默回退成全部', async () => {
    setUrl(`${TOOLS_URL}&${TOOLS_PARAM}=ghost`)
    render(<App />)
    await settle()
    expect(toolRowsShown()).toBe(0)
    expect(paramOf(TOOLS_PARAM)).toBe('ghost')
    expect(screen.getByTestId('tool-filter-unmatched').textContent).toContain('ghost')
    const empty = screen.getByTestId('tools-empty-miss').textContent ?? ''
    expect(empty).toContain('这不是「没有工具」')
    expect(empty).toContain('投影里其实有 3 张能力卡')
    // 这条空态不得复用「来源缺失」那句：那是另一种事实。
    expect(empty).not.toContain('快照未携带适配器能力卡')
  })

  it('零写入：筛选只改地址，不发请求、不碰 web storage、不动侧车', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    render(<App />)
    await settle()
    fetchSpy.mockClear()
    await act(async () => { screen.getByTestId('tool-filter-option-qoder').click() })
    await act(async () => { screen.getByTestId('tool-filter-option-codex').click() })
    await act(async () => { screen.getByTestId('tool-filter-option-qoder').click() })
    await act(async () => { screen.getByTestId('tool-filter-all').click() })
    expect(fetchSpy).not.toHaveBeenCalled()
    expect(window.localStorage.length).toBe(0)
    expect(window.sessionStorage.length).toBe(0)
    expect(paramOf(TOOLS_PARAM)).toBeNull()
    fetchSpy.mockRestore()
  })

  it('两维互不覆盖：?targets 与 ?tools 各自筛各自的对象', async () => {
    setUrl(`${TOOLS_URL}&${TARGETS_PARAM}=design-lab&${TOOLS_PARAM}=codex`)
    render(<App />)
    await settle()
    expect(paramOf(TARGETS_PARAM)).toBe('design-lab')
    expect(paramOf(TOOLS_PARAM)).toBe('codex')
    expect(toolRowsShown()).toBe(1)
    expect(screen.getByTestId('tool-filter-scope').textContent).toContain('另有 2 项未显示')
    // 工具屏的范围声明要把两维都点名，否则读者会把一维筛选读成全局筛选。
    const note = screen.getByTestId('tools-target-scope').textContent ?? ''
    expect(note).toContain('?targets')
    expect(note).toContain('?tools')
  })
})
