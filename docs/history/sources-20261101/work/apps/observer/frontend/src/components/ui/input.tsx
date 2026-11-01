import * as React from 'react'
import { Search } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * UI_COMPONENTS (20260921): Input / SearchInput / Select — styled native
 * controls that resolve through SPEC-A CSS variables (no new dependencies).
 */
const fieldBase =
  'h-10 w-full rounded-md border border-border bg-panel px-3 text-sm text-ink ' +
  'placeholder:text-muted transition-colors duration-fast ' +
  'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-bg ' +
  'disabled:opacity-50 disabled:pointer-events-none'

const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(fieldBase, className)} {...props} />
  ),
)
Input.displayName = 'Input'

const SearchInput = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <div className={cn('relative', className)}>
      <Search
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted"
        aria-hidden="true"
      />
      <input
        ref={ref}
        type="search"
        className={cn(fieldBase, 'pl-9', 'appearance-none', '[&::-webkit-search-cancel-button]:hidden')}
        {...props}
      />
    </div>
  ),
)
SearchInput.displayName = 'SearchInput'

const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, children, ...props }, ref) => (
    <select ref={ref} className={cn(fieldBase, 'cursor-pointer pr-8', className)} {...props}>
      {children}
    </select>
  ),
)
Select.displayName = 'Select'

export { Input, SearchInput, Select }
