import { Flame } from 'lucide-react'
import { EmptyState } from '../EmptyState'
import { RankCard } from '../RankCard'
import type { Company } from '../../types'

/** 行业热度：真实按行业统计。当前企业库行业字段尚无真实数据 → 显示空状态；
 * 一旦企业带有行业字段，自动切换为真实排行（按企业数与信号强度）。
 */
export function IndustryPulse({ companies }: { companies: Company[] }) {
  const withIndustry = companies.filter((c) => c.industry)
  const grouped = new Map<string, { count: number; signals: number }>()
  for (const c of withIndustry) {
    const key = c.industry as string
    const row = grouped.get(key) || { count: 0, signals: 0 }
    row.count += 1
    row.signals += c.signal_count ?? 0
    grouped.set(key, row)
  }
  const ranked = Array.from(grouped.entries())
    .map(([name, v]) => ({ name, ...v }))
    .sort((a, b) => b.count * 10 + b.signals - (a.count * 10 + a.signals))
    .slice(0, 5)
  const maxScore = ranked.length ? Math.max(...ranked.map((r) => r.count * 10 + r.signals)) : 1

  if (!ranked.length) {
    return (
      <EmptyState title="暂无行业热度数据" description="当前真实企业尚未标注行业；为企业补充行业字段或接入更多真实数据后自动生成排行。">
        <span className="chip"><Flame size={11} /> 排序完全来自数据库</span>
      </EmptyState>
    )
  }
  return (
    <div className="opp-mini-list" style={{ maxHeight: 250 }}>
      {ranked.map((r, idx) => (
        <RankCard
          key={r.name}
          rank={idx + 1}
          title={r.name}
          sub={`${r.count} 家企业 · ${r.signals} 条信号`}
          score={Math.round(r.count * 10 + r.signals)}
          maxScore={maxScore}
        />
      ))}
    </div>
  )
}
