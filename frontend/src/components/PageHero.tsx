import type { ReactNode } from 'react'
import { HeroGlobe } from './HeroGlobe'

export function PageHero({ eyebrow, title, highlight, description, floatCards, sideSlogan, children }: {
  eyebrow?: string
  title: string
  highlight?: string
  description: string
  /** 右侧浮动信号卡（仅展示真实存在的业务说明，不显示虚构百分比） */
  floatCards?: { icon: ReactNode; title: string; desc: string; tone?: 'blue' | 'purple' }[]
  sideSlogan?: { lines: [string, string]; tips: string[] }
  children?: ReactNode
}) {
  return (
    <div className="page-hero">
      <div className="hero-copy">
        {eyebrow && <div className="hero-eyebrow">{eyebrow}</div>}
        <h1>{title} {highlight && <span>{highlight}</span>}</h1>
        <p>{description}</p>
        {children}
      </div>
      {floatCards && floatCards.length > 0 && (
        <div className="hero-float-cards">
          {floatCards.map((c, i) => (
            <div className="hero-float-card" key={i}>
              <div className={`hfc-icon ${c.tone === 'purple' ? 'purple' : ''}`}>{c.icon}</div>
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
      <HeroGlobe />
    </div>
  )
}
