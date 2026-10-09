import { useCallback, useEffect, useState } from 'react'
import { FlaskConical, CirclePlay, Handshake, CircleDollarSign, Plus, Target, Send } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { Modal, FormField } from '../components/Modal'
import { GradeChip } from '../components/GradeChip'
import {
  completeExperiment, createExperiment, createInteraction, getExperiments, getExperimentTargets, startExperiment, updateTarget, getErrorMessage,
} from '../api'
import {
  EXPERIMENT_CONCLUSION_LABELS,
  EXPERIMENT_REJECT_REASON_LABELS,
  EXPERIMENT_STATUS_LABELS,
  INTERACTION_CHANNEL_LABELS,
  INTERACTION_TYPE_LABELS,
  TARGET_FLOW_STATUSES,
  TARGET_STATUS_LABELS,
  type Experiment,
  type ExperimentTarget,
} from '../types'

const PAGE_SIZE = 30

const FUNNEL_STEPS: { key: string; label: string }[] = [
  { key: 'targets', label: '目标企业' },
  { key: 'contacted', label: '已联系' },
  { key: 'replied', label: '已回复' },
  { key: 'meetings', label: '已会议' },
  { key: 'quotes', label: '已报价' },
  { key: 'pilots', label: '已试点' },
  { key: 'wins', label: '已成交' },
]

export default function ExperimentsPage() {
  const [data, setData] = useState<{ items: Experiment[]; total: number } | null>(null)
  const [selected, setSelected] = useState<Experiment | null>(null)
  const [targets, setTargets] = useState<ExperimentTarget[]>([])
  const [createOpen, setCreateOpen] = useState(false)
  const [rejectTarget, setRejectTarget] = useState<ExperimentTarget | null>(null)
  const [rejectReason, setRejectReason] = useState('NO_NEED')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    name: '', hypothesis: '', target_customer: '', value_proposition: '', offer_description: '',
    price_amount: '9800', target_contacts: '30', target_replies: '5', target_meetings: '3',
    target_quotes: '2', target_pilots: '1', target_wins: '1', success_criteria: '',
  })
  const [interactionForm, setInteractionForm] = useState({
    targetId: '', interactionType: 'OUTREACH', channel: 'EMAIL', direction: 'OUTBOUND',
    subject: '', summary: '', result: '', next_action: '',
  })

  const load = useCallback(async () => {
    try {
      const page = await getExperiments({ page: 1, page_size: PAGE_SIZE })
      setData(page)
      if (selected) {
        const fresh = page.items.find((x) => x.id === selected.id)
        setSelected(fresh || null)
      }
    } catch (e) { message.error(getErrorMessage(e)) }
  }, [selected])

  const loadTargets = useCallback(async (experimentId: string) => {
    try {
      setTargets(await getExperimentTargets(experimentId))
    } catch (e) { message.error(getErrorMessage(e)) }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (selected) loadTargets(selected.id) }, [selected, loadTargets])

  const openDetail = async (exp: Experiment) => {
    setSelected(exp)
    setTargets(await getExperimentTargets(exp.id).catch(() => []))
  }

  const doCreate = async () => {
    if (!form.name.trim() || !form.hypothesis.trim()) { message.warning('实验名称与假设必填'); return }
    setBusy(true)
    try {
      const created = await createExperiment({
        name: form.name.trim(), hypothesis: form.hypothesis.trim(),
        target_customer: form.target_customer.trim() || undefined,
        value_proposition: form.value_proposition.trim() || undefined,
        offer_description: form.offer_description.trim() || undefined,
        price_amount: Number(form.price_amount) || undefined,
        price_currency: 'CNY',
        target_contacts: Number(form.target_contacts) || 0,
        target_replies: Number(form.target_replies) || 0,
        target_meetings: Number(form.target_meetings) || 0,
        target_quotes: Number(form.target_quotes) || 0,
        target_pilots: Number(form.target_pilots) || 0,
        target_wins: Number(form.target_wins) || 0,
        success_criteria: form.success_criteria.trim() || undefined,
      })
      message.success('实验已创建（草稿/就绪），加入机会后即可开始验证')
      setCreateOpen(false)
      load()
      openDetail(created)
    } catch (e) { message.error(getErrorMessage(e)) } finally { setBusy(false) }
  }

  const doStart = async () => {
    if (!selected) return
    setBusy(true)
    try {
      const updated = await startExperiment(selected.id)
      message.success('实验已开始（RUNNING）')
      setSelected(updated)
      load()
    } catch (e) { message.error(getErrorMessage(e)) } finally { setBusy(false) }
  }

  const doComplete = async (conclusion: string) => {
    if (!selected) return
    setBusy(true)
    try {
      await completeExperiment(selected.id, conclusion, '人工判定结论')
      message.success(`实验已完成，结论：${EXPERIMENT_CONCLUSION_LABELS[conclusion]}`)
      load()
    } catch (e) { message.error(getErrorMessage(e)) } finally { setBusy(false) }
  }

  const moveTarget = async (target: ExperimentTarget, status: string) => {
    setBusy(true)
    try {
      await updateTarget(target.id, { status })
      message.success(`已更新为「${TARGET_STATUS_LABELS[status] || status}」`)
      loadTargets(target.experiment_id)
      load()
    } catch (e) { message.error(getErrorMessage(e)) } finally { setBusy(false) }
  }

  const doRejectTarget = async () => {
    if (!rejectTarget) return
    setBusy(true)
    try {
      await updateTarget(rejectTarget.id, { status: 'REJECTED', reject_reason: rejectReason })
      message.success('已记录拒绝（原因已留档，用于复盘）')
      setRejectTarget(null)
      loadTargets(rejectTarget.experiment_id)
      load()
    } catch (e) { message.error(getErrorMessage(e)) } finally { setBusy(false) }
  }

  const doLogInteraction = async () => {
    const target = targets.find((t) => t.id === interactionForm.targetId)
    if (!target) { message.warning('请选择目标企业'); return }
    setBusy(true)
    try {
      await createInteraction({
        company_id: target.company_id,
        experiment_id: target.experiment_id,
        target_id: target.id,
        opportunity_id: target.opportunity_id || undefined,
        interaction_type: interactionForm.interactionType,
        direction: interactionForm.direction,
        channel: interactionForm.channel,
        subject: interactionForm.subject.trim() || undefined,
        summary: interactionForm.summary.trim() || undefined,
        result: interactionForm.result || undefined,
        next_action: interactionForm.next_action.trim() || undefined,
        occurred_at: new Date().toISOString(),
      })
      message.success('互动已记录，目标状态与机会阶段已按真实进展同步')
      setInteractionForm((prev) => ({ ...prev, subject: '', summary: '', result: '', next_action: '' }))
      loadTargets(target.experiment_id)
      load()
    } catch (e) { message.error(getErrorMessage(e)) } finally { setBusy(false) }
  }

  const funnel = selected?.funnel || selected?.metrics
  const metrics = selected?.metrics

  return <div className="page-stack">
    <PageHero eyebrow="验证实验" title="验证实验" description="用真实客户反馈验证市场、报价与转化路径。所有数量来自真实互动记录，不预填、不造假。"/>
    <div className="stats-grid four">
      <StatCard icon={<FlaskConical/>} label="实验总数" value={data?.total ?? 0}/>
      <StatCard icon={<CirclePlay/>} label="进行中" value={data?.items?.filter((x) => x.status === 'RUNNING').length ?? 0}/>
      <StatCard icon={<Handshake/>} label="已成交试点" value={metrics?.wins ?? 0}/>
      <StatCard icon={<CircleDollarSign/>} label="已收款（真实）" value={metrics?.received_revenue ?? 0}/>
    </div>

    <SectionCard
      title="实验列表"
      subtitle="每个实验验证一个明确的市场/报价假设"
      action={<button className="primary-btn" onClick={() => setCreateOpen(true)}><Plus size={14}/>新建实验</button>}
    >
      {data && data.items.length > 0
        ? <div className="opp-grid">{data.items.map((exp) => (
            <button className="opp-card" key={exp.id} onClick={() => openDetail(exp)}>
              <div className="opp-card-head">
                <div className="opp-card-title">
                  <strong>{exp.name}</strong>
                  <span>假设：{exp.hypothesis.slice(0, 60)}{exp.hypothesis.length > 60 ? '…' : ''}</span>
                </div>
                <span className="chip">{EXPERIMENT_STATUS_LABELS[exp.status] || exp.status}</span>
              </div>
              <div className="opp-card-meta">
                {exp.price_amount != null && <span className="chip">试点价 ¥{exp.price_amount}</span>}
                <span className="chip">目标 {exp.target_contacts} 家</span>
                {exp.conclusion && <span className="chip">结论：{EXPERIMENT_CONCLUSION_LABELS[exp.conclusion]}</span>}
                <span className="chip">{new Date(exp.updated_at).toLocaleDateString('zh-CN')}</span>
              </div>
            </button>
          ))}</div>
        : <EmptyState title="暂无实验" description="点击「新建实验」创建第一个真实客户验证实验。"/>}
    </SectionCard>

    {selected && (
      <SectionCard
        title={`实验详情 · ${selected.name}`}
        subtitle={`假设：${selected.hypothesis}`}
        action={
          <div className="modal-actions wrap">
            {['DRAFT', 'READY', 'PAUSED'].includes(selected.status) && (
              <button className="primary-btn" disabled={busy} onClick={doStart}><CirclePlay size={14}/>开始实验</button>
            )}
            {['RUNNING', 'PAUSED'].includes(selected.status) && Object.keys(EXPERIMENT_CONCLUSION_LABELS).map((c) => (
              <button key={c} className="secondary-btn" disabled={busy} onClick={() => doComplete(c)}>结束为「{EXPERIMENT_CONCLUSION_LABELS[c]}」</button>
            ))}
          </div>
        }
      >
        <div className="opp-detail-section">
          <strong>实验定义</strong>
          <p>目标客户：{selected.target_customer || '—'}；价值主张：{selected.value_proposition || '—'}</p>
          <p>试点报价：{selected.price_amount != null ? `¥${selected.price_amount}` : '—'}；成功标准：{selected.success_criteria || '—'}</p>
        </div>

        {metrics && (
          <div className="opp-detail-section">
            <strong>真实转化指标（按企业数统计；报价不算收入）</strong>
            <div className="score-strip">
              <span>联系率 {metrics.contact_rate}%</span><span>回复率 {metrics.reply_rate}%</span>
              <span>会议率 {metrics.meeting_rate}%</span><span>报价率 {metrics.quote_rate}%</span>
              <span>试点率 {metrics.pilot_rate}%</span><span>成交率 {metrics.close_rate}%</span>
              <span>签约收入 {metrics.contracted_revenue}</span><span>已收款 {metrics.received_revenue}</span>
            </div>
          </div>
        )}

        {funnel && (
          <div className="opp-detail-section">
            <strong>验证漏斗（真实状态）</strong>
            <div className="score-strip">
              {FUNNEL_STEPS.map((s) => <span key={s.key}>{s.label} {(funnel as Record<string, number>)[s.key] ?? 0}</span>)}
              <span>拒绝 {funnel.rejected ?? 0}</span><span>无回复 {funnel.no_response ?? 0}</span>
            </div>
          </div>
        )}

        <div className="opp-detail-section">
          <strong>目标企业（{targets.length}）</strong>
          {targets.length === 0
            ? <p className="muted-tip">尚未加入目标企业：在企业机会详情页「加入实验」，或先审核机会。</p>
            : (
              <div className="opp-grid">
                {targets.map((t) => (
                  <div className="opp-card" key={t.id}>
                    <div className="opp-card-head">
                      <div className="opp-card-title">
                        <strong>{t.company_name}</strong>
                        <span>{t.opportunity_title || '—'}</span>
                      </div>
                      <span className="chip">{TARGET_STATUS_LABELS[t.status] || t.status}</span>
                    </div>
                    {t.opportunity_score != null && (
                      <div className="opp-card-meta">
                        <GradeChip grade={t.opportunity_grade || 'C'}/>
                        <span className="chip">预测分 {t.opportunity_score}</span>
                        {t.last_interaction_at && <span className="chip">最近互动 {new Date(t.last_interaction_at).toLocaleDateString('zh-CN')}</span>}
                      </div>
                    )}
                    <div className="modal-actions wrap">
                      {TARGET_FLOW_STATUSES.filter((s) => s !== t.status).map((s) => (
                        <button key={s} className="chip clickable" disabled={busy} onClick={() => moveTarget(t, s)}>
                          {TARGET_STATUS_LABELS[s]}
                        </button>
                      ))}
                      <button className="chip clickable danger" disabled={busy} onClick={() => setRejectTarget(t)}>记录拒绝…</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
        </div>

        <div className="opp-detail-section">
          <strong>记录真实互动（人工执行后填写；系统不自动外发）</strong>
          <div className="filter-bar">
            <select className="select-input compact" value={interactionForm.targetId} onChange={(e) => setInteractionForm((p) => ({ ...p, targetId: e.target.value }))}>
              <option value="">选择目标企业…</option>
              {targets.map((t) => <option key={t.id} value={t.id}>{t.company_name}</option>)}
            </select>
            <select className="select-input compact" value={interactionForm.interactionType} onChange={(e) => setInteractionForm((p) => ({ ...p, interactionType: e.target.value, direction: e.target.value === 'REPLY' || e.target.value === 'REJECTION' ? 'INBOUND' : e.target.value === 'RESEARCH' || e.target.value === 'NOTE' ? 'INTERNAL' : 'OUTBOUND' }))}>
              {Object.entries(INTERACTION_TYPE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select className="select-input compact" value={interactionForm.channel} onChange={(e) => setInteractionForm((p) => ({ ...p, channel: e.target.value }))}>
              {Object.entries(INTERACTION_CHANNEL_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="filter-bar">
            <input className="text-input" style={{ flex: 2 }} placeholder="主题（如：首次触达邮件）" value={interactionForm.subject} onChange={(e) => setInteractionForm((p) => ({ ...p, subject: e.target.value }))}/>
            <input className="text-input" style={{ flex: 3 }} placeholder="摘要（客户原话/进展；回复时必填）" value={interactionForm.summary} onChange={(e) => setInteractionForm((p) => ({ ...p, summary: e.target.value }))}/>
          </div>
          <div className="filter-bar">
            <button className="primary-btn" disabled={busy || !interactionForm.targetId} onClick={doLogInteraction}><Send size={14}/>记录互动</button>
            <span className="muted-tip">方向自动校验：客户回复必须 INBOUND；收入只能记录在签约/收款。</span>
          </div>
        </div>
      </SectionCard>
    )}

    <Modal open={createOpen} title="新建验证实验" subtitle="实验必须回答：验证什么、卖给谁、报价多少、什么算成功" onClose={() => setCreateOpen(false)} width={620}>
      <FormField label="实验名称 *">
        <input className="text-input" placeholder="例：制造业海外获客验证" value={form.name} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}/>
      </FormField>
      <FormField label="验证假设 *">
        <input className="text-input" placeholder="例：AI 线索挖掘可显著缩短海外获客时间" value={form.hypothesis} onChange={(e) => setForm((p) => ({ ...p, hypothesis: e.target.value }))}/>
      </FormField>
      <FormField label="目标客户">
        <input className="text-input" placeholder="例：20~200 人制造企业" value={form.target_customer} onChange={(e) => setForm((p) => ({ ...p, target_customer: e.target.value }))}/>
      </FormField>
      <FormField label="价值主张">
        <input className="text-input" placeholder="例：降低销售寻找海外客户的时间" value={form.value_proposition} onChange={(e) => setForm((p) => ({ ...p, value_proposition: e.target.value }))}/>
      </FormField>
      <FormField label="试点报价（元）">
        <input className="text-input" type="number" value={form.price_amount} onChange={(e) => setForm((p) => ({ ...p, price_amount: e.target.value }))}/>
      </FormField>
      <FormField label="实验目标（联系/回复/会议/报价/试点/成交）">
        <div className="filter-bar">
          {(['target_contacts', 'target_replies', 'target_meetings', 'target_quotes', 'target_pilots', 'target_wins'] as const).map((k) => (
            <input key={k} className="text-input" type="number" style={{ width: 64 }} value={form[k]} onChange={(e) => setForm((p) => ({ ...p, [k]: e.target.value }))}/>
          ))}
        </div>
      </FormField>
      <FormField label="成功标准">
        <input className="text-input" placeholder="例：回复率>=10%；至少1个付费试点" value={form.success_criteria} onChange={(e) => setForm((p) => ({ ...p, success_criteria: e.target.value }))}/>
      </FormField>
      <div className="modal-actions">
        <button className="secondary-btn" onClick={() => setCreateOpen(false)}>取消</button>
        <button className="primary-btn" disabled={busy} onClick={doCreate}><Target size={14}/>创建实验</button>
      </div>
    </Modal>

    <Modal open={!!rejectTarget} title="记录拒绝" subtitle={rejectTarget?.company_name || ''} onClose={() => setRejectTarget(null)} width={480}>
      <FormField label="拒绝原因（必须来自客户真实反馈；无回复请用目标状态「无回复」）">
        <select className="select-input" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}>
          {Object.entries(EXPERIMENT_REJECT_REASON_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </FormField>
      <div className="modal-actions">
        <button className="secondary-btn" onClick={() => setRejectTarget(null)}>取消</button>
        <button className="primary-btn danger" disabled={busy} onClick={doRejectTarget}>确认记录</button>
      </div>
    </Modal>
  </div>
}
