import type { ReactNode } from 'react'
import { ChevronRight } from 'lucide-react'

export function SectionCard({ title, subtitle, icon, onMore, moreText = '查看更多', action, children, className = '' }: {
  title: string
  subtitle?: string
  /** 标题左侧图标（设计稿中每张卡片带彩色小图标） */
  icon?: ReactNode
  onMore?: () => void
  moreText?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`section-card ${className}`}>
      <div className="section-head">
        <div>
          <h3>{icon}{title}</h3>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action ?? (onMore && <button className="more-link" onClick={onMore}>{moreText} <ChevronRight size={14}/></button>)}
      </div>
      <div className="section-body">{children}</div>
    </section>
  )
}
