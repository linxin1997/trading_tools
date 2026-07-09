import { Card } from 'antd'
import ReactEChartsCore from 'echarts-for-react'
import type { BacktestResult } from '../../../services/api'

interface NavChartProps {
  result: BacktestResult | null
}

/**
 * 净值曲线图
 * 使用 ECharts 折线图展示策略与沪深 300 的净值走势对比
 */
function NavChart({ result }: NavChartProps) {
  if (!result || !result.nav.length) return null

  const dates = result.nav.map((d) => d.date)
  const strategyData = result.nav.map((d) => +(d.strategy * 100).toFixed(2))
  const benchmarkData = result.nav.map((d) => +(d.benchmark * 100).toFixed(2))

  const option = {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['策略净值', '沪深300'] },
    grid: { left: 60, right: 20, bottom: 40, top: 40 },
    xAxis: {
      type: 'category' as const,
      data: dates,
      axisLabel: { rotate: 45, fontSize: 11 },
    },
    yAxis: {
      type: 'value' as const,
      name: '净值 (%)',
    },
    series: [
      {
        name: '策略净值',
        type: 'line' as const,
        data: strategyData,
        smooth: true,
        lineStyle: { color: '#f5222d', width: 2 },
        itemStyle: { color: '#f5222d' },
        areaStyle: { color: 'rgba(245, 34, 45, 0.1)' },
      },
      {
        name: '沪深300',
        type: 'line' as const,
        data: benchmarkData,
        smooth: true,
        lineStyle: { color: '#1677ff', width: 2 },
        itemStyle: { color: '#1677ff' },
      },
    ],
  }

  return (
    <Card title="净值曲线" size="small">
      <ReactEChartsCore option={option} style={{ height: 380 }} />
    </Card>
  )
}

export default NavChart
