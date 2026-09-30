/** Opportunity Score 环形评分（分数由后端 Score Engine 计算，前端只展示）。 */
export function ScoreRing({ score, grade, size = 74 }: { score: number; grade: string; size?: number }) {
  const radius = (size - 10) / 2
  const circumference = 2 * Math.PI * radius
  const ratio = Math.max(0, Math.min(score / 100, 1))
  const color = score >= 90 ? '#23e0aa' : score >= 80 ? '#2ec7ff' : score >= 70 ? '#7b8cff' : score >= 60 ? '#ffad42' : '#ff5e74'
  return (
    <div className="score-ring" style={{ width: size, height: size }} title={`Opportunity Score ${score}（后端评分引擎计算）`}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#123454" strokeWidth="6" />
        <circle
          cx={size / 2} cy={size / 2} r={radius} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={`${circumference * ratio} ${circumference}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="score-ring-copy">
        <strong style={{ color }}>{Math.round(score)}</strong>
        <small>{grade} 级</small>
      </div>
    </div>
  )
}
