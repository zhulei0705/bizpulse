import { useNavigate } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { SignalBadge } from '../SignalBadge'
import { FactTag } from '../FactTag'
import { VerificationTag } from '../EvidencePanel'
import { SourceGradeChip } from '../GradeChip'
import { Skeleton } from '../Feedback'
import { EmptyState } from '../EmptyState'
import type { DashboardSummary } from '../../types'

type StreamSignal = DashboardSummary['recent_signals'][number]

/** SignalStream：企业动态流升级版。
 * 每条：时间 · 类型 · 企业 · 标题 · 来源等级 · 事实/AI推断 · 验证状态。
 * 高置信信号（≥80）轻量高亮；点击追溯至企业证据链。禁止演示动态。
 */
export function SignalStream({ signals, loading }: { signals: StreamSignal[]; loading?: boolean }) {
  const navigate = useNavigate()
  if (loading) {
    return <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}><Skeleton height={46} /><Skeleton height={46} /><Skeleton height={46} /></div>
  }
  if (!signals.length) {
    return <EmptyState compact title="暂无真实动态" description="分析一个公开网页开始产生商业信号。每条动态均可追溯原始网页。" />
  }
  return (
    <div className="signal-stream">
      {signals.map((s) => (
        <button
          key={s.id}
          className={`signal-stream-row ${s.confidence >= 80 ? 'hot' : ''}`}
          onClick={() => navigate(`/companies/${s.company_id || ''}`)}
          title="点击查看该企业的完整证据链"
        >
          <span className="timeline-dot" />
          <span className="ss-time">{new Date(s.collected_at).toLocaleTimeString('zh-CN', { hour12: false, hour: '2-digit', minute: '2-digit' })}</span>
          <div className="ss-body">
            <div className="ss-head">
              <SignalBadge type={s.signal_type} small />
              <FactTag value={s.fact_or_inference} />
              {s.verification_status === 'VERIFIED' && <VerificationTag status="VERIFIED" />}
            </div>
            <strong className="ss-title">{s.title}</strong>
            <small className="ss-sub">{s.company_name || '未关联企业'} · {new Date(s.collected_at).toLocaleDateString('zh-CN')}</small>
          </div>
          <div className="ss-side">
            {s.reliability_grade && <SourceGradeChip grade={s.reliability_grade} />}
            <span className="conf-chip" title="置信度">{s.confidence}</span>
            <ExternalLink size={12} className="ss-go" />
          </div>
        </button>
      ))}
    </div>
  )
}
