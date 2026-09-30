import { useState } from 'react'
import { message } from 'antd'
import { RadioTower } from 'lucide-react'
import { Modal, FormField } from './Modal'
import { createSignal, getErrorMessage } from '../api'
import { SIGNAL_TYPE_LABELS } from '../types'

/** 人工创建商业信号：必须提供证据（source_record_id 或 证据URL），fact_or_inference 明确区分。 */
export function SignalCreateModal({ open, companyId, defaultSourceRecordId, onClose, onDone }: {
  open: boolean
  companyId: string
  defaultSourceRecordId?: string
  onClose: () => void
  onDone?: () => void
}) {
  const [signalType, setSignalType] = useState('HIRING')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [evidenceUrl, setEvidenceUrl] = useState('')
  const [confidence, setConfidence] = useState(70)
  const [inference, setInference] = useState(false)
  const [busy, setBusy] = useState(false)

  const close = () => { setTitle(''); setDescription(''); setEvidenceUrl(''); setConfidence(70); setInference(false); onClose() }

  const submit = async () => {
    if (!title.trim()) { message.warning('请填写信号标题'); return }
    setBusy(true)
    try {
      await createSignal({
        company_id: companyId,
        signal_type: signalType,
        title: title.trim(),
        description: description.trim() || undefined,
        confidence,
        fact_or_inference: inference ? 'INFERENCE' : 'FACT',
        ...(defaultSourceRecordId ? { source_record_id: defaultSourceRecordId } : evidenceUrl.trim() ? { evidence_url: evidenceUrl.trim() } : {}),
      })
      message.success('商业信号已创建')
      onDone?.()
      close()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="新增商业信号" subtitle="人工信号同样必须挂接可追溯证据；推断内容将标记为 AI推断">
      <FormField label="Signal Type">
        <select className="select-input" value={signalType} onChange={(e) => setSignalType(e.target.value)}>
          {Object.entries(SIGNAL_TYPE_LABELS).map(([key, label]) => <option key={key} value={key}>{label}（{key}）</option>)}
        </select>
      </FormField>
      <FormField label="标题">
        <input className="text-input" value={title} placeholder="例：官网显示正在招聘海外销售" onChange={(e) => setTitle(e.target.value)} />
      </FormField>
      <FormField label="描述">
        <textarea className="textarea-input" rows={3} value={description} placeholder="具体发生了什么…" onChange={(e) => setDescription(e.target.value)} />
      </FormField>
      {!defaultSourceRecordId && (
        <FormField label="证据 URL" hint="保证信号可追溯到真实网页">
          <input className="text-input" value={evidenceUrl} placeholder="https://…" onChange={(e) => setEvidenceUrl(e.target.value)} />
        </FormField>
      )}
      <FormField label="性质">
        <div className="radio-row">
          <button className={`toggle-chip ${!inference ? 'on' : ''}`} onClick={() => setInference(false)}>事实（来自公开记录）</button>
          <button className={`toggle-chip inference ${inference ? 'on' : ''}`} onClick={() => setInference(true)}>AI推断（需人工判断）</button>
        </div>
      </FormField>
      <FormField label={`Confidence：${confidence}`}>
        <input type="range" min={0} max={100} value={confidence} onChange={(e) => setConfidence(Number(e.target.value))} />
      </FormField>
      <div className="modal-actions">
        <button className="secondary-btn" onClick={close}>取消</button>
        <button className="primary-btn" disabled={busy} onClick={submit}><RadioTower size={15}/>{busy ? '保存中…' : '创建信号'}</button>
      </div>
    </Modal>
  )
}
