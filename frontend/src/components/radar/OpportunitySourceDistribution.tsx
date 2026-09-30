import { BizChart, ChartEmpty } from '../BizChart'
import { Skeleton } from '../Feedback'
import type { SourceDistributionItem } from '../../types'

const SOURCE_COLORS = ['#29d3ff', '#8a5cff', '#2ee6a8', '#ffb03a', '#7b8cff', '#ff8ba0', '#4a7ba6']

/** 机会来源占比：真实 source_type 聚合环形图（企业官网/网页采集/人工录入…）。
 * 数据库没有的类型不显示；禁止构造比例。
 */
export function OpportunitySourceDistribution({ distribution, loading }: { distribution: SourceDistributionItem[]; loading?: boolean }) {
  if (loading) return <div style={{ height: 128, display: 'grid', placeItems: 'center' }}><Skeleton width={150} height={150} radius={75} /></div>
  if (!distribution.length) return <ChartEmpty height={128} text="暂无足够真实来源数据" />
  const sum = distribution.reduce((acc, d) => acc + d.count, 0)
  const option = {
    tooltip: { trigger: 'item', formatter: (p: { name: string; value: number; percent: number }) => `${p.name}：${p.value} 个（${p.percent}%）` },
    legend: {
      orient: 'vertical', right: 4, top: 'middle',
      icon: 'circle', itemWidth: 9, itemHeight: 9, itemGap: 10,
      textStyle: { color: '#9db1c5', fontSize: 11.5 },
      formatter: (name: string) => {
        const item = distribution.find((d) => d.label === name)
        return item ? `${name}  ${Math.round((item.count / sum) * 100)}%` : name
      },
    },
    series: [{
      type: 'pie',
      radius: ['56%', '80%'],
      center: ['34%', '50%'],
      itemStyle: { borderColor: '#0a1626', borderWidth: 2 },
      label: { show: false },
      data: distribution.map((d, i) => ({ name: d.label, value: d.count, itemStyle: { color: SOURCE_COLORS[i % SOURCE_COLORS.length] } })),
    }],
    graphic: [
      { type: 'text', left: '26%', top: '44%', style: { text: String(sum), textAlign: 'center', fill: '#eaf4ff', fontSize: 19, fontWeight: 700 } },
      { type: 'text', left: '25.5%', top: '57%', style: { text: '机会总数', textAlign: 'center', fill: '#7d97ae', fontSize: 9.5 } },
    ],
  }
  return <BizChart option={option} height={128} />
}
