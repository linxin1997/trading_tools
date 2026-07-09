import { useMemo } from 'react'
import ReactEChartsCore from 'echarts-for-react'
import type { ScreenResultItem } from '../types'
import { getScoreColor } from '../types'

/** 评分柱状图属性 */
interface ScoreChartProps {
  dataSource: ScreenResultItem[]
}

/**
 * 评分分布柱状图组件
 * 基于 ECharts 展示 Top 20 选股结果的评分柱状图
 */
function ScoreChart({ dataSource = [] }: ScoreChartProps) {
  /** 生成 ECharts 配置 */
  const option = useMemo(() => {
    const items = dataSource.slice(0, 20)
    return {
      tooltip: {
        trigger: 'axis' as const,
        axisPointer: { type: 'shadow' as const },
        formatter: (params: { name: string; value: number }[]) => {
          const item = params[0]
          if (!item) return ''
          const stock = items[Number(item.name) - 1]
          return stock
            ? `${stock.code} ${stock.name}<br/>评分：${stock.score.toFixed(1)}<br/>均线：${stock.maStatus}<br/>MACD：${stock.macdSignal}`
            : ''
        },
      },
      grid: { left: 40, right: 20, top: 10, bottom: 40 },
      xAxis: {
        type: 'category' as const,
        data: items.map((_, idx) => `${idx + 1}`),
        axisLabel: { fontSize: 10 },
      },
      yAxis: {
        type: 'value' as const,
        name: '评分',
        min: 0,
        max: 100,
      },
      series: [
        {
          type: 'bar' as const,
          data: items.map((item) => ({
            value: item.score,
            itemStyle: { color: getScoreColor(item.score) },
          })),
          barMaxWidth: 24,
        },
      ],
    }
  }, [dataSource])

  if (dataSource.length === 0) return null

  return (
    <div style={{ marginTop: 16 }}>
      <ReactEChartsCore option={option} style={{ height: 200 }} notMerge />
    </div>
  )
}

export default ScoreChart
