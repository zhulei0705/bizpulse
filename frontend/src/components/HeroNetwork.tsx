/** Hero 右侧「商业感知网络」：抽象全球商业网络视觉（装饰性节点，非真实地理数据点）
 * + 四项真实业务状态标注（Signal 数 / Opportunity 数 / 数据源 / AI 分析）。
 * BizPulse 视觉符号体系：Pulse 波形中心核 · Signal 发光点 · Opportunity 环 · Evidence 链路。
 */
export function HeroNetwork({ signalCount, opportunityCount, sourcesActive, aiConfigured }: {
  signalCount: number
  opportunityCount: number
  sourcesActive: number
  aiConfigured: boolean
}) {
  const stats = [
    { label: '商业信号', value: signalCount, tone: 'cyan' },
    { label: '商业机会', value: opportunityCount, tone: 'purple' },
    { label: '数据源', value: sourcesActive, tone: 'green' },
    { label: 'AI 分析', value: aiConfigured ? '已配置' : '未配置', tone: aiConfigured ? 'gold' : 'muted' },
  ]
  return (
    <div className="hero-network" aria-hidden="false">
      <svg className="net-svg" viewBox="0 0 620 300" fill="none">
        <defs>
          <linearGradient id="netLink" x1="0" y1="0" x2="1" y2="0">
            <stop stopColor="#29d3ff" stopOpacity=".55" />
            <stop offset="1" stopColor="#8a5cff" stopOpacity=".5" />
          </linearGradient>
          <radialGradient id="netCore" cx="0.35" cy="0.3" r="1">
            <stop stopColor="#7fe4ff" />
            <stop offset=".5" stopColor="#2f9bff" />
            <stop offset="1" stopColor="#5b3ff0" />
          </radialGradient>
        </defs>
        {/* 轨道 */}
        <ellipse cx="478" cy="150" rx="190" ry="112" stroke="rgba(80,160,240,.2)" strokeDasharray="2 6" />
        <ellipse cx="478" cy="150" rx="126" ry="70" stroke="rgba(80,160,240,.16)" strokeDasharray="2 6" />
        {/* 连线：中心核 ↔ 卫星节点 */}
        <path d="M478 150 Q 390 84 290 96" stroke="url(#netLink)" strokeWidth="1" />
        <path d="M478 150 Q 586 92 624 74" stroke="url(#netLink)" strokeWidth="1" />
        <path d="M478 150 Q 370 208 296 226" stroke="url(#netLink)" strokeWidth="1" />
        <path d="M478 150 Q 600 216 626 210" stroke="url(#netLink)" strokeWidth="1" />
        <path d="M478 150 Q 450 60 380 40" stroke="url(#netLink)" strokeWidth="1" strokeDasharray="3 5" />
        <path d="M478 150 Q 540 250 596 262" stroke="url(#netLink)" strokeWidth="1" strokeDasharray="3 5" />
        {/* 卫星节点 */}
        <g className="net-node"><circle cx="290" cy="96" r="5" fill="#29d3ff" /><circle cx="290" cy="96" r="10" fill="rgba(41,211,255,.14)" /></g>
        <g className="net-node"><circle cx="624" cy="74" r="4" fill="#8a5cff" /><circle cx="624" cy="74" r="9" fill="rgba(138,92,255,.16)" /></g>
        <g className="net-node"><circle cx="296" cy="226" r="6" fill="#2ee6a8" /><circle cx="296" cy="226" r="11" fill="rgba(46,230,168,.14)" /></g>
        <g className="net-node"><circle cx="626" cy="210" r="4" fill="#ffb03a" /><circle cx="626" cy="210" r="9" fill="rgba(255,176,58,.15)" /></g>
        <g className="net-node"><circle cx="380" cy="40" r="4" fill="#4fdcff" /><circle cx="380" cy="40" r="8" fill="rgba(79,220,255,.15)" /></g>
        <g className="net-node"><circle cx="596" cy="262" r="4.5" fill="#c5a8ff" /><circle cx="596" cy="262" r="9" fill="rgba(197,168,255,.15)" /></g>
        {/* 中心核：BizPulse 数字地球（球体明暗 + 经纬弧 + Pulse 波形） */}
        <circle cx="478" cy="150" r="34" fill="url(#netCore)" opacity=".95" />
        <circle cx="478" cy="150" r="34" stroke="rgba(170,230,255,.7)" strokeWidth="1" />
        <ellipse cx="478" cy="150" rx="34" ry="12" stroke="rgba(190,235,255,.35)" fill="none" />
        <ellipse cx="478" cy="150" rx="12" ry="34" stroke="rgba(190,235,255,.28)" fill="none" />
        <ellipse cx="478" cy="150" rx="44" ry="36" stroke="rgba(110,190,255,.3)" strokeDasharray="2 4" fill="none" />
        <ellipse cx="470" cy="140" rx="16" ry="10" fill="rgba(255,255,255,.22)" style={{ filter: 'blur(2px)' }} />
        <circle cx="478" cy="150" r="52" stroke="rgba(90,190,255,.25)" className="core-pulse" style={{ transformOrigin: '478px 150px' }} />
        <path d="M462 150 h8 l5 -12 l8 24 l6 -15 l5 3 h12" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        {/* 流动光点：沿连线移动（克制节奏） */}
        <circle r="3" fill="#7fe4ff">
          <animateMotion dur="7s" repeatCount="indefinite" path="M478 150 Q 390 84 290 96" />
        </circle>
        <circle r="2.6" fill="#c5a8ff">
          <animateMotion dur="9s" repeatCount="indefinite" path="M478 150 Q 600 216 626 210" />
        </circle>
        <circle r="2.4" fill="#ffe9b8">
          <animateMotion dur="8s" begin="-4s" repeatCount="indefinite" path="M478 150 Q 370 208 296 226" />
        </circle>
      </svg>
      <div className="net-stats">
        {stats.map((s) => (
          <div className={`net-stat tone-${s.tone}`} key={s.label}>
            <span className="net-stat-dot" />
            <span className="net-stat-label">{s.label}</span>
            <strong className="net-stat-value">{s.value}</strong>
          </div>
        ))}
      </div>
    </div>
  )
}
