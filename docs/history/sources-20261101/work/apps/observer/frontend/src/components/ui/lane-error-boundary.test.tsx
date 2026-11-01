import * as React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { LaneErrorBoundary } from './lane-error-boundary'

function Throwing({ message }: { message: string }): React.ReactNode {
  throw new Error(message)
}

describe("lane error boundary", () => {
  it("shows the failure inside the lane instead of blanking the app", () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <div>
        <nav>sidebar stays mounted</nav>
        <LaneErrorBoundary lane="models">
          <Throwing message="快照字段缺失" />
        </LaneErrorBoundary>
      </div>,
    )
    expect(screen.getByRole('alert').textContent).toContain('该视图渲染失败')
    expect(screen.getByRole('alert').textContent).toContain('models')
    expect(screen.getByRole('alert').textContent).toContain('快照字段缺失')
    // The shell survives: an uncaught render error used to take the whole tree with it.
    expect(screen.getByText('sidebar stays mounted')).toBeInTheDocument()
  })

  it("recovers when the lane changes, without retrying the read itself", () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const onReset = vi.fn()
    const { rerender } = render(
      <LaneErrorBoundary lane="models" onReset={onReset}>
        <Throwing message="boom" />
      </LaneErrorBoundary>,
    )
    expect(screen.getByRole('alert')).toBeInTheDocument()

    rerender(
      <LaneErrorBoundary lane="agents" onReset={onReset}>
        <p>另一个视图正常</p>
      </LaneErrorBoundary>,
    )
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('另一个视图正常')).toBeInTheDocument()
  })

  it("the reset button clears the error and hands control back to the caller", () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    const onReset = vi.fn()
    let broken = true
    function Child() {
      if (broken) throw new Error("boom")
      return <p>恢复正常</p>
    }
    render(
      <LaneErrorBoundary lane="models" onReset={onReset}>
        <Child />
      </LaneErrorBoundary>,
    )
    fireEvent.click(screen.getByRole('button', { name: '返回总览' }))
    expect(onReset).toHaveBeenCalledTimes(1)
    // The caller switched the lane, so the same component no longer throws. Without
    // this pairing a reset would re-render the failing child and show the alert again.
    broken = false
    fireEvent.click(screen.getByRole('button', { name: '返回总览' }))
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.getByText('恢复正常')).toBeInTheDocument()
  })

  it("reports the error text when the thrown value is not an Error", () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    function ThrowString(): React.ReactNode {
      // eslint-disable-next-line no-throw-literal
      throw 'plain string failure'
    }
    render(
      <LaneErrorBoundary lane="audit">
        <ThrowString />
      </LaneErrorBoundary>,
    )
    expect(screen.getByRole('alert').textContent).toContain('plain string failure')
  })
})
