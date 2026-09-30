export function ChartPlaceholder({ variant = 'line' }: {variant?: 'line' | 'bars' | 'donut' | 'radar'}) {
  return <div className={`chart-placeholder ${variant}`}><div className="chart-grid"/><div className="chart-art"/></div>
}
