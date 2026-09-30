import type { ReactNode } from 'react'
import { DatabaseZap } from 'lucide-react'

export function EmptyState({ title = '暂无真实数据', description = '连接后端数据源后，这里将显示真实商业数据。', children, compact }: {
  title?: string
  description?: string
  children?: ReactNode
  /** 紧凑空状态：无数据时收缩高度，不占用与有数据时相同的空间 */
  compact?: boolean
}) {
  return (
    <div className={`empty-state ${compact ? 'compact' : ''}`}>
      {!compact && <div className="empty-icon"><DatabaseZap size={28} /></div>}
      <strong>{title}</strong>
      <span>{description}</span>
      {children}
    </div>
  )
}
