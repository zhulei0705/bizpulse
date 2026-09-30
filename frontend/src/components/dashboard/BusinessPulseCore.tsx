import { Activity, Wand2, ShieldCheck, FileCheck2, BrainCircuit, Gauge } from 'lucide-react'

/** 商业脉搏核心区：数据可信指数（真实：已人工验证来源记录占比 0-100）。
 * 三类信息视觉区分：事实（真实计数）/ AI 分析（配置状态）/ 数据质量（验证覆盖率）。
 * 指数完全由后端真实数据产生，无记录时为 0。
 */
export function BusinessPulseCore({ verifiedRecords, totalRecords, todaySignals, todayCompanies, todayOpportunities, llmConfigured, loading, onDetail }: {
  verifiedRecords: number
  totalRecords: number
  todaySignals: number
  todayCompanies: number
  todayOpportunities: number
  llmConfigured: boolean
  loading?: boolean
  onDetail?: () => void
}) {
  const index = totalRecords > 0 ? Math.round((verifiedRecords / totalRecords) * 100) : 0
  const R = 62
  const C = 2 * Math.PI * R
  const ratio = Math.max(0, Math.min(index / 100, 1))
  const summary = loading
    ? '正在读取真实业务统计…'
    : totalRecords === 0
      ? '暂无真实数据 —— 分析一个公开网页开始建立数据链，形成商业脉搏。'
      : `今日新增信号 ${todaySignals} 条、企业 ${todayCompanies} 家、机会 ${todayOpportunities} 个。已人工验证证据 ${verifiedRecords}/${totalRecords} 条，每条数据均可追溯至原始网页。`

  const rows = [
    { icon: <FileCheck2 size={13} />, label: '事实', tone: 'fact', text: `真实信号 ${todaySignals} 条 · 企业 ${todayCompanies} 家 · 机会 ${todayOpportunities} 个` },
    { icon: <BrainCircuit size={13} />, label: 'AI分析', tone: 'inference', text: llmConfigured ? 'LLM 已配置，辅助推断已启用' : 'AI分析未配置 —— 规则引擎正常运行，不阻塞采集' },
    { icon: <Gauge size={13} />, label: '数据质量', tone: 'quality', text: `${verifiedRecords}/${totalRecords} 条证据已人工验证 · 全量可追溯` },
  ]

  return (
    <div className="pulse-core">
      <div className="pulse-gauge-wrap">
        <div className="pulse-gauge-ring">
          <svg width={152} height={152} viewBox="0 0 152 152">
            <circle cx="76" cy="76" r={R} fill="none" stroke="rgba(40, 84, 132, 0.5)" strokeWidth="11" />
            <circle
              cx="76" cy="76" r={R} fill="none" stroke="url(#pulseGrad)" strokeWidth="11" strokeLinecap="round"
              strokeDasharray={`${C * ratio} ${C}`} transform="rotate(-90 76 76)"
              style={{ transition: 'stroke-dasharray .8s ease' }}
            />
            <defs>
              <linearGradient id="pulseGrad" x1="0" y1="0" x2="1" y2="1">
                <stop stopColor="#29d3ff" /><stop offset="1" stopColor="#7b5cff" />
              </linearGradient>
            </defs>
          </svg>
          <div className="pulse-gauge-copy">
            {loading ? <span style={{ fontSize: 20 }}>…</span> : <span>{index}</span>}
            <small>数据可信指数</small>
          </div>
        </div>
        <div className="pulse-gauge-sub">
          <span className="status-dot">证据链在线</span>
          <small>{verifiedRecords}/{totalRecords} 条已验证</small>
        </div>
      </div>
      <div className="pulse-insight">
        <div className="pulse-insight-head"><Activity size={14} /> 数据摘要</div>
        <p>{summary}</p>
        <div className="pulse-fact-rows">
          {rows.map((r) => (
            <div className={`pulse-fact-row tone-${r.tone}`} key={r.label}>
              <span className="pf-tag">{r.icon}{r.label}</span>
              <span className="pf-text">{r.text}</span>
            </div>
          ))}
        </div>
        {onDetail && <button className="ghost-btn slim" onClick={onDetail}>查看详细分析 →</button>}
      </div>
    </div>
  )
}
