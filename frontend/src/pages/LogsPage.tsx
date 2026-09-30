import { useCallback, useEffect, useState } from 'react'
import { ScrollText } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { getAuditLogs, getErrorMessage } from '../api'
import type { AuditLogRow, PageData } from '../types'

const ACTION_LABELS: Record<string, string> = {
  CREATE: '创建', UPDATE: '更新', REVIEW: '人工审核', STAGE_CHANGE: '阶段流转',
  ADD_EVIDENCE: '补充证据', INGEST_URL: 'URL采集', RUN: '任务运行',
}

export default function LogsPage() {
  const [logs, setLogs] = useState<PageData<AuditLogRow> | null>(null)

  const load = useCallback(async () => {
    try {
      setLogs(await getAuditLogs({ page: 1, page_size: 50 }))
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  return <div className="page-stack">
    <PageHero eyebrow="分析日志" title="审计日志" description="所有创建、采集、审核动作全量留痕，保证数据来源可追溯。"/>
    <div className="split-layout wide-main">
      <SectionCard title="审计日志" subtitle="最近 50 条" action={<span className="muted-tip">共 {logs?.total ?? 0} 条</span>}>
        {logs && logs.items.length > 0 ? (
          <div className="signal-feed compact">
            {logs.items.map((log) => (
              <div className="signal-item" key={log.id}>
                <div className="signal-item-head">
                  <span className="chip">{ACTION_LABELS[log.action] || log.action}</span>
                  {log.entity_type && <span className="chip">{log.entity_type}</span>}
                  <span className="conf-chip">{new Date(log.created_at).toLocaleString('zh-CN', { hour12: false })}</span>
                </div>
                <strong>{log.action} · {log.entity_type || '—'}</strong>
                <small>{JSON.stringify(log.payload_json).slice(0, 160)}</small>
              </div>
            ))}
          </div>
        ) : <EmptyState title="暂无审计记录" description="执行采集、创建或审核动作后，这里将显示完整留痕。"/>}
      </SectionCard>
      <SectionCard title="追溯说明" subtitle="T02 数据真实性原则">
        <div className="opp-detail-section" style={{ borderTop: 0 }}>
          <strong>NO_FAKE_DATA</strong>
          <p>系统不写入任何虚构企业、信号或机会；空数据如实显示。</p>
          <strong>可追溯链路</strong>
          <p>每一次 URL 采集、信号创建、机会审核都会写入 audit_logs，并挂接 SourceRecord 原始证据。</p>
          <strong>人工审核留痕</strong>
          <p>机会的通过/驳回/修改/加入验证都会记录审核时间、审核人与备注。</p>
        </div>
      </SectionCard>
    </div>
  </div>
}
