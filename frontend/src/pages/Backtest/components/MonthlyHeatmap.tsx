import { Card } from 'antd'
import ReactEChartsCore from 'echarts-for-react'
import type { BacktestResult } from '../../../services/api'

interface MonthlyHeatmapProps {
  result: BacktestResult | null
}

/**
 * 月度收益热力图
 * 使用 ECharts 热力图展示各月收益率，绿色=盈利，红色=亏损（与A股习惯符号相反）
 */
function MonthlyHeatmap({ result }: MonthlyHeatmapProps) {
  if (!result || !result.monthly_returns.length) return null

  /** 将月度数据映射为 12 个月的日历热力图格式 */
  const months = result.monthly_returns.map((m) => {
    const [year, month] = m.month.split('-')
    return { year: +year, month: +month, value: m.value }
  })

  const years = [...new Set(months.map((m) => m.year))].sort()
  const allMonths = Array.from({ length: 12 }, (_, i) => i + 1)

  /** 构造热力图数据：[年索引, 月索引, 收益率] */
  const heatData: [number, number, number][] = []
  years.forEach((year, yi) => {
    allMonths.forEach((month) => {
      const found = months.find((m) => m.year === year && m.month === month)
      heatData.push([yi, month - 1, found ? +(found.value * 100).toFixed(2) : 0])
    })
  })

  const option = {
    tooltip: {
      formatter: (params: { value: number[] }) => {
        const [yi, mi, val] = params.value
        const year = years[yi]
        return `${year}年${mi + 1}月<br/>收益率: ${val.toFixed(2)}%`
      },
    },
    grid: { left: 60, right: 40, bottom: 30, top: 20 },
    xAxis: {
      type: 'category' as const,
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'category' as const,
      data: years.map(String),
      axisLabel: { fontSize: 11 },
    },
    visualMap: {
      min: -10,
      max: 10,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      inRange: {
        color: ['#52c41a', '#e8f5e9', '#fff', '#ffebee', '#f5222d'],
      },
    },
    series: [
      {
        type: 'heatmap' as const,
        data: heatData,
        label: {
          show: true,
          fontSize: 11,
          formatter: (params: { value: number[] }) => {
            const val = params.value[2]
            return val ? `${val.toFixed(1)}%` : ''
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
        },
      },
    ],
  }

  return (
    <Card title="月度收益热力图" size="small">
      <ReactEChartsCore option={option} style={{ height: 280 }} />
    </Card>
  )
}

export default MonthlyHeatmap
