import { useCallback, useEffect, useState } from 'react'
import { CirclePlay, BadgeCheck, AlertTriangle, Timer } from 'lucide-react'
import { message } from 'antd'
import { PageHero } from '../components/PageHero'
import { StatCard } from '../components/StatCard'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'
import { getJobs, getErrorMessage } from '../api'
import type { CollectionJobRow } from '../api'

const STATUS_LABEL: Record<string, string> = {
  PENDING: '等待中', RUNNING: '执行中', SUCCESS: '成功', PARTIAL_SUCCESS: '部分成功',
  FAILED: '失败', CANCELLED: '已取消',
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<CollectionJobRow[] | null>(null)
  const [stats, setStats] = useState({ running: 0, success: 0, failed: 0 })

  const load = useCallback(async () => {
    try {
      const data = await getJobs({ page: 1, page_size: 50 })
      setJobs(data.items)
      setStats({
        running: data.items.filter((j) => j.status === 'RUNNING' || j.status === 'PENDING').length,
        success: data.items.filter((j) => j.status === 'SUCCESS' || j.status === 'PARTIAL_SUCCESS').length,
        failed: data.items.filter((j) => j.status === 'FAILED').length,
      })
    } catch (e) {
      message.error(getErrorMessage(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  return <div className="page-stack">
    <PageHero eyebrow="采集任务" title="采集" highlight="任务" description="每次采集都有完整执行记录：访问 URL、状态、耗时与新增数据统计。"/>
    <div className="stats-grid four">
      <StatCard icon={<CirclePlay/>} label="执行中任务" value={stats.running}/>
      <StatCard icon={<BadgeCheck/>} label="成功任务" value={stats.success}/>
      <StatCard icon={<AlertTriangle/>} label="失败任务" value={stats.failed}/>
      <StatCard icon={<Timer/>} label="任务总数" value={jobs?.length ?? '—'}/>
    </div>
    <div className="split-layout wide-main">
      <SectionCard title="任务列表" subtitle="真实执行记录（倒序）" action={<span className="muted-tip">共 {jobs?.length ?? 0} 条</span>}>
        {jobs && jobs.length > 0 ? (
          <div className="job-list">
            {jobs.map((job) => (
              <div className="job-row" key={job.id}>
                <div className="job-main">
                  <strong>{job.name}</strong>
                  <small>{job.job_type} · {new Date(job.created_at).toLocaleString('zh-CN', { hour12: false })} · 耗时 {job.duration_seconds != null ? `${Math.round(job.duration_seconds)}s` : '—'}</small>
                </div>
                <div className="job-meta">
                  <span className={`chip ${job.status === 'SUCCESS' ? '' : job.status === 'FAILED' ? 'warn' : ''}`}>{STATUS_LABEL[job.status] || job.status}</span>
                  <span className="chip">发现 {job.items_found}</span>
                  <span className="chip">新增 {job.items_created}</span>
                  <span className="chip">更新 {job.items_updated}</span>
                  <span className="chip">跳过 {job.items_skipped}</span>
                  {job.error_count > 0 && <span className="chip warn">失败 {job.error_count}</span>}
                </div>
              </div>
            ))}
          </div>
        ) : <EmptyState title="暂无采集任务" description="在数据源页面配置数据源后执行采集，任务记录会显示在这里。"/>}
      </SectionCard>
      <SectionCard title="说明" subtitle="T03 采集中心">
        <div className="opp-detail-section" style={{ borderTop: 0 }}>
          <strong>执行方式</strong>
          <p>数据源页面「执行采集」按钮手动运行；daily 频率数据源可通过 BIZPULSE_ENABLE_SCHEDULER=true 启用定时。</p>
          <strong>失败留痕</strong>
          <p>访问受限（如验证页）的页面会保存 parse_status=FAILED 的记录，不生成假正文、不绕过验证。</p>
          <strong>版本历史</strong>
          <p>同一 URL 内容变化时保留全部历史版本，可在证据详情中追溯。</p>
        </div>
      </SectionCard>
    </div>
  </div>
}
