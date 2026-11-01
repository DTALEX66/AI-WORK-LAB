// HUD 四态（H01 常驻窄面板 / H02 悬停摘要 / H03 单工具详情 / H04 外部回复提醒）。
// 一比一复刻 references/hud/H01..H04.png 的结构：notch 拖动把手、圆形额度槽位 + 右对齐数值列、
// 页脚状态点 + 齿轮。快照没有额度/余额/重置时间/用量序列：槽位保留，值一律 UNKNOWN，
// 环画成无进度，不画百分比、不画柱状图（DESIGN.md 与项目真值规则同时要求）。
// 原生窄窗宽 150px：展开态（H02/H03/H04）在窄窗里纵向堆叠在条体下方；440px 面板里按参考左右并排。
// 面板里的行是 agent 运行时，不是客户端总表：按 capability matrix 声明的 role 分人口，被分出去的数量要说明。
import { useMemo, useState } from 'react'
import type { SnapshotV3 } from '@/types'
import { fmtTimestamp } from '@/lib/api'
import { Settings, Sparkles } from 'lucide-react'
import { ThemeHonestyNote, THEME_HONESTY_ID_HUD, T } from '@/daily/DailyChrome'
import { AgentMark, isMonitoredAgentRole } from '@/daily/agentMarks'
import { readTargetSelection } from '@/daily/dailyData'

export type HudState = 'h01' | 'h02' | 'h03' | 'h04'

// LINE/ACCENT stay as local aliases so the strip reads the same as before, but they now carry the
// theme's own var() references: this window used to be drawn from literals of its own, which is why
// its screenshot was byte-identical under ?theme=dark and ?theme=light.
const LINE = T.line
const ACCENT = T.accent
const DIM = T.dim

/** One row of the strip: the adapter card's own identity, plus the counts the exclusion line needs. */
type HudAgent = { id: string; name: string }

/**
 * Which adapter cards the HUD monitors, and what it had to leave out.
 *
 * The strip used to map over every card in the snapshot, which is how a repository host ended up in an
 * "agent monitor". `role` is the capability matrix's own declaration, so the partition is made from a
 * statement the operator has to argue with in that file. A card with no declared role is counted separately:
 * dropping it silently would turn a source gap into "this client is not an agent", which is a different claim
 * than the data supports.
 */
function hudAgents(snap: SnapshotV3 | null): {
  agents: HudAgent[]
  excludedNonAgent: number
  excludedNoRole: number
} {
  const cards = snap?.adapterCapabilities ?? []
  const agents: HudAgent[] = []
  let excludedNonAgent = 0
  let excludedNoRole = 0
  for (const card of cards) {
    if (card.role === undefined || card.role === 'UNKNOWN') {
      excludedNoRole += 1
    } else if (!isMonitoredAgentRole(card.role)) {
      excludedNonAgent += 1
    } else {
      agents.push({ id: card.clientId, name: card.displayName || card.clientId })
    }
  }
  return { agents, excludedNonAgent, excludedNoRole }
}

/**
 * The reference draws a progress ring per tool. The snapshot carries no quota field, so the ring is
 * rendered as a full, un-filled track: the slot exists, the value says UNKNOWN, and no arc implies a
 * percentage nobody measured.
 *
 * The ring's colour is a theme token painted through `style`, and `data-ring-role` says which role it
 * plays. The narrow-strip gate reads both: the role to find the hovered row, the RESOLVED stroke to
 * prove the lit ring is a different painted colour from the idle ones in whichever theme is live
 * (an attribute holding a literal amber could no longer be compared against a token value).
 */
function RingSlot({ tool, active = false }: { tool: HudAgent; active?: boolean }) {
  return (
    <span className="flex items-center justify-between gap-2">
      <span className="relative inline-flex h-9 w-9 shrink-0 items-center justify-center">
        <svg viewBox="0 0 36 36" width="36" height="36" aria-hidden="true">
          {/* 参考的 H02 给被悬停那一行亮琥珀环，值仍按真实数据走 UNKNOWN，不跟着变绿变高。 */}
          <circle cx="18" cy="18" r="15" fill="none" data-ring-role={active ? 'active' : 'idle'}
            style={{ stroke: active ? T.warnMark : LINE }} strokeWidth={active ? 3.5 : 3} />
        </svg>
        {/* The reference put a per-tool figure here. It used to be the first two letters of the display
            name, which made every row in the strip look like the same grey pill; the figure is now the
            agent's own mark, keyed by the software id the registry knows. */}
        {/* The figure is the only identity cue this row paints — 150px has no room for the name, and the
            h02 capsule that spells it out only exists while a pointer is on the row. So the name travels
            as the accessible name of the figure instead: a decorative glyph with nothing beside it would
            leave the row unlabelled for anyone not reading the pixels. */}
        <span className="absolute inset-[9px]" data-hud-agent={tool.id} role="img" aria-label={tool.name}
          style={{ color: active ? T.warnText : ACCENT }}>
          <AgentMark softwareId={tool.id} />
        </span>
      </span>
      <span className="text-xs" style={{ color: DIM }}>额度 UNKNOWN</span>
    </span>
  )
}

function readHs(): HudState {
  try {
    const s = new URLSearchParams(window.location.search).get('hs')
    if (s === 'h02' || s === 'h03' || s === 'h04') return s
  } catch { /* no URL */ }
  return 'h01'
}

function writeHs(state: HudState) {
  if (typeof window === 'undefined') return
  const p = new URLSearchParams(window.location.search)
  if (state === 'h01') p.delete('hs')
  else p.set('hs', state)
  const qs = p.toString()
  window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''))
}

export function HudDaily(props: { snap: SnapshotV3 | null; nativeStrip?: boolean }) {
  const { snap } = props
  const native = props.nativeStrip === true
  const [state, setState] = useState<HudState>(readHs)
  const [hoveredTool, setHoveredTool] = useState<string | null>(null)
  const [miniSettings, setMiniSettings] = useState(false)
  // E2：主窗口用 ?targets= 限定显示子集时，窄窗的两个常驻数字必须说清自己算的是哪一层。
  // 窄窗不放筛选控件（150px 里再排一排切换就是第二套显示状态），只读地址；地址由
  // App.tsx 的 URL 写回白名单保留（与 dv/dp/… 同一名单），所以标签不会在快照到达后翻脸。
  const [addressSelection] = useState<string[] | null>(() => {
    try { return readTargetSelection(window.location.search) } catch { return null }
  })
  const targetFilterActive = addressSelection !== null
  const onState = (s: HudState) => { setState(s); writeHs(s) }
  const { agents, excludedNonAgent, excludedNoRole } = useMemo(() => hudAgents(snap), [snap])
  const waitingApprovals = (snap?.executions ?? [])
    .filter((e) => e.state === 'WAITING_APPROVAL' || e.state === 'WAITING_USER').length
  const activeProjects = (snap?.projects ?? []).filter((p) => p.activityState === 'ACTIVE').length
  const transport = snap?.transport
  // The strip is a summary surface: the reference keeps the footer pinned, so the row list is
  // capped and the remainder is stated instead of scrolling the footer out of the window.
  const MAX_STRIP_ROWS = 5
  const visibleTools = native ? agents.slice(0, MAX_STRIP_ROWS) : agents
  const hiddenToolCount = agents.length - visibleTools.length

  const h01Card = (
    <section aria-label="工具额度窄面板" data-landmark="h01"
      className="w-full max-w-[150px] rounded-2xl border bg-[color:var(--daily-shell)] p-3"
      style={{ borderColor: LINE }}>
      <ul className="space-y-2.5">
        {agents.length === 0 && (
          <li className="py-2 text-center text-xs" style={{ color: DIM }}>未连接工具</li>
        )}
        {visibleTools.map((tool) => (
          <li key={tool.id}
            onMouseEnter={native ? () => setHoveredTool(tool.id) : undefined}
            onMouseLeave={native ? () => setHoveredTool((cur) => (cur === tool.id ? null : cur)) : undefined}
            onFocus={native ? () => setHoveredTool(tool.id) : undefined}
            onBlur={native ? () => setHoveredTool((cur) => (cur === tool.id ? null : cur)) : undefined}>
            <RingSlot tool={tool} active={hoveredTool === tool.id} />
            {/* 参考的 H02 是悬停行旁的内联小胶囊，不是另起一张卡。放在行内：指针天然留在
                展开区内，不会像追加卡那样要滚动才能看到自己唤出的内容。 */}
            {native && hoveredTool === tool.id && (
              <div aria-label="悬停摘要" data-landmark="h02"
                className="mt-1 rounded-lg border px-2 py-1 text-xs" style={{ borderColor: LINE, color: DIM }}>
                {tool.name}：窗口 待确认 · 数值 UNKNOWN · 重置时间 待确认
              </div>
            )}
          </li>
        ))}
        {hiddenToolCount > 0 && (
          // 条体高度有限：参考图也是"少数几行 + 常驻页脚"。溢出如实说明，不把页脚顶出视口。
          <li className="pt-1 text-center text-xs" style={{ color: DIM }}>
            另有 {hiddenToolCount} 个工具未在此列出（完整列表在主窗口）
          </li>
        )}
        {(excludedNonAgent > 0 || excludedNoRole > 0) && (
          // 这块面板是 agent 监视器，不是客户端总表。被按角色分出去的客户端要说出去：
          // 只写"少了"会被读成没连接，写清是"不作为 agent 监控"才知道是筛选的结果。
          // 没有声明角色的单独一档——那是来源缺口，不能算成"它不是 agent"。
          // 措辞要短：窄窗宽 150px，页脚必须留在视口里，这一行每多一行都算在条体高度里。
          <li className="pt-1 text-center text-xs" style={{ color: DIM }} data-testid="hud-agent-scope">
            {excludedNonAgent > 0 && `已排除非 agent ${excludedNonAgent}`}
            {excludedNonAgent > 0 && excludedNoRole > 0 && ' · '}
            {excludedNoRole > 0 && `未声明角色 ${excludedNoRole}`}
          </li>
        )}
        {/* 余额行：快照没有余额字段，槽位在、值未知 */}
        <li className="border-t pt-2" style={{ borderColor: LINE }}>
          <span className="flex items-center justify-between gap-2">
            <span className="shrink-0 text-xs" style={{ color: DIM }}>余额</span>
            <span className="min-w-0 text-sm font-semibold" style={{ color: T.warnText }}>UNKNOWN</span>
          </span>
        </li>
      </ul>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 border-t pt-2 text-xs" style={{ borderColor: LINE }}>
        {/* 两个计数各占一行并且不许断字：150px 里把"运行中项目 0 · 待审 0"排成一行会让"待审"的数字
            被挤到下一行单独悬着（实测 108px 宽、第二行只剩一个 0）。分成两行后每行都是一个完整的
            「名词＋数」，读的人不必把两行拼回一句话。 */}
        <span className="flex min-w-0 flex-col gap-y-0.5" style={{ color: DIM }} data-testid="hud-project-counts">
          <span className="whitespace-nowrap">{targetFilterActive ? '全机 ' : ''}运行中项目 {activeProjects}</span>
          <span className="whitespace-nowrap">待审 {waitingApprovals}</span>
        </span>
        <button type="button" onClick={() => onState('h03')} className="shrink-0" style={{ color: ACCENT }}>详情</button>
        {targetFilterActive && (
          // 主窗口的 ?targets 只限显示子集，窄窗这两个数算的是整个快照：不把范围写在数旁边，
          // 就会被读成「筛选后只剩这些」。只在筛选态出现，默认窄窗的像素与几何不变。
          <p className="w-full shrink-0" style={{ color: DIM }} data-testid="hud-count-scope">
            上面是全机计数，不随主窗口 ?targets 显示筛选变化。
          </p>
        )}
      </div>
    </section>
  )

  const h02Section = (
    <section aria-label="悬停摘要" data-landmark="h02"
      className="w-full max-w-[300px] rounded-2xl border bg-[color:var(--daily-shell)] p-3" style={{ borderColor: LINE }}>
      <h2 className="text-xs font-semibold">当前工具对应窗口</h2>
      {agents.length === 0
        ? <p className="mt-2 text-xs" style={{ color: DIM }}>未连接工具</p>
        : agents.slice(0, 3).map((tool) => (
          <div key={tool.id} className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span>{tool.name}</span>
            <span style={{ color: DIM }}>窗口 待确认 · 数值 UNKNOWN · 重置时间 待确认</span>
          </div>
        ))}
      <p className="mt-3 text-xs" style={{ color: DIM }}>
        额度口径未提供（余额与额度分开显示，不做百分比）。
      </p>
      <div className="mt-2 flex flex-wrap gap-x-2 gap-y-1">
        <button type="button" onClick={() => onState('h01')} className="shrink-0 text-xs" style={{ color: ACCENT }}>返回面板</button>
        <button type="button" onClick={() => onState('h03')} className="text-xs" style={{ color: ACCENT }}>
          工具详情（键盘等效入口）
        </button>
      </div>
    </section>
  )

  const h03Section = (
    <section aria-label="工具详情" data-landmark="h03"
      className="w-full max-w-[400px] rounded-2xl border bg-[color:var(--daily-shell)] p-4" style={{ borderColor: LINE }}>
      <div className="flex items-center gap-3">
        {/* The detail card is about one agent, so it shows that agent's own figure. When the strip has no
            monitored agent the dashed UNMARKED figure is the honest picture -- an empty avatar with a
            letter in it would claim a tool the snapshot does not report. */}
        <span aria-hidden="true"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border"
          style={{ borderColor: LINE, background: T.surface, color: ACCENT }}>
          <AgentMark softwareId={agents[0]?.id ?? 'UNKNOWN'} />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{agents[0]?.name ?? '未连接工具'}</h2>
          <p className="text-xs" style={{ color: DIM }}>账户 UNKNOWN · 额度窗口 待确认</p>
        </div>
      </div>
      {/* 参考的 H03 主体是三行额度表（圆点＋标签＋进度条＋值＋重置时间）。快照没有任何额度
          字段，所以槽位照画、进度条画成空轨、值一律 UNKNOWN——不编百分比，也不把"没有字段"
          画成"额度为零"。 */}
      <div className="mt-4 space-y-2" data-landmark="h03-quota-rows">
        {([['当前会话', T.ok], ['周额度', T.warnMark],
          [`周上限 · ${agents[0]?.name ?? '未连接工具'}`, T.ok]] as [string, string][]).map(([label, dot]) => (
          <div key={label} className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: dot }} />
            <span className="shrink-0">{label}</span>
            <span aria-hidden="true" className="h-1 w-12 shrink-0 rounded-full" style={{ background: LINE }} />
            <span className="ml-auto shrink-0 font-medium" style={{ color: DIM }}>UNKNOWN</span>
            {/* 「重置时间 待确认」 needs ~87px and this row has 85 after the strip's own padding and the
                scrollbar the long states reserve, so it broke as 「重置时间 待确」+「认」 — one ideograph
                alone on a line. The shorter label is the same statement and fits on one line. */}
            <span className="w-full shrink-0 text-right" style={{ color: DIM }}>重置 待确认</span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs" style={{ color: DIM }}>
        以上三项是参考面板的额度维度；当前快照未提供任何额度字段，全部保持 UNKNOWN。
      </p>
      <dl className="mt-4 space-y-2 text-xs">
        <div className="flex flex-wrap justify-between gap-x-3 gap-y-0.5"><dt className="shrink-0">更新时间</dt>
          <dd className="ml-auto text-right" style={{ color: DIM }}>
            {snap?.adapterCapabilities?.[0]?.observedAt ? fmtTimestamp(snap.adapterCapabilities[0].observedAt) : 'UNKNOWN'}
          </dd></div>
        <div className="flex flex-wrap justify-between gap-x-3 gap-y-0.5"><dt className="shrink-0">相关会话</dt>
          <dd className="ml-auto" style={{ color: DIM }}>{snap ? `${snap.executions.length} 条执行记录` : 'UNKNOWN'}</dd></div>
        <div className="flex flex-wrap justify-between gap-x-3 gap-y-0.5"><dt className="shrink-0">关联项目</dt>
          <dd className="ml-auto text-right" style={{ color: DIM }}>
            {(snap?.projects ?? []).length ? (snap?.projects ?? []).map((p) => p.displayName ?? p.projectId).join('、') : '未记录'}
          </dd></div>
      </dl>
      {/* 参考在此画 Tokens 柱状图；快照没有用量序列，槽位保留并写明没有数据 */}
      <div className="mt-3 rounded-lg border p-3" style={{ borderColor: LINE, background: T.bg }}>
        <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-0.5 text-xs">
          <span className="shrink-0 font-semibold">Tokens</span>
          <span className="ml-auto" style={{ color: DIM }}>24h · UNKNOWN</span>
        </div>
        <p className="mt-1 text-xs" style={{ color: DIM }}>
          无用量序列数据：不绘制柱状图，不虚构数值。
        </p>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1">
        <button type="button" onClick={() => onState('h01')} className="shrink-0 text-xs" style={{ color: ACCENT }}>返回面板</button>
        <button type="button" onClick={() => onState('h04')} className="shrink-0 text-xs" style={{ color: ACCENT }}>提醒</button>
      </div>
    </section>
  )

  const h04Section = (
    <section aria-label="新回复提醒" data-landmark="h04"
      className="w-full max-w-[380px] rounded-2xl border bg-[color:var(--daily-shell)] p-4" style={{ borderColor: LINE }}>
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles size={14} aria-hidden="true" style={{ color: T.warnMark }} />
            <span className="min-w-0">外部回复提醒</span>
          </h2>
          <p className="mt-0.5 text-xs" style={{ color: DIM }}>
            工具：{agents[0]?.name ?? '未连接'} · 关联项目：{(snap?.projects ?? [])[0]?.displayName ?? '未记录'}
          </p>
        </div>
        <span className="flex shrink-0 items-center gap-2">
          <span className="rounded-full border px-2 py-0.5 text-xs" style={{ borderColor: LINE, color: ACCENT }}>新回复</span>
          <button type="button" onClick={() => onState('h01')} aria-label="关闭提醒" style={{ color: DIM }}>✕</button>
        </span>
      </div>
      <p className="mt-3 text-xs font-medium">启动与依赖排查脚本已就绪</p>
      <p className="mt-1 text-xs" style={{ color: DIM }}>
        当前数据源未提供外部回复事件，摘要保持 待确认；外部回复不等于系统确认，审批回到原工具处理。
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-2 gap-y-1 text-xs" style={{ color: DIM }}>
        <span className="min-w-0">时间：{snap ? fmtTimestamp(snap.sourceWatermark) : 'UNKNOWN'}</span>
        <span className="shrink-0 rounded border px-1.5 py-0.5" style={{ borderColor: LINE }}>
          项目: {(snap?.projects ?? [])[0]?.projectId ?? '未记录'}
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-x-2 gap-y-1">
        <button type="button" onClick={() => onState('h03')}
          className="shrink-0 rounded border px-2.5 py-1 text-xs" style={{ borderColor: LINE, color: DIM }}>
          查看相关用量
        </button>
        <button type="button" onClick={() => onState('h03')}
          className="min-w-0 flex-1 rounded bg-[color:var(--daily-accent)] px-2.5 py-1 text-xs font-medium text-[color:var(--daily-on-accent)]">
          返回外部工具查看 ↗
        </button>
      </div>
    </section>
  )

  const stateSwitcher = (
    <div className="flex flex-wrap justify-center gap-1 text-xs" aria-label="HUD 状态切换">
      {(['h01', 'h02', 'h03', 'h04'] as HudState[]).map((s) => (
        <button key={s} type="button" onClick={() => onState(s)}
          aria-pressed={state === s}
          className={`rounded px-2 py-1 ${state === s ? 'bg-[color:var(--daily-surface)] text-[color:var(--daily-accent)]' : 'text-[color:var(--daily-dim)]'}`}>
          {s.toUpperCase()}
        </button>
      ))}
    </div>
  )

  const footer = native ? (
    <div data-landmark="hud-footer"
      className="mt-auto flex w-full shrink-0 items-center justify-between border-t pt-2 text-xs" style={{ borderColor: LINE }}>
      <span className="flex items-center gap-1.5" style={{ color: DIM }}>
        <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full"
          style={{ background: transport?.transportState === 'LIVE' ? T.ok : DIM }} />
        {transport?.transportState ?? 'UNKNOWN'}
      </span>
      <button type="button" aria-expanded={miniSettings} aria-label="HUD 设置"
        onClick={() => setMiniSettings((v) => !v)} style={{ color: DIM }}>
        <Settings size={14} aria-hidden="true" />
      </button>
    </div>
  ) : null

  /**
   * The footer gear's block. It REPLACES the state card in the strip rather than appending under it:
   * the H01 column already reaches y=500 in a 480px window with six monitored agents, so an appended
   * block painted at y=508 — measured 2026-10-28 by `scripts/audit/hud_strip_geometry_via_cdp.py`, which
   * is the only thing that ever presses this button. A control whose result is off-screen is a control
   * the user cannot use, whatever the DOM says.
   */
  const settingsBlock = (
    <div data-landmark="hud-settings"
      className="w-full shrink-0 rounded-xl border bg-[color:var(--daily-shell)] p-2 text-xs"
      style={{ borderColor: LINE }}>
      <p style={{ color: DIM }}>
        数据源：{transport?.transportState ?? 'UNKNOWN'}；
        修订 {snap?.revision ?? 'UNKNOWN'}。
        更多设置在主窗口设置页。
      </p>
      {/* E1：这一屏现在确实跟着主题令牌换色，所以说明写的是它接的是哪一套值。窄窗里放短句——
          完整那段在 126px 的列里要排十几行，会把这个块整个顶出视口。 */}
      <ThemeHonestyNote id={THEME_HONESTY_ID_HUD} surface="hud" />
      <button type="button" onClick={() => setMiniSettings(false)} className="mt-1" style={{ color: ACCENT }}>
        收起
      </button>
    </div>
  )

  const stateSection = (
    <>
      {state === 'h01' && h01Card}
      {state === 'h02' && h02Section}
      {state === 'h03' && h03Section}
      {state === 'h04' && h04Section}
    </>
  )

  return (
    // The native strip is a fixed 150x480 always-on-top window: the footer must stay inside the
    // viewport, so the frame itself never scrolls — the content region does, and the footer is
    // its sibling. (Measured: with the frame as the scroller, hovering H02 pushed the footer to
    // y=874 of a 480px window, i.e. entirely off-screen.)
    <div className={`flex h-screen flex-col items-center gap-2 bg-[color:var(--daily-bg)] p-2 text-[color:var(--daily-text)] ${
      native ? 'justify-start' : 'justify-center gap-3 overflow-y-auto'}`}
      data-hud-state={state} data-hud-frame={native ? 'native-strip' : 'panel'}>
      {/* Identity on the surface that has no rail and no title bar. The strip is 150x480 with a pinned
          footer, so this takes 22px of a capped column -- the HUD geometry gate is what says whether it fits. */}
      <span aria-hidden="true" className="daily-brand-mark shrink-0" data-brand-mark="work-lab" />
      {native && (
        // 参考图顶部的 notch 把手：borderless 窄窗的拖动面（与 TopStatusBar 的 .drag-region 同一属性约定）。
        <div data-tauri-drag-region aria-hidden="true"
          className="mx-auto h-1.5 w-10 shrink-0 rounded-full" style={{ background: LINE }} />
      )}

      {native ? (
        <>
          <div className="flex min-h-0 w-full flex-1 flex-col items-center gap-2 overflow-y-auto">
          {miniSettings ? settingsBlock : stateSection}
          </div>
          {footer}
        </>
      ) : (
        <>
          <div className="flex w-full items-start justify-center gap-3">
            {state === 'h01' && h01Card}
            {state === 'h02' && h02Section}
            {state === 'h03' && h03Section}
            {state === 'h04' && h04Section}
          </div>
          {stateSwitcher}
        </>
      )}
    </div>
  )
}
