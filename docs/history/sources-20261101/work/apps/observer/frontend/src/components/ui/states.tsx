import * as React from 'react'
import { Ban, CircleSlash, CloudOff, EyeOff, HelpCircle, Inbox, Lock, Timer, TriangleAlert } from 'lucide-react'
import { cn } from '@/lib/utils'
// WUI-11: the eight-state vocabulary. The cards below print it rather than restating it, so a page and
// the matrix cannot drift into two different meanings for the same word.
import { STATE_BY_ID, STATE_DEFINITIONS, type ProductState } from '@/lib/stateVocabulary'

/**
 * UI_COMPONENTS (20260921) · L10b (2026-09-27): the five L7 view-state
 * contracts as reusable shells. These are HONEST states — they render real
 * placeholders, never fabricated KPIs; the view supplies the actual message
 * (e.g. "快照未携带治理契约明细").
 *
 * L10b: the visual shell is the B10 `.empty` block verbatim —
 *   .empty            text-align:center; padding:56px 20px; color:muted
 *   .empty .icon      64px circle, primary border + primary glyph + glow
 * Titles keep the repo's text contract; the icon slot is a div (not an SVG)
 * so the B10 child selector `.empty .icon` matches.
 */
function StateShell({
  icon,
  title,
  description,
  action,
  className,
  role,
}: {
  icon: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  className?: string
  role?: string
}) {
  return (
    <div className={cn('empty', className)} role={role}>
      <div className="icon" aria-hidden="true">{icon}</div>
      <div>
        <p className="text-sm font-semibold text-ink">{title}</p>
        {description ? <p className="mx-auto mt-1 max-w-xl text-xs">{description}</p> : null}
      </div>
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  )
}

export interface EmptyStateProps {
  title: string
  description?: string
  /** optional call-to-action button (rendered when provided) */
  action?: React.ReactNode
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <StateShell
      icon={<Inbox size={26} strokeWidth={1.8} />}
      title={title}
      description={description}
      action={action}
      className={className}
    />
  )
}

// M-2 (UI-CHECK-20261006): LoadingSkeleton is gone. It had zero callers, and the
// shell settled on a load strip instead (App.tsx `loadingStrip`) because the B5
// rule pins every KPI to UNKNOWN with no snapshot — a skeleton that *replaces*
// content hides exactly the state that rule defends. Keeping an unused skeleton
// in the design system invited the other implementation: it is the one loading
// affordance whose presence would make a real UNKNOWN invisible.

export interface ErrorStateProps {
  message: string
  className?: string
}

/**
 * ErrorState is a pure message surface. L10b removed the optional 重试 action:
 * Observer is strictly read-only, so no state component may hand a caller a
 * retry/write affordance (Observer §8 iron law) — a failed read is reported,
 * not re-driven from a projection page.
 */
export function ErrorState({ message, className }: ErrorStateProps) {
  return (
    <StateShell
      icon={<TriangleAlert size={26} strokeWidth={1.8} />}
      title="无法加载"
      description={message}
      className={className}
      role="alert"
    />
  )
}

export interface OfflineStateProps {
  className?: string
  /**
   * WHAT is offline, in the user's own vocabulary — usually the active view's label.
   *
   * Without it the shell renders one identical card for all 22 views, and a user who clicks through
   * the rail sees nothing change and concludes the navigation is dead. That is the shape this prop
   * exists to break: the failure is global (the transport is down), but the report has to say which
   * surface is being read, so the click has a visible consequence and the reader knows the rail works.
   */
  subject?: string
}

export function OfflineState({ className, subject }: OfflineStateProps) {
  // No action slot and no spinner here, deliberately: StateShell renders `action` as a left-aligned
  // block, so an icon-only "still working" glyph in it reads as a stray mark rather than a status
  // (it did — visible in the 2026-10-08 desktop screenshot), and SCREEN_SPEC assigns the
  // "still fetching?" signal to the first-frame strip, which the shell already renders.
  return (
    <StateShell
      icon={<CloudOff size={26} strokeWidth={1.8} />}
      title={subject ? `「${subject}」读不到快照` : '连接中断'}
      description={subject
        ? `后端快照不可达，此视图的数值全部保持 UNKNOWN（不伪造）。其他视图同样读不到：切换后看到的是各自的名称，不是界面卡住。`
        : '后端快照不可达，正在等待重连…'}
      className={className}
      role="status"
    />
  )
}

export interface UnknownStateProps {
  title?: string
  description?: string
  className?: string
}

export function UnknownState({
  title = '数据未知',
  description,
  className,
}: UnknownStateProps) {
  return (
    <StateShell
      icon={<Inbox size={26} strokeWidth={1.8} />}
      title={title}
      description={description}
      className={className}
      role="status"
    />
  )
}

export interface PermissionStateProps {
  /** what the user cannot do here, in one line */
  blocked: string
  /** WHY it is blocked: the contract or permission that owns the write */
  reason: string
  /** what this surface still does, so the reader is not left with a dead end */
  stillAvailable?: string
  title?: string
  className?: string
}

/**
 * PERMISSION / READ-ONLY state (UI prompt pack G1).
 *
 * Distinct from UnknownState on purpose: UNKNOWN says "the projection has no
 * value", this says "the value may be known and this surface still cannot act".
 * The prompt pack forbids a write action that merely looks available, so a
 * read-only lane has to name the owner of the write rather than go quiet.
 */
export function PermissionState({
  blocked,
  reason,
  stillAvailable,
  title = '此界面只读',
  className,
}: PermissionStateProps) {
  return (
    <StateShell
      icon={<Lock size={26} strokeWidth={1.8} />}
      title={title}
      description={
        [blocked, reason, stillAvailable].filter(Boolean).join(' — ')
      }
      className={className}
      role="status"
    />
  )
}

/* ---------------------------------------------------------------------------
 * WUI-11 · the eight states, told apart.
 *
 * The five shells above cover empty / error / offline / unknown / permission. The taskpack asks for
 * eight separately explained states, and a lane that renders 无数据 where the truth is 延迟 (or, worse,
 * 权限不足) is not a shorter path — it is a different statement. So each of the remaining states gets its
 * own affordance, and every one of them prints the field it is based on and the next action, taken from
 * `lib/stateVocabulary` rather than restated here. That is what keeps the matrix and the pages from
 * drifting into two vocabularies.
 * ------------------------------------------------------------------------ */

const STATE_ICONS: Record<string, React.ReactNode> = {
  unsupported: <Ban size={26} strokeWidth={1.8} />,
  delayed: <Timer size={26} strokeWidth={1.8} />,
  'hidden-by-policy': <EyeOff size={26} strokeWidth={1.8} />,
  'partial-failure': <CircleSlash size={26} strokeWidth={1.8} />,
  'not-existing': <HelpCircle size={26} strokeWidth={1.8} />,
  'insufficient-permission': <Lock size={26} strokeWidth={1.8} />,
  'no-data': <Inbox size={26} strokeWidth={1.8} />,
  'not-connected': <CloudOff size={26} strokeWidth={1.8} />,
}

export interface ProductStateCardProps {
  state: ProductState
  /** the concrete subject — a lane name, an id, a field — so the card is about something */
  subject?: string
  /** what this page actually observed, in one line */
  detail?: string
  className?: string
  /**
   * Lower the PRESENTATION weight without touching the state's meaning.
   *
   * `.empty` is the page-level shell: a 56px band and a 64px icon circle. For a state that this repository
   * shows as a long-term norm rather than an incident — a read-only projection whose source declines
   * sensitive names and prunes regenerable directories on every run (measured 231 / 114) — that weight is
   * alarm fatigue, and an always-shouting card teaches a reader to stop reading it. `compact` therefore
   * keeps `data-state`, the vocabulary label, the detail, 依据 and 下一步 exactly as they are and changes
   * only the shell: left-aligned, inline, no icon circle, no page-level whitespace. The words and the
   * counts are the caller's, so this cannot rewrite a verdict.
   */
  compact?: boolean
}

/** One of the eight states, rendered with its evidence rule and its way out. */
export function ProductStateCard({ state, subject, detail, className, compact = false }: ProductStateCardProps) {
  const definition = STATE_BY_ID[state]
  // In the page-level shell the paragraphs centre inside the `.empty` band; the compact strip is
  // left-aligned, so the centring widths are what drop out — never the text.
  const measure = compact ? 'min-w-0' : 'mx-auto max-w-xl'
  const body = (
    <div className="min-w-0">
      <p className="text-sm font-semibold text-ink">
        {definition.label}{subject ? ` · ${subject}` : ''}
      </p>
      <p className={cn('mt-1 text-xs', measure)}>{detail ? detail : definition.meaning}</p>
      <p className={cn('mt-2 text-[12px] text-muted', measure)}>
        依据：{definition.signal}
      </p>
      <p className={cn('mt-1 text-[12px] text-muted', measure)}>
        下一步：{definition.nextAction}
      </p>
      {definition.projectable === false && (
        <p className={cn('mt-2 text-[12px] text-warning', measure)} data-testid={`state-not-projectable-${state}`}>
          当前 v3 快照不携带可判定该状态的项目；本卡只在调用方明确告知时出现，不由空值推断。
        </p>
      )}
    </div>
  )
  if (compact) {
    return (
      <div
        className={cn(
          // token-driven only: panel2, the hairline and radius-md are the shell's own variables.
          'flex min-w-0 items-start gap-2 rounded-md border border-border/60 bg-panel2 p-2 text-left',
          className,
        )}
        role="status"
        data-state={state}
        data-presentation="compact"
      >
        <span className="mt-0.5 shrink-0 text-secondary-ink" aria-hidden="true">{STATE_ICONS[state]}</span>
        {body}
      </div>
    )
  }
  return (
    <div className={cn('empty', className)} role="status" data-state={state}>
      <div className="icon" aria-hidden="true">{STATE_ICONS[state]}</div>
      {body}
    </div>
  )
}

/**
 * The state matrix itself (master page 14_states): all eight rows, each with whether the shipped
 * projection can answer it. A developer reads this to know which affordance is legitimate where; the
 * two rows that say 快照不携带 are the ones a view must never reach for by default.
 */
export function StateMatrixCard({ className }: { className?: string }) {
  return (
    <div className={cn('list', className)} data-testid="state-matrix">
      {STATE_DEFINITIONS.map((definition) => (
        <div key={definition.id} className="list-item flex-col items-stretch gap-1" data-state={definition.id}>
          <div className="flex items-center justify-between gap-3">
            <span className="text-[12px] font-semibold text-ink">{definition.label}</span>
            <span className={cn('text-[12px]',
              definition.projectable === false ? 'text-warning' : 'text-muted')}>
              {definition.projectable === false ? '快照不携带'
                : definition.projectable === 'partly' ? '部分可判定' : '可由投影判定'}
            </span>
          </div>
          <span className="text-[12px] text-muted">{definition.meaning}</span>
          <span className="text-[12px] text-muted">依据：{definition.signal}</span>
          <span className="text-[12px] text-muted">下一步：{definition.nextAction}</span>
        </div>
      ))}
    </div>
  )
}
