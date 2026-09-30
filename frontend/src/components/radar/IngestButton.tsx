import { useState } from 'react'
import { Radar } from 'lucide-react'
import { IngestModal } from '../IngestModal'

/** 「分析网页」按钮 + 弹窗（复用首页组件）。 */
export function IngestButton({ onDone }: { onDone?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button className="ghost-btn" onClick={() => setOpen(true)}><Radar size={15}/>分析网页</button>
      <IngestModal open={open} onClose={() => setOpen(false)} onDone={onDone}/>
    </>
  )
}
