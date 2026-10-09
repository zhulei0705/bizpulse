import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { UserPlus, MessageCircle, Presentation, HandCoins, Trophy, LayoutList, Columns3, ThumbsUp, ThumbsDown, PlayCircle, Pencil, Sparkles, FileSearch, CircleAlert } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { GradeChip } from '../components/GradeChip'
import { ScoreRing } from '../components/ScoreRing'
import { Modal, FormField } from '../components/Modal'
import {
  analyzeCompanyOpportunities,
  addToExperiment,
  approveCandidate,
  candidateNeedMoreEvidence,
  getExperiments,
  getOpportunities,
  getOpportunity,
  getOpportunityCandidate,
  getOpportunityCandidates,
  rejectCandidate,
  reviewOpportunity,
  runOpportunityAnalysisJob,
  updateOpportunityStage,
  getErrorMessage,
} from '../api'
import {
  EXPERIMENT_STATUS_LABELS,
  GRADE_LABELS,
  OBSERVED_INTENT_LABELS,
  OPPORTUNITY_CANDIDATE_STATUS_LABELS,
  OPPORTUNITY_REJECT_REASONS,
  OPPORTUNITY_STAGES,
  OPPORTUNITY_STAGE_LABELS,
  type Experiment,
  type Opportunity,
  type OpportunityCandidate,
  type PageData,
} from '../types'

const PAGE_SIZE = 50

export default function OpportunitiesPage() {
  const [params, setParams] = useSearchParams()
  const focusId = params.get('focus')
  const [data, setData] = useState<PageData<Opportunity> | null>(null)
  const [candidates, setCandidates] = useState<OpportunityCandidate[]>([])
  const [candidateDetail, setCandidateDetail] = useState<OpportunityCandidate | null>(null)
  const [rejectTarget, setRejectTarget] = useState<OpportunityCandidate | null>(null)
  const [rejectReason, setRejectReason] = useState('WEAK_EVIDENCE')
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

  const loadCandidates = useCallback(async () => {
    try {
      const page = await getOpportunityCandidates({ page: 1, page_size: 20 })
      setCandidates(page.items)
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { loadCandidates() }, [loadCandidates])

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
    // T06 状态机：REJECTED 需要拒绝原因、WON 需要真实合同金额 —— 引导走详情审核弹窗
    if (stage === 'REJECTED' || stage === 'WON') {
      message.info(stage === 'REJECTED' ? '拒绝需选择真实拒绝原因：请打开详情后操作' : '成交需录入真实合同金额：请打开详情后操作')
      openDetail(opp.id)
      return
    }
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

  // ---- T05：AI 候选审核 ----
  const runBatchAnalysis = async () => {
    setBusy(true)
    try {
      const r = await runOpportunityAnalysisJob()
      message.success(`批量分析完成：分析 ${r.analyzed} 家、跳过 ${r.skipped} 家、新建 ${r.created} 个、更新 ${r.updated} 个候选`)
      loadCandidates()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const analyzeSingle = async (candidate: OpportunityCandidate) => {
    setBusy(true)
    try {
      const r = await analyzeCompanyOpportunities(candidate.company_id, true)
      message.success(r.status === 'ANALYZED' ? '已重新分析该企业的机会候选' : `未执行分析：${r.reason || r.status}`)
      loadCandidates()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const doCandidateApprove = async (candidate: OpportunityCandidate) => {
    setBusy(true)
    try {
      const r = await approveCandidate(candidate.id, { note: note.trim() || undefined })
      message.success('候选已通过，正式机会已生成（阶段：待审核）')
      setCandidateDetail(null)
      setNote('')
      loadCandidates()
      load()
      if (r.opportunity_id) setParams({ focus: r.opportunity_id })
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const doCandidateNeedMoreEvidence = async (candidate: OpportunityCandidate) => {
    setBusy(true)
    try {
      await candidateNeedMoreEvidence(candidate.id, { note: note.trim() || undefined })
      message.success('已标记证据不足，补充证据后可重新分析')
      setCandidateDetail(null)
      setNote('')
      loadCandidates()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const doCandidateReject = async () => {
    if (!rejectTarget) return
    setBusy(true)
    try {
      await rejectCandidate(rejectTarget.id, { reject_reason: rejectReason, note: note.trim() || undefined })
      message.success('候选已拒绝')
      setRejectTarget(null)
      setCandidateDetail(null)
      setNote('')
      loadCandidates()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  const openCandidateDetail = async (id: string) => {
    try {
      setCandidateDetail(await getOpportunityCandidate(id))
      setNote('')
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }

  // T06：机会加入实验（须已审核；联动创建验证目标）
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [joinExperimentId, setJoinExperimentId] = useState('')
  const loadExperiments = useCallback(async () => {
    try {
      const page = await getExperiments({ page: 1, page_size: 50 })
      setExperiments(page.items)
    } catch (e) { message.error(getErrorMessage(e)) }
  }, [])
  useEffect(() => { loadExperiments() }, [loadExperiments])

  const doJoinExperiment = async () => {
    if (!detail) return
    if (!joinExperimentId) { message.warning('请选择实验'); return }
    setBusy(true)
    try {
      const r = await addToExperiment(detail.id, joinExperimentId)
      message.success(r.target_created
        ? '已加入实验，并创建了对应验证目标（状态：新加入）'
        : '已加入实验，关联到已有验证目标')
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally { setBusy(false) }
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

  const candCard = (c: OpportunityCandidate) => (
    <div className="opp-card" key={c.id}>
      <div className="opp-card-head">
        <ScoreRing score={c.total_score} grade={c.grade} size={52}/>
        <div className="opp-card-title">
          <strong>{c.company_name || '未关联企业'}</strong>
          <span>{c.title}</span>
        </div>
        <span className="chip">{OPPORTUNITY_CANDIDATE_STATUS_LABELS[c.status] || c.status}</span>
      </div>
      <div className="opp-card-meta">
        <GradeChip grade={c.grade}/>
        {c.pain_category_label && <span className="chip">{c.pain_category_label}</span>}
        <span className="chip">证据 {c.evidence_refs.length}</span>
        <span className="chip">{c.generated_by === 'LLM' ? 'AI 解释' : '规则生成'}</span>
        <span className="chip">{new Date(c.updated_at).toLocaleDateString('zh-CN')}</span>
      </div>
      {c.why_now && <p className="opp-problem">Why now：{c.why_now}</p>}
      {c.evidence_summary && <p className="opp-solution">证据：{c.evidence_summary}</p>}
      {c.risk_notes.length > 0 && (
        <p className="opp-problem"><CircleAlert size={13} style={{ verticalAlign: '-2px' }}/> {c.risk_notes[0]}{c.risk_notes.length > 1 ? ` 等 ${c.risk_notes.length} 项风险` : ''}</p>
      )}
      <div className="modal-actions wrap">
        <button className="secondary-btn" onClick={() => openCandidateDetail(c.id)}><FileSearch size={14}/>详情</button>
        {c.status === 'REVIEW' || c.status === 'DETECTED' || c.status === 'NEED_MORE_EVIDENCE' ? (
          <>
            <button className="primary-btn" onClick={() => doCandidateApprove(c)}><ThumbsUp size={14}/>通过转正式</button>
            <button className="secondary-btn" disabled={busy} onClick={() => doCandidateNeedMoreEvidence(c)}>证据不足</button>
            <button className="secondary-btn danger" disabled={busy} onClick={() => { setRejectTarget(c); setNote('') }}><ThumbsDown size={14}/>拒绝</button>
          </>
        ) : (
          <span className="muted-tip">人工已处理（{OPPORTUNITY_CANDIDATE_STATUS_LABELS[c.status] || c.status}）</span>
        )}
      </div>
    </div>
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

    {/* T05：AI 候选审核（候选 → 人工审核 → 正式机会） */}
    <SectionCard
      title="AI 机会候选"
      subtitle="机会判断引擎基于已批准信号自动生成（无证据不生成）；审核通过后转为正式机会"
      action={
        <button className="secondary-btn" disabled={busy} onClick={runBatchAnalysis}>
          <Sparkles size={14}/>批量分析
        </button>
      }
    >
      {candidates.length === 0
        ? <EmptyState title="暂无候选" description="先在企业详情页批准真实信号，再点「批量分析」由引擎生成候选。"/>
        : <div className="opp-grid">{candidates.map(candCard)}</div>}
    </SectionCard>

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
          {(detail.contact_count || detail.observed_intent || detail.confirmed_budget) && (
            <div className="opp-detail-section">
              <strong>真实验证进展</strong>
              <div className="score-strip">
                <span>联系 {detail.contact_count ?? 0} 次</span>
                {detail.last_contacted_at && <span>最后联系 {new Date(detail.last_contacted_at).toLocaleDateString('zh-CN')}</span>}
                {detail.observed_intent && <span>真实意图：{OBSERVED_INTENT_LABELS[detail.observed_intent] || detail.observed_intent}</span>}
                {detail.confirmed_budget && <span>确认预算：{detail.confirmed_budget}</span>}
              </div>
            </div>
          )}
          {detail.review_status === 'APPROVED' && (
            <div className="opp-detail-section">
              <strong>加入验证实验</strong>
              <div className="filter-bar">
                <select className="select-input compact" style={{ flex: 2 }} value={joinExperimentId} onChange={(e) => setJoinExperimentId(e.target.value)}>
                  <option value="">选择实验…</option>
                  {experiments.filter((x) => ['DRAFT', 'READY', 'RUNNING', 'PAUSED'].includes(x.status)).map((x) => (
                    <option key={x.id} value={x.id}>{x.name}（{EXPERIMENT_STATUS_LABELS[x.status]}）</option>
                  ))}
                </select>
                <button className="primary-btn" disabled={busy || !joinExperimentId} onClick={doJoinExperiment}>加入实验</button>
              </div>
            </div>
          )}
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

    {/* T05：候选详情 + 审核 */}
    <Modal open={!!candidateDetail} title="机会候选 · 人工审核" subtitle={candidateDetail?.company_name || ''} onClose={() => { setCandidateDetail(null); setNote('') }} width={680}>
      {candidateDetail && (
        <div className="opp-detail">
          <div className="opp-detail-top">
            <ScoreRing score={candidateDetail.total_score} grade={candidateDetail.grade} size={84}/>
            <div>
              <h3>{candidateDetail.title}</h3>
              <div className="opp-card-meta">
                <GradeChip grade={candidateDetail.grade}/>
                <span className="chip">{OPPORTUNITY_CANDIDATE_STATUS_LABELS[candidateDetail.status] || candidateDetail.status}</span>
                <span className="chip">置信度 {candidateDetail.confidence}</span>
                {candidateDetail.grade_cap_reason && <span className="chip">等级封顶：{candidateDetail.grade_cap_reason}</span>}
              </div>
            </div>
          </div>
          <div className="opp-detail-section">
            <strong>问题假设（AI 推断）</strong><p>{candidateDetail.problem_hypothesis}</p>
            <strong>方案假设（需验证）</strong><p>{candidateDetail.solution_hypothesis}</p>
            {candidateDetail.value_hypothesis && <><strong>价值假设</strong><p>{candidateDetail.value_hypothesis}</p></>}
            {candidateDetail.trigger_summary && <><strong>触发信号</strong><p>{candidateDetail.trigger_summary}</p></>}
            {candidateDetail.why_now && <><strong>Why now</strong><p>{candidateDetail.why_now}</p></>}
          </div>
          <div className="score-strip">
            <span>Pain {candidateDetail.pain_score}</span><span>Budget {candidateDetail.budget_score}</span><span>Intent {candidateDetail.intent_score}</span>
            <span>Urgency {candidateDetail.urgency_score}</span><span>AgentFit {candidateDetail.agent_fit_score}</span><span>Reach {candidateDetail.reachability_score}</span>
            <span className={candidateDetail.evidence_score < 60 ? 'warn' : ''}>Evidence {candidateDetail.evidence_score}{candidateDetail.evidence_score < 60 ? '（<60 最高B）' : ''}</span>
          </div>
          {candidateDetail.risk_notes.length > 0 && (
            <div className="opp-detail-section">
              <strong>风险备注</strong>
              {candidateDetail.risk_notes.map((r, i) => <p key={i}>· {r}</p>)}
            </div>
          )}
          {candidateDetail.validation_questions.length > 0 && (
            <div className="opp-detail-section">
              <strong>验证问题（客户访谈用）</strong>
              {candidateDetail.validation_questions.map((q, i) => <p key={i}>{i + 1}. {q}</p>)}
            </div>
          )}
          {candidateDetail.evidence_refs.length > 0 && (
            <div className="opp-detail-section">
              <strong>原文证据（{candidateDetail.evidence_refs.length} 条）</strong>
              {candidateDetail.evidence_refs.map((ev, i) => (
                <div className="opp-evidence-row" key={i}>
                  <span>{(ev.excerpt || '').slice(0, 60)}…（{ev.grade ? `${ev.grade} 级来源` : '来源未知'}）</span>
                  {ev.url && <a href={ev.url} target="_blank" rel="noreferrer noopener">查看原始来源</a>}
                </div>
              ))}
            </div>
          )}
          {candidateDetail.contradicting_evidence.length > 0 && (
            <div className="opp-detail-section">
              <strong>矛盾证据</strong>
              {candidateDetail.contradicting_evidence.map((ev, i) => <p key={i}>· {(ev.excerpt || '').slice(0, 100)}</p>)}
            </div>
          )}
          {candidateDetail.review_note && <p className="form-hint">审核备注：{candidateDetail.review_note}（{candidateDetail.reviewed_by || '—'} · {candidateDetail.reviewed_at ? new Date(candidateDetail.reviewed_at).toLocaleString('zh-CN', { hour12: false }) : '—'}）</p>}
          <FormField label="审核备注">
            <input className="text-input" value={note} placeholder="例：证据充分，转正式机会跟进" onChange={(e) => setNote(e.target.value)}/>
          </FormField>
          <div className="modal-actions wrap">
            {candidateDetail.status === 'REVIEW' || candidateDetail.status === 'DETECTED' || candidateDetail.status === 'NEED_MORE_EVIDENCE' ? (
              <>
                <button className="primary-btn" disabled={busy} onClick={() => doCandidateApprove(candidateDetail)}><ThumbsUp size={15}/>通过转正式</button>
                <button className="secondary-btn" disabled={busy} onClick={() => doCandidateNeedMoreEvidence(candidateDetail)}>证据不足</button>
                <button className="secondary-btn danger" disabled={busy} onClick={() => setRejectTarget(candidateDetail)}><ThumbsDown size={15}/>拒绝</button>
                <button className="secondary-btn" disabled={busy} onClick={() => analyzeSingle(candidateDetail)}><Sparkles size={15}/>重新分析</button>
              </>
            ) : (
              <span className="muted-tip">该候选人工已处理，仅可查看。</span>
            )}
          </div>
        </div>
      )}
    </Modal>

    {/* T05：拒绝候选（原因用于后续复盘） */}
    <Modal open={!!rejectTarget} title="拒绝候选" subtitle={rejectTarget?.title || ''} onClose={() => setRejectTarget(null)} width={480}>
      <FormField label="拒绝原因（复盘依据）">
        <select className="select-input" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}>
          {Object.entries(OPPORTUNITY_REJECT_REASONS).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
      </FormField>
      <FormField label="备注（可选）">
        <input className="text-input" value={note} placeholder="补充说明" onChange={(e) => setNote(e.target.value)}/>
      </FormField>
      <div className="modal-actions">
        <button className="secondary-btn" onClick={() => setRejectTarget(null)}>取消</button>
        <button className="primary-btn danger" disabled={busy} onClick={doCandidateReject}>确认拒绝</button>
      </div>
    </Modal>
  </div>
}
