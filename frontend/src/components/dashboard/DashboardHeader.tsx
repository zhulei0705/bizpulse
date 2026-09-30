import type { ReactNode } from 'react'

/** 首页 Hero 头部：问候 + 主标题 + 副标题 + 主按钮（左侧文案由调用方组合）。 */
export function DashboardHeader({ greeting, title, highlight, description, lastUpdated, actions, floatCards, sideSlogan }: {
  greeting: string
  title: string
  highlight: string
  description: string
  /** 来自真实系统时间的最后更新时间 */
  lastUpdated?: string
  actions?: ReactNode
  floatCards?: { icon: ReactNode; title: string; desc: string; tone?: 'blue' | 'purple' | 'green' }[]
  sideSlogan?: { lines: [string, string]; tips: string[] }
}) {
  return (
    <>
      <div className="hero-copy">
        <div className="hero-eyebrow">{greeting}</div>
        <h1>{title} <span>{highlight}</span></h1>
        <p>{description}</p>
        {lastUpdated && <p className="hero-updated">数据最后更新：{lastUpdated}（本地系统时间）</p>}
        {actions && <div className="hero-actions">{actions}</div>}
      </div>
      {floatCards && floatCards.length > 0 && (
        <div className="hero-float-cards">
          {floatCards.map((c, i) => (
            <div className="hero-float-card" key={i}>
              <div className={`hfc-icon ${c.tone === 'purple' ? 'purple' : c.tone === 'green' ? 'green' : ''}`}>{c.icon}</div>
              <div><strong>{c.title}</strong><small>{c.desc}</small></div>
            </div>
          ))}
        </div>
      )}
      {sideSlogan && (
        <div className="hero-side-slogan">
          <strong>{sideSlogan.lines[0]}<br/>{sideSlogan.lines[1]}</strong>
          <small>{sideSlogan.tips.map((t) => <b key={t}>{t}</b>)}</small>
        </div>
      )}
    </>
  )
}
