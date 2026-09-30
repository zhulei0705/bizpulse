import { EmptyState } from './EmptyState'

export function DataTableShell({ columns }: {columns: string[]}) {
  return (
    <div className="data-table-shell">
      <div className="table-head-row">{columns.map((c) => <span key={c}>{c}</span>)}</div>
      <EmptyState />
    </div>
  )
}
