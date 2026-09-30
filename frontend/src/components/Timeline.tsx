import type { ReactNode } from 'react'

export type TimelineItem = {
  time: string
  title: ReactNode
  sub?: ReactNode
  side?: ReactNode
}

/** 竖向时间轴（首页实时动态 / 雷达机会流通用）。 */
export function Timeline({ items, max }: { items: TimelineItem[]; max?: number | string }) {
  return (
    <div className="timeline" style={max !== undefined ? { maxHeight: typeof max === 'number' ? `${max}px` : max } : undefined}>
      {items.map((item, idx) => (
        <div className="timeline-row" key={idx}>
          <span className="timeline-dot" />
          <span className="timeline-time">{item.time}</span>
          <div className="timeline-body">
            <strong>{item.title}</strong>
            {item.sub && <small>{item.sub}</small>}
          </div>
          {item.side && <div className="timeline-side">{item.side}</div>}
        </div>
      ))}
    </div>
  )
}
