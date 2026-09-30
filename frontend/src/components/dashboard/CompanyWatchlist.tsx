import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../EmptyState'
import { Skeleton } from '../Feedback'
import type { DashboardSummary } from '../../types'

type WatchItem = DashboardSummary['companies_to_watch'][number]

/** CompanyWatchlist：今日值得关注的企业。
 * 每行：企业首字图标 · 名称 · 行业 · 核心 Signal · 最高 Opportunity Score · 证据数量 · 查看企业。
 * 排序来自后端（最近真实信号时间）；无数据时紧凑空状态。
 */
export function CompanyWatchlist({ items, loading }: { items: WatchItem[]; loading?: boolean }) {
  const navigate = useNavigate()
  if (loading) {
    return <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}><Skeleton height={48} /><Skeleton height={48} /><Skeleton height={48} /></div>
  }
  if (!items.length) {
    return <EmptyState compact title="暂无值得关注的企业" description="企业产生真实商业信号后自动进入榜单，排序完全来自数据库。" />
  }
  return (
    <div className="watchlist">
      <div className="watchlist-head">
        <span>企业名称</span><span>行业</span><span>核心 Signal</span><span>最高 Score</span><span>证据</span><span>操作</span>
      </div>
      {items.map((c) => (
        <div className="watchlist-row watchlist-cols" key={c.company_id}>
          <button className="watchlist-company" onClick={() => navigate(`/companies/${c.company_id}`)}>
            <span className="cell-lead" style={{ width: 34, height: 34, fontSize: 13 }}>{c.company_name.slice(0, 1)}</span>
            <strong>{c.company_name}</strong>
          </button>
          <span className="watchlist-cell">{c.industry || '—'}</span>
          <span className="watchlist-cell" title={c.latest_signal_title}>{c.latest_signal_title}</span>
          <span className="cell-strong">
            {c.top_opportunity_score != null ? (
              <>
                {c.top_opportunity_score}
                {c.opportunity_level && <span className={`opp-grade-badge g-${c.opportunity_level.toLowerCase()}`} style={{ marginLeft: 8 }}>{c.opportunity_level}</span>}
              </>
            ) : '—'}
          </span>
          <span className="cell-strong">{c.evidence_count}</span>
          <button className="ghost-btn slim" onClick={() => navigate(`/companies/${c.company_id}`)}>查看企业</button>
        </div>
      ))}
    </div>
  )
}
