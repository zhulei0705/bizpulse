import type { ReactNode } from 'react'
import { Skeleton, AnimatedNumber } from '../Feedback'

export type PulseCardProps = {
  title: string
  value?: number | string
  description?: string
  icon: ReactNode
  /** 仅当存在真实趋势数据时传入；没有真实趋势不得生成数字 */
  trend?: string
  tone?: 'blue' | 'cyan' | 'purple' | 'gold' | 'green' | 'danger'
  loading?: boolean
}

/** 核心指标卡（参考图第一层四卡）。 */
export function PulseCard({ title, value, description, icon, trend, tone = 'blue', loading }: PulseCardProps) {
  return (
    <div className={`stat-card pulse-border ${tone ? `tone-${tone}` : ''}`}>
      <div className="stat-icon">{icon}</div>
      <div className="stat-copy">
        <span>{title}</span>
        {loading
          ? <Skeleton width={72} height={28} style={{ margin: '4px 0 2px' }} />
          : <AnimatedNumber value={value ?? '—'} />}
        {description && <small>{description}</small>}
        {!description && trend && <small className="pulse-trend">{trend}</small>}
      </div>
      <div className="mini-spark"><i/><i/><i/><i/><i/></div>
    </div>
  )
}
