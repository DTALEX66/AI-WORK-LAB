/**
 * WUI-01 / WUI-02 · the desktop home, the navigation model and the object-detail surface.
 *
 * These are render-level tests over the real shell (App + Sidebar + the new views), because the property
 * the taskpack asks for is behavioural: the landing page answers the project question, a rail entry moves
 * the page, a demoted lane is still reachable and says why, and an identity the projection does not carry
 * produces an explanation rather than a plausible substitute.
 *
 * What each test refuses to be: a presence check on a class or a label. This repo has already been burned
 * by a green suite over a visibly broken surface (SCREEN_SPEC / ERR-219 history), so the assertions below
 * read rendered text, attributes and hrefs, and several of them assert that something is ABSENT.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  live: { snap: null as any, source: 'live' as any, live: true, error: null as string | null },
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => mocks.live }
})

import App from '@/App'
import { mkProject, mkExecution, mkSnap } from '@/test/snapshotFixture'
import { DAILY_DESTINATION_IDS, OFF_DEFAULT_NAV_IDS, OFF_NAV_NOTES } from '@/lib/navigation'
import { OVERVIEW_LABEL } from '@/lib/viewRegistry'

function setUrl(qs: string) {
  window.history.replaceState(null, '', '/index.html' + qs)
}

function snapWith(projects: any[], executions: any[] = []) {
  return mkSnap({ projects, executions })
}

beforeEach(() => {
  mocks.live = { snap: null, source: 'live', live: true, error: null }
})

afterEach(() => {
  cleanup()
  setUrl('')
  document.documentElement.classList.remove('light')
})

describe('WUI-01 · the landing lane is 项目监控', () => {
  it('titles the default landing page 项目监控 and opens on the project collection', () => {
    mocks.live = {
      snap: snapWith([
        mkProject({ projectId: 'work-lab', displayName: 'WORK-LAB' }),
        mkProject({ projectId: 'design-lab', displayName: 'DESIGN-LAB' }),
      ]),
      source: 'live', live: true, error: null,
    }
    setUrl('')
    render(<App />)
    // the page heading, not the rail button that carries the same word
    expect(screen.getByRole('heading', { level: 2, name: OVERVIEW_LABEL })).toBeTruthy()
    expect(screen.getByText('项目集合')).toBeTruthy()
    expect(screen.getByTestId('project-row-count').textContent).toBe('2 / 2 个项目')
    // the identity, not just the display name, is what the home has to offer
    expect(screen.getByText('design-lab')).toBeTruthy()
  })

  it('leaves no factless chart frame and no dead execute affordance on the home', () => {
    mocks.live = { snap: snapWith([mkProject()]), source: 'live', live: true, error: null }
    const { container } = render(<App />)
    // 无事实图表: the trend sparkline (no series) and the six hardcoded signal-map nodes are gone.
    expect(container.querySelector('.spark')).toBeNull()
    expect(container.querySelector('.graph-stage')).toBeNull()
    // 禁用执行主按钮: a disabled button is not a read-only boundary, it is a dead control.
    const disabled = Array.from(container.querySelectorAll('button:disabled'))
    expect(disabled.map((button) => button.textContent?.trim())).toEqual([])
    expect(screen.queryByText('新建执行')).toBeNull()
    expect(screen.queryByText('Observer Signal Map')).toBeNull()
  })

  it('names a missing participant as a projection gap instead of inventing one', () => {
    mocks.live = {
      snap: snapWith(
        [mkProject({ agentPlatform: null })],
        [mkExecution({ agent: null })],
      ),
      source: 'live', live: true, error: null,
    }
    render(<App />)
    expect(screen.getAllByText('未投影').length).toBeGreaterThanOrEqual(1)
  })

  it('filters rows in the view only, and says so in the label', () => {
    mocks.live = {
      snap: snapWith([
        mkProject({ projectId: 'work-lab', displayName: 'WORK-LAB' }),
        mkProject({ projectId: 'design-lab', displayName: 'DESIGN-LAB' }),
      ]),
      source: 'live', live: true, error: null,
    }
    render(<App />)
    const input = screen.getByLabelText(/筛选项目/) as HTMLInputElement
    expect(input.getAttribute('placeholder')).toContain('projectId')
    fireEvent.change(input, { target: { value: 'design' } })
    expect(screen.getByTestId('project-row-count').textContent).toBe('1 / 2 个项目')
    fireEvent.change(input, { target: { value: 'nosuchproject' } })
    // an empty filter result is reported as a filter result, not as an empty projection
    expect(screen.getByText(/没有匹配到项目行/).textContent).toContain('快照里有 2 个项目')
  })

  it('reports the empty project set as queried-and-empty, never as a zero padded from no source', () => {
    mocks.live = { snap: snapWith([]), source: 'live', live: true, error: null }
    render(<App />)
    expect(screen.getByTestId('project-row-count').textContent).toBe('0 / 0 个项目')
    expect(screen.getByText(/快照已查询，项目集合为空/).textContent)
      .toContain('这是「无项目」，不是「未投影」')
  })

  it('keeps the first-frame UNKNOWN discipline with no snapshot at all', () => {
    mocks.live = { snap: null, source: 'stale', live: false, error: null }
    setUrl('')
    render(<App />)
    expect(screen.getByText('项目集合')).toBeTruthy()
    expect(screen.getByText('项目集合未到达')).toBeTruthy()
    expect(document.body.textContent).not.toMatch(/0 \/ 0 个项目/)
  })
})

describe('WUI-02 · the rail, the demoted lane and the object detail', () => {
  const railLanes = (root: HTMLElement) => Array.from(
    root.querySelectorAll<HTMLButtonElement>('.nav button[data-lane]'))

  it('the rail marks the daily destinations and drops the demoted lane from navigation', () => {
    setUrl('?view=overview')
    const { container } = render(<App />)
    const buttons = railLanes(container)
    const daily = buttons.filter((b) => b.getAttribute('data-daily') === 'true')
      .map((b) => b.getAttribute('data-lane'))
    expect(new Set(daily)).toEqual(new Set(
      DAILY_DESTINATION_IDS.filter((id) => buttons.some((b) => b.getAttribute('data-lane') === id))))
    const ids = buttons.map((b) => b.getAttribute('data-lane'))
    expect(new Set(ids).size).toBe(ids.length)
    for (const id of OFF_DEFAULT_NAV_IDS) expect(ids).not.toContain(id)
  })

  it('the demoted lane still renders its working page and states why it left the rail', () => {
    setUrl('?view=' + OFF_DEFAULT_NAV_IDS[0])
    const { container } = render(<App />)
    const note = container.querySelector('[data-testid="off-nav-entry-note"]')
    expect(note, 'the off-nav lane arrived with no explanation').not.toBeNull()
    expect(note!.textContent).toContain('本页不在默认导航里')
    expect(note!.textContent).toContain(OFF_NAV_NOTES[OFF_DEFAULT_NAV_IDS[0]].slice(0, 12))
    // the implementation is intact, not a stub: the lane rendered its own surface below the note
    expect(container.querySelectorAll('.panel').length).toBeGreaterThan(1)
  })

  it('the demoted lane is reachable through search, labelled as an experimental entry', () => {
    setUrl('?view=overview')
    render(<App />)
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    const field = screen.getByRole('textbox')
    fireEvent.change(field, { target: { value: '编辑器' } })
    expect(screen.getAllByText('编辑器').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('实验入口（不在默认导航）')).toBeTruthy()
  })

  it('a project row reaches the object detail by identity, through a link', () => {
    mocks.live = { snap: snapWith([mkProject({ projectId: 'work-lab' })]), source: 'live', live: true, error: null }
    render(<App />)
    const link = screen.getByTestId('project-detail-link-work-lab') as HTMLAnchorElement
    expect(link.tagName).toBe('A')
    expect(link.getAttribute('href')).toContain('view=project-detail')
    expect(link.getAttribute('href')).toContain('projectId=work-lab')
  })

  it('the detail reads the addressed project and states the collaboration chain as 未接入', () => {
    mocks.live = {
      snap: snapWith([mkProject({ projectId: 'work-lab', displayName: 'WORK-LAB' })],
        [mkExecution({ executionId: 'ex-9', anchorProjectId: 'work-lab', state: 'BLOCKED' })]),
      source: 'live', live: true, error: null,
    }
    setUrl('?view=project-detail&projectId=work-lab')
    render(<App />)
    expect(screen.getByRole('heading', { level: 2, name: '项目详情' })).toBeTruthy()
    expect(screen.getByText('work-lab')).toBeTruthy()
    // three axes stay three claims
    expect(screen.getByText(/工作轴 · 活动/)).toBeTruthy()
    expect(screen.getByText(/健康轴 · 关注度/)).toBeTruthy()
    expect(screen.getByText(/观测轴 · 传输/)).toBeTruthy()
    // 协作摘要 lives here and does not pretend a peer answered
    expect(screen.getByText('协作摘要')).toBeTruthy()
    expect(screen.getByText('未接入')).toBeTruthy()
    expect(screen.getAllByText(/未投影|无强证据时间/).length).toBeGreaterThanOrEqual(1)
    expect(document.body.textContent).not.toMatch(/对端已接收|已送达|专业接受通过/)
  })

  it('an identity the projection does not carry is refused without substituting another project', () => {
    mocks.live = {
      snap: snapWith([mkProject({ projectId: 'work-lab', displayName: 'WORK-LAB' })]),
      source: 'live', live: true, error: null,
    }
    setUrl('?view=project-detail&projectId=ghost-project')
    const { container } = render(<App />)
    expect(screen.getByText('该项目不在投影里')).toBeTruthy()
    expect(screen.getByText(/projectId=ghost-project/)).toBeTruthy()
    expect(container.textContent).toContain('原身份保留供复制：ghost-project')
    // the real project is not rendered as if it were the one asked for
    expect(screen.queryByText(/工作轴 · 活动/)).toBeNull()
  })

  it('an unaddressed detail page points back to the collection instead of picking a project', () => {
    mocks.live = { snap: snapWith([mkProject({ projectId: 'work-lab' })]), source: 'live', live: true, error: null }
    setUrl('?view=project-detail')
    const { container } = render(<App />)
    expect(screen.getByText('地址里没有 projectId')).toBeTruthy()
    const goto = container.querySelector('[data-testid="project-detail-goto-home"]')
    expect(goto!.getAttribute('href')).toContain('view=overview')
    expect(screen.queryByText(/工作轴 · 活动/)).toBeNull()
  })

  it('a rejected identity in the address is named, not dropped', () => {
    mocks.live = { snap: snapWith([mkProject()]), source: 'live', live: true, error: null }
    setUrl('?view=project-detail&projectId=' + encodeURIComponent('bad id'))
    render(<App />)
    expect(screen.getByText('地址被拒绝')).toBeTruthy()
    expect(screen.getByText(/projectId · 定位标识包含非法字符/)).toBeTruthy()
  })

  it('the unknown-lane fallback now says where it goes', () => {
    setUrl('?view=not-a-lane')
    render(<App />)
    // an id the registry does not carry is reported, not silently turned into the home page
    expect(screen.getByText('未知视图')).toBeTruthy()
    expect(screen.getByText(/not-a-lane/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '返回项目监控' }))
    expect(screen.getByRole('heading', { level: 2, name: OVERVIEW_LABEL })).toBeTruthy()
  })
})

describe('WUI-03 · the pack palette is opt-in and never the default', () => {
  it('a bare address renders the shipped palette: no attribute on the document', () => {
    setUrl('')
    render(<App />)
    expect(document.documentElement.hasAttribute('data-palette')).toBe(false)
  })

  it('?palette=master opts in, survives a lane switch in the address, and touches no web storage', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    mocks.live = { snap: null, source: 'live', live: true, error: null }
    setUrl('?view=overview&palette=master')
    const { container } = render(<App />)
    expect(document.documentElement.getAttribute('data-palette')).toBe('master')
    const lane = container.querySelector('.nav button[data-lane="tools"]') as HTMLButtonElement
    fireEvent.click(lane)
    expect(window.location.search).toContain('palette=master')
    expect(window.location.search).toContain('view=tools')
    expect(setItem, 'the palette was persisted in web storage instead of the address').not.toHaveBeenCalled()
    setItem.mockRestore()
  })

  it('the palette switch is a command, worded so the default is not described as replaced', () => {
    setUrl('?view=overview')
    render(<App />)
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true })
    const field = screen.getByRole('textbox')
    fireEvent.change(field, { target: { value: '配色' } })
    const option = screen.getByText('改用母版建议配色（现行值不被覆盖）')
    fireEvent.click(option)
    expect(document.documentElement.getAttribute('data-palette')).toBe('master')
    expect(window.location.search).toContain('palette=master')
  })
})

describe('WUI-04 · identity stays an identity', () => {
  it('two projects sharing a display name stay two rows, each with its own id', () => {
    mocks.live = {
      snap: snapWith([
        mkProject({ projectId: 'alpha', displayName: 'Same Name', agentPlatform: 'codex' }),
        mkProject({ projectId: 'beta', displayName: 'Same Name', agentPlatform: 'hermes' }),
      ]),
      source: 'live', live: true, error: null,
    }
    const { container } = render(<App />)
    expect(screen.getByTestId('project-row-count').textContent).toBe('2 / 2 个项目')
    expect(screen.getAllByText('Same Name').length).toBeGreaterThanOrEqual(2)
    expect(container.querySelectorAll('[data-testid^="same-name-"]')).toHaveLength(2)
    expect(screen.getByTestId('project-detail-link-alpha').getAttribute('href'))
      .toContain('projectId=alpha')
    expect(screen.getByTestId('project-detail-link-beta').getAttribute('href'))
      .toContain('projectId=beta')
  })

  it('an unpopulated repositories list is reported as a producer gap, never as "no repositories"', () => {
    mocks.live = {
      snap: snapWith([mkProject({ projectId: 'alpha', repositories: [] })]),
      source: 'live', live: true, error: null,
    }
    setUrl('?view=project-detail&projectId=alpha')
    const { container } = render(<App />)
    const text = container.textContent || ''
    expect(text).toContain('生产者缺口')
    expect(text).not.toContain('已投影，结果为空')
    // the four identity questions the snapshot cannot answer are named on the page
    expect(screen.getByText('这个项目关联哪些仓库？')).toBeTruthy()
    expect(screen.getByText('同一仓库的哪个 worktree？')).toBeTruthy()
    expect(screen.getByText('身份是否冲突？')).toBeTruthy()
    expect(screen.getByText('这个项目本身的观测连通状态？')).toBeTruthy()
  })

  it('an empty working-area list says it was aggregated from executions, not that the project has no directory', () => {
    mocks.live = { snap: snapWith([mkProject({ projectId: 'alpha', workingAreas: [] })]), source: 'live', live: true, error: null }
    setUrl('?view=project-detail&projectId=alpha')
    const { container } = render(<App />)
    expect((container.textContent || '')).toContain('没有执行登记过工作区')
  })
})
