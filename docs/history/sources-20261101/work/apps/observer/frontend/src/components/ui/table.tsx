// L10 (2026-09-27) · L10b: B04/L4 DataTable — unified table surface.
//
// L10b: the wrapper + table adopt the verbatim B10 structure
//   <div class="table-wrap"><table class="table">…</table></div>
// `.table-wrap` = overflow:auto, `.table` = 100% width, collapsed borders,
// min-width 720px, 12px/10px cells, 13px text, muted header, hover row tint
// (all verbatim in src/skins/b10.css). The L4 density option still controls the
// cell padding utility; the B10 class supplies everything else.
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface DataTableColumn<T> {
  key: string
  header: ReactNode
  cell: (row: T) => ReactNode
  className?: string
  /** column alignment (default left) */
  align?: 'left' | 'right'
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  /** stable row key */
  rowKey: (row: T, index: number) => string
  /** honest empty-state body (no fabricated rows) */
  empty?: ReactNode
  className?: string
  /** L4 density: comfortable (56px) | compact (44px) */
  density?: 'comfortable' | 'compact'
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  empty,
  className,
  density = 'comfortable',
}: DataTableProps<T>) {
  return (
    <div className={cn('table-wrap', className)}>
      <table className="table">
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={cn(c.align === 'right' && 'text-right', c.className)}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className={cn(density === 'compact' ? 'py-4' : 'py-8', 'text-center text-xs text-muted')}>
                {empty ?? '暂无数据（UNKNOWN）'}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={rowKey(row, i)}>
                {columns.map((c) => (
                  <td key={c.key} className={cn(c.align === 'right' && 'text-right tabular-nums', c.className)}>
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
