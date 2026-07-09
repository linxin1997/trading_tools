import { useState } from 'react'
import { Card, Table, Tabs, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { TabsProps } from 'antd'
import useMarketStore from '../../../stores/useMarketStore'

/** 自选股分组定义 */
interface WatchlistGroup {
  key: string
  label: string
  /** 该分组包含的股票代码列表，空数组表示全部 */
  codes: string[]
}

/** 分组配置 */
const GROUPS: WatchlistGroup[] = [
  { key: 'all', label: '全部', codes: [] },
  { key: 'core', label: '核心持仓', codes: ['000001.SZ', '600519.SH', '000333.SZ'] },
  { key: 'observe', label: '观察池', codes: ['601318.SH', '600036.SH'] },
]

/** 自选股表格行数据类型 */
interface WatchlistRow {
  code: string
  name: string
  price: number
  changePercent: number
}

/** 表格列配置 */
const columns: ColumnsType<WatchlistRow> = [
  { title: '代码', dataIndex: 'code', key: 'code', width: 90 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 100 },
  {
    title: '最新价',
    dataIndex: 'price',
    key: 'price',
    width: 90,
    render: (price: number) => price.toFixed(2),
  },
  {
    title: '涨跌幅',
    dataIndex: 'changePercent',
    key: 'changePercent',
    width: 90,
    render: (value: number) => (
      <Tag color={value > 0 ? 'red' : value < 0 ? 'green' : 'default'} style={{ fontWeight: 500 }}>
        {value >= 0 ? '+' : ''}
        {value.toFixed(2)}%
      </Tag>
    ),
  },
]

/**
 * 自选股表格组件
 * 显示自选股列表，支持分组 Tab 切换（全部 / 核心持仓 / 观察池）
 * 数据来自 WebSocket 实时推送
 */
function WatchlistTable() {
  const [activeGroup, setActiveGroup] = useState('all')
  const quotes = useMarketStore((state) => state.quotes)
  const watchlist = useMarketStore((state) => state.watchlist)

  /** 根据当前选中的分组过滤自选股 */
  const currentGroup = GROUPS.find((g) => g.key === activeGroup)
  const filteredCodes =
    currentGroup && currentGroup.codes.length > 0 ? currentGroup.codes : watchlist

  /** 组装表格数据 */
  const dataSource: WatchlistRow[] = filteredCodes
    .map((code) => {
      const q = quotes.get(code)
      if (!q) return null
      return {
        code: q.code,
        name: q.name,
        price: q.price,
        changePercent: q.changePercent,
      }
    })
    .filter((item): item is WatchlistRow => item !== null)

  /** Tab 配置 */
  const tabItems: TabsProps['items'] = GROUPS.map((group) => ({
    key: group.key,
    label: group.label,
  }))

  return (
    <Card title="自选股" size="small">
      <Tabs
        activeKey={activeGroup}
        onChange={setActiveGroup}
        items={tabItems}
        size="small"
        style={{ marginBottom: 0 }}
      />
      <Table
        columns={columns}
        dataSource={dataSource}
        rowKey="code"
        size="small"
        pagination={false}
        locale={{ emptyText: '暂无数据，等待 WebSocket 推送...' }}
      />
    </Card>
  )
}

export default WatchlistTable
