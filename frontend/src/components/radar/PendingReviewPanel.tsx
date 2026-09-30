import { Clock3 } from 'lucide-react'
import { Skeleton } from '../Feedback'
import type { RadarOpportunity } from '../../types'

/** 待人工审核（严格对齐参考图紧凑表格）：企业名称/行业/触发Signal/AI评分/发现时间/操作。
 * 无数据时保留表头 + 紧凑提示；禁止大面积空白。
 */
export function PendingReviewPanel({ items, loading, onSelect, onReview }: {
  items: RadarOpportunity[]
  loading?: boolean
  onSelect: (opp: RadarOpportunity) => void
  onReview: (opp: RadarOpportunity) => void
}) {
  return (
    <div className="prv-table">
      <div className="prv-head prv-cols">
        <span>企业名称</span><span>行业</span><span>触发 Signal</span><span>AI 评分</span><span>发现时间</span><span>操作</span>
      </div>
      {loading ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: '10px 2px' }}>{[0, 1].map((i) => <Skeleton key={i} height={38} />)}</div>
      ) : items.length === 0 ? (
        <div className="prv-empty"><Clock3 size={14} /> 当前没有待人工审核机会 —— 所有真实机会均已处理</div>
      ) : (
        items.slice(0, 4).map((o) => (
          <div className="prv-row prv-cols" key={o.id}>
            <button className="prv-company" onClick={() => onSelect(o)}>
              <span className="cell-lead" style={{ width: 28, height: 28, fontSize: 12 }}>{(o.company_name || '·').slice(0, 1)}</span>
              <strong>{o.company_name || '未关联企业'}</strong>
            </button>
            <span className="prv-cell">—</span>
            <span className="prv-cell" title={o.latest_signal_title || ''}>{o.latest_signal_title || '—'}</span>
            <span className="prv-score">{o.total_score}</span>
            <span className="prv-cell">{new Date(o.created_at).toLocaleDateString('zh-CN')}</span>
            <span className="prv-actions">
              <button className="ghost-btn slim" onClick={() => onSelect(o)}>查看</button>
              <button className="primary-btn slim-btn" onClick={() => onReview(o)}>审核</button>
            </span>
          </div>
        ))
      )}
    </div>
  )
}
