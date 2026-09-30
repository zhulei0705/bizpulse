import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RadioTower, Gem, BadgeCheck, Newspaper, ChevronLeft, ChevronRight, Plus } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { SignalBadge } from '../components/SignalBadge'
import { FactTag } from '../components/FactTag'
import { EvidencePanel } from '../components/EvidencePanel'
import { SignalCreateModal } from '../components/SignalCreateModal'
import { getCompanies, getSignals, getErrorMessage } from '../api'
import { SIGNAL_TYPE_LABELS, type Company, type PageData, type Signal } from '../types'

const PAGE_SIZE = 12

export default function SignalsPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<PageData<Signal> | null>(null)
  const [companies, setCompanies] = useState<Company[]>([])
  const [selected, setSelected] = useState<Signal | null>(null)
  const [loading, setLoading] = useState(false)
  const [signalType, setSignalType] = useState('')
  const [companyId, setCompanyId] = useState('')
  const [status, setStatus] = useState('')
  const [minConfidence, setMinConfidence] = useState(0)
  const [timeRange, setTimeRange] = useState('')
  const [page, setPage] = useState(1)
  const [createOpen, setCreateOpen] = useState(false)

  useEffect(() => {
    getCompanies({ page: 1, page_size: 100 }).then((r) => setCompanies(r.items)).catch(() => setCompanies([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const days = timeRange ? Number(timeRange) : 0
      const collectedFrom = days ? new Date(Date.now() - days * 24 * 3600 * 1000).toISOString() : undefined
      const result = await getSignals({
        signal_type: signalType || undefined,
        company_id: companyId || undefined,
        status: status || undefined,
        min_confidence: minConfidence || undefined,
        collected_from: collectedFrom,
        page, page_size: PAGE_SIZE,
      })
      setData(result)
      setSelected((prev) => (prev ? result.items.find((s) => s.id === prev.id) || result.items[0] || null : result.items[0] || null))
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [signalType, companyId, status, minConfidence, timeRange, page])

  useEffect(() => { load() }, [load])

  const totalPages = useMemo(() => (data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1), [data])
  const highValue = useMemo(() => (data?.items || []).filter((s) => s.confidence >= 80).length, [data])
  const pendingCheck = useMemo(() => (data?.items || []).filter((s) => s.confidence < 60).length, [data])

  return <div className="page-stack">
    <PageHero eyebrow="商业信号" title="商业" highlight="信号" description="追踪市场变化，捕捉购买意图与企业增长信号。每条信号都标注事实与推断。"/>
    <div className="stats-grid four">
      <StatCard icon={<RadioTower/>} label="当前筛选信号" value={data?.total ?? '—'}/>
      <StatCard icon={<Gem/>} label="高置信（≥80）" value={highValue}/>
      <StatCard icon={<BadgeCheck/>} label="低置信待确认（<60）" value={pendingCheck}/>
      <StatCard icon={<Newspaper/>} label="今日新增" value={data?.stats?.today_new ?? 0}/>
    </div>

    <div className="filter-bar">
      <select className="select-input compact" value={signalType} onChange={(e) => { setPage(1); setSignalType(e.target.value) }}>
        <option value="">全部类型</option>
        {Object.entries(SIGNAL_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <select className="select-input compact" value={companyId} onChange={(e) => { setPage(1); setCompanyId(e.target.value) }}>
        <option value="">全部企业</option>
        {companies.map((c) => <option key={c.id} value={c.id}>{c.company_name}</option>)}
      </select>
      <select className="select-input compact" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value) }}>
        <option value="">全部状态</option>
        <option value="VALID">有效</option>
        <option value="INVALID">已失效</option>
      </select>
      <select className="select-input compact" value={minConfidence} onChange={(e) => { setPage(1); setMinConfidence(Number(e.target.value)) }}>
        <option value={0}>全部可信度</option>
        <option value={60}>≥ 60</option>
        <option value={80}>≥ 80</option>
      </select>
      <select className="select-input compact" value={timeRange} onChange={(e) => { setPage(1); setTimeRange(e.target.value) }}>
        <option value="">全部时间</option>
        <option value="7">近 7 天</option>
        <option value="30">近 30 天</option>
      </select>
      <button className="primary-btn" onClick={() => setCreateOpen(true)} disabled={companies.length === 0}><Plus size={15}/>新增信号</button>
    </div>
    {companies.length === 0 && <p className="form-hint">暂无企业数据 —— 先在「数据源」或「企业库」分析一个公开网页，才能挂接人工信号。</p>}

    <div className="split-layout signal-layout">
      <SectionCard title="信号流" subtitle="按采集时间倒序" action={loading ? <span className="muted-tip">加载中…</span> : <span className="muted-tip">共 {data?.total ?? 0} 条</span>}>
        {data && data.items.length > 0 ? (
          <div className="signal-feed">
            {data.items.map((s) => (
              <button className={`signal-item ${selected?.id === s.id ? 'selected' : ''}`} key={s.id} onClick={() => setSelected(s)}>
                <div className="signal-item-head">
                  <span className="row-lead">{(s.company_name || '·').slice(0, 1)}</span>
                  <strong style={{ flex: 1 }}>{s.company_name || '未关联企业'}</strong>
                  <small style={{ color: '#5f7b95', fontSize: 10.5 }}>{new Date(s.collected_at).toLocaleString('zh-CN', { hour12: false })}</small>
                </div>
                <div className="signal-item-head">
                  <SignalBadge type={s.signal_type}/>
                  <FactTag value={s.fact_or_inference}/>
                  <span className="conf-chip" title="置信度">置信 {s.confidence}</span>
                </div>
                <strong>{s.title}</strong>
                {s.description && <p>{s.description}</p>}
              </button>
            ))}
            <div className="pager">
              <button className="ghost-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={15}/>上一页</button>
              <span>{page} / {totalPages}</span>
              <button className="ghost-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页<ChevronRight size={15}/></button>
            </div>
          </div>
        ) : (
          <EmptyState title="暂无真实信号" description="分析一个公开网页，或为已有企业手动创建信号。"/>
        )}
      </SectionCard>

      <SectionCard title="信号详情" subtitle="证据与原始来源可追溯">
        {selected ? (
          <div className="signal-detail">
            <div className="signal-item-head">
              <SignalBadge type={selected.signal_type}/>
              <FactTag value={selected.fact_or_inference}/>
              <span className="conf-chip">置信 {selected.confidence}</span>
              <span className="conf-chip">状态 {selected.status === 'VALID' ? '有效' : selected.status}</span>
            </div>
            <h4>{selected.title}</h4>
            {selected.description && <p>{selected.description}</p>}
            {selected.company_name && (
              <p className="form-hint">企业：{selected.company_name}</p>
            )}
            <EvidencePanel evidences={selected.evidence ? [selected.evidence] : []} emptyHint="该信号暂无挂接证据。"/>
            {selected.company_id && (
              <button className="secondary-btn full" onClick={() => navigate(`/companies/${selected.company_id}`)}>查看企业完整数据链</button>
            )}
          </div>
        ) : <EmptyState title="请选择一条信号" description="选择信号后展示证据与 AI 推断。"/>}
      </SectionCard>
    </div>

    {companyId && (
      <SignalCreateModal open={createOpen} companyId={companyId} onClose={() => setCreateOpen(false)} onDone={load}/>
    )}
    {!companyId && companies.length > 0 && (
      <SignalCreateModal open={createOpen} companyId={companies[0].id} onClose={() => setCreateOpen(false)} onDone={load}/>
    )}
  </div>
}
