import { useNavigate } from 'react-router-dom'
import { SignalBadge } from '../SignalBadge'
import { FactTag } from '../FactTag'
import { SourceGradeChip } from '../GradeChip'
import { Skeleton } from '../Feedback'
import type { RadarSignal } from '../../types'

/** 机会流（严格对齐参考图）：Timeline Rail + 圆点 + 紧凑卡片（一屏约 6 条）。
 * 点击追溯企业证据链；只有 N 条真实数据就显示 N 条，禁止复制填充。
 */
export function OpportunityStream({ signals, loading }: { signals: RadarSignal[]; loading?: boolean }) {
  const navigate = useNavigate()
  if (loading) {
    return <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} height={56} />)}</div>
  }
  if (!signals.length) {
    return (
      <div className="empty-state compact">
        <strong>暂未发现新的商业机会</strong>
        <span>调整筛选条件，或分析一个公开网页产生新信号。</span>
      </div>
    )
  }
  return (
    <div className="os-rail">
      {signals.slice(0, 7).map((s, idx) => (
        <button
          key={s.id}
          className="os-item"
          onClick={() => navigate(`/companies/${s.company_id || ''}`)}
          title="点击查看该企业的完整证据链（Signal → Evidence → 原始 URL）"
        >
          <span className={`os-dot ${idx === 0 ? 'first' : ''}`} />
          <span className="os-time">{new Date(s.collected_at).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })}</span>
          <div className="os-card">
            <div className="os-head">
              <span className="os-lead">{(s.company_name || '·').slice(0, 1)}</span>
              <div className="os-title-wrap">
                <strong className="os-title">{s.title}</strong>
                <small className="os-company">{s.company_name || '未关联企业'}</small>
              </div>
              {s.opportunity_score != null && <span className="os-score">{s.opportunity_score}</span>}
            </div>
            <div className="os-meta">
              <SignalBadge type={s.signal_type} small />
              <FactTag value={s.fact_or_inference} />
              {s.reliability_grade && <SourceGradeChip grade={s.reliability_grade} />}
              <span className="conf-chip">置信 {s.confidence}</span>
              <span className="chip">🔗 {s.evidence_count}</span>
            </div>
          </div>
        </button>
      ))}
    </div>
  )
}
