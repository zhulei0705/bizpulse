import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, Building2, ThumbsUp, ThumbsDown, PlayCircle } from 'lucide-react'
import { message } from 'antd'
import { ScoreRing } from '../ScoreRing'
import { GradeChip } from '../GradeChip'
import { FactTag } from '../FactTag'
import { EvidencePanel } from '../EvidencePanel'
import { getOpportunity, reviewOpportunity, getErrorMessage } from '../../api'
import type { Evidence, Opportunity, RadarOpportunity } from '../../types'

const SCORE_BREAKDOWN: { key: keyof RadarOpportunity; label: string; weight: string }[] = [
  { key: 'pain_score', label: '痛点强度', weight: '25%' },
  { key: 'budget_score', label: '预算能力', weight: '20%' },
  { key: 'intent_score', label: '购买意图', weight: '20%' },
  { key: 'urgency_score', label: '紧迫程度', weight: '10%' },
  { key: 'agent_fit_score', label: 'AI 适配度', weight: '10%' },
  { key: 'reachability_score', label: '可触达性', weight: '5%' },
  { key: 'evidence_score', label: '证据质量', weight: '10%' },
]

/** 机会快速详情 Drawer：评分拆解 / 事实与推断 / Evidence / 审核（局部更新，不整页刷新）。 */
export function OpportunityDrawer({ open, opportunity, onClose, onReviewed }: {
  open: boolean
  opportunity: RadarOpportunity | null
  onClose: () => void
  /** 审核完成后回调：页面局部刷新数据 */
  onReviewed?: () => void
}) {
  const navigate = useNavigate()
  const [detail, setDetail] = useState<Opportunity | null>(null)
  const [evidences, setEvidences] = useState<Evidence[]>([])
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!open || !opportunity) return
    setDetail(null)
    setEvidences([])
    setNote('')
    getOpportunity(opportunity.id).then((d) => {
      setDetail(d)
      setEvidences((d.evidences || []).map((e) => ({
        source_record_id: e.source_record_id || '',
        url: e.url || '',
        title: e.title ?? null,
        published_at: null,
        collected_at: new Date().toISOString(),
        excerpt: e.evidence_excerpt ?? null,
        source_name: null,
        reliability_grade: null,
        reliability_score: null,
      })))
    }).catch((e) => message.error(getErrorMessage(e)))
  }, [open, opportunity])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open || !opportunity) return null
  // 展示统一结构：详情补齐 latest_signal_title（来自雷达数据），评分拆解字段两边同构
  const o: RadarOpportunity = detail
    ? { ...opportunity, ...detail, company_name: detail.company_name ?? opportunity.company_name, latest_signal_title: opportunity.latest_signal_title, evidence_count: detail.evidence_count ?? opportunity.evidence_count }
    : opportunity

  const doReview = async (action: 'approve' | 'reject' | 'ready') => {
    setBusy(true)
    try {
      const updated = await reviewOpportunity(opportunity.id, { action, note: note.trim() || undefined })
      message.success({ approve: '已通过', reject: '已驳回', ready: '已加入验证' }[action])
      setDetail(updated)
      onReviewed?.()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const reviewable = o.stage === 'NEW' || o.stage === 'REVIEW'

  return (
    <div className="drawer-mask" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <aside className="drawer-card">
        <div className="drawer-head">
          <div>
            <small>机会快速详情</small>
            <strong>{o.title}</strong>
            <p>{o.company_name || '未关联企业'} · 更新于 {new Date(o.updated_at).toLocaleString('zh-CN', { hour12: false })}</p>
          </div>
          <div className="drawer-head-side">
            <ScoreRing score={o.total_score} grade={o.grade} size={78} />
            <button className="icon-btn small" onClick={onClose} aria-label="关闭"><X size={16} /></button>
          </div>
        </div>

        <div className="drawer-body">
          <div className="drawer-chips">
            <GradeChip grade={o.grade} />
            <span className="chip">阶段：{o.stage}</span>
            <span className="chip">审核：{o.review_status === 'PENDING' ? '待审核' : o.review_status === 'APPROVED' ? '已通过' : o.review_status === 'REJECTED' ? '已驳回' : '已修改'}</span>
            <span className="chip">证据 {o.evidence_count}</span>
          </div>

          <div className="drawer-section">
            <strong>触发事件</strong>
            <p><FactTag value="FACT" /> {o.trigger_event || o.latest_signal_title || '—'}</p>
          </div>
          <div className="drawer-section">
            <strong>核心问题</strong>
            <p>{o.problem}</p>
          </div>
          <div className="drawer-section">
            <strong>建议解决方案（AI推断 / 人工假设）</strong>
            <p><FactTag value="INFERENCE" /> {o.solution}</p>
          </div>
          {o.value_proposition && (
            <div className="drawer-section">
              <strong>价值主张</strong>
              <p>{o.value_proposition}</p>
            </div>
          )}
          {o.purchase_intent && (
            <div className="drawer-section">
              <strong>购买意图</strong>
              <p>{o.purchase_intent}（意图分 {o.intent_score} · 紧迫度 {o.urgency_score}）</p>
            </div>
          )}

          <div className="drawer-section">
            <strong>评分拆解（后端评分引擎）</strong>
            <div className="drawer-scores">
              {SCORE_BREAKDOWN.map((f) => {
                const value = Number(o[f.key]) || 0
                return (
                  <div className="drawer-score-row" key={f.key}>
                    <span>{f.label}<small>{f.weight}</small></span>
                    <div className="rank-bar"><i style={{ width: `${value}%` }} className={f.key === 'evidence_score' && value < 60 ? 'evidence-low' : ''} /></div>
                    <b>{value}</b>
                  </div>
                )
              })}
            </div>
            {o.evidence_score < 60 && <p className="drawer-warn">证据质量 &lt; 60：等级上限 B（防止推断伪装成高确定性机会）</p>}
          </div>

          <div className="drawer-section">
            <strong>Evidence（原始证据）</strong>
            <EvidencePanel evidences={evidences} emptyHint="该机会的证据均关联真实来源记录。" />
          </div>

          {o.review_note && (
            <div className="drawer-section">
              <strong>最近审核记录</strong>
              <p>{o.review_note} · {o.reviewed_at ? new Date(o.reviewed_at).toLocaleString('zh-CN', { hour12: false }) : '—'}</p>
            </div>
          )}

          {reviewable && (
            <div className="drawer-review">
              <input className="text-input" placeholder="审核备注（可选）" value={note} onChange={(e) => setNote(e.target.value)} />
              <div className="drawer-review-actions">
                <button className="secondary-btn" disabled={busy} onClick={() => doReview('approve')}><ThumbsUp size={15} />通过</button>
                <button className="secondary-btn danger" disabled={busy} onClick={() => doReview('reject')}><ThumbsDown size={15} />驳回</button>
                <button className="primary-btn" disabled={busy} onClick={() => doReview('ready')}><PlayCircle size={15} />加入验证</button>
              </div>
            </div>
          )}

          <button className="ghost-btn full" onClick={() => navigate(`/companies/${o.company_id}`)}>
            <Building2 size={14} /> 查看企业完整数据链
          </button>
        </div>
      </aside>
    </div>
  )
}
