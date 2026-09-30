import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { message } from 'antd'
import { Radar, RadioTower, Trophy, PieChart, ClipboardCheck, RotateCcw, Search, Radar as RadarIcon } from 'lucide-react'
import { SectionCard } from '../components/SectionCard'
import { ErrorState, Skeleton } from '../components/Feedback'
import { GlobalOpportunityMap } from '../components/radar/GlobalOpportunityMap'
import { OpportunityStream } from '../components/radar/OpportunityStream'
import { PriorityOpportunityRanking } from '../components/radar/PriorityOpportunityRanking'
import { OpportunityScoreDistribution } from '../components/radar/OpportunityScoreDistribution'
import { OpportunitySourceDistribution } from '../components/radar/OpportunitySourceDistribution'
import { PendingReviewPanel } from '../components/radar/PendingReviewPanel'
import { OpportunityDrawer } from '../components/radar/OpportunityDrawer'
import { IngestButton } from '../components/radar/IngestButton'
import { getRadarOverview, getErrorMessage } from '../api'
import { SIGNAL_TYPE_LABELS, GRADE_LABELS } from '../types'
import type { RadarFilters, RadarMetrics, RadarOpportunity, RadarSummaryData } from '../types'

const AUTO_REFRESH_MS = 5 * 60 * 1000

const fadeIn = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: 'easeOut' as const },
}

/** 顶部紧凑指标（参考图形态：标签+大数字，非卡片）。 */
function CompactMetric({ label, value, tone, loading }: { label: string; value?: number; tone: string; loading?: boolean }) {
  return (
    <div className={`cm2-metric tone-${tone}`}>
      <span className="cm2-label">{label}</span>
      {loading ? <Skeleton width={40} height={26} /> : <strong className="cm2-value">{value ?? 0}</strong>}
      <span className="cm2-dot" />
    </div>
  )
}

export default function RadarPage() {
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<RadarSummaryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [updatedAt, setUpdatedAt] = useState('')
  const [drawerOpp, setDrawerOpp] = useState<RadarOpportunity | null>(null)

  const filters = useMemo<RadarFilters>(() => ({
    industry: params.get('industry') || undefined,
    grade: params.get('grade') || undefined,
    min_score: params.get('min_score') ? Number(params.get('min_score')) : undefined,
    min_evidence_score: params.get('min_evidence_score') ? Number(params.get('min_evidence_score')) : undefined,
    signal_type: params.get('signal_type') || undefined,
    days: params.get('days') ? Number(params.get('days')) : undefined,
  }), [params])

  const load = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      const clean = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== '')) as Record<string, string | number>
      setData(await getRadarOverview(clean))
      setUpdatedAt(new Date().toLocaleString('zh-CN', { hour12: false }))
    } catch (e) {
      setFailed(true)
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    const timer = setInterval(load, AUTO_REFRESH_MS)
    return () => clearInterval(timer)
  }, [load])

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const clearFilters = () => setParams(new URLSearchParams(), { replace: true })
  const filterActive = Object.values(filters).some(Boolean)
  const m: RadarMetrics | undefined = data?.metrics

  return <div className="page-stack radar-page ui023">
    {/* 顶部融合背景区（无大卡片）：标题 + 副标题 + 全球雷达视觉 + 右侧紧凑指标 + 分析网页 */}
    <div className="r3-top">
      <div className="r3-title">
        <div className="hero-eyebrow">实时商业机会发现控制台{updatedAt ? ` · 更新于 ${updatedAt}` : ''}</div>
        <h1>机会<span>雷达</span></h1>
        <p>从海量商业信号中发现最值得行动的机会</p>
      </div>
      <div className="r3-globe" aria-hidden="true">
        <div className="r3-orbit-ring" />
        <div className="r3-orbit-ring b" />
        <div className="r3-core" />
        <span className="r3-node n1" /><span className="r3-node n2" /><span className="r3-node n3" />
      </div>
      <div className="r3-right">
        <div className="r3-metrics">
          <CompactMetric label="真实商业信号" tone="cyan" value={m ? m.today_signals : undefined} loading={loading} />
          <CompactMetric label="潜在商业机会" tone="purple" value={m?.potential_opportunities} loading={loading} />
          <CompactMetric label="高优先级机会" tone="gold" value={m?.high_value_opportunities} loading={loading} />
        </div>
        <div className="r3-actions">
          <button className="primary-btn" onClick={load} disabled={loading}><RadarIcon size={14} />{loading ? '刷新中…' : '刷新数据'}</button>
          <IngestButton onDone={load} />
        </div>
      </div>
    </div>

    {/* 筛选 Panel（58-68px，含搜索主按钮） */}
    <div className="r3-filter">
      <select className="select-input compact" value={filters.industry || ''} onChange={(e) => setFilter('industry', e.target.value)}>
        <option value="">行业</option>
        {(data?.industry_options || []).map((i) => <option key={i} value={i}>{i}</option>)}
      </select>
      <select className="select-input compact" value={filters.grade || ''} onChange={(e) => setFilter('grade', e.target.value)}>
        <option value="">机会等级</option>
        {Object.keys(GRADE_LABELS).map((g) => <option key={g} value={g}>{GRADE_LABELS[g]}</option>)}
      </select>
      <select className="select-input compact" value={filters.days ?? ''} onChange={(e) => setFilter('days', e.target.value)}>
        <option value="">时间范围</option>
        <option value="7">近 7 天</option>
        <option value="30">近 30 天</option>
        <option value="90">近 90 天</option>
      </select>
      <select className="select-input compact" value={filters.min_score ?? ''} onChange={(e) => setFilter('min_score', e.target.value)}>
        <option value="">购买意图（最低分）</option>
        {[60, 70, 80, 90].map((s) => <option key={s} value={s}>≥ {s}</option>)}
      </select>
      <select className="select-input compact" value={filters.signal_type || ''} onChange={(e) => setFilter('signal_type', e.target.value)}>
        <option value="">信号类型</option>
        {Object.entries(SIGNAL_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
      </select>
      <select className="select-input compact" value={filters.min_evidence_score ?? ''} onChange={(e) => setFilter('min_evidence_score', e.target.value)}>
        <option value="">最低证据分</option>
        {[60, 70, 80].map((s) => <option key={s} value={s}>≥ {s}</option>)}
      </select>
      {filterActive && <button className="ghost-btn slim" onClick={clearFilters}><RotateCcw size={13} />重置</button>}
      <button className="primary-btn r3-search-btn" onClick={load} disabled={loading}><Search size={15} />搜索机会</button>
    </div>

    {failed ? (
      <ErrorState onRetry={load} title="机会雷达数据加载失败" />
    ) : (
      <>
        {/* 核心三栏 36% / 25% / 39% */}
        <motion.div className="r3-main" {...fadeIn}>
          <SectionCard title="全球机会分布" icon={<Radar size={16} />} subtitle="WORLD MAP · RADAR · 真实机会节点">
            <GlobalOpportunityMap locations={data?.locations || []} metrics={m} loading={loading} onSelect={(loc) => {
              const opp = (data?.top_opportunities || []).find((o) => o.company_id === loc.company_id)
              if (opp) setDrawerOpp(opp)
            }} />
          </SectionCard>
          <SectionCard title="机会流" icon={<RadioTower size={16} />} subtitle="实时捕捉最新商业机会">
            <OpportunityStream signals={data?.latest_signals || []} loading={loading} />
          </SectionCard>
          <SectionCard title="高优先级机会" icon={<Trophy size={16} />} subtitle="后端 total_score 排序 · Score 环">
            <PriorityOpportunityRanking opportunities={data?.top_opportunities || []} loading={loading} onSelect={setDrawerOpp} />
          </SectionCard>
        </motion.div>

        {/* 底部三栏 31% / 31% / 38% */}
        <motion.div className="r3-bottom" {...fadeIn} transition={{ ...fadeIn.transition, delay: 0.06 }}>
          <SectionCard title="机会评分分布" icon={<PieChart size={16} />} subtitle="真实总分区间">
            <OpportunityScoreDistribution distribution={data?.score_distribution || []} loading={loading} />
          </SectionCard>
          <SectionCard title="机会来源占比" icon={<Radar size={16} />} subtitle="真实来源聚合">
            <OpportunitySourceDistribution distribution={data?.source_distribution || []} loading={loading} />
          </SectionCard>
          <SectionCard title="待人工审核机会" icon={<ClipboardCheck size={16} />} subtitle="NEW / REVIEW 真实机会">
            <PendingReviewPanel items={data?.pending_reviews || []} loading={loading} onSelect={setDrawerOpp} onReview={setDrawerOpp} />
          </SectionCard>
        </motion.div>
      </>
    )}

    <OpportunityDrawer open={!!drawerOpp} opportunity={drawerOpp} onClose={() => setDrawerOpp(null)} onReviewed={load} />
  </div>
}
