import { Card } from 'antd'
import ReactEChartsCore from 'echarts-for-react/lib/core'
import * as echarts from 'echarts/core'
import { TreemapChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import useMarketStore from '../../../stores/useMarketStore'

// 注册 ECharts treemap 所需的组件
echarts.use([TreemapChart, TooltipComponent, CanvasRenderer])

/** A 股涨跌颜色配置 */
const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

/**
 * 板块热力图组件
 * 使用 ECharts 矩形树图展示申万一级行业板块，色块大小=成交额，颜色深浅=涨跌幅
 */
function SectorHeatmap() {
  const sectors = useMarketStore((state) => state.sectors)

  /**
   * 根据涨跌幅获取板块颜色
   * @param value - 涨跌幅
   * @returns 颜色值
   */
  function getSectorColor(value: number): string {
    if (value > 0) {
      // 涨幅越大颜色越深
      const intensity = Math.min(Math.abs(value) / 5, 1)
      const r = 0xf5
      const g = Math.round(0x22 + (0xff - 0x22) * (1 - intensity))
      const b = Math.round(0x2d + (0xff - 0x2d) * (1 - intensity))
      return `rgb(${r}, ${g}, ${b})`
    }
    if (value < 0) {
      // 跌幅越大颜色越深
      const intensity = Math.min(Math.abs(value) / 5, 1)
      const r = Math.round(0x52 + (0xff - 0x52) * (1 - intensity))
      const g = 0xc4
      const b = Math.round(0x1a + (0xff - 0x1a) * (1 - intensity))
      return `rgb(${r}, ${g}, ${b})`
    }
    return COLORS.flat
  }

  /** 构建 ECharts 树图数据 */
  const treeData = sectors.map((sector) => ({
    name: sector.name,
    value: sector.amount,
    itemStyle: {
      color: getSectorColor(sector.changePercent),
    },
    // 自定义数据，用于 tooltip 展示
    changePercent: sector.changePercent,
  }))

  /** 无数据时的占位树图数据 */
  const placeholderData = [
    { name: '暂无板块数据', value: 1, itemStyle: { color: COLORS.flat }, changePercent: 0 },
  ]

  /** ECharts 配置项 */
  const option = {
    tooltip: {
      trigger: 'item' as const,
      formatter: (params: { name: string; value: number; data: { changePercent: number } }) => {
        const sign = params.data.changePercent >= 0 ? '+' : ''
        const amount =
          params.value >= 1e8
            ? `${(params.value / 1e8).toFixed(2)}亿`
            : `${(params.value / 1e4).toFixed(2)}万`
        return `<strong>${params.name}</strong><br/>成交额：${amount}<br/>涨跌幅：<span style="color:${params.data.changePercent >= 0 ? COLORS.up : COLORS.down}">${sign}${params.data.changePercent.toFixed(2)}%</span>`
      },
    },
    series: [
      {
        type: 'treemap',
        data: treeData.length > 0 ? treeData : placeholderData,
        roam: false,
        leafDepth: 1,
        label: {
          show: true,
          formatter: (params: { name: string }) => params.name,
          fontSize: 12,
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 2,
        },
        levels: [
          {
            colorSaturation: [0.3, 0.6],
            itemStyle: {
              borderColor: '#fff',
              borderWidth: 2,
              gapWidth: 2,
            },
          },
        ],
      },
    ],
    grid: {
      containLabel: true,
    },
  }

  return (
    <Card title="板块热力图" size="small">
      <ReactEChartsCore
        echarts={echarts}
        option={option}
        style={{ height: 360 }}
        notMerge
        lazyUpdate
      />
    </Card>
  )
}

export default SectorHeatmap
