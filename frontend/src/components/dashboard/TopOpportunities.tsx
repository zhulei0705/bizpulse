import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { EmptyState } from '../EmptyState'
import { GradeChip } from '../GradeChip'
import { ScoreRing } from '../ScoreRing'
import { FactTag } from '../FactTag'
import { VerificationTag } from '../EvidencePanel'
import { Skeleton } from '../Feedback'
import { OPPORTUNITY_STAGE_LABELS } from '../../types'
import type { Opportunity } from '../../types'

/** 高价值机会：首页第二视觉重点。Opportunity Score 由后端计算；
 * 机会本身属于假设，明确标注 AI推断/人工假设。只有一条就显示一条，不复制填充。
 */
export function TopOpportunities({ opportunities, loading }: { opportunities: Opportunity[]; loading?: boolean }) {
  const navigate = useNavigate()
  if (loading) {
    return <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}><Skeleton height={96} /></div>
  }
  if (!opportunities.length) {
    return <EmptyState compact title="暂无高价值机会" description="基于真实信号创建机会并通过人工审核后，这里将成为第二视觉重点。" />
  }
  return (
    <div className="top-opp-list">
      {opportunities.map((o) => (
        <button className="top-opp-card" key={o.id} onClick={() => navigate(`/opportunities?focus=${o.id}`)}>
          <ScoreRing score={o.total_score} grade={o.grade} size={92} />
          <div className="top-opp-body">
            <div className="top-opp-head">
              <FactTag value="INFERENCE" />
              <strong>{o.company_name || '未关联企业'} · {o.title}</strong>
            </div>
            <p className="top-opp-problem">{o.problem}</p>
            <div className="opp-card-meta">
              <GradeChip grade={o.grade} />
              <span className="chip">{OPPORTUNITY_STAGE_LABELS[o.stage] || o.stage}</span>
              <span className="top-opp-trigger">⚡ {(o.trigger_event || '—').slice(0, 24)}</span>
              <span className={`chip ${o.evidence_score < 60 ? 'warn' : ''}`}>证据质量 {o.evidence_score}{o.evidence_score < 60 ? '（<60 最高B）' : ''}</span>
              <span className="top-opp-evidence">🔗 证据 {o.evidence_count ?? 0}</span>
              {o.review_status === 'APPROVED' && <VerificationTag status="VERIFIED" />}
            </div>
          </div>
          <span className="top-opp-go"><ArrowRight size={17} /></span>
        </button>
      ))}
    </div>
  )
}
