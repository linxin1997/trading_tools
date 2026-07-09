import { useState, useEffect, useCallback } from 'react'
import { Card, Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import useMarketStore from '../../../stores/useMarketStore'
import { getTopGainers } from '../../../services/api'
import type { Quote } from '../../../hooks/useWebSocket'

/** 涨幅榜行数据类型 */
interface GainerRow {
  code: string
  name: string
  price: number
  changePercent: number
  amount: number
}

/** 表格列配置 */
const columns: ColumnsType<GainerRow> = [
  { title: '代码', dataIndex: 'code', key: 'code', width: 80 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 100 },
  {
    title: '最新价',
    dataIndex: 'price',
    key: 'price',
    width: 80,
    render: (price: number) => price.toFixed(2),
  },
  {
    title: '涨幅',
    dataIndex: 'changePercent',
    key: 'changePercent',
    width: 80,
    render: (value: number) => (
      <Tag color={value > 0 ? 'red' : value < 0 ? 'green' : 'default'} style={{ fontWeight: 500 }}>
        {value >= 0 ? '+' : ''}
        {value.toFixed(2)}%
      </Tag>
    ),
  },
  {
    title: '成交额',
    dataIndex: 'amount',
    key: 'amount',
    width: 100,
    render: (value: number) => {
      if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
      if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
      return value.toFixed(2)
    },
  },
]

/**
 * 涨幅榜组件
 * 显示涨幅前 10 的股票，每 30 秒自动刷新
 */
function TopGainers() {
  const [data, setData] = useState<GainerRow[]>([])
  const [loading, setLoading] = useState(false)
  const topGainers = useMarketStore((state) => state.topGainers)
  const setTopGainers = useMarketStore((state) => state.setTopGainers)

  /** 从 API 拉取涨幅榜数据 */
  const fetchTopGainers = useCallback(async () => {
    setLoading(true)
    try {
      const result = await getTopGainers(10)
      setTopGainers(result)
      setData(
        result.map((item: Quote) => ({
          code: item.code,
          name: item.name,
          price: item.price,
          changePercent: item.changePercent,
          amount: item.amount,
        })),
      )
    } catch {
      console.warn('涨幅榜数据拉取失败')
    } finally {
      setLoading(false)
    }
  }, [setTopGainers])

  /** 初始加载 + 每 30 秒轮询 */
  useEffect(() => {
    fetchTopGainers()
    const timer = setInterval(fetchTopGainers, 30000)
    return () => clearInterval(timer)
  }, [fetchTopGainers])

  /** 如果 store 中已有涨幅榜数据，优先使用（可能来自 WebSocket 实时推送） */
  useEffect(() => {
    if (topGainers.length > 0) {
      setData(
        topGainers.map((item: Quote) => ({
          code: item.code,
          name: item.name,
          price: item.price,
          changePercent: item.changePercent,
          amount: item.amount,
        })),
      )
    }
  }, [topGainers])

  return (
    <Card title="涨幅榜" size="small">
      <Table
        columns={columns}
        dataSource={data}
        rowKey="code"
        size="small"
        loading={loading}
        pagination={false}
        locale={{ emptyText: '暂无数据' }}
      />
    </Card>
  )
}

export default TopGainers
