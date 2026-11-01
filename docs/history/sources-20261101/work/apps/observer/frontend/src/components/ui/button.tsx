import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import type { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * UI_COMPONENTS (20260921) · L10b (2026-09-27): shared Button.
 *
 * L10b: the visual contract is now the B10 single-file's own button classes —
 * `.primary-btn` / `.ghost-btn` / `.soft-btn` / `.danger-btn` (verbatim in
 * src/skins/b10.css, which loads AFTER index.css so those rules win). The B10
 * classes carry the radius (12px), padding (10/14), gradient fill, glow shadow
 * and hover lift, so no Tailwind shape utilities are applied on top — only the
 * focus-visible ring, the disabled contract and the caller's className.
 *
 * Behavior contract is unchanged: `variant`, `size` (kept for call sites that
 * only need the density hint) and `iconLeft` still resolve as before.
 */
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 select-none ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ' +
  'focus-visible:ring-offset-bg ' +
  'disabled:opacity-50 disabled:pointer-events-none',
  {
    variants: {
      variant: {
        // B10 `.primary-btn` — gradient (primary → secondary), white bold label
        primary: 'primary-btn',
        // B10 `.soft-btn` — secondary-tinted soft surface
        secondary: 'soft-btn',
        // B10 `.ghost-btn` — surface2 fill + border, lifts 1px on hover
        ghost: 'ghost-btn',
        // B10 `.danger-btn` — error gradient
        danger: 'danger-btn',
      },
      size: {
        sm: 'text-xs',
        md: 'text-sm',
        lg: 'text-base',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  iconLeft?: LucideIcon
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, iconLeft: Icon, children, type = 'button', ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    >
      {Icon ? <Icon className="h-4 w-4" aria-hidden="true" /> : null}
      {children}
    </button>
  ),
)
Button.displayName = 'Button'

export { Button, buttonVariants }
