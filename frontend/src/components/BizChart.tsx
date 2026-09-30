import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import ReactECharts from 'echarts-for-react'

use([CanvasRenderer, LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

/** BizPulse 统一 ECharts 封装：深色透明底、低对比网格、品牌化配色。
 * 禁止直接使用 ECharts 默认样式 —— 所有图表经过这里。
 */
export function BizChart({ option, height = 220, onEvents }: { option: Record<string, unknown>; height?: number; onEvents?: Record<string, (params: unknown) => void> }) {
  const base = {
    backgroundColor: 'transparent',
    textStyle: { fontFamily: 'Bahnschrift, Inter, "PingFang SC", "Microsoft YaHei", sans-serif', color: '#9db1c5' },
    tooltip: {
      backgroundColor: 'rgba(10, 22, 38, 0.94)',
      borderColor: 'rgba(90, 160, 235, 0.4)',
      borderWidth: 1,
      textStyle: { color: '#eaf4ff', fontSize: 12 },
      axisPointer: { lineStyle: { color: 'rgba(90, 170, 255, 0.4)' } },
    },
  }
  return (
    <ReactECharts
      option={{ ...base, ...option }}
      notMerge
      style={{ height, width: '100%' }}
      opts={{ renderer: 'canvas' }}
      onEvents={onEvents}
    />
  )
}

/** 品牌化坐标轴（低对比网格）。 */
export function brandAxis(data?: string[]) {
  return {
    xAxis: {
      type: 'category',
      data,
      axisLine: { lineStyle: { color: 'rgba(74, 132, 205, 0.3)' } },
      axisTick: { show: false },
      axisLabel: { color: '#5f7b95', fontSize: 10.5 },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: 'rgba(74, 132, 205, 0.14)', type: 'dashed' } },
      axisLabel: { color: '#5f7b95', fontSize: 10.5 },
    },
  }
}

/** 图表空状态（无真实数据不画图）。 */
export function ChartEmpty({ height = 220, text = '暂无足够真实数据生成趋势图' }: { height?: number; text?: string }) {
  return (
    <div style={{ height, display: 'grid', placeItems: 'center' }}>
      <div style={{ textAlign: 'center', color: '#5f7b95', fontSize: 12 }}>
        <div style={{ fontSize: 26, marginBottom: 8, opacity: 0.6 }}>〰</div>
        {text}
      </div>
    </div>
  )
}
