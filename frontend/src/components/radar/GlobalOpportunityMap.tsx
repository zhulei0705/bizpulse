import { useNavigate } from 'react-router-dom'
import { GradeChip } from '../GradeChip'
import { Skeleton } from '../Feedback'
import { WORLD_DOT_MASK } from './worldDots'
import type { RadarLocation, RadarMetrics } from '../../types'

/** 世界地图机会雷达（严格对齐参考图：WORLD MAP + RADAR + OPPORTUNITY NODES）。
 * 顶部紧凑真实统计（潜在机会 / 高优先级 / 真实覆盖地区）+ 底部优先级图例 + 右侧地域列表。
 * 地图/雷达圈/图例为 UI 视觉；业务点仅来自真实 locations（无地理数据→0 个点）。
 */
export function GlobalOpportunityMap({ locations, metrics, loading, onSelect }: {
  locations: RadarLocation[]
  metrics?: RadarMetrics
  loading?: boolean
  onSelect?: (loc: RadarLocation) => void
}) {
  const navigate = useNavigate()
  if (loading) {
    return <div style={{ height: 330, display: 'grid', placeItems: 'center' }}><Skeleton width={320} height={300} radius={150} /></div>
  }
  const dots: { x: number; y: number }[] = []
  WORLD_DOT_MASK.forEach((row, r) => row.forEach((cell, c) => { if (cell) dots.push({ x: 16 + c * 15.6, y: 20 + r * 23 }) }))

  const potential = locations.reduce((acc, l) => acc + l.opportunity_count, 0)
  const covered = new Set(locations.map((l) => l.city || l.province || l.country)).size

  return (
    <div className="gom-wrap">
      {/* 顶部紧凑真实统计（参考图左上） */}
      <div className="gom-stats">
        <div className="gom-stat"><span>潜在机会</span><strong>{potential || (metrics?.today_opportunities ?? 0)}</strong></div>
        <div className="gom-stat gold"><span>高优先级</span><strong>{metrics?.high_value_opportunities ?? 0}</strong></div>
        <div className="gom-stat green"><span>真实覆盖地区</span><strong>{covered}</strong></div>
      </div>

      <div className="gom-stage">
        <svg viewBox="0 0 420 300" className="gom-svg">
          <defs>
            <radialGradient id="gomCore" cx="0.35" cy="0.3" r="1">
              <stop stopColor="#7fe4ff" /><stop offset=".5" stopColor="#2f9bff" /><stop offset="1" stopColor="#5b3ff0" />
            </radialGradient>
            <linearGradient id="gomLink" x1="0" y1="0" x2="1" y2="0">
              <stop stopColor="#29d3ff" stopOpacity=".5" /><stop offset="1" stopColor="#8a5cff" stopOpacity=".45" />
            </linearGradient>
          </defs>
          {/* 点阵世界地图（UI 装饰） */}
          {dots.map((d, i) => (
            <circle key={i} cx={d.x} cy={d.y} r="1.9" fill="rgba(96,158,226,.42)" />
          ))}
          {/* 装饰网络连线 */}
          <path d="M210 150 Q 140 78 70 92" stroke="url(#gomLink)" fill="none" strokeDasharray="3 5" />
          <path d="M210 150 Q 292 66 356 74" stroke="url(#gomLink)" fill="none" strokeDasharray="3 5" />
          <path d="M210 150 Q 128 214 66 232" stroke="url(#gomLink)" fill="none" strokeDasharray="3 5" />
          <path d="M210 150 Q 300 224 362 234" stroke="url(#gomLink)" fill="none" strokeDasharray="3 5" />
          {/* 雷达同心圈 + 准线 */}
          {[58, 92, 126].map((r) => (
            <circle key={r} cx="210" cy="150" r={r} fill="none" stroke="rgba(80,160,240,.26)" strokeDasharray="2 5" />
          ))}
          <line x1="210" y1="10" x2="210" y2="290" stroke="rgba(80,160,240,.1)" />
          <line x1="46" y1="150" x2="374" y2="150" stroke="rgba(80,160,240,.1)" />
          {/* 中心脉冲核 */}
          <circle cx="210" cy="150" r="19" fill="url(#gomCore)" />
          <circle cx="210" cy="150" r="19" stroke="rgba(170,230,255,.7)" />
          <circle cx="210" cy="150" r="30" stroke="rgba(90,190,255,.34)" className="gom-core-pulse" />
          {/* 真实企业机会点（确定性轨道分布；无地理数据时为 0 个） */}
          {locations.map((loc, i) => {
            const ring = 58 + (i % 3) * 34
            const angle = (-90 + (360 / Math.max(locations.length, 1)) * i) * (Math.PI / 180)
            const x = 210 + ring * Math.cos(angle)
            const y = 150 + ring * Math.sin(angle)
            const tone = ['S', 'A'].includes(loc.top_grade) ? 'strong' : loc.top_grade === 'B' ? 'normal' : 'weak'
            return (
              <g key={loc.company_id} className={`gom-node ${tone}`} onClick={() => onSelect?.(loc)} style={{ cursor: 'pointer' }}>
                <circle cx={x} cy={y} r={tone === 'strong' ? 6.5 : tone === 'normal' ? 5 : 4} fill={tone === 'strong' ? '#ffb03a' : tone === 'normal' ? '#29d3ff' : '#4a7ba6'} />
                <circle cx={x} cy={y} r={tone === 'strong' ? 12 : 9} fill="none" stroke={tone === 'strong' ? 'rgba(255,176,58,.5)' : 'rgba(41,211,255,.4)'} className="gom-halo" />
                <title>{`${loc.company_name} · ${[loc.country, loc.province, loc.city].filter(Boolean).join(' ')} · 最高 ${loc.top_score}（${loc.top_grade}级）· 机会 ${loc.opportunity_count}`}</title>
              </g>
            )
          })}
        </svg>
        <div className="gom-sweep" />
        {locations.length === 0 && (
          <div className="gom-empty">
            <strong>真实地理机会数据正在积累</strong>
            <span>地图与雷达为系统视觉；机会点仅在企业具备真实地理信息时出现</span>
          </div>
        )}
      </div>

      {/* 底部图例（视觉定义，非业务数据） */}
      <div className="gom-legend">
        <span><i className="lg strong" />高优先级</span>
        <span><i className="lg normal" />中优先级</span>
        <span><i className="lg weak" />低优先级</span>
      </div>

      {/* 右侧地域列表（真实数据） */}
      <div className="gom-side">
        <div className="gom-side-head">地域机会（真实）</div>
        {locations.length === 0 ? (
          <div className="empty-state compact" style={{ margin: 0 }}><strong>暂无地域聚合数据</strong><span>等待企业地理信息积累。</span></div>
        ) : locations.slice(0, 7).map((loc) => (
          <button className="gom-side-row" key={loc.company_id} onClick={() => navigate(`/companies/${loc.company_id}`)}>
            <div className="gom-side-main">
              <strong>{loc.company_name}</strong>
              <small>{[loc.country, loc.province, loc.city].filter(Boolean).join(' · ')}</small>
            </div>
            <GradeChip grade={loc.top_grade} />
            <span className="gom-score">{loc.top_score}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
