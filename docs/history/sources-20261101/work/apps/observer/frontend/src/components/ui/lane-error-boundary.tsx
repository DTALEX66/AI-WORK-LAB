import * as React from 'react'

/**
 * A lane that throws used to blank the entire Observer: React unmounts the tree above
 * an uncaught render error, so one bad projection field took the sidebar, the truth
 * strip and the window controls with it, and the user was left with a black frameless
 * window and no message. Observer is read-only, so the correct failure mode is to drop
 * the lane, keep the shell, and show what actually went wrong.
 *
 * This is a projection-surface boundary, not a write-retry affordance: it reports the
 * failure and offers to return to the overview lane. It never re-drives a read, because
 * ErrorState's contract (states.tsx) is that a failed read is reported, not retried.
 */
export interface LaneErrorBoundaryProps {
  /** Identifies which lane failed, shown in the message and used as the reset key. */
  lane: string
  onReset?: () => void
  children: React.ReactNode
}

interface State {
  error: Error | null
}

export class LaneErrorBoundary extends React.Component<LaneErrorBoundaryProps, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error): void {
    // Kept on the console for a human reading logs; no telemetry, no prompt bodies,
    // and nothing leaves the process.
    console.error(`[observer] lane "${this.props.lane}" failed to render`, error)
  }

  componentDidUpdate(prev: LaneErrorBoundaryProps): void {
    if (prev.lane !== this.props.lane && this.state.error) this.setState({ error: null })
  }

  render(): React.ReactNode {
    const error = this.state.error
    if (!error) return this.props.children
    return (
      <div className="panel mx-auto mt-10 max-w-xl text-center" role="alert">
        <div className="mb-2 text-lg text-error">该视图渲染失败</div>
        <p className="whitespace-pre-wrap text-xs text-muted">
          {this.props.lane}：{error.message || String(error)}
        </p>
        <p className="mt-3 text-[12px] text-muted">
          其余界面与窗口控件仍可用；这里只显示已发生的渲染错误，不伪造数据，也不在此重试读取。
        </p>
        {this.props.onReset ? (
          <p className="mt-3">
            <button
              type="button"
              className="ghost-btn"
              onClick={() => {
                this.setState({ error: null })
                this.props.onReset?.()
              }}
            >
              返回总览
            </button>
          </p>
        ) : null}
      </div>
    )
  }
}
