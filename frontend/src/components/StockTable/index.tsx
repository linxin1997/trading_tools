import { Table } from 'antd'
import type { ColumnsType } from 'antd/es/table'

/** A 股涨跌颜色配置 */
const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

/** 股票数据行 */
export interface StockRecord {
  code: string
  name: string
  price: number
  changePercent: number
  volume: number
  amount: number
}

/** 股票表格组件属性 */
interface StockTableProps {
  dataSource?: StockRecord[]
  loading?: boolean
}

/**
 * 获取涨跌幅对应的颜色
 * @param value - 涨跌幅数值
 * @returns 颜色值
 */
function getChangeColor(value: number): string {
  if (value > 0) return COLORS.up
  if (value < 0) return COLORS.down
  return COLORS.flat
}

/** 表格列配置 */
const columns: ColumnsType<StockRecord> = [
  { title: '代码', dataIndex: 'code', key: 'code', width: 100 },
  { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
  {
    title: '最新价',
    dataIndex: 'price',
    key: 'price',
    width: 100,
    render: (price: number) => price != null ? Number(price).toFixed(2) : '--',
  },
  {
    title: '涨跌幅',
    dataIndex: 'changePercent',
    key: 'changePercent',
    width: 100,
    render: (value: number) => (
      <span style={{ color: getChangeColor(value), fontWeight: 500 }}>
        {value >= 0 ? '+' : ''}
        {value.toFixed(2)}%
      </span>
    ),
  },
  {
    title: '成交量',
    dataIndex: 'volume',
    key: 'volume',
    width: 120,
    render: (value: number) => {
      if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
      return `${value.toFixed(0)}`
    },
  },
  {
    title: '成交额',
    dataIndex: 'amount',
    key: 'amount',
    width: 120,
    render: (value: number) => {
      if (value >= 1e8) return `${(value / 1e8).toFixed(2)}亿`
      if (value >= 1e4) return `${(value / 1e4).toFixed(2)}万`
      return value.toFixed(2)
    },
  },
]

/**
 * 股票列表表格组件
 * 通用组件，用于展示股票行情数据列表，涨跌幅以颜色标识（红涨绿跌）
 */
function StockTable({ dataSource = [], loading = false }: StockTableProps) {
  return (
    <Table
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      rowKey="code"
      size="small"
      pagination={{ pageSize: 20, showSizeChanger: true }}
    />
  )
}

export default StockTable
