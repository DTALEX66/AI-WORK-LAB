// STITCH 交接包（references/main/*.png + DESIGN.md，2026-10-24）里日常壳的共享图元：
// 顶栏（logo 瓦片 / 居中搜索 + Ctrl+K 芯片 / HUD 按钮 / 无边框窗口控制）、左栏
// （WORKSPACE 标签 + 三项线性图标 + 底部设置与状态胶囊），以及卡片族图元。
// 复刻的是**布局与节奏**；槽位里出现的每个数都来自真实快照字段，缺字段就写 UNKNOWN，
// 需要执行动作的槽位保留视觉但禁用并写明被挡的效果（Observer 严格只读）。
import { ReactNode, useCallback, useEffect, useState } from 'react'
import {
  ChevronDown, Clock, Command, FolderOpen, Lightbulb, Link2, Maximize2, Minimize2,
  Plug, Search, Settings, ShieldCheck, SquareArrowOutUpRight, Wrench, X,
} from 'lucide-react'
import { WindowControls } from '@/components/layout/WindowControls'
import { dailyVar, type DailyRole } from '@/theme/tokens'

/**
 * The palette this shell paints with, 2026-10-27. Every value is a `var(--daily-<role>)` reference and
 * nothing else: the numbers live in src/index.css (`:root` + `html.light`, recorded machine-readably by
 * DAILY_TOKENS in src/theme/tokens.ts), so this shell repaints when the theme class changes instead of
 * carrying 144 hex literals that made `?theme=light` a no-op on the one screen the owner actually looks
 * at. The role names describe what they paint (layers, ink weights, status roles), never a hue.
 * `src/daily/dailyThemeTokens.contract.test.ts` fails if a hex or a Tailwind named colour comes back.
 */
export const T: Record<DailyRole, string> = {
  bg: dailyVar('bg'), shell: dailyVar('shell'), surface: dailyVar('surface'),
  line: dailyVar('line'), text: dailyVar('text'), dim: dailyVar('dim'),
  disabledText: dailyVar('disabledText'), accent: dailyVar('accent'),
  onAccent: dailyVar('onAccent'), warnText: dailyVar('warnText'),
  warnMark: dailyVar('warnMark'), warnLine: dailyVar('warnLine'),
  decisionMark: dailyVar('decisionMark'), ok: dailyVar('ok'),
  accentTint: dailyVar('accentTint'), accentTintLine: dailyVar('accentTintLine'),
  warnTint: dailyVar('warnTint'), warnTintLine: dailyVar('warnTintLine'),
  scrim: dailyVar('scrim'),
}

export type DailyNav = 'home' | 'issues' | 'tools' | 'governance'

/**
 * The daily shell's first-level population, in one declaration.
 *
 * It used to be a literal `['home','issues','tools']` inside the rail, with the labels spelled out in a
 * ternary and the URL parser carrying its own hand-written chain of `dvRaw === …` comparisons. Adding a
 * screen therefore meant editing three places that never check each other, and the settings page kept a
 * fourth list of links to the professional views — which is how a surface ends up with two entries for
 * one thing. `Rail`, `readParams` and the settings link list all read this table now, and a test asserts
 * the real-browser gate's expected labels match it.
 *
 * `governance` is the one entry D2 adds, and its label is the wording the sign-off pack
 * (`.project-local/runs/d2/D2-SIGNOFF-PACK.md` §1/§3) settled on.
 */
export const DAILY_NAV: ReadonlyArray<{ id: DailyNav; label: string }> = [
  { id: 'home', label: '项目' },
  { id: 'issues', label: '问题与经验' },
  { id: 'tools', label: '我的工具' },
  { id: 'governance', label: '治理与诊断' },
]

// ── E1 · 主题生效声明 ──────────────────────────────────────────────────────
// 这段文字有历史，改它要如实。2026-10-25 实测的是相反的事实：?theme=light 确实写进 html.class
// （App.tsx 的主题效果与 index.html 预渲染同一套契约），但日常壳与 HUD 窄窗里 `var(--)` 出现 0 次、
// 十六进制值写死，所以窄窗截图在两个主题下逐字节相同（md5 3f53ee67…），当时唯一的诚实做法是把
// 「这一屏暂时不跟着变」写在屏幕上。
// 2026-10-27 接线完成：两张面的每一层颜色都改从 --daily-* 主题令牌取值，浅色那套值在 index.css 的
// html.light 与 tokens.ts 的 DAILY_TOKENS.light 里成对声明，于是那句免责声明会变成反向说谎——它否认
// 一件现在真的发生了的事。措辞因此改成如实描述生效机制与其证据；同一约束仍然成立：不许反向说谎，
// 不得写成「本产品只有深色」，也不得把专业投影壳说成不换色。
export const THEME_HONESTY_ID_DAILY = 'daily-theme-honesty-note'
export const THEME_HONESTY_ID_HUD = 'hud-theme-honesty-note'

export const THEME_HONESTY_TEXT =
  '这个按钮改 html 上的主题类，也把 ?theme= 写进地址；日常壳的每一层颜色都从 --daily-* 主题令牌取值——'
  + '深色值写在 src/index.css 的 :root、浅色值写在同一文件的 html.light，src/theme/tokens.ts 的 DAILY_TOKENS'
  + ' 是同一份记录的机器可读副本——所以切到浅色时这一屏确实换成浅色那一套值，HUD 窄窗（?surface=hud）接的是同一套令牌。'
  + '这句不是自我声明：src/daily/dailyThemeTokens.contract.test.ts 逐个令牌比对样式表与记录、要求浅色的每个值都'
  + '不等于它的深色伙伴，并按 WCAG 实测两个主题里每一对「文字与它自己的底」（正文 4.5:1；被禁用的标签这里不豁免，'
  + '固定皮肤把它画在 55% 不透明度上，仍要求 3.0:1）；'
  + 'scripts/audit/text_legibility_via_cdp.py --shell-surfaces 再在真实浏览器里把深浅两个主题各扫一遍。'
  + '母版配色（?palette=master，WUI-03）是与深浅正交的可选主题：它不覆盖这套默认值，选了它这两张面也跟着换成母版值。'
  + '专业投影壳（?view=…）的主题切换同样生效，用的是 --color-* 那一套令牌。'

export const THEME_HONESTY_TEXT_HUD =
  '这个窄窗接在同一套 --daily-* 主题令牌上：?theme= 写进 html 的主题类后，这一屏每一层颜色都换成 '
  + 'src/index.css 里 html.light 记录的浅色值。完整说明在主窗口设置页。'

/**
 * The statement about how the theme control behaves on this surface, painted (never hover-only) and
 * keyboard reachable (tabIndex 0 + role=note) so it is not colour-only or tooltip-only information. The
 * control it describes points here with aria-describedby, and `title` repeats it for a pointer reader.
 *
 * It paints with the same two tokens as the rest of the shell (dim on bg, the lead-in in text on bg),
 * so it inherits whatever theme is in effect instead of being a fixed-dark island — and it clears the
 * floor by construction: dim on the daily ground measured 8.53:1 dark / 5.83:1 light, the lead-in ink
 * 16.23:1 / 15.19:1, both at text-xs = 12px, recomputed from the token record itself by
 * src/daily/dailyThemeTokens.contract.test.ts and re-measured in the browser by the legibility gate.
 * No new size, no new colour pair.
 */
export function ThemeHonestyNote(props: { id: string; surface: 'daily' | 'hud' }) {
  const text = props.surface === 'hud' ? THEME_HONESTY_TEXT_HUD : THEME_HONESTY_TEXT
  return (
    <p id={props.id} role="note" tabIndex={0} title={text}
      data-testid="theme-honesty-note" data-theme-honesty="applied"
      data-surface={props.surface}
      className="mt-2 rounded border border-[color:var(--daily-line)] bg-[color:var(--daily-bg)] p-2 text-xs leading-relaxed text-[color:var(--daily-dim)]">
      <span className="font-semibold text-[color:var(--daily-text)]">主题在本视图生效：</span>{text}
    </p>
  )
}

const NAV_ICONS: Record<DailyNav, typeof FolderOpen> = {
  home: FolderOpen, issues: Lightbulb, tools: Wrench, governance: ShieldCheck,
}

export function isNativeShell(): boolean {
  if (typeof window === 'undefined') return false
  try {
    if (new URLSearchParams(window.location.search).get('shell') === 'tauri') return true
  } catch { /* no URL */ }
  return '__TAURI_INTERNALS__' in window || '__TAURI__' in window
}

/** A rounded icon tile with the subject's own initials — derived from a real name, never a made-up glyph. */
export function IconTile({ label, size = 36, tone = 'shell' }: { label: string; size?: number; tone?: 'shell' | 'surface' }) {
  const initials = label.trim().slice(0, 2).toUpperCase()
  return (
    <span aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-lg border ${tone === 'shell' ? 'bg-[color:var(--daily-surface)]' : 'bg-[color:var(--daily-shell)]'} font-semibold`}
      style={{ width: size, height: size, borderColor: T.line, color: T.accent, fontSize: Math.max(12, size * 0.34) }}>
      {initials}
    </span>
  )
}

// The reference's status vocabulary, one token per status rather than one hex per status: the dot keeps
// its meaning when the theme changes (需要关注 stays an amber-family mark, 已完成 a green-family one).
const PILL_TONE: Record<string, string> = {
  正在推进: T.accent, 需要关注: T.warnMark, 等待你决定: T.decisionMark, 已完成: T.ok, 暂停: T.dim,
}

/** The reference's "● 状态" capsule: dot + label inside a bordered pill. */
export function StatusPill({ status }: { status: string }) {
  const color = PILL_TONE[status] ?? T.dim
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs"
      style={{ borderColor: T.line, background: T.surface, color: T.text }}>
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {status}
    </span>
  )
}

export function Chip({ children, tone = 'neutral' }: { children: ReactNode; tone?: 'neutral' | 'accent' | 'warn' }) {
  const style = tone === 'accent'
    ? { borderColor: T.accentTintLine, background: T.accentTint, color: T.accent }
    : tone === 'warn'
      ? { borderColor: T.warnTintLine, background: T.warnTint, color: T.warnText }
      : { borderColor: T.line, background: T.surface, color: T.dim }
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-0.5 text-xs" style={style}>
      {children}
    </span>
  )
}

/** Section heading with the reference's accent left bar. */
export function SectionTitle({ children, right, rightTone = 'text' }: {
  children: ReactNode; right?: ReactNode; rightTone?: 'text' | 'chip'
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
      <h2 className="flex shrink-0 items-center gap-2 text-sm font-semibold" style={{ color: T.text }}>
        <span aria-hidden="true" className="h-4 w-[3px] rounded-full" style={{ background: T.accent }} />
        {children}
      </h2>
      {right ? (rightTone === 'chip' ? (
        <span className="rounded-full border px-2 py-0.5 text-xs"
          style={{ borderColor: T.line, color: T.dim }}>{right}</span>
      ) : (
        <span className="min-w-0 text-right text-xs" style={{ color: T.dim }}>{right}</span>
      )) : null}
    </div>
  )
}

export function MetaItem({ icon, children }: { icon?: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: T.dim }}>
      {icon ?? null}{children}
    </span>
  )
}

export const TimeIcon = () => <Clock size={13} aria-hidden="true" />

/**
 * A slot the reference gives to an action the Observer must not take (launch a tool, register a
 * project). The visual stays so the layout is a true 1:1, but the control is disabled and names
 * the blocked effect instead of pretending to work.
 */
export function DisabledAction({ label, reason, primary = false, icon }: {
  label: string; reason: string; primary?: boolean; icon?: ReactNode
}) {
  return (
    <span className="inline-flex flex-col items-end gap-1">
      <button type="button" disabled aria-disabled="true" title={reason}
        className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm opacity-60"
        style={primary
          ? { borderColor: T.line, background: T.surface, color: T.disabledText }
          : { borderColor: T.line, background: T.shell, color: T.disabledText }}>
        {icon ?? null}{label}
        {icon ? null : <SquareArrowOutUpRight size={13} aria-hidden="true" />}
      </button>
      {/* the explanation is painted at full opacity, so it owes the body-text ratio, not the 3:1
          floor of the dimmed control above it */}
      <span className="text-xs" style={{ color: T.dim }}>{reason}</span>
    </span>
  )
}

/** Toggle the native HUD strip. Under a browser entry there is no window to show, so it says so. */
function useHudToggle() {
  const native = isNativeShell()
  const [why, setWhy] = useState<string | null>(null)
  const toggle = useCallback(async () => {
    if (!native) { setWhy('浏览器入口没有原生窄窗；桌面主窗口或 HUD 窗口内可用') ; return }
    try {
      const { invoke } = await import('@tauri-apps/api/core')
      await invoke('show_hud')
      setWhy(null)
    } catch {
      setWhy('桌面壳未提供窄窗切换命令')
    }
  }, [native])
  return { native, why, toggle }
}

export function TopBar({ query, onQuery, hudHint }: {
  query: string; onQuery: (v: string) => void; hudHint: string | null
}) {
  const { toggle, why } = useHudToggle()
  useEffect(() => {
    if (!hudHint) return
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && (e.key === 'h' || e.key === 'H')) { e.preventDefault(); void toggle() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hudHint, toggle])
  const blocked = why ?? hudHint
  return (
    <header data-landmark="topbar" data-tauri-drag-region
      className="flex h-[52px] shrink-0 items-center gap-4 border-b px-4"
      style={{ borderColor: T.line, background: T.shell }}>
      <div className="flex items-center gap-2.5">
        <span aria-hidden="true" className="daily-brand-mark" data-brand-mark="work-lab" />
        <span className="text-sm font-semibold tracking-wide" style={{ color: T.text }}>WORK-LAB</span>
      </div>
      <div className="relative mx-auto flex w-full max-w-[560px] items-center">
        <Search size={14} aria-hidden="true" className="pointer-events-none absolute left-3" style={{ color: T.dim }} />
        <input
          type="search" id="daily-global-search" value={query} onChange={(e) => onQuery(e.target.value)}
          aria-label="全局搜索" placeholder="快速导航或全局搜索…"
          className="h-8 w-full rounded-md border pl-9 pr-16 text-sm outline-none"
          style={{ borderColor: T.line, background: T.bg, color: T.text }}
        />
        <span className="pointer-events-none absolute right-3 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs"
          style={{ borderColor: T.line, background: T.surface, color: T.dim }}>
          <Command size={11} aria-hidden="true" />K
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => void toggle()} title={blocked ?? '显示／隐藏 HUD 窄窗'}
          className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs"
          style={{ borderColor: T.line, background: T.surface, color: T.text }}>
          <Plug size={13} aria-hidden="true" style={{ color: T.accent }} />
          HUD<span style={{ color: T.dim }}>Alt+H</span>
        </button>
      </div>
      <WindowControls />
    </header>
  )
}

export function Rail({ view, onNavigate, transportLabel, transportTone }: {
  view: DailyNav | 'settings'; onNavigate: (v: DailyNav | 'settings') => void
  transportLabel: string; transportTone: 'live' | 'unknown' | 'offline'
}) {
  const dot = transportTone === 'live' ? T.ok : transportTone === 'offline' ? T.warnMark : T.dim
  return (
    <nav aria-label="主导航" data-landmark="rail"
      className="flex w-[176px] shrink-0 flex-col border-r px-3 py-4"
      style={{ borderColor: T.line, background: T.shell }}>
      <span aria-hidden="true" className="daily-rail-brand" data-brand-mark="work-lab" />
      <div className="mb-3 px-2 text-xs uppercase tracking-wider" style={{ color: T.dim }}>工作区</div>
      <ul className="space-y-1">
        {DAILY_NAV.map(({ id, label }) => {
          const Icon = NAV_ICONS[id]
          const active = view === id
          return (
            <li key={id}>
              <button type="button" onClick={() => onNavigate(id)} aria-current={active ? 'page' : undefined}
                className="relative flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm"
                style={active
                  ? { background: T.surface, color: T.accent }
                  : { color: T.dim }}>
                {active && (
                  <span aria-hidden="true" className="absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full"
                    style={{ background: T.accent }} />
                )}
                <Icon size={15} aria-hidden="true" />
                {label}
              </button>
            </li>
          )
        })}
      </ul>
      <div className="mt-auto">
        <button type="button" onClick={() => onNavigate('settings')} aria-current={view === 'settings' ? 'page' : undefined}
          className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm"
          style={view === 'settings' ? { background: T.surface, color: T.accent } : { color: T.dim }}>
          <Settings size={15} aria-hidden="true" />设置
        </button>
        <div data-landmark="transport"
          className="mt-3 flex items-center justify-between gap-2 whitespace-nowrap rounded-md border px-2 py-1.5 text-xs"
          style={{ borderColor: T.line, background: T.bg, color: T.dim }}>
          <span className="inline-flex min-w-0 items-center gap-1.5 truncate">
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: dot }} />
            {transportLabel}
          </span>
          <span className="shrink-0 uppercase tracking-wide">{transportTone === 'live' ? 'LIVE' : transportTone === 'offline' ? 'OFFLINE' : 'UNKNOWN'}</span>
        </div>
      </div>
    </nav>
  )
}

export { ChevronDown, Link2, Maximize2, Minimize2, X }
