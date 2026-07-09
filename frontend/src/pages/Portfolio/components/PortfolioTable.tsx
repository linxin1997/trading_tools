import { Table, Button, Space, Popconfirm } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Position } from '../../../services/api'

/** 盈亏颜色：A 股红涨绿跌 */
const profitColor = '#f5222d'
const lossColor = '#52c41a'

interface PortfolioTableProps {
  positions: Position[]
  loading: boolean
  onEdit: (record: Position) => void
  onDelete: (id: number) => void
}

/**
 * 持仓列表表格
 * 展示所有持仓的代码、名称、成本价、现价、持股数、盈亏、分组等信息
 */
function PortfolioTable({ positions, loading, onEdit, onDelete }: PortfolioTableProps) {
  const columns: ColumnsType<Position> = [
    { title: '代码', dataIndex: 'code', key: 'code', width: 100 },
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    {
      title: '成本价',
      dataIndex: 'cost_price',
      key: 'cost_price',
      width: 100,
      align: 'right',
      render: (v: number) => v.toFixed(2),
    },
    {
      title: '现价',
      dataIndex: 'current_price',
      key: 'current_price',
      width: 100,
      align: 'right',
      render: (v: number) => v.toFixed(2),
    },
    {
      title: '持股数',
      dataIndex: 'shares',
      key: 'shares',
      width: 100,
      align: 'right',
      render: (v: number) => v.toLocaleString(),
    },
    {
      title: '盈亏',
      key: 'pnl',
      width: 120,
      align: 'right',
      render: (_: unknown, record: Position) => {
        const pnl = (record.current_price - record.cost_price) * record.shares
        const color = pnl >= 0 ? profitColor : lossColor
        const sign = pnl >= 0 ? '+' : ''
        return <span style={{ color, fontWeight: 600 }}>{sign}{pnl.toFixed(2)}</span>
      },
    },
    {
      title: '盈亏%',
      key: 'pnlPercent',
      width: 100,
      align: 'right',
      render: (_: unknown, record: Position) => {
        const pct = ((record.current_price - record.cost_price) / record.cost_price) * 100
        const color = pct >= 0 ? profitColor : lossColor
        const sign = pct >= 0 ? '+' : ''
        return <span style={{ color, fontWeight: 600 }}>{sign}{pct.toFixed(2)}%</span>
      },
    },
    {
      title: '分组',
      dataIndex: 'group_id',
      key: 'group_id',
      width: 120,
      render: (gid: number) => gid ? `分组 ${gid}` : '未分组',
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: Position) => (
        <Space>
          <Button type="link" size="small" onClick={() => onEdit(record)}>
            修改
          </Button>
          <Popconfirm title="确认删除该持仓？" onConfirm={() => onDelete(record.id)}>
            <Button type="link" size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={positions}
      rowKey="id"
      loading={loading}
      pagination={false}
      size="middle"
      bordered
    />
  )
}

export default PortfolioTable
