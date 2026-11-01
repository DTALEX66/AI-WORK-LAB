// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { act } from 'react'
// Vitest stubs CSS imports (css:false), so the pinned skin is read from disk instead: the
// assertion must see the same bytes the bundle ships, not a module stub.
import { readFileSync } from 'node:fs'
import { render, screen } from '@testing-library/react'
import { Drawer, DRAWER_EXIT_MS } from '@/components/ui/drawer'
import { Toaster, TOAST_EXIT_MS } from '@/components/ui/toast'
import type { ToastItem } from '@/components/ui/toast'

/**
 * The pinned skin declares an entrance for both overlays — `b10.css` `.drawer{transition:right .28s …}` with
 * `.drawer.open{right:0}`, and `.toast{opacity:0;transform:translateY(12px) …;transition:.22s ease}` with
 * `.toast.show{…}`. A transition needs two painted states; the components used to mount with the open class
 * already applied, so the browser was told once and the promised slide never happened.
 *
 * These cases pin the order, not the class list: the first paint must be the CLOSED state, and the open class
 * may only arrive on a later frame. A component that went straight to `.open` would pass a class-list test and
 * still show no motion, which is exactly how the defect survived.
 */
async function frames(count = 2) {
  for (let i = 0; i < count; i += 1) {
    await act(async () => { await new Promise<void>((resolve) => requestAnimationFrame(() => resolve())) })
  }
}

async function settle(ms: number) {
  await act(async () => { await new Promise<void>((resolve) => setTimeout(resolve, ms)) })
}

function panel(): HTMLElement | null {
  return document.querySelector('aside.drawer')
}

describe('抽屉真的滑进来，也真的滑出去', () => {
  it('第一帧画的是关闭态，开启类要晚一帧才出现', async () => {
    render(<Drawer open onClose={() => {}} title="工作区"><p>内容</p></Drawer>)
    const first = panel()
    expect(first, 'the panel mounts so the closed state has something to transition from').not.toBeNull()
    expect(first!.classList.contains('open'), 'a first paint that is already open gives the browser nothing to animate')
      .toBe(false)
    await frames()
    expect(panel()!.classList.contains('open')).toBe(true)
  })

  it('关闭后先留在文档里把退场画完，超过声明时长才卸载', async () => {
    const { rerender } = render(<Drawer open onClose={() => {}} title="工作区"><p>内容</p></Drawer>)
    await frames()
    rerender(<Drawer open={false} onClose={() => {}} title="工作区"><p>内容</p></Drawer>)
    await act(async () => { await Promise.resolve() })
    const leaving = panel()
    expect(leaving, 'removing .open and unmounting in the same tick would skip the exit transition').not.toBeNull()
    expect(leaving!.classList.contains('open')).toBe(false)
    await settle(DRAWER_EXIT_MS + 80)
    expect(panel()).toBeNull()
  })

  it('退场预算读的是皮肤真正声明的时长，不是手写的数', async () => {
    const css = readFileSync('src/skins/b10.css', 'utf8')
    const declared = /\.drawer\{[^}]*?transition:right\s+(\.?\d+(?:\.\d+)?)s/.exec(css)
    expect(declared, 'the pinned skin must still declare the slide this component waits for').not.toBeNull()
    const ms = Number(declared![1]) * 1000
    expect(DRAWER_EXIT_MS).toBeGreaterThanOrEqual(ms)
    expect(DRAWER_EXIT_MS).toBeLessThan(ms + 60)
  })
})

describe('吐司真的淡进来', () => {
  const toast = (over: Partial<ToastItem> = {}): ToastItem =>
    ({ id: 1, title: '暂无新的通知', variant: 'info', ...over } as ToastItem)

  it('第一帧没有 .show，之后才有', async () => {
    render(<Toaster toasts={[toast()]} onDismiss={() => {}} />)
    const first = document.querySelector('div.toast')
    expect(first).not.toBeNull()
    expect(first!.classList.contains('show'), 'an element that appears already at opacity 1 has no fade').toBe(false)
    await frames()
    expect(document.querySelector('div.toast')!.classList.contains('show')).toBe(true)
  })

  it('每一条吐司自己决定何时进入开启态，不跟着列表里第一条一起跳', async () => {
    const { rerender } = render(<Toaster toasts={[toast({ id: 1, title: '第一条' })]} onDismiss={() => {}} />)
    await frames()
    rerender(<Toaster toasts={[toast({ id: 1, title: '第一条' }), toast({ id: 2, title: '第二条' })]}
      onDismiss={() => {}} />)
    const rows = Array.from(document.querySelectorAll('div.toast'))
    expect(rows).toHaveLength(2)
    expect(rows[0].classList.contains('show'), 'the row that has been up for a frame stays shown').toBe(true)
    expect(rows[1].classList.contains('show'), 'the new row must still get its own closed first paint').toBe(false)
    await frames()
    expect(document.querySelectorAll('div.toast.show')).toHaveLength(2)
  })

  it('吐司的退场预算同样读 .toast 真正声明的过渡', () => {
    const css = readFileSync('src/skins/b10.css', 'utf8')
    const declared = /\.toast\{[^}]*?transition:\s*(\.?\d+(?:\.\d+)?)(s|ms)/.exec(css)
    expect(declared, 'the pinned skin must still declare the fade this row waits for').not.toBeNull()
    const ms = declared![2] === 's' ? Number(declared![1]) * 1000 : Number(declared![1])
    expect(TOAST_EXIT_MS).toBeGreaterThanOrEqual(ms)
    expect(TOAST_EXIT_MS).toBeLessThan(ms + 40)
  })

  it('dismiss 先摘掉 .show 让淡出画完，超过声明时长才从文档里消失', async () => {
    const { rerender } = render(<Toaster toasts={[toast({ id: 7, title: '第三条' })]} onDismiss={() => {}} />)
    await frames()
    expect(document.querySelector('div.toast')!.classList.contains('show')).toBe(true)
    rerender(<Toaster toasts={[toast({ id: 7, title: '第三条', leaving: true })]} onDismiss={() => {}} />)
    await act(async () => { await Promise.resolve() })
    const leaving = document.querySelector('div.toast')
    expect(leaving, 'removing the item in the same tick would skip the fade-out entirely').not.toBeNull()
    expect(leaving!.classList.contains('show')).toBe(false)
    await settle(TOAST_EXIT_MS + 80)
    expect(document.querySelector('div.toast')).toBeNull()
  })

  it('列表里没有任何一项时不留下空的 toast-stack', async () => {
    const { rerender } = render(<Toaster toasts={[toast()]} onDismiss={() => {}} />)
    await frames()
    rerender(<Toaster toasts={[]} onDismiss={() => {}} />)
    await settle(TOAST_EXIT_MS + 80)
    expect(document.querySelector('.toast-stack')).toBeNull()
  })

  it('screen 上仍读得到内容：先画关闭态不等于把内容藏起来', async () => {
    render(<Toaster toasts={[toast({ variant: 'error', title: '提交失败' })]} onDismiss={() => {}} />)
    expect(screen.getByText('提交失败')).toBeTruthy()
    await frames()
  })
})
