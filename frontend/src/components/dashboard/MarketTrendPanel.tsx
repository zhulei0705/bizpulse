import { useState } from 'react'
import { BizChart, brandAxis, ChartEmpty } from '../BizChart'

const RANGES = [
  { key: 7, label: '近7天' },
  { key: 14, label: '近14天' },
  { key: 30, label: '近30天' },
]

/** 市场趋势面板：真实「每日新增商业信号」面积折线，支持近7/14/30天切换（对齐参考图 tab 交互）。
 * 无历史数据显示空图状态。
 */
export function MarketTrendPanel({ trend, loading }: { trend: { date: string; count: number }[]; loading?: boolean }) {
  const [range, setRange] = useState<number>(14)
  const sliced = trend.slice(-range)

  if (loading) return <div style={{ height: 210 }} />
  if (!sliced.length || sliced.every((t) => t.count === 0)) {
    return <ChartEmpty text="暂无足够真实数据形成信号趋势 —— 采集产生历史数据后自动生成" />
  }
  const option = {
    grid: { left: 34, right: 14, top: 18, bottom: 26 },
    xAxis: brandAxis(sliced.map((t) => t.date)).xAxis,
    yAxis: brandAxis().yAxis,
    series: [{
      type: 'line',
      data: sliced.map((t) => t.count),
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { width: 2.5, color: '#29d3ff', shadowColor: 'rgba(41, 211, 255, 0.45)', shadowBlur: 12 },
      itemStyle: { color: '#29d3ff', borderColor: '#0a1626', borderWidth: 2 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(41, 211, 255, 0.32)' },
            { offset: 1, color: 'rgba(41, 211, 255, 0.02)' },
          ],
        },
      },
    }],
  }
  return (
    <div>
      <div className="trend-tabs">
        {RANGES.map((r) => (
          <button key={r.key} className={`trend-tab ${range === r.key ? 'on' : ''}`} onClick={() => setRange(r.key)}>{r.label}</button>
        ))}
      </div>
      <BizChart option={option} height={200} />
    </div>
  )
}
