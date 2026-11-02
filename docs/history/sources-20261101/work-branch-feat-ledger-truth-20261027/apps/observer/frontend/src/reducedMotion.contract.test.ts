import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

describe('reduced-motion preference', () => {
  it('disables animation, transition, and smooth scrolling across the production shell', () => {
    const shellCss = readFileSync('src/skins/l10b-shell.css', 'utf8')
    const ruleStart = shellCss.lastIndexOf('/* Reduced-motion floor')
    expect(ruleStart).toBeGreaterThanOrEqual(0)
    const rule = shellCss.slice(ruleStart)
    expect(rule).toContain('@media (prefers-reduced-motion: reduce)')
    expect(rule).toContain('animation: none !important')
    expect(rule).toContain('transition: none !important')
    expect(rule).toContain('scroll-behavior: auto !important')
  })
})
