import type React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Bell, ChevronDown, Search, Sparkles, Home, Radar, ChartNoAxesCombined, Building2, RadioTower, BriefcaseBusiness, FlaskConical, Database, CirclePlay, ScrollText, Settings, Menu } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { BrandMark } from '../components/BrandMark'
import { useUIStore } from '../stores/ui'

type NavItem = { to: string; label: string; icon: LucideIcon; sep?: false } | { sep: true }

const nav: NavItem[] = [
  { to: '/', label: '首页', icon: Home },
  { to: '/radar', label: '机会雷达', icon: Radar },
  { to: '/markets', label: '市场机会', icon: ChartNoAxesCombined },
  { to: '/companies', label: '企业库', icon: Building2 },
  { to: '/signals', label: '商业信号', icon: RadioTower },
  { to: '/opportunities', label: '客户机会', icon: BriefcaseBusiness },
  { to: '/experiments', label: '验证实验', icon: FlaskConical },
  { sep: true },
  { to: '/sources', label: '数据源', icon: Database },
  { to: '/jobs', label: '采集任务', icon: CirclePlay },
  { to: '/logs', label: '分析日志', icon: ScrollText },
  { to: '/settings', label: '系统设置', icon: Settings },
]

export default function AppLayout() {
  const { collapsed, setCollapsed } = useUIStore()
  return (
    <div className="app-shell">
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <BrandMark compact={collapsed}/>
        <nav className="side-nav">
          {nav.map((item, idx) => 'sep' in item && item.sep ? <div className="nav-sep" key={idx}/> : (
            <NavLink key={item.to} to={item.to} end={item.to === '/'} className={({isActive}) => `nav-item ${isActive ? 'active' : ''}`}>
              <item.icon size={19}/> {!collapsed && <span>{item.label}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          {!collapsed && <div className="slogan-card"><span>用 AI 洞察商业世界</span><div className="slogan-row"><strong>让增长更确定</strong><span className="slogan-arrow"><ChevronDown size={14} style={{ transform: 'rotate(-90deg)' }}/></span></div></div>}
          <button className="collapse-btn" onClick={() => setCollapsed(!collapsed)}><Menu size={18}/></button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="global-search"><Search size={18}/><input placeholder="搜索企业、行业、机会或关键词…"/></div>
          <div className="top-actions">
            <button className="ai-btn"><Sparkles size={16}/>AI 对话</button>
            <button className="icon-btn" title="通知（暂无）"><Bell size={18}/></button>
            <div className="user-chip"><div className="avatar">BP</div><div><strong>本地环境</strong><small>增长团队</small></div><ChevronDown size={15}/></div>
          </div>
        </header>
        <main className="page-content"><Outlet/></main>
      </div>
    </div>
  )
}
