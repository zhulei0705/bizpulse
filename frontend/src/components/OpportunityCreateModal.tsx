import { useEffect, useState } from 'react'
import { message } from 'antd'
import { BriefcaseBusiness } from 'lucide-react'
import { Modal, FormField } from './Modal'
import { createOpportunity, getErrorMessage } from '../api'
import type { Signal } from '../types'

const SCORE_FIELDS: { key: string; label: string }[] = [
  { key: 'pain_score', label: 'Pain 痛点' },
  { key: 'budget_score', label: 'Budget 预算' },
  { key: 'intent_score', label: 'Intent 意图' },
  { key: 'urgency_score', label: 'Urgency 紧迫' },
  { key: 'agent_fit_score', label: 'AgentFit AI适配' },
  { key: 'reachability_score', label: 'Reachability 触达' },
  { key: 'evidence_score', label: 'Evidence 证据' },
]

/** 人工从 Company + Signal 创建 Opportunity（总分由后端 Score Engine 计算）。 */
export function OpportunityCreateModal({ open, companyId, signals, defaultSignalId, onClose, onDone }: {
  open: boolean
  companyId: string
  signals: Signal[]
  defaultSignalId?: string
  onClose: () => void
  onDone?: () => void
}) {
  const [title, setTitle] = useState('')
  const [problem, setProblem] = useState('')
  const [solution, setSolution] = useState('')
  const [valueProp, setValueProp] = useState('')
  const [signalId, setSignalId] = useState<string>(defaultSignalId || '')
  const [scores, setScores] = useState<Record<string, number>>({
    pain_score: 60, budget_score: 50, intent_score: 50, urgency_score: 50, agent_fit_score: 60, reachability_score: 50, evidence_score: 50,
  })
  const [busy, setBusy] = useState(false)

  useEffect(() => { setSignalId(defaultSignalId || '') }, [defaultSignalId, open])

  const close = () => { setTitle(''); setProblem(''); setSolution(''); setValueProp(''); onClose() }
  const setScore = (key: string, value: number) => setScores((prev) => ({ ...prev, [key]: value }))

  const submit = async () => {
    if (!title.trim() || !problem.trim() || !solution.trim()) { message.warning('标题、问题、建议方案为必填'); return }
    // 真实数据规范：没有证据信号的机会不允许生成（只能作为待验证线索存在）
    if (!signalId) { message.warning('必须关联至少 1 条商业信号作为证据 —— 无证据只能保存为待验证线索，不能生成正式机会'); return }
    setBusy(true)
    try {
      await createOpportunity({
        company_id: companyId,
        primary_signal_id: signalId || null,
        title: title.trim(), problem: problem.trim(), solution: solution.trim(),
        value_proposition: valueProp.trim() || undefined,
        trigger_event: signals.find((s) => s.id === signalId)?.title,
        ...scores,
      })
      message.success('机会已创建，总分由后端评分引擎计算')
      onDone?.()
      close()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="创建商业机会" subtitle="基于真实信号建立机会假设；Evidence < 60 时等级最高 B（评分由后端计算）" width={620}>
      <FormField label="关联信号（必选）" hint="evidence_count=0 时禁止生成正式机会">
        <select className="select-input" value={signalId} onChange={(e) => setSignalId(e.target.value)}>
          <option value="">请选择证据信号…</option>
          {signals.map((s) => <option key={s.id} value={s.id}>{s.signal_type} · {s.title.slice(0, 40)}</option>)}
        </select>
      </FormField>
      {signals.length === 0 && <p className="form-hint">该企业暂无商业信号 —— 请先分析公开网页或人工新增信号。</p>}
      <FormField label="机会标题">
        <input className="text-input" value={title} placeholder="例：海外销售线索获取自动化" onChange={(e) => setTitle(e.target.value)} />
      </FormField>
      <FormField label="问题（观察到什么）">
        <textarea className="textarea-input" rows={2} value={problem} placeholder="企业当前遇到的问题…" onChange={(e) => setProblem(e.target.value)} />
      </FormField>
      <FormField label="建议解决方案">
        <textarea className="textarea-input" rows={2} value={solution} placeholder="我们如何解决…" onChange={(e) => setSolution(e.target.value)} />
      </FormField>
      <FormField label="价值主张（可选）">
        <input className="text-input" value={valueProp} onChange={(e) => setValueProp(e.target.value)} />
      </FormField>
      <div className="score-editor">
        {SCORE_FIELDS.map((f) => (
          <label key={f.key} className="score-row">
            <span>{f.label}</span>
            <input type="range" min={0} max={100} value={scores[f.key]} onChange={(e) => setScore(f.key, Number(e.target.value))} />
            <strong>{scores[f.key]}</strong>
          </label>
        ))}
      </div>
      <div className="modal-actions">
        <button className="secondary-btn" onClick={close}>取消</button>
        <button className="primary-btn" disabled={busy} onClick={submit}><BriefcaseBusiness size={15}/>{busy ? '保存中…' : '创建机会'}</button>
      </div>
    </Modal>
  )
}
