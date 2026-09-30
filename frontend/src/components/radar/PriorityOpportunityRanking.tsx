import { GradeChip } from '../GradeChip'
import { ScoreRing } from '../ScoreRing'
import { Skeleton } from '../Feedback'
import { OPPORTUNITY_STAGE_LABELS } from '../../types'
import type { RadarOpportunity } from '../../types'

/** 高优先级机会（严格对齐参考图完整排名卡）：
 * 排名徽章 + 企业首字 Logo + 企业名 + 机会描述 + 地区 + Signal 标签 + Score 环 + 状态 + 查看详情。
 * 排序=后端 total_score DESC；只有 1 条就显示 1 条，面板保持正式结构与高度。
 */
export function PriorityOpportunityRanking({ opportunities, loading, onSelect }: {
  opportunities: RadarOpportunity[]
  loading?: boolean
  onSelect: (opp: RadarOpportunity) => void
}) {
  if (loading) {
    return <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>{[0, 1, 2].map((i) => <Skeleton key={i} height={108} />)}</div>
  }
  return (
    <div className="pr-list">
      {opportunities.length === 0 ? (
        <div className="empty-state compact"><strong>暂无满足条件的高价值机会</strong><span>调整筛选条件，或基于真实信号创建机会。</span></div>
      ) : opportunities.slice(0, 4).map((o, idx) => (
        <button className={`pr-card ${idx === 0 ? 'first' : ''}`} key={o.id} onClick={() => onSelect(o)}>
          <div className="pr-card-head">
            <span className={`rank-badge ${idx === 0 ? 'rank-1' : idx === 1 ? 'rank-2' : idx === 2 ? 'rank-3' : 'rank-n'}`}>{idx + 1}</span>
            <span className="pr-lead">{(o.company_name || '·').slice(0, 1)}</span>
            <div className="pr-title-wrap">
              <strong className="pr-company">{o.company_name || '未关联企业'}</strong>
              <span className="pr-desc">{o.title}</span>
            </div>
            <ScoreRing score={o.total_score} grade={o.grade} size={62} />
          </div>
          <div className="pr-card-meta">
            <span className="pr-region">📍 {o.trigger_event ? o.trigger_event.slice(0, 16) : '触发事件待补充'}</span>
            <span className="chip">意图 {o.intent_score}</span>
            <span className="chip">🔗 {o.evidence_count}</span>
            <GradeChip grade={o.grade} />
            <span className="chip">{OPPORTUNITY_STAGE_LABELS[o.stage] || o.stage}</span>
            <span className="pr-go">查看详情 →</span>
          </div>
        </button>
      ))}
      {opportunities.length > 0 && opportunities.length < 4 && (
        <div className="pr-more-hint">更多真实机会正在积累 —— 排序完全来自后端评分引擎</div>
      )}
    </div>
  )
}
