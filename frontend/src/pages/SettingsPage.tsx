import { Settings, ShieldCheck, Database, Sparkles } from 'lucide-react'
import { PageHero } from '../components/PageHero'
import { SectionCard } from '../components/SectionCard'

export default function SettingsPage(){ return <div className="page-stack">
  <PageHero eyebrow="系统设置" title="系统设置" description="管理 BizPulse 的运行环境、数据策略与模型配置。"/>
  <div className="settings-grid">
    <SectionCard title="基础设置"><div className="settings-list"><div><Settings/><span><strong>系统名称</strong><small>商脉 BizPulse</small></span></div><div><ShieldCheck/><span><strong>数据真实性模式</strong><small>NO_FAKE_DATA = TRUE</small></span></div></div></SectionCard>
    <SectionCard title="数据库"><div className="settings-list"><div><Database/><span><strong>连接状态</strong><small>由后端接口实时返回</small></span></div></div></SectionCard>
    <SectionCard title="AI 模型"><div className="settings-list"><div><Sparkles/><span><strong>LLM Provider</strong><small>后续由 LLMAdapter 配置</small></span></div></div></SectionCard>
  </div>
</div> }
