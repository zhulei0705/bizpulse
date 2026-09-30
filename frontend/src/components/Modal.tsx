import { useEffect, type ReactNode } from 'react'
import { X } from 'lucide-react'

/** 轻量 Modal：延续 BizPulse 深色情报中枢视觉。 */
export function Modal({ open, title, subtitle, onClose, children, width = 560 }: {
  open: boolean
  title: string
  subtitle?: string
  onClose: () => void
  children: ReactNode
  width?: number
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div className="modal-mask" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal-card" style={{ width }}>
        <div className="modal-head">
          <div>
            <strong>{title}</strong>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="icon-btn small" onClick={onClose} aria-label="关闭"><X size={16}/></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}

export function FormField({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="form-field">
      <span>{label}{hint && <em>{hint}</em>}</span>
      {children}
    </label>
  )
}
