import { FlaskConical, CirclePlay, Handshake, CircleDollarSign } from 'lucide-react'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { ChartPlaceholder } from '../components/ChartPlaceholder'

export default function ExperimentsPage(){ return <div className="page-stack">
  <PageHero eyebrow="验证实验" title="验证实验" description="用真实客户反馈验证市场、报价与转化路径。"/>
  <div className="stats-grid four"><StatCard icon={<FlaskConical/>} label="实验数量"/><StatCard icon={<CirclePlay/>} label="进行中"/><StatCard icon={<Handshake/>} label="已成交试点"/><StatCard icon={<CircleDollarSign/>} label="累计收入"/></div>
  <div className="split-layout experiment-layout"><SectionCard title="进行中的实验"><EmptyState/></SectionCard><SectionCard title="实验概览"><EmptyState title="请选择一个实验"/></SectionCard></div>
  <div className="dashboard-grid two"><SectionCard title="转化漏斗"><ChartPlaceholder variant="bars"/></SectionCard><SectionCard title="周度进展"><ChartPlaceholder variant="line"/></SectionCard></div>
</div> }
