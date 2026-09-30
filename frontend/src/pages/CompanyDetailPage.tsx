import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, RadioTower, Target, BrainCircuit, Plus, ExternalLink } from 'lucide-react'
import { message } from 'antd'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { SignalBadge } from '../components/SignalBadge'
import { FactTag } from '../components/FactTag'
import { GradeChip } from '../components/GradeChip'
import { ScoreRing } from '../components/ScoreRing'
import { EvidencePanel } from '../components/EvidencePanel'
import { SignalCreateModal } from '../components/SignalCreateModal'
import { OpportunityCreateModal } from '../components/OpportunityCreateModal'
import { getCompanyOverview, getErrorMessage } from '../api'
import { GRADE_LABELS, OPPORTUNITY_STAGE_LABELS, type CompanyOverview, type Signal } from '../types'

function fmt(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
}

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [overview, setOverview] = useState<CompanyOverview | null>(null)
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null)
  const [signalModal, setSignalModal] = useState(false)
  const [oppModal, setOppModal] = useState(false)

  const load = useCallback(async () => {
    if (!id) return
    try {
      const data = await getCompanyOverview(id)
      setOverview(data)
      setSelectedSignal((prev) => (prev ? data.signals.find((s) => s.id === prev.id) || data.signals[0] || null : data.signals[0] || null))
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }, [id])

  useEffect(() => { load() }, [load])

  if (!overview) {
    return <div className="page-stack">
      <SectionCard title="企业详情"><EmptyState title="加载中…" description="正在读取企业数据链。"/></SectionCard>
    </div>
  }

  const { company, signals, pain_points, opportunities, source_records, counts } = overview

  return <div className="page-stack">
    <div className="detail-hero">
      <div className="detail-hero-main">
        <button className="ghost-btn slim" onClick={() => navigate('/companies')}><ArrowLeft size={15}/>返回企业库</button>
        <div className="detail-title-row">
          <div className="stat-icon big"><Building2/></div>
          <div>
            <h2>{company.company_name}</h2>
            <div className="detail-sub">
              {company.domain && <a href={company.website || `https://${company.domain}`} target="_blank" rel="noreferrer noopener">{company.domain} <ExternalLink size={12}/></a>}
              <span>{[company.industry, company.sub_industry].filter(Boolean).join(' / ') || '行业未识别'}</span>
              <span>{[company.country, company.province, company.city].filter(Boolean).join(' · ') || '地区未知'}</span>
              <span>{company.employee_range || '规模未知'}</span>
            </div>
          </div>
        </div>
        {company.company_description && <p className="detail-desc">{company.company_description}</p>}
        {((company.main_products?.length ?? 0) > 0 || (company.main_markets?.length ?? 0) > 0) && (
          <div className="detail-chips">
            {company.main_products.map((p) => <span className="chip" key={`p-${p}`}>产品 · {p}</span>)}
            {company.main_markets.map((m) => <span className="chip" key={`m-${m}`}>市场 · {m}</span>)}
          </div>
        )}
        <div className="detail-chips">
          <span className="chip">来源记录 {counts.source_records}</span>
          <span className="chip">商业信号 {counts.signals}</span>
          <span className="chip">AI推断痛点 {counts.pain_points}</span>
          <span className="chip">商业机会 {counts.opportunities}</span>
          <span className="chip">入库 {fmt(company.created_at)}</span>
        </div>
      </div>
      <div className="detail-actions">
        <button className="secondary-btn" onClick={() => setSignalModal(true)}><Plus size={15}/>新增商业信号</button>
        <button className="primary-btn" onClick={() => setOppModal(true)}><Target size={15}/>创建商业机会</button>
      </div>
    </div>

    <div className="split-layout signal-layout">
      <SectionCard title="商业信号" subtitle="来自真实网页的事实记录（规则引擎 + 人工录入）" action={<span className="muted-tip">{signals.length} 条</span>}>
        {signals.length === 0 ? (
          <EmptyState title="暂无商业信号" description="分析一个该企业的公开网页，或手动新增信号。"/>
        ) : (
          <div className="signal-feed">
            {signals.map((s) => (
              <button className={`signal-item ${selectedSignal?.id === s.id ? 'selected' : ''}`} key={s.id} onClick={() => setSelectedSignal(s)}>
                <div className="signal-item-head">
                  <SignalBadge type={s.signal_type}/>
                  <FactTag value={s.fact_or_inference}/>
                  <span className="conf-chip" title="置信度">置信 {s.confidence}</span>
                </div>
                <strong>{s.title}</strong>
                {s.description && <p>{s.description}</p>}
                <small>采集 {fmt(s.collected_at)}</small>
              </button>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="信号证据" subtitle="每条信号都可追溯到原始公开网页">
        {selectedSignal ? (
          <div className="signal-detail">
            <div className="signal-item-head">
              <SignalBadge type={selectedSignal.signal_type}/>
              <FactTag value={selectedSignal.fact_or_inference}/>
              <span className="conf-chip">置信 {selectedSignal.confidence}</span>
            </div>
            <h4>{selectedSignal.title}</h4>
            {selectedSignal.description && <p>{selectedSignal.description}</p>}
            <EvidencePanel evidences={selectedSignal.evidence ? [selectedSignal.evidence] : []} emptyHint="该信号暂无挂接证据。"/>
          </div>
        ) : <EmptyState title="请选择一条信号"/>}
      </SectionCard>
    </div>

    <div className="split-layout signal-layout">
      <SectionCard title="潜在痛点" subtitle="以下内容为 AI推断，不作为事实使用" action={<FactTag value="INFERENCE"/>}>
        {pain_points.length === 0 ? (
          <EmptyState title="暂无痛点推断" description="配置 LLM 后将基于真实信号自动推断；或人工创建机会。"/>
        ) : (
          <div className="pain-list">
            {pain_points.map((p) => (
              <div className="pain-item" key={p.id}>
                <div className="signal-item-head">
                  <BrainCircuit size={15}/>
                  <FactTag value="INFERENCE"/>
                  <span className="conf-chip">置信 {p.confidence}</span>
                </div>
                <strong>{p.description}</strong>
                {p.reason && <p>{p.reason}</p>}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      <SectionCard title="商业机会" subtitle="评分与等级由后端 Score Engine 计算" action={<span className="muted-tip">{opportunities.length} 个</span>}>
        {opportunities.length === 0 ? (
          <EmptyState title="暂无商业机会" description="基于真实信号人工创建机会假设，进入审核与验证流程。"/>
        ) : (
          <div className="opp-mini-list">
            {opportunities.map((o) => (
              <button className="opp-mini" key={o.id} onClick={() => navigate(`/opportunities?focus=${o.id}`)}>
                <ScoreRing score={o.total_score} grade={o.grade} size={64}/>
                <div className="opp-mini-copy">
                  <strong>{o.title}</strong>
                  <span className="opp-mini-meta">
                    <GradeChip grade={o.grade}/>
                    <span className="chip">{GRADE_LABELS[o.grade] || o.grade}</span>
                    <span className="chip">{OPPORTUNITY_STAGE_LABELS[o.stage] || o.stage}</span>
                    <span className="chip">意图 {o.intent_score}</span>
                    <span className="chip">紧迫 {o.urgency_score}</span>
                    <span className="chip">AI适配 {o.agent_fit_score}</span>
                    <span className="chip">证据 {o.evidence_score}</span>
                  </span>
                </div>
              </button>
            ))}
          </div>
        )}
      </SectionCard>
    </div>

    <SectionCard title="原始证据（来源记录）" subtitle="该企业最初被系统发现的真实公开网页" action={<RadioTower size={16}/>}>
      <EvidencePanel evidences={source_records} emptyHint="暂无来源记录。"/>
    </SectionCard>

    {id && (
      <>
        <SignalCreateModal open={signalModal} companyId={id} onClose={() => setSignalModal(false)} onDone={load}/>
        <OpportunityCreateModal open={oppModal} companyId={id} signals={signals} onClose={() => setOppModal(false)} onDone={load}/>
      </>
    )}
  </div>
}
