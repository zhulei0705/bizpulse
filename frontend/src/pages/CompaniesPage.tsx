import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, PlusCircle, Target, Award, ChevronLeft, ChevronRight, Globe2 } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { IngestModal } from '../components/IngestModal'
import { getCompanies, getErrorMessage } from '../api'
import type { Company, PageData } from '../types'

const PAGE_SIZE = 10

export default function CompaniesPage() {
  const navigate = useNavigate()
  const [data, setData] = useState<PageData<Company> | null>(null)
  const [loading, setLoading] = useState(false)
  const [q, setQ] = useState('')
  const [industry, setIndustry] = useState('')
  const [city, setCity] = useState('')
  const [sort, setSort] = useState('updated_at')
  const [page, setPage] = useState(1)
  const [ingestOpen, setIngestOpen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setData(await getCompanies({ q: q || undefined, industry: industry || undefined, city: city || undefined, sort, page, page_size: PAGE_SIZE }))
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [q, industry, city, sort, page])

  useEffect(() => { load() }, [load])

  const totalPages = useMemo(() => (data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1), [data])
  const industries = useMemo(() => Array.from(new Set((data?.items || []).map((c) => c.industry).filter(Boolean))) as string[], [data])

  return <div className="page-stack">
    <PageHero
      eyebrow="企业库"
      title="企业库"
      description="沉淀企业画像、商业信号与增长轨迹，建立可持续的商业数据资产。所有企业均来自真实公开网页采集。"
      floatCards={[
        { icon: <Globe2 size={15}/>, title: '更全的企业数据', desc: '采集即建档，来源可追溯' },
        { icon: <Target size={15}/>, title: '发现下一个增长客户', desc: '从真实信号出发', tone: 'purple' },
      ]}
    />
    <div className="stats-grid four">
      <StatCard icon={<Building2/>} label="企业总量" tone="blue" value={data?.total ?? '—'}/>
      <StatCard icon={<PlusCircle/>} label="今日新增" tone="cyan" value={data?.stats?.today_new ?? 0}/>
      <StatCard icon={<Target/>} label="当前页高意向" tone="purple" value={(data?.items || []).filter((c) => c.opportunity_level && c.opportunity_level !== 'D').length}/>
      <StatCard icon={<Award/>} label="A级企业" tone="gold" value={(data?.items || []).filter((c) => c.opportunity_level === 'A' || c.opportunity_level === 'S').length}/>
    </div>

    <div className="filter-bar">
      <div className="search-box">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <input placeholder="搜索企业名称、域名或关键词…" value={q} onChange={(e) => { setPage(1); setQ(e.target.value) }}/>
      </div>
      <select className="select-input compact" value={industry} onChange={(e) => { setPage(1); setIndustry(e.target.value) }}>
        <option value="">全部行业</option>
        {industries.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
      <input className="text-input compact" placeholder="城市筛选" value={city} onChange={(e) => { setPage(1); setCity(e.target.value) }}/>
      <select className="select-input compact" value={sort} onChange={(e) => setSort(e.target.value)}>
        <option value="updated_at">最近更新</option>
        <option value="created_at">最新入库</option>
        <option value="company_name">名称排序</option>
        <option value="pulse_score">脉搏分优先</option>
      </select>
      <button className="primary-btn" onClick={() => setIngestOpen(true)}>分析网页</button>
    </div>

    <SectionCard title="企业列表" subtitle="点击企业查看信号、证据与机会的完整数据链" action={loading ? <span className="muted-tip">加载中…</span> : <span className="muted-tip">共 {data?.total ?? 0} 家</span>}>
      {data && data.items.length > 0 ? (
        <div className="company-table">
          <div className="table-head-row company-cols"><span>企业名称</span><span>行业 / 地区</span><span>规模</span><span>脉搏分</span><span>来源</span><span>更新时间</span></div>
          {data.items.map((c) => (
            <button className="company-row company-cols" key={c.id} onClick={() => navigate(`/companies/${c.id}`)}>
              <span className="cell-main">
                <span className="cell-lead">{c.company_name.slice(0, 1)}</span>
                <span>
                  <strong>{c.company_name}</strong>
                  {c.domain && <small><Globe2 size={11}/> {c.domain}</small>}
                </span>
              </span>
              <span className="cell-sub">{c.industry || '—'}<small>{[c.province, c.city].filter(Boolean).join(' · ') || '—'}</small></span>
              <span className="cell-sub">{c.employee_range || '—'}<small>{c.business_model || '—'}</small></span>
              <span className="cell-strong">
                {c.pulse_score ?? '—'}
                {c.pulse_score != null && <span className="pulse-bar"><i style={{ width: `${Math.min(100, c.pulse_score)}%` }}/></span>}
              </span>
              <span className="cell-strong">{c.source_count}</span>
              <span className="cell-sub">{new Date(c.updated_at).toLocaleDateString('zh-CN')}
                <small>{c.opportunity_level ? <span className={`opp-grade-badge g-${c.opportunity_level.toLowerCase()}`}>{c.opportunity_level}</span> : '—'}</small>
              </span>
            </button>
          ))}
          <div className="pager">
            <button className="ghost-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={15}/>上一页</button>
            <span>{page} / {totalPages}</span>
            <button className="ghost-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>下一页<ChevronRight size={15}/></button>
          </div>
        </div>
      ) : (
        <EmptyState title="暂无企业数据" description="添加一个公开网页开始发现商业机会">
          <button className="primary-btn" onClick={() => setIngestOpen(true)}>分析网页</button>
        </EmptyState>
      )}
    </SectionCard>

    <IngestModal open={ingestOpen} onClose={() => setIngestOpen(false)} onDone={load}/>
  </div>
}
