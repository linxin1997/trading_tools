import { useEffect, useRef } from 'react'
import { init, dispose, type Chart } from 'klinecharts'
import { getKLine } from '../../services/api'

/** K 线图组件属性 */
interface KLineChartProps {
  symbol?: string
  width?: number | string
  height?: number | string
}

/**
 * K 线图组件
 * 基于 klinecharts 库封装，用于展示股票 K 线行情
 * 根据 symbol prop 调用 API 加载 K 线数据并渲染
 */
function KLineChart({ symbol = '000001.SH', width = '100%', height = 400 }: KLineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstance = useRef<Chart | null>(null)

  useEffect(() => {
    // 初始化图表
    if (chartRef.current && !chartInstance.current) {
      chartInstance.current = init(chartRef.current)
    }

    // 根据 symbol 加载 K 线数据
    let cancelled = false
    const loadData = async () => {
      try {
        const data = await getKLine(symbol)
        if (!cancelled && chartInstance.current) {
          chartInstance.current.applyNewData(data)
        }
      } catch {
        console.warn('K 线数据加载失败')
      }
    }
    loadData()

    return () => {
      cancelled = true
      if (chartInstance.current) {
        dispose(chartInstance.current)
        chartInstance.current = null
      }
    }
  }, [symbol])

  return <div ref={chartRef} style={{ width, height }} />
}

export default KLineChart
