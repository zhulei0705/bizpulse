import { BizChart, brandAxis, ChartEmpty } from '../BizChart'
import { Skeleton } from '../Feedback'
import type { ScoreDistributionItem } from '../../types'

/** 机会评分分布：真实总分区间柱状图（0~20 / 21~40 / 41~60 / 61~80 / 81~100）。 */
export function OpportunityScoreDistribution({ distribution, loading }: { distribution: ScoreDistributionItem[]; loading?: boolean }) {
  if (loading) return <div style={{ height: 128, display: 'grid', placeItems: 'center' }}><Skeleton width={260} height={150} /></div>
  const nonZero = distribution.filter((d) => d.count > 0)
  if (!nonZero.length) return <ChartEmpty height={128} text="暂无真实机会评分数据" />
  const option = {
    grid: { left: 30, right: 10, top: 14, bottom: 24 },
    xAxis: brandAxis(distribution.map((d) => d.label)).xAxis,
    yAxis: { ...brandAxis().yAxis, max: (value: { max: number }) => (value.max < 2 ? 2 : value.max) },
    series: [{
      type: 'bar',
      barWidth: '46%',
      data: distribution.map((d) => ({
        value: d.count,
        itemStyle: {
          borderRadius: [5, 5, 0, 0],
          color: d.label === '81~100'
            ? { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#3fe6b0' }, { offset: 1, color: 'rgba(63,230,176,.25)' }] }
            : { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#29d3ff' }, { offset: 1, color: 'rgba(41,211,255,.2)' }] },
        },
      })),
    }],
  }
  return <BizChart option={option} height={128} />
}
