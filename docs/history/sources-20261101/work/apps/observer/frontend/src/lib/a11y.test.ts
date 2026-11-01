// U03 / WlA11y parity behavior test: the React Observer now owns a WCAG AA
// polite live region for status announcements — the one valid a11y capability
// the retired static web/ surface (WlA11y.announce) had and React lacked.
// These are real-DOM assertions (jsdom), not phantom snapshots: they prove an
// announce actually lands in a role=status[aria-live=polite] region that an
// assistive tech would pick up.
import { describe, it, expect, beforeEach } from 'vitest'
import { announce, lastAnnouncement, liveRegionCount } from '@/lib/a11y'

describe('U03 a11y live-region announcements (WlA11y parity)', () => {
  beforeEach(() => {
    // tear down any region the previous test left in the body so each test
    // counts from a clean sheet.
    document
      .querySelectorAll('div[role="status"][aria-live="polite"]')
      .forEach((el) => el.remove())
  })

  it('announce lands text in a polite status live region', () => {
    announce('已切换为深色主题')
    expect(liveRegionCount()).toBe(1)
    expect(document.querySelector('div[role="status"][aria-live="polite"]')).not.toBeNull()
    expect(lastAnnouncement()).toBe('已切换为深色主题')
  })

  it('repeated identical messages are held via a live region (no crash)', () => {
    announce('已加载实时投影数据')
    announce('已加载实时投影数据')
    // idempotent, no duplicate region nodes.
    expect(liveRegionCount()).toBe(1)
    expect(lastAnnouncement()).toBe('已加载实时投影数据')
  })

  it('empty message is a no-op (announcements stay silent, never fabricated)', () => {
    announce('')
    expect(lastAnnouncement()).toBe('')
    expect(liveRegionCount()).toBe(0)
  })

  it('a second announce reuses the singleton region, not a new node', () => {
    announce('已加载只读投影数据')
    const first = document.querySelector('div[role="status"][aria-live="polite"]')
    announce('实时数据不可用，已保留上次良好投影（last-good，标记为 STALE）')
    const second = document.querySelector('div[role="status"][aria-live="polite"]')
    expect(liveRegionCount()).toBe(1)
    expect(first).toBe(second)
    expect(lastAnnouncement()).toContain('STALE')
  })

  it('the three static-surface state announcements map 1:1', () => {
    // The retired static web/ announced exactly these four transitions;
    // each must be representable through the React announcer.
    for (const msg of [
      '已切换为深色主题',
      '已加载实时投影数据',
      '实时数据不可用，已保留上次良好投影（last-good，标记为 STALE）',
      '实时数据不可用，界面显示 OFFLINE（不加载假数据）',
    ]) {
      announce(msg)
      expect(lastAnnouncement()).toBe(msg)
    }
    expect(liveRegionCount()).toBe(1)
  })
})
