import { useState, useEffect, useMemo, useCallback } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopStatusBar } from '@/components/layout/TopStatusBar'
import { CommandPalette, type PaletteItem } from '@/components/ui/command-palette'
import { Drawer } from '@/components/ui/drawer'
import { Toaster, useToaster } from '@/components/ui/toast'
import { UnknownState, OfflineState } from '@/components/ui/states'
import { CompactHUD } from '@/views/CompactHUD'
// 2026-10-24 TRAE 交接包：日常壳（M01–M05）与 HUD 四态，经 ?shell=daily / ?hud=daily 进入。
import { DailyApp } from '@/daily/DailyApp'
import { HudDaily } from '@/daily/HudDaily'
// L10 (2026-09-27): B10 overview landing surface (KPI grid + trends +
// Observer Map + system status + alerts + recent task packs).
import { OverviewView } from '@/views/OverviewView'
import {
  useLiveSnapshot,
  type ThemeMode, type LayoutMode,
} from '@/lib/api'
import { VIEW_REGISTRY, OVERVIEW_ID, OVERVIEW_LABEL } from '@/lib/viewRegistry'
// WUI-01/WUI-02: which lanes are daily destinations, which left the default nav, and why — read from
// the navigation model so the rail, the palette and this shell cannot disagree about the IA.
import { isOnDefaultNav, paletteGroupForLane, OFF_NAV_NOTES } from '@/lib/navigation'
// P1-02: record-level deep links ride the SAME ?view= lane mechanism — a task or
// execution is addressed by ?taskId= / ?executionId=, never by a second router.
import {
  readRecordFocus, writeRecordFocus, EMPTY_FOCUS,
  type RecordFocus,
} from '@/lib/recordFocus'
// REQ-RANGE-20261007: the evidence slice address rides the same single ?view= mechanism; the URL writer has
// to keep it or a refresh silently turns an addressed read into an unaddressed one.
import { EVIDENCE_PARAM_NAMES } from '@/lib/evidenceRange'
import { LaneErrorBoundary } from '@/components/ui/lane-error-boundary'
import { announce } from '@/lib/a11y'
// WUI-14: one IME guard shared by the shell shortcut and the palette.
import { isImeComposing } from '@/lib/keyGuards'
// WUI-03: the palette dimension. Orthogonal to light/dark, URL-carried, and defaulted to the shipped
// colours so opting in is the only way a session sees the 20261009 pack's values.
import { DEFAULT_PALETTE_ID, PALETTE_LABELS, type PaletteId } from '@/theme/tokens'
import { applyPalette, readPaletteParam } from '@/theme/paletteMode'

type ViewId = string

/**
 * An unknown ?view= id used to call setView() from inside render and return
 * null: React warned about updating during render, the user saw one blank
 * frame, and the invalid link was never explained. It now reports the state and
 * offers an explicit way out.
 */
function UnknownLane({ requested, onFallback }: { requested: string; onFallback: () => void }) {
  return (
    <div>
      <UnknownState
        title="未知视图"
        description={`链接要求的 lane「${requested}」不在注册表中，因此未渲染任何内容；地址也没有被静默改写。`}
      />
      <div className="mt-3 flex justify-center">
        <button type="button" className="ghost-btn" onClick={onFallback}>
          返回项目监控
        </button>
      </div>
    </div>
  )
}

// U04/U05: the active view + theme are driven by URL params (?view=, ?theme=,
// ?layout=) so the dashboard is deep-linkable and Full/Compact/Dark/Light is
// real, not a hardcoded class. The default landing view is the Overview panel.
function readInitialView(): ViewId {
  try {
    const s = new URLSearchParams(window.location.search)
    const v = s.get('view')
    if (!v) return OVERVIEW_ID
    // `?view=full|compact` is the legacy Tauri entry contract for the LAYOUT (readInitialLayout), not
    // a lane. Treating it as an unknown lane would turn every saved floating-panel link into a report.
    if (v === 'full' || v === 'compact') return OVERVIEW_ID
    if (VIEW_REGISTRY.some((e) => e.id === v) || v === OVERVIEW_ID) return v
    // WUI-02/WUI-13: an id the registry does not carry is KEPT rather than rewritten. Falling back to
    // the home silently is how a stale link becomes an unexplained landing page — the same rule the
    // record addresses follow (never jump to "the latest" or the nearest same-named object).
    return v
  } catch { /* no URL (SSR/test) -> default */ }
  return OVERVIEW_ID
}

function readInitialTheme(): ThemeMode {
  try {
    const t = new URLSearchParams(window.location.search).get('theme')
    if (t === 'light' || t === 'dark') return t
  } catch { /* ignore */ }
  return 'dark'
}

function readInitialLayout(): LayoutMode {
  try {
    const s = new URLSearchParams(window.location.search)
    const l = s.get('layout')
    if (l === 'full' || l === 'compact') return l
    // B2: the legacy tauri.conf.json entry contract picks the LAYOUT via
    // view=full|compact (not a lane). Honor it as a layout alias so the
    // floating panel (?view=compact) really renders the Compact HUD and old
    // saved links keep working; `layout=` stays the canonical param that the
    // URL write-back persists on navigation.
    const v = s.get('view')
    if (v === 'full' || v === 'compact') return v
  } catch { /* no URL (SSR/test) -> default */ }
  return 'full'
}

// WUI-03: which palette the address asks for. An unrecognised value is the shipped one, not an error and
// not a guess — an old link must keep the colours it was saved with.
function readInitialPalette(): PaletteId {
  try {
    return readPaletteParam(window.location.search)
  } catch { /* no URL (SSR/test) -> default */ }
  return DEFAULT_PALETTE_ID
}

// P1-02: the record a deep link points at, read once from the URL. An id that fails validation is kept
// as a reason to show, not dropped silently — a link that "did nothing" is indistinguishable from a
// broken product unless the product says why.
function readInitialFocus(): { focus: RecordFocus; rejected: string[] } {
  try {
    return readRecordFocus(window.location.search)
  } catch {
    return { focus: EMPTY_FOCUS, rejected: [] }
  }
}

/** Which surface the user is looking at, in the same words the rail uses. Overview is not a registry
 *  entry, so it is named here rather than being reported as an unknown id. */
function viewIdentity(view: ViewId): { label: string; lane: string } {
  const entry = VIEW_REGISTRY.find((e) => e.id === view)
  return entry ? { label: entry.label, lane: entry.lane } : { label: OVERVIEW_LABEL, lane: 'overview' }
}

// WORK-LAB-FRONTEND-TASKPACK-20260930: Control/Observer contract enforcement.
// Per taskpack authority: only Control Surface executes writes (through adapter/service contract); Observer projection never writes. All observer lanes (observer, rules-policy, audit, approvals as read-only projection) stay READ-ONLY; any approve/retry/cancel/rollback/install/apply must be blocked by backend contract and must not be reachable through hidden shortcuts/deep-links/shared components.
export default function App() {
  const [view, setView] = useState<ViewId>(readInitialView)
  const [theme, setTheme] = useState<ThemeMode>(readInitialTheme)
  const [layout, setLayout] = useState<LayoutMode>(readInitialLayout)
  const [palette, setPalette] = useState<PaletteId>(readInitialPalette)
  // P1-02: the focused record (taskId / executionId) and any id the URL carried but the
  // validator refused. Selecting a row in a lane updates this; the URL writer below persists it.
  const [initialFocus] = useState(readInitialFocus)
  const [focus, setFocus] = useState<RecordFocus>(initialFocus.focus)
  // U06/SSE: live snapshot — first poll + server-sent events, no fixed ports.
  const { snap, source, live, error } = useLiveSnapshot()

  // UI_SHELL (20260921): command palette. The rail is the only navigation
  // surface — the shell is desktop-only, so there is no drawer state to hold.
  const [paletteOpen, setPaletteOpen] = useState(false)
  // L10b: B10 global overlays — the right-hand 工作区 / Context drawer and the
  // bottom-right Toast (B10 `.drawer` + `.toast`, 1800ms auto-hide).
  const [workspaceOpen, setWorkspaceOpen] = useState(false)
  const { toasts, toast, dismiss } = useToaster(1800)

  const openPalette = useCallback(() => setPaletteOpen(true), [])
  const closePalette = useCallback(() => setPaletteOpen(false), [])

  // L6 keyboard authority: global Ctrl/Cmd+K toggles the command palette.
  // L10b: Esc closes every B10 overlay in one place (palette → modal handled
  // by the Modal itself → drawer), matching the B10 single-file keydown block.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // WUI-14: while an input method owns the keystroke, this shell has no business acting on it.
      if (isImeComposing(e)) return
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
      if (e.key === 'Escape') {
        setPaletteOpen(false)
        setWorkspaceOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // CommandPalette items = every reachable view (jump = setView) plus the
  // theme/layout actions. Deep-link mechanism (?view=/theme=/layout=) is
  // unchanged — selecting just calls setView, which the existing URL writer
  // (useEffect below) persists.
  //
  // WUI-02: the items are grouped by the navigation model rather than dumped into one 跳转 list, so the
  // palette answers "where is this lane in the product" as well as "how do I get there". The lane list
  // still comes from the registry, which means a lane cannot be forgotten by the palette.
  const paletteItems = useMemo<PaletteItem[]>(() => {
    const viewItems: PaletteItem[] = [
      { id: 'nav-overview', label: OVERVIEW_LABEL, group: paletteGroupForLane(OVERVIEW_ID), run: () => setView(OVERVIEW_ID) },
      ...VIEW_REGISTRY.map((e): PaletteItem => ({
        id: 'nav-' + e.id,
        label: e.label,
        group: paletteGroupForLane(e.id),
        run: () => setView(e.id),
      })),
    ]
    const actions: PaletteItem[] = [
      {
        id: 'act-theme',
        label: theme === 'dark' ? '切换到浅色主题' : '切换到深色主题',
        group: '动作',
        run: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
      },
      {
        id: 'act-layout',
        label: layout === 'full' ? '切换到紧凑布局' : '切换到完整布局',
        group: '动作',
        run: () => setLayout((l) => (l === 'full' ? 'compact' : 'full')),
      },
      {
        // WUI-03: an opt-in palette, worded so the reader knows the shipped colours are not being
        // replaced — they stay what a bare address renders.
        id: 'act-palette',
        label: palette === 'master' ? '切回现行配色（默认）' : '改用母版建议配色（现行值不被覆盖）',
        group: '动作',
        run: () => setPalette((current) => (current === 'master' ? DEFAULT_PALETTE_ID : 'master')),
      },
      {
        id: 'act-workspace',
        label: '打开工作区 / Context',
        group: '动作',
        run: () => setWorkspaceOpen(true),
      },
    ]
    return [...viewItems, ...actions]
  }, [theme, layout, palette])

  // U05/B3: theme is projected through the SAME contract as the pre-render
  // script in index.html — the CSS defines :root (dark default) + html.light
  // and has NO .dark rule, so the old .dark class toggle was a visual no-op.
  // Unify: toggle .light + colorScheme, exactly like index.html does.
  useEffect(() => {
    const root = document.documentElement
    // The pinned skin animates `transition:.2s ease` on the rail rows, and an ease between two real
    // palettes passes through colours nobody chose: nav text was measured at 1.22:1 for up to ~300ms
    // after a switch. A theme change is a state change, not a performance, so it is applied with the
    // transitions held off for exactly the frames the swap needs — hover motion stays animated.
    root.classList.add('theme-instant')
    root.classList.toggle('light', theme === 'light')
    root.style.colorScheme = theme === 'light' ? 'light' : 'dark'
    requestAnimationFrame(() => requestAnimationFrame(() => root.classList.remove('theme-instant')))
  }, [theme])

  // WUI-03: the palette rides the same attribute contract as index.html's pre-render script, and the
  // default REMOVES the attribute instead of writing `worklab` — otherwise the shipped sheets would no
  // longer be the single description of what a default session renders.
  useEffect(() => {
    applyPalette(document.documentElement, palette)
    announce(`配色：${PALETTE_LABELS[palette]}`)
  }, [palette])

  // UI_SHELL (20260921): keep the deep-link (?view=/?theme=/?layout=) in sync
  // so refreshing / sharing a URL preserves the active view + theme + layout.
  // This extends (does not change) the existing read-only deep-link init.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const p = new URLSearchParams()
    if (view !== OVERVIEW_ID) p.set('view', view)
    if (theme !== 'dark') p.set('theme', theme)
    if (layout !== 'full') p.set('layout', layout)
    // WUI-03: the palette is part of what makes an address reproducible, so it survives navigation for
    // the same reason the theme does — and only when it is NOT the default.
    if (palette !== DEFAULT_PALETTE_ID) p.set('palette', palette)
    // B4: keep the validated data-source param (?api=) that the Tauri shell
    // injects — api.ts loadRuntimeDescriptor() reads it at module init, so
    // dropping it on navigation/refresh would silently fall back to the
    // non-authoritative static-preview default. Only a present, non-empty api
    // is preserved; other runtime params are not blindly carried.
    const params = new URLSearchParams(window.location.search)
    const api = params.get('api')
    if (api) p.set('api', api)
    // The shell marker must survive navigation too, or the window controls would
    // vanish on the first lane switch.
    const shell = params.get('shell')
    if (shell) p.set('shell', shell)
    // 2026-10-24 日常壳与 HUD 四态的自有地址参数（?dv/dp/dq/dm/dtool/hs），以及 CL-12
    // 原生窄窗的 surface 标记。漏掉任何一个都会被下面的 replaceState 冲掉——实测过：
    // surface 不被保留时，快照到达后的第一次重渲染就把 150px 窄窗渲染成了专业壳。
    // targets 是 E2 的显示筛选（同一类 omission，同一类后果），必须在名单里。
    // tools 是它的另一维（工具／软件对象），与 dv/dp/dq 同级：三处同步——这里的写回白名单、
    // DailyApp 的 readParams 与 writeParams（以及那份 DAILY_PARAMS 名单），少一处就会冷启动丢参数。
    for (const name of ['dv', 'dp', 'dq', 'dm', 'dtool', 'hs', 'surface', 'di', 'targets', 'tools']) {
      const v = params.get(name)
      if (v) p.set(name, v)
    }
    // The compact HUD's own view state (tab + selected source) is written by
    // CompactHUD itself; this writer must carry it through a theme/layout change
    // instead of silently dropping the face the owner is looking at.
    const hud = params.get('hud')
    if (hud) p.set('hud', hud)
    const agent = params.get('agent')
    if (agent) p.set('agent', agent)
    // P1-02: the focused record survives refresh, back/forward and copy-paste exactly like the lane.
    writeRecordFocus(p, focus)
    // REQ-RANGE-20261007: an addressed evidence slice is the same kind of deep link. It is preserved while
    // the evidence lane is the active one, so a theme/layout toggle cannot silently drop the read the owner
    // is looking at — and it is dropped the moment another lane takes over, because a stale byte interval is
    // not a state worth carrying.
    if (view === 'evidence') {
      const current = new URLSearchParams(window.location.search)
      for (const name of EVIDENCE_PARAM_NAMES) {
        const value = current.get(name)
        if (value !== null && value !== '') p.set(name, value)
      }
    }
    const qs = p.toString()
    const url = window.location.pathname + (qs ? '?' + qs : '')
    window.history.replaceState(null, '', url)
  }, [view, theme, layout, palette, focus])

  const isOverview = view === OVERVIEW_ID

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  const toggleLayout = () => setLayout((l) => (l === 'full' ? 'compact' : 'full'))
  const isCompact = layout === 'compact'

  // U03/WlA11y parity: announce theme transitions to assistive tech (the static
  // web/ surface did this via WlA11y.announce on theme switch).
  useEffect(() => {
    announce(theme === 'dark' ? '已切换为深色主题' : '已切换为浅色主题')
  }, [theme])

  // U03/WlA11y parity: announce data-source transitions (LOADING / LIVE / STALE /
  // OFFLINE) — the load strip on screen says LOADING, so the live region has to
  // say it too or a screen-reader user gets silence during the first fetch.
  useEffect(() => {
    if (!snap && !error) {
      announce('投影加载中，首次快照未到达，数值保持 UNKNOWN')
    } else if (error && !snap) {
      announce(`实时数据不可用，「${viewIdentity(view).label}」显示 OFFLINE（不加载假数据）`)
    } else if (live) {
      announce('已加载实时投影数据')
    } else if (snap && source === 'stale') {
      announce('实时数据不可用，已保留上次良好投影（last-good，标记为 STALE）')
    }
  }, [snap, source, live, error, view])

  const active = viewIdentity(view)
  const mainContent = (
    error && !snap ? (
      <div className="panel mx-auto mt-10 max-w-xl text-center" role="alert">
        <div className="mb-2 text-lg text-error">数据源不可用 ·「{active.label}」</div>
        {/* The named offline affordance, not just prose: this is the one surface
            where the transport is known-failed rather than merely unmeasured, and
            OfflineState is what says so in the same vocabulary the lanes use. It is
            also the only proof a click had a consequence — with one identical card for
            all 22 views the rail reads as dead while it is working. */}
        <OfflineState subject={active.label} />
        <p className="whitespace-pre-wrap text-xs text-muted">{error}</p>
        <p className="mt-3 text-[12px] text-muted">
          保持 UNKNOWN 真相 — 不伪造 Agent / 模型 / 成本 / 资源
        </p>
      </div>
    ) : isOverview ? (
      <OverviewView snap={snap} source={source} live={live} />
    ) : (
      (() => {
        // Single resolution path: every lane, including monitoring/trust/settings,
        // comes from VIEW_REGISTRY. The hardcoded branches that used to sit here
        // won over the registry, so "add a lane by editing only the registry"
        // silently stopped being true.
        const entry = VIEW_REGISTRY.find((e) => e.id === view)
        if (!entry || !entry.component) {
          return <UnknownLane onFallback={() => setView(OVERVIEW_ID)} requested={view} />
        }
        const C = entry.component
        // A lane that left the default rail but is still reachable by deep link says so on arrival.
        // Without the note, an address that renders a working page nobody can click to is indistinguishable
        // from a page that was silently deleted.
        const offNavNote = isOnDefaultNav(view) ? null : OFF_NAV_NOTES[view] ?? null
        return (
          <>
            {offNavNote && (
              <div className="panel mb-3 p-3" role="note" data-testid="off-nav-entry-note">
                <div className="text-[12px] font-semibold text-ink">实验入口：本页不在默认导航里</div>
                <p className="mt-1 text-[12px] text-muted">{offNavNote}</p>
              </div>
            )}
            <C
              snap={snap}
              focus={focus}
              onFocus={setFocus}
              focusRejected={initialFocus.rejected}
              // WUI-12: the settings surface shows and changes the three appearance facts. They are
              // passed rather than re-parsed inside the lane so there is exactly one reader of UI state
              // in this shell; every other lane ignores props it does not declare.
              theme={theme}
              layout={layout}
              palette={palette}
              onTheme={setTheme}
              onLayout={setLayout}
              onPalette={setPalette}
            />
          </>
        )
      })()
    )
  )

  // L10b: the B10 global overlays (palette / workspace drawer / toast) render
  // in BOTH layouts so the Ctrl/Cmd+K contract, the honest toasts and the
  // read-only context drawer never depend on the shell variant.
  const overlays = (
    <>
      <CommandPalette
        open={paletteOpen}
        onClose={closePalette}
        items={paletteItems}
        title="命令面板"
      />
      <Drawer
        open={workspaceOpen}
        onClose={() => setWorkspaceOpen(false)}
        title="工作区 / Context"
      >
        <p className="m-0 text-sm text-muted">
          本地个人研究工作区：{snap ? 'Sidecar v3 快照投影已接入' : '数据源未接入（UNKNOWN）'}。
          Command Palette（Ctrl/Cmd + K）、Drawer、Toast 与 Modal 均可用；
          Observer 严格只读，无访问令牌 / 无锁定 / 无鉴权入口。
        </p>
        <div className="status-stack my-4">
          <span className="tag info">{live ? 'Live Transport' : (snap?.transport.transportState || 'UNKNOWN')}</span>
          <span className="tag ok">Local State</span>
          <span className="tag warn">Read-only</span>
        </div>
        <div className="panel">
          <h3>界面与辅助功能</h3>
          <div className="list">
            <div className="list-item"><span>减少动态效果</span><span className="tag info">遵循系统设置</span></div>
            <div className="list-item"><span>Palette</span><span className="tag info">Ctrl/Cmd + K</span></div>
            <div className="list-item"><span>Snapshot revision</span><span className="tag info">{snap ? String(snap.revision) : 'UNKNOWN'}</span></div>
          </div>
        </div>
      </Drawer>
      <Toaster toasts={toasts} onDismiss={dismiss} />
    </>
  )

  // U05: compact is a DEDICATED HUD — no sidebar, single column, 320px-safe.
  // full keeps the B10 sidebar + multi-panel layout.
  //
  // First-frame loading affordance. It sits ABOVE the lane content rather than
  // replacing it: the B5 rule pins that with no snapshot every KPI renders
  // UNKNOWN and never a fabricated 0, so swapping the content for a skeleton
  // would hide the very state the test defends. The strip answers "is it still
  // fetching?" without touching that discipline.
  const loadingStrip = (!snap && !error) ? (
    <div className="load-strip" role="status">
      投影加载中 · 首次快照未到达，数值保持 UNKNOWN，不预填任何数据
    </div>
  ) : null

  // CL-12 (2026-10-24): the native narrow strip (tauri label=hud, 150×480) is its own
  // surface, not the compact panel squeezed to 150px. Measured: at that width the compact
  // TopStatusBar pushes ten controls past the viewport while `.app{overflow:hidden}` keeps
  // scrollWidth at 150 — a clipped, unreachable control bar. So this frame carries the
  // HUD content only; the tray toggles it and its own header drags it.
  if (typeof window !== 'undefined'
    && new URLSearchParams(window.location.search).get('surface') === 'hud') {
    return (
      <LaneErrorBoundary lane="hud" onReset={() => { window.location.href = '/index.html?surface=hud' }}>
        <HudDaily snap={snap} nativeStrip />
      </LaneErrorBoundary>
    )
  }

  if (isCompact) {
    return (
      <div data-layout={layout} className="app app-compact">
        <div className="ambient" aria-hidden="true" />
        <div className="grid-bg" aria-hidden="true" />
        <main className="main">
          <TopStatusBar
            snap={snap}
            source={source}
            live={live}
            error={error}
            theme={theme}
            layout={layout}
            onCycleTheme={toggleTheme}
            onCycleLayout={toggleLayout}
            onOpenSearch={openPalette}
            onOpenDrawer={() => setWorkspaceOpen(true)}
            onNotify={() => toast({ title: '暂无新的通知', variant: 'info' })}
          />
          {loadingStrip}
          <section className="content" id="content">
            <LaneErrorBoundary lane="compact" onReset={() => setLayout('full')}>
              {new URLSearchParams(window.location.search).get('hud') === 'daily'
                ? <HudDaily snap={snap} />
                : <CompactHUD snap={snap} live={live} error={error} />}
            </LaneErrorBoundary>
          </section>
        </main>
        {overlays}
      </div>
    )
  }

  // 2026-10-24：桌面主窗口入口已切到日常壳。入口由 `surface=daily` 声明，`shell=tauri`
  // 保留为无边框壳的自声明（`apps/observer/tests/test_desktop_component_contract.js` 钉着：
  // 前端没有别的确定性办法知道自己是桌面入口）。浏览器侧 `?shell=daily` 与
  // `?view=` 专业深链都不受影响，31 个入口原样可达。
  const entryParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null
  if (entryParams
    && (entryParams.get('shell') === 'daily' || entryParams.get('surface') === 'daily')) {
    return (
      <LaneErrorBoundary lane="daily" onReset={() => { window.location.href = '/index.html?surface=daily' }}>
        <DailyApp snap={snap} live={live} error={error} theme={theme} onTheme={setTheme} />
      </LaneErrorBoundary>
    )
  }

  return (
    <div data-layout={layout} className="app">
      {/* L10 B10 `.ambient` + `.grid-bg`: the 32px grid backdrop (radial fade
          mask) + floating glow blobs — the "faint blue ambient light" the B10
          spec locks in (D-08: B10 beats the §八 "no glassmorphism flood"
          reading; the glow is the requested system state language). Both are
          the verbatim B10 elements: `.ambient` carries the `::before/::after`
          blobs, `.grid-bg` the grid. */}
      <div className="ambient" aria-hidden="true" />
      <div className="grid-bg" aria-hidden="true" />
      <Sidebar
        activeView={view}
        onSelect={(id) => {
          setView(id)
          // A lane switch was silent for assistive tech: focus stayed on the
          // rail and nothing announced the new context.
          const label = VIEW_REGISTRY.find((e) => e.id === id)?.label ?? id
          announce('已进入 ' + label)
        }}
      />
      <main className="main">
        <TopStatusBar
          snap={snap}
          source={source}
          live={live}
          error={error}
          theme={theme}
          layout={layout}
          onCycleTheme={toggleTheme}
          onCycleLayout={toggleLayout}
          onOpenSearch={openPalette}
          onOpenDrawer={() => setWorkspaceOpen(true)}
          onNotify={() => toast({ title: '暂无新的通知', variant: 'info' })}
        />
        {loadingStrip}
        <section className="content" id="content">
          <LaneErrorBoundary lane={view} onReset={() => setView(OVERVIEW_ID)}>
            {mainContent}
          </LaneErrorBoundary>
        </section>
      </main>
      {overlays}
    </div>
  )
}
