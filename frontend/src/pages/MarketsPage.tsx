import { Gem, Eye, Clock4, TrendingUp } from 'lucide-react'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { FilterBar } from '../components/FilterBar'
import { ChartPlaceholder } from '../components/ChartPlaceholder'
import { DataTableShell } from '../components/DataTableShell'

export default function MarketsPage(){ return <div className="page-stack">
  <PageHero eyebrow="市场机会" title="市场" highlight="机会" description="识别高价值赛道，评估进入优先级与自动化空间。"/>
  <div className="stats-grid four"><StatCard icon={<Gem/>} label="高潜力市场"/><StatCard icon={<TrendingUp/>} label="重点验证市场"/><StatCard icon={<Eye/>} label="持续观察市场"/><StatCard icon={<Clock4/>} label="暂缓市场"/></div>
  <div className="dashboard-grid market-grid">
    <SectionCard title="市场热力地图"><ChartPlaceholder variant="radar"/></SectionCard>
    <SectionCard title="细分场景矩阵" subtitle="支付意愿 × 自动化空间"><ChartPlaceholder variant="radar"/></SectionCard>
    <SectionCard title="热门赛道排行榜"><ChartPlaceholder variant="bars"/></SectionCard>
  </div>
  <FilterBar searchPlaceholder="搜索场景或关键词…"/>
  <SectionCard title="市场评估清单"><DataTableShell columns={['场景','所属赛道','目标客户','当前痛点','预算水平','市场评分','验证状态','操作']}/></SectionCard>
</div> }
