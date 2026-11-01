// 2026-10-26 E1 · 主题控件的诚实声明。
// 这句话有两个历史状态，都必须被测试钉住，否则下一次回归可以任选一边说谎：
//   · 2026-10-25 实测：?theme=light 确实写进 html.class，但 src/daily/DailyApp.tsx / HudDaily.tsx /
//     DailyChrome.tsx 里 `var(--)` 出现 0 次、色值写死，窄窗截图在两个主题下逐字节相同（md5 3f53ee67…）。
//     owner 当时的决定是「如实说明，不假装切换」，所以屏幕上写着「这一屏暂时不跟着变」。
//   · 2026-10-27 接线到 --daily-* 主题令牌（src/index.css 的 :root 与 html.light 各一套值，
//     src/theme/tokens.ts 的 DAILY_TOKENS 记录同一份值，src/daily/dailyThemeTokens.contract.test.ts
//     比对镜像、要求浅色的每个值都不等于深色、并按 WCAG 实测两主题）。那句否认生效的免责声明从此变成
//     反向说谎，于是它改成本文件断言的样子：说清机制、说清证据、并且仍然不许把范围夸大或缩小。
// 两侧都钉：两张桌面表面必须带这句「已生效」的说明并且说得出令牌；专业投影壳继续不带任何限定语
// ——只测一边，就等于允许把免责声明或邀功声明盖满整个产品。
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, act, fireEvent } from '@testing-library/react'

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  // 本文件测的是「主题这句话怎么说、颜色从哪儿取」，与快照内容无关：给空快照，两侧表面都按无数据处理。
  return { ...actual, useLiveSnapshot: () => ({ snap: null, source: 'stale', live: false, error: null, dataUpdatedAt: 0 }) }
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
import { HudDaily } from '@/daily/HudDaily'
import { THEME_HONESTY_ID_DAILY, THEME_HONESTY_ID_HUD, T } from '@/daily/DailyChrome'

const NOTE = '[data-testid="theme-honesty-note"]'

function setUrl(search: string) {
  window.history.replaceState(null, '', `/index.html${search}`)
}
function notes(): Element[] {
  return Array.from(document.querySelectorAll(NOTE))
}

beforeEach(() => { setUrl('?shell=daily&dv=settings') })
afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', window.location.pathname)
})

describe('E1 · 日常壳的主题声明说的是已生效', () => {
  it('声明是画在屏幕上的文字，不是 hover 才出现的信息，并且承认主题已经作用于本视图', async () => {
    const { container } = render(<App />)
    await act(async () => { await Promise.resolve() })
    const daily = notes()
    expect(daily).toHaveLength(1)
    const note = daily[0] as HTMLElement
    expect(note.getAttribute('data-surface')).toBe('daily')
    expect(note.getAttribute('id')).toBe(THEME_HONESTY_ID_DAILY)
    // 2026-10-27 起这个属性写的是 applied：接线前它是 not-applied，配合当时那句免责声明。
    // 属性与句子必须一起翻，只改文字不改属性（或反之）在这里都会红。
    expect(note.getAttribute('data-theme-honesty')).toBe('applied')
    expect((note.textContent ?? '').trim().length).toBeGreaterThan(0)
    expect(container.querySelector('#daily-content')).toBeTruthy()
  })

  it('键盘可达：声明本身可聚焦，主题控件用 aria-describedby 指向它，title 不再否认生效', async () => {
    render(<App />)
    await act(async () => { await Promise.resolve() })
    const note = screen.getByTestId('theme-honesty-note') as HTMLElement
    expect(note.getAttribute('tabindex')).toBe('0')
    expect(note.getAttribute('role')).toBe('note')
    note.focus()
    expect(document.activeElement).toBe(note)

    const control = screen.getByTestId('daily-theme-toggle')
    expect(control.getAttribute('aria-describedby')).toBe(THEME_HONESTY_ID_DAILY)
    // 说明目标必须真的存在，否则 aria-describedby 是一句空话。
    expect(document.getElementById(THEME_HONESTY_ID_DAILY)).toBe(note)
    const title = control.getAttribute('title') ?? ''
    expect(title).toContain('本视图的配色随之换成')
    expect(title).not.toContain('不随之换色')
    // 悬停不是唯一通道：不派发任何鼠标事件也能拿到这句话。
    expect(note.getAttribute('title')).toContain('专业投影壳')
  })

  it('措辞：说清机制与证据，不认领没做的东西，也不反向说谎', () => {
    render(<App />)
    const text = (screen.getByTestId('theme-honesty-note').textContent ?? '')
    // 本表面的事实：颜色取自令牌，令牌有深浅两值。
    expect(text).toContain('--daily-')
    expect(text).toContain('html.light')
    expect(text).toContain('换成浅色那一套值')
    // 证据是可跑的，不是形容词。
    expect(text).toContain('dailyThemeTokens.contract.test.ts')
    expect(text).toContain('text_legibility_via_cdp.py')
    expect(text).toContain('4.5:1')
    // 可选母版配色与深浅正交，且不覆盖这套默认值。
    expect(text).toContain('?palette=master')
    expect(text).toContain('不覆盖这套默认值')
    // 不夸大也不缩小范围：专业壳确实会换，HUD 也确实会换。
    expect(text).toContain('专业投影壳')
    expect(text).toContain('同样生效')
    expect(text).toContain('HUD 窄窗')
    // 反向说谎的两条老话与两条新话都不能出现。
    expect(text).not.toContain('只有深色')
    expect(text).not.toContain('不支持浅色')
    expect(text).not.toContain('暂时不跟着变')
    expect(text).not.toContain('不会把本视图变成浅色')
    expect(text).not.toContain('按固定深色值写死')
    // 控件的标签现在可以说「当前是深色」：它不再只是一个地址参数，画面确实是这样。
    const label = screen.getByTestId('daily-theme-toggle').textContent ?? ''
    expect(label).toBe('页面主题：深色')
    expect(label).not.toContain('当前地址值')
  })

  it('地板：这句话仍用日常壳唯一的 12px 文字档，而且它自己的颜色也来自令牌', () => {
    render(<App />)
    const note = screen.getByTestId('theme-honesty-note') as HTMLElement
    expect(note.className).toContain('text-xs')
    expect(note.className).not.toMatch(/text-\[1[01]px\]|text-\[9px\]|text-\[10px\]/)
    // 声明本身不能是一块钉死的深色孤岛：它换上了令牌，才谈得上「本视图跟随主题」。
    expect(note.className).toContain('var(--daily-dim)')
    expect(note.className).toContain('var(--daily-bg)')
    expect(note.className).not.toMatch(/#[0-9a-fA-F]{3,8}/)
  })

  it('DOM 接线证据：这一屏的背景、正文与控件都引用令牌，而不是靠句子自称', () => {
    const { container } = render(<App />)
    const shell = container.querySelector('[data-shell="daily"]') as HTMLElement
    expect(shell.className).toContain('bg-[color:var(--daily-bg)]')
    expect(shell.className).toContain('text-[color:var(--daily-text)]')
    // 顶栏与左栏是另两个表面区域，各自也必须是令牌引用（写死时它们是纯色块）。
    const topbar = container.querySelector('[data-landmark="topbar"]') as HTMLElement
    expect(topbar.getAttribute('style') ?? '').toContain('var(--daily-shell)')
    const rail = container.querySelector('[data-landmark="rail"]') as HTMLElement
    expect(rail.getAttribute('style') ?? '').toContain('var(--daily-line)')
    // 共享调色板对象不再持有任何字面量：它只有 var() 引用，值一律在样式表里。
    const values = Object.values(T)
    expect(values.length).toBeGreaterThanOrEqual(19)
    expect(values.filter((v) => !v.startsWith('var(--daily-'))).toEqual([])
  })
})

describe('E1 · HUD 窄窗带同一句已生效的说明', () => {
  it('设置面板里的声明说的是窄窗自己接了令牌，且窄窗背景是令牌引用', () => {
    setUrl('?surface=hud')
    render(<HudDaily snap={null} nativeStrip />)
    // 默认不展开设置面板时，窄窗里没有主题控件，也就不该有说明占位。
    expect(notes()).toHaveLength(0)
    fireEvent.click(screen.getByLabelText('HUD 设置'))
    const note = screen.getByTestId('theme-honesty-note') as HTMLElement
    expect(note.getAttribute('data-surface')).toBe('hud')
    expect(note.getAttribute('id')).toBe(THEME_HONESTY_ID_HUD)
    expect(note.getAttribute('tabindex')).toBe('0')
    expect(note.getAttribute('data-theme-honesty')).toBe('applied')
    const text = note.textContent ?? ''
    expect(text).toContain('这个窄窗接在同一套 --daily-* 主题令牌上')
    expect(text).toContain('html.light')
    // 反向说谎：不能说窄窗仍然不换色，也不能把它说成整个产品只有深色。
    expect(text).not.toContain('按固定的深色值绘制')
    expect(text).not.toContain('暂时不会改变它的配色')
    expect(text).not.toContain('整个应用只有深色')
    // 句子之外要有像素来源的证据：窄窗根元素用令牌上色。
    const frame = document.querySelector('[data-hud-frame]') as HTMLElement
    expect(frame.className).toContain('bg-[color:var(--daily-bg)]')
    expect(frame.className).toContain('text-[color:var(--daily-text)]')
  })
})

describe('E1 · 专业投影壳不需要这句话', () => {
  it('专业壳（默认入口）的主题控件存在，且没有任何诚实声明', () => {
    setUrl('')
    render(<App />)
    const control = screen.getByRole('button', { name: /切换到浅色主题/ })
    expect(notes()).toHaveLength(0)
    // 专业壳的 html.class 真的跟着 ?theme= 走（App.behavior.test.tsx 钉着），所以这里不加限定语。
    expect(control.getAttribute('aria-describedby')).toBeNull()
    expect((control.getAttribute('title') ?? '')).toBe('浅色主题')
  })

  it('专业隐私与采集页（?view=privacy）的 data-setting=theme 控件同样不带免责声明', () => {
    setUrl('?view=privacy')
    render(<App />)
    const control = document.querySelector('[data-setting="theme"]')
    expect(control).toBeTruthy()
    expect((control as HTMLElement).textContent).toContain('切到浅色')
    expect(control?.getAttribute('aria-describedby')).toBeNull()
    expect(notes()).toHaveLength(0)
    // 也不带邀功版：这句话只属于曾经需要它的两张桌面表面。
    expect(document.querySelector('[data-theme-honesty]')).toBeNull()
  })
})
