import { useCallback, useEffect, useState } from 'react'
import { Database, RadioTower, AlertTriangle, ShieldCheck, Radar } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { SourceGradeChip } from '../components/GradeChip'
import { EvidencePanel } from '../components/EvidencePanel'
import { IngestModal } from '../components/IngestModal'
import { getSources, getSourceRecords, runSource, getErrorMessage } from '../api'
import type { PageData, Source, SourceRecord } from '../types'

export default function SourcesPage() {
  const [sources, setSources] = useState<PageData<Source> | null>(null)
  const [records, setRecords] = useState<PageData<SourceRecord> | null>(null)
  const [selected, setSelected] = useState<Source | null>(null)
  const [ingestOpen, setIngestOpen] = useState(false)
  const [running, setRunning] = useState<string | null>(null)

  const runNow = async (source: Source) => {
    setRunning(source.id)
    try {
      const result = await runSource(source.id)
      message.success(`采集完成：${result.status} · 新增 ${result.items_created} / 更新 ${result.items_updated} / 跳过 ${result.items_skipped}`)
      load()
    } catch (e) {
      message.error(getErrorMessage(e))
    } finally {
      setRunning(null)
    }
  }

  const load = useCallback(async () => {
    try {
      const [src, rec] = await Promise.all([getSources({ page: 1, page_size: 50 }), getSourceRecords({ page: 1, page_size: 20 })])
      setSources(src)
      setRecords(rec)
      setSelected((prev) => src.items.find((s) => s.id === prev?.id) || src.items[0] || null)
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  const avgReliability = sources?.items.length
    ? Math.round(sources.items.reduce((sum, s) => sum + s.reliability_score, 0) / sources.items.length)
    : 0

  return <div className="page-stack">
    <PageHero eyebrow="数据源" title="数据" highlight="源" description="管理公开数据入口，保证商业洞察有证据、可追溯。通过「分析网页」手动接入任意公开页面。">
      <div className="hero-actions">
        <button className="primary-btn" onClick={() => setIngestOpen(true)}><Radar size={16}/>分析网页</button>
      </div>
    </PageHero>
    <div className="stats-grid four">
      <StatCard icon={<Database/>} label="已启用数据源" value={sources?.items.filter((s) => s.enabled).length ?? '—'}/>
      <StatCard icon={<RadioTower/>} label="来源记录总数" value={records?.total ?? '—'}/>
      <StatCard icon={<AlertTriangle/>} label="停用数据源" value={sources?.items.filter((s) => !s.enabled).length ?? 0}/>
      <StatCard icon={<ShieldCheck/>} label="平均可靠性" value={avgReliability || '—'}/>
    </div>

    <div className="split-layout wide-main">
      <SectionCard title="数据源列表" subtitle="手动URL分析与人工录入证据会自动建档" action={<span className="muted-tip">共 {sources?.total ?? 0} 个</span>}>
        {sources && sources.items.length > 0 ? (
          <div className="source-list">
            {sources.items.map((s) => (
              <button className={`source-row ${selected?.id === s.id ? 'selected' : ''}`} key={s.id} onClick={() => setSelected(s)}>
                <div className="source-row-main">
                  <strong>{s.name}</strong>
                  <small>{s.source_type}{s.notes ? ` · ${s.notes.slice(0, 36)}` : ''}</small>
                </div>
                <div className="source-row-meta">
                  <SourceGradeChip grade={s.reliability_grade}/>
                  <span className="chip">{s.enabled ? '启用' : '停用'}</span>
                  <span className="chip">{s.collector_type || 'web_page'}</span>
                  <span className="chip" onClick={(e) => { e.stopPropagation(); runNow(s) }}>{running === s.id ? '执行中…' : '▶ 执行采集'}</span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="暂无数据源" description="点击「分析网页」接入第一个真实公开网页。">
            <button className="primary-btn" onClick={() => setIngestOpen(true)}>分析网页</button>
          </EmptyState>
        )}
      </SectionCard>
      <SectionCard title="来源详情" subtitle={selected?.name || '选择左侧数据源'}>
        {selected ? (
          <div className="source-detail">
            <div className="detail-chips">
              <SourceGradeChip grade={selected.reliability_grade}/>
              <span className="chip">可信度 {selected.reliability_score}</span>
              <span className="chip">{selected.source_type}</span>
              <span className="chip">{selected.enabled ? '启用中' : '已停用'}</span>
              <span className="chip">创建 {new Date(selected.created_at).toLocaleDateString('zh-CN')}</span>
            </div>
            {selected.notes && <p className="form-hint">{selected.notes}</p>}
            <h4 className="section-subtitle">最近采集记录（全库最新 20 条）</h4>
            <EvidencePanel evidences={records?.items || []} emptyHint="暂无采集记录。"/>
          </div>
        ) : <EmptyState title="请选择一个数据源"/>}
      </SectionCard>
    </div>

    <IngestModal open={ingestOpen} onClose={() => setIngestOpen(false)} onDone={load}/>
  </div>
}
