import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Building2, RadioTower, Target, Star, ArrowRight, Globe2, Activity, ShieldCheck, Trophy, LineChart } from 'lucide-react'
import { message } from 'antd'
import { SectionCard } from '../components/SectionCard'
import { HeroNetwork } from '../components/HeroNetwork'
import { DashboardHeader } from '../components/dashboard/DashboardHeader'
import { PulseCard } from '../components/dashboard/PulseCard'
import { BusinessPulseCore } from '../components/dashboard/BusinessPulseCore'
import { MarketTrendPanel } from '../components/dashboard/MarketTrendPanel'
import { IndustryPulse } from '../components/dashboard/IndustryPulse'
import { TopOpportunities } from '../components/dashboard/TopOpportunities'
import { SignalStream } from '../components/dashboard/SignalStream'
import { CompanyWatchlist } from '../components/dashboard/CompanyWatchlist'
import { IngestModal } from '../components/IngestModal'
import { ErrorState } from '../components/Feedback'
import { getSystemInfo, getDashboard, getOpportunities, getCompanies, getErrorMessage } from '../api'
import type { Company, DashboardSummary, Opportunity, SystemInfo } from '../types'

const fadeIn = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.35, ease: 'easeOut' as const },
}

export default function HomePage() {
  const navigate = useNavigate()
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null)
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [ingestOpen, setIngestOpen] = useState(false)
  const [updatedAt, setUpdatedAt] = useState<string>('')
  const [companies, setCompanies] = useState<Company[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setFailed(false)
    try {
      const [info, dash, opps] = await Promise.all([
        getSystemInfo().catch(() => null),
        getDashboard(),
        getOpportunities({ page: 1, page_size: 5 }),
      ])
      if (info) setSystem(info)
      setDashboard(dash)
      setOpportunities(opps.items)
      setUpdatedAt(new Date().toLocaleString('zh-CN', { hour12: false }))
      getCompanies({ page: 1, page_size: 100 }).then((r) => setCompanies(r.items)).catch(() => setCompanies([]))
    } catch (e) {
      setFailed(true)
      message.error(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const d = dashboard

  return <div className="page-stack">
    <div className="page-hero">
      <DashboardHeader
        greeting="👋 商业情报总览"
        title="发现市场机会，"
        highlight="找到潜在客户"
        description="基于真实公开网页采集与证据链验证，帮你更早发现变化、更快找到机会，让企业增长更确定。"
        lastUpdated={updatedAt}
        actions={
          <>
            <button className="primary-btn" onClick={() => setIngestOpen(true)}>分析网页 <ArrowRight size={16} /></button>
            <Link to="/radar"><button className="secondary-btn">查看机会雷达</button></Link>
          </>
        }
      />
      <HeroNetwork
        signalCount={d?.signal_count ?? 0}
        opportunityCount={d?.opportunity_count ?? 0}
        sourcesActive={d?.active_sources ?? 0}
        aiConfigured={d?.llm_configured ?? false}
      />
    </div>

    {failed ? (
      <ErrorState onRetry={load} title="数据加载失败" />
    ) : (
      <>
        <motion.div className="stats-grid four" {...fadeIn}>
          <PulseCard icon={<Building2 />} title="今日新增企业" tone="blue" loading={loading} value={d?.today_new_companies ?? 0} description="来自真实采集与录入" />
          <PulseCard icon={<RadioTower />} title="今日新增信号" tone="cyan" loading={loading} value={d?.today_new_signals ?? 0} description="每条均可追溯证据" />
          <PulseCard icon={<Target />} title="今日新增机会" tone="purple" loading={loading} value={d?.today_new_opportunities ?? 0} description="关联真实信号证据" />
          <PulseCard icon={<Star />} title="A级以上机会" tone="gold" loading={loading} value={d?.grade_a_or_higher ?? 0} description="证据门槛：弱证据最高B" />
        </motion.div>

        <motion.div className="dashboard-grid home-grid" {...fadeIn} transition={{ ...fadeIn.transition, delay: 0.06 }}>
          <SectionCard title="今日商业脉搏" icon={<Activity size={16} />} subtitle="数据可信指数 · 反映证据链健康度">
            <BusinessPulseCore
              loading={loading}
              verifiedRecords={d?.verified_records ?? 0}
              totalRecords={d?.total_records ?? 0}
              todaySignals={d?.today_new_signals ?? 0}
              todayCompanies={d?.today_new_companies ?? 0}
              todayOpportunities={d?.today_new_opportunities ?? 0}
              llmConfigured={d?.llm_configured ?? false}
              onDetail={() => navigate('/logs')}
            />
          </SectionCard>
          <SectionCard title="实时市场动态" icon={<RadioTower size={16} />} subtitle="SignalStream · 最新真实商业信号" onMore={() => navigate('/signals')}>
            <SignalStream loading={loading} signals={d?.recent_signals ?? []} />
          </SectionCard>
          <SectionCard title="行业热度趋势" icon={<LineChart size={16} />} subtitle="最近 14 天每日新增商业信号">
            <MarketTrendPanel loading={loading} trend={d?.signal_trend ?? []} />
          </SectionCard>
          <SectionCard title="高潜力行业 TOP 5" icon={<Globe2 size={16} />} subtitle="真实行业统计（来自数据库）">
            <IndustryPulse companies={companies} />
          </SectionCard>
          <SectionCard title="今日值得关注的企业" icon={<Building2 size={16} />} subtitle="CompanyWatchlist · 按最近真实信号排序" onMore={() => navigate('/companies')}>
            <CompanyWatchlist loading={loading} items={d?.companies_to_watch ?? []} />
          </SectionCard>
        </motion.div>

        <motion.div {...fadeIn} transition={{ ...fadeIn.transition, delay: 0.12 }}>
          <SectionCard title="高价值机会" icon={<Star size={16} />} subtitle="Opportunity Score 由后端评分引擎计算" onMore={() => navigate('/opportunities')}>
            <TopOpportunities loading={loading} opportunities={opportunities} />
          </SectionCard>
        </motion.div>

        <div className="system-strip">
          <div><Globe2 size={17} /><span>运行环境</span><strong>{system?.environment || '本地环境'}</strong></div>
          <div><Activity size={17} /><span>后端服务</span><strong className={system ? 'ok' : 'danger'}>{system ? '已连接' : '未连接'}</strong></div>
          <div><ShieldCheck size={17} /><span>数据原则</span><strong>REAL_DATA_ONLY</strong></div>
          <div><Trophy size={17} /><span>成交机会</span><strong>{d?.won ?? '—'}</strong></div>
          <div><Target size={17} /><span>待审核机会</span><strong>{d?.pending_review ?? '—'}</strong></div>
        </div>
      </>
    )}

    <IngestModal open={ingestOpen} onClose={() => setIngestOpen(false)} onDone={load} />
  </div>
}
