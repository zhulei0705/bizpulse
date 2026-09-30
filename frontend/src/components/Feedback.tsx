import type { ReactNode } from 'react'

/** BizPulse 统一 Skeleton：占位保持页面结构稳定（替代孤零零的 Spin）。 */
export function Skeleton({ width = '100%', height = 14, radius = 7, style }: { width?: number | string; height?: number; radius?: number; style?: React.CSSProperties }) {
  return <span className="bp-skeleton" style={{ width, height, borderRadius: radius, ...style }} />
}

export function SkeletonBlock({ rows = 3 }: { rows?: number }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={13} width={`${100 - i * 12}%`} />
      ))}
    </div>
  )
}

/** 统一错误状态：数据加载失败 + 重新加载（不得以假数据兜底）。 */
export function ErrorState({ onRetry, title = '数据加载失败' }: { onRetry?: () => void; title?: string }) {
  return (
    <div className="empty-state">
      <div className="empty-icon" style={{ color: '#ff8ba0' }}>!</div>
      <strong>{title}</strong>
      <span>请确认后端服务正在运行，然后重试。</span>
      {onRetry && <button className="secondary-btn" style={{ height: 32, marginTop: 6 }} onClick={onRetry}>重新加载</button>}
    </div>
  )
}

/** 数字滚动过渡容器（内容变化时轻微淡入）。 */
export function AnimatedNumber({ value, className }: { value: ReactNode; className?: string }) {
  return (
    <strong className={className} key={String(value)} style={{ animation: 'numIn .35s ease' }}>
      {value}
    </strong>
  )
}
