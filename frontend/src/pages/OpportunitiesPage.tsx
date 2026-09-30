import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { UserPlus, MessageCircle, Presentation, HandCoins, Trophy, LayoutList, Columns3, ThumbsUp, ThumbsDown, PlayCircle, Pencil } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { GradeChip } from '../components/GradeChip'
import { ScoreRing } from '../components/ScoreRing'
import { Modal, FormField } from '../components/Modal'
import { getOpportunities, getOpportunity, reviewOpportunity, updateOpportunityStage, getErrorMessage } from '../api'
import { GRADE_LABELS, OPPORTUNITY_STAGES, OPPORTUNITY_STAGE_LABELS, type Opportunity, type PageData } from '../types'

const PAGE_SIZE = 50

export default function OpportunitiesPage() {
  const [params, setParams] = useSearchParams()
  const focusId = params.get('focus')
  const [data, setData] = useState<PageData<Opportunity> | null>(null)
  const [view, setView] = useState<'kanban' | 'list'>('kanban')
  const [stageFilter, setStageFilter] = useState('')
  const [gradeFilter, setGradeFilter] = useState('')
  const [minScore, setMinScore] = useState(0)
  const [detail, setDetail] = useState<Opportunity | null>(null)
  const [editOpen, setEditOpen] = useState(false)
  const [note, setNote] = useState('')
  const [editScores, setEditScores] = useState<Record<string, number>>({})
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      setData(await getOpportunities({ stage: stageFilter || undefined, grade: gradeFilter || undefined, min_score: minScore || undefined, page: 1, page_size: PAGE_SIZE }))
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }, [stageFilter, gradeFilter, minScore])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!focusId || !data) return
    const found = data.items.find((o) => o.id === focusId)
    if (found) setDetail(found)
    setParams({}, { replace: true })
  }, [focusId, data, setParams])

  const byStage = useMemo(() => {
    const map: Record<string, Opportunity[]> = {}
    for (const stage of OPPORTUNITY_STAGES) map[stage] = []
    for (const item of data?.items || []) (map[item.stage] || (map[item.stage] = [])).push(item)
    return map
  }, [data])

  const openDetail = async (id: string) => {
    try {
      setDetail(await getOpportunity(id))
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }

  const doReview = async (action: 'approve' | 'reject' | 'ready') => {
    if (!detail) return
    setBusy(true)
    try {
      const updated = await reviewOpportunity(detail.id, { action, note: note.trim() || undefined })
      message.success({ approve: '已通过，进入验证', reject: '已驳回', ready: '已加入验证' }[action])
      setDetail(updated)
      setNote('')
      load()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const doEdit = async () => {
    if (!detail) return
    setBusy(true)
    try {
      const updated = await reviewOpportunity(detail.id, { action: 'edit', note: note.trim() || undefined, updates: editScores })
      message.success('已保存修改，评分已重算')
      setDetail(updated)
      setEditOpen(false)
      setEditScores({})
      load()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const moveStage = async (opp: Opportunity, stage: string) => {
    try {
      await updateOpportunityStage(opp.id, stage)
      message.success(`已移动到「${OPPORTUNITY_STAGE_LABELS[stage]}」`)
      load()
      setDetail((prev) => (prev && prev.id === opp.id ? { ...prev, stage } : prev))
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }

  const openEdit = () => {
    if (!detail) return
    setEditScores({
      pain_score: detail.pain_score, budget_score: detail.budget_score, intent_score: detail.intent_score,
      urgency_score: detail.urgency_score, agent_fit_score: detail.agent_fit_score,
      reachability_score: detail.reachability_score, evidence_score: detail.evidence_score,
    })
    setEditOpen(true)
  }

  const oppCard = (o: Opportunity, compact = false) => (
    <button className="opp-card" key={o.id} onClick={() => openDetail(o.id)}>
      <div className="opp-card-head">
        <ScoreRing score={o.total_score} grade={o.grade} size={52}/>
        <div className="opp-card-title">
          <strong>{o.company_name || '未关联企业'}</strong>
          <span>{o.title}</span>
        </div>
      </div>
      {!compact && <p className="opp-problem">{o.problem}</p>}
      {!compact && o.solution && <p className="opp-solution">方案：{o.solution}</p>}
      <div className="opp-card-meta">
        <GradeChip grade={o.grade}/>
        <span className="chip">触发：{(o.trigger_event || '—').slice(0, 18)}</span>
        <span className="chip">证据 {o.evidence_count ?? 0}</span>
        <span className="chip">{new Date(o.updated_at).toLocaleDateString('zh-CN')}</span>
      </div>
    </button>
  )

  return <div className="page-stack">
    <PageHero eyebrow="客户机会" title="客户" highlight="机会" description="把发现的机会推进到真实客户验证，形成从商机到成交的闭环。人工审核保障机会质量。"/>
    <div className="stats-grid five">
      <StatCard icon={<UserPlus/>} label="待审核" tone="cyan" value={data?.counts?.pending_review ?? 0}/>
      <StatCard icon={<MessageCircle/>} label="验证中" tone="blue" value={data?.counts?.validating ?? 0}/>
      <StatCard icon={<Presentation/>} label="已成交" tone="gold" value={data?.counts?.won ?? 0}/>
      <StatCard icon={<HandCoins/>} label="已拒绝" tone="danger" value={data?.counts?.rejected ?? 0}/>
      <StatCard icon={<Trophy/>} label="机会总数" tone="purple" value={data?.total ?? 0}/>
    </div>

    <div className="filter-bar">
      <select className="select-input compact" value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}>
        <option value="">全部阶段</option>
        {OPPORTUNITY_STAGES.map((s) => <option key={s} value={s}>{OPPORTUNITY_STAGE_LABELS[s]}</option>)}
      </select>
      <select className="select-input compact" value={gradeFilter} onChange={(e) => setGradeFilter(e.target.value)}>
        <option value="">全部等级</option>
        {Object.keys(GRADE_LABELS).map((g) => <option key={g} value={g}>{GRADE_LABELS[g]}</option>)}
      </select>
      <select className="select-input compact" value={minScore} onChange={(e) => setMinScore(Number(e.target.value))}>
        <option value={0}>全部分数</option>
        <option value={60}>≥ 60</option>
        <option value={70}>≥ 70</option>
        <option value={80}>≥ 80</option>
      </select>
      <div className="view-toggle">
        <button className={`toggle-chip ${view === 'list' ? 'on' : ''}`} onClick={() => setView('list')}><LayoutList size={14}/>列表</button>
        <button className={`toggle-chip ${view === 'kanban' ? 'on' : ''}`} onClick={() => setView('kanban')}><Columns3 size={14}/>Kanban</button>
      </div>
    </div>

    {view === 'kanban' ? (
      <div className="kanban-shell">
        {OPPORTUNITY_STAGES.map((stage) => (
          <div className="kanban-col" key={stage} data-stage={stage}>
            <div className="kanban-head"><strong>{OPPORTUNITY_STAGE_LABELS[stage]}</strong><span>{byStage[stage].length}</span></div>
            {byStage[stage].length === 0
              ? <EmptyState title="暂无机会" description="真实机会进入该阶段后会显示在这里。"/>
              : <div className="kanban-cards">{byStage[stage].map((o) => oppCard(o, true))}</div>}
          </div>
        ))}
      </div>
    ) : (
      <SectionCard title="机会列表" subtitle="按总分倒序（分数由后端 Score Engine 计算）" action={<span className="muted-tip">共 {data?.total ?? 0} 个</span>}>
        {data && data.items.length > 0
          ? <div className="opp-grid">{data.items.map((o) => oppCard(o))}</div>
          : <EmptyState title="暂无真实机会" description="在企业详情页基于真实信号创建机会，或先分析公开网页。"/>}
      </SectionCard>
    )}

    {/* 机会详情 + 人工审核 */}
    <Modal open={!!detail} title="机会详情 · 人工审核" subtitle={detail?.company_name || ''} onClose={() => { setDetail(null); setNote('') }} width={680}>
      {detail && (
        <div className="opp-detail">
          <div className="opp-detail-top">
            <ScoreRing score={detail.total_score} grade={detail.grade} size={84}/>
            <div>
              <h3>{detail.title}</h3>
              <div className="opp-card-meta">
                <GradeChip grade={detail.grade}/>
                <span className="chip">{OPPORTUNITY_STAGE_LABELS[detail.stage]}</span>
                <span className="chip">证据 {detail.evidence_count ?? detail.evidences?.length ?? 0}</span>
                <span className="chip">审核状态 {detail.review_status === 'PENDING' ? '待审核' : detail.review_status === 'APPROVED' ? '已通过' : detail.review_status === 'REJECTED' ? '已驳回' : '已修改'}</span>
              </div>
            </div>
          </div>
          <div className="opp-detail-section">
            <strong>问题</strong><p>{detail.problem}</p>
            <strong>建议方案</strong><p>{detail.solution}</p>
            {detail.value_proposition && <><strong>价值主张</strong><p>{detail.value_proposition}</p></>}
            {detail.trigger_event && <><strong>核心触发事件</strong><p>{detail.trigger_event}</p></>}
          </div>
          <div className="score-strip">
            <span>Pain {detail.pain_score}</span><span>Budget {detail.budget_score}</span><span>Intent {detail.intent_score}</span>
            <span>Urgency {detail.urgency_score}</span><span>AgentFit {detail.agent_fit_score}</span><span>Reach {detail.reachability_score}</span>
            <span className={detail.evidence_score < 60 ? 'warn' : ''}>Evidence {detail.evidence_score}{detail.evidence_score < 60 ? '（<60 最高B）' : ''}</span>
          </div>
          {detail.evidences && detail.evidences.length > 0 && (
            <div className="opp-detail-section">
              <strong>关联证据</strong>
              {detail.evidences.map((ev) => (
                <div className="opp-evidence-row" key={ev.id}>
                  <span>{ev.title || ev.evidence_excerpt || '证据记录'}</span>
                  {ev.url && <a href={ev.url} target="_blank" rel="noreferrer noopener">查看原始来源</a>}
                </div>
              ))}
            </div>
          )}
          {detail.review_note && <p className="form-hint">审核备注：{detail.review_note}（{detail.reviewed_by || '—'} · {detail.reviewed_at ? new Date(detail.reviewed_at).toLocaleString('zh-CN', { hour12: false }) : '—'}）</p>}
          <FormField label="审核备注">
            <input className="text-input" value={note} placeholder="例：证据充分，进入验证" onChange={(e) => setNote(e.target.value)}/>
          </FormField>
          <div className="modal-actions wrap">
            <button className="secondary-btn" disabled={busy} onClick={() => doReview('approve')}><ThumbsUp size={15}/>通过</button>
            <button className="secondary-btn danger" disabled={busy} onClick={() => doReview('reject')}><ThumbsDown size={15}/>驳回</button>
            <button className="secondary-btn" disabled={busy} onClick={openEdit}><Pencil size={15}/>修改</button>
            <button className="primary-btn" disabled={busy} onClick={() => doReview('ready')}><PlayCircle size={15}/>加入验证</button>
          </div>
          <div className="stage-move">
            <span>阶段流转：</span>
            {OPPORTUNITY_STAGES.filter((s) => s !== detail.stage).map((s) => (
              <button key={s} className="chip clickable" onClick={() => moveStage(detail, s)}>{OPPORTUNITY_STAGE_LABELS[s]}</button>
            ))}
          </div>
        </div>
      )}
    </Modal>

    {/* 修改评分（action=edit → 后端重算总分） */}
    <Modal open={editOpen} title="修改机会" subtitle="调整字段或评分，总分与等级由后端 Score Engine 重新计算" onClose={() => setEditOpen(false)} width={560}>
      <div className="score-editor">
        {(['pain_score', 'budget_score', 'intent_score', 'urgency_score', 'agent_fit_score', 'reachability_score', 'evidence_score'] as const).map((key) => (
          <label className="score-row" key={key}>
            <span>{key.replace('_score', '').toUpperCase()}</span>
            <input type="range" min={0} max={100} value={editScores[key] ?? 0} onChange={(e) => setEditScores((prev) => ({ ...prev, [key]: Number(e.target.value) }))}/>
            <strong>{editScores[key] ?? 0}</strong>
          </label>
        ))}
      </div>
      <div className="modal-actions">
        <button className="secondary-btn" onClick={() => setEditOpen(false)}>取消</button>
        <button className="primary-btn" disabled={busy} onClick={doEdit}>保存修改</button>
      </div>
    </Modal>
  </div>
}
