import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * L10b (2026-09-27): B10 `.panel` card family.
 *
 * The B10 single-file defines ONE surface primitive — `.panel` — as
 *   background: linear-gradient(surface 82% → surface 94% black)
 *   border: 1px solid border/70 · radius 18px · padding 18px
 *   shadow: --shadow-soft + inset top highlight · hover: primary edge
 *   (verbatim in src/skins/b10.css, which loads AFTER index.css and therefore
 *    wins the cascade over the Tailwind `@layer components` `.panel` rule)
 *
 * So Card renders the B10 structure directly (`div.panel`) and the panel header
 * is the B10 `<h3>` slot: 15px, 600, 14px bottom margin. CardContent carries no
 * padding utility of its own — `.panel` supplies the 18px.
 */
const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('panel', className)} {...props} />
  ),
)
Card.displayName = 'Card'

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex items-center justify-between gap-3 m-0 mb-3.5 text-[15px] font-semibold tracking-[0.02em] text-ink',
        className,
      )}
      {...props}
    />
  ),
)
CardHeader.displayName = 'CardHeader'

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn(className)} {...props} />
  ),
)
CardContent.displayName = 'CardContent'

export { Card, CardHeader, CardContent }
