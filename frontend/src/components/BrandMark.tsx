import { Activity } from 'lucide-react'

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand-mark">
      <div className="brand-icon"><Activity size={26} strokeWidth={2.4} /></div>
      {!compact && (
        <div>
          <div className="brand-title">商脉 <span>BizPulse</span></div>
          <div className="brand-subtitle">AI 企业增长平台</div>
        </div>
      )}
    </div>
  )
}
