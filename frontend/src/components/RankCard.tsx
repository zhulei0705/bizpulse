import type { ReactNode } from 'react'

/** 排行卡：名次徽章（金银铜）+ 内容 + 进度条 + 右侧分数。 */
export function RankCard({ rank, title, sub, badge, score, maxScore = 100, onClick }: {
  rank: number
  title: ReactNode
  sub?: ReactNode
  badge?: ReactNode
  score: number
  maxScore?: number
  onClick?: () => void
}) {
  const rankClass = rank === 1 ? 'rank-1' : rank === 2 ? 'rank-2' : rank === 3 ? 'rank-3' : 'rank-n'
  return (
    <button className="rank-card" onClick={onClick}>
      <span className={`rank-badge ${rankClass}`}>{rank}</span>
      <div className="rank-main">
        <strong>{title}</strong>
        {sub && <small style={{ color: '#6f8ba5', fontSize: 10.5 }}>{sub}</small>}
        <div className="rank-bar"><i className={score / maxScore >= 0.8 ? 'green' : ''} style={{ width: `${Math.max(4, Math.min(100, (score / maxScore) * 100))}%` }} /></div>
      </div>
      {badge}
      <div className="rank-side"><strong>{score}</strong></div>
    </button>
  )
}
