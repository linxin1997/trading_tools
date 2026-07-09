import { Table, Button, Space, Typography } from 'antd'
import { EyeOutlined, DownloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import type { ReportRow } from '../types'

/** A 股涨跌颜色 */
const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

const { Text } = Typography

/** 报告列表属性 */
interface ReportListProps {
  dataSource: ReportRow[]
  loading?: boolean
  onRead: (date: string) => void
  onDownload: (date: string) => void
}

/**
 * 报告列表组件
 * 展示按日期倒序排列的复盘报告表格
 */
function ReportList({ dataSource = [], loading = false, onRead, onDownload }: ReportListProps) {
  /** 获取涨跌幅颜色 */
  function getChangeColor(value: number): string {
    if (value > 0) return COLORS.up
    if (value < 0) return COLORS.down
    return COLORS.flat
  }

  /** 表格列定义 */
  const columns: ColumnsType<ReportRow> = [
    {
      title: '日期',
      dataIndex: 'date',
      key: 'date',
      width: 120,
      defaultSortOrder: 'descend',
      sorter: (a, b) => a.date.localeCompare(b.date),
    },
    {
      title: '大盘涨跌',
      dataIndex: 'marketChange',
      key: 'marketChange',
      width: 100,
      render: (value: number) => (
        <Text strong style={{ color: getChangeColor(value) }}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}%
        </Text>
      ),
    },
    {
      title: '涨停数',
      dataIndex: 'limitUpCount',
      key: 'limitUpCount',
      width: 80,
    },
    {
      title: '北向资金(亿)',
      dataIndex: 'northFlow',
      key: 'northFlow',
      width: 120,
      render: (value: number) => {
        const color = value >= 0 ? COLORS.up : COLORS.down
        const sign = value >= 0 ? '+' : ''
        return <Text style={{ color }}>{sign}{value.toFixed(2)}亿</Text>
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: unknown, record: ReportRow) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onRead(record.date)}
          >
            阅读
          </Button>
          <Button
            type="link"
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => onDownload(record.date)}
          >
            下载
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={dataSource}
      loading={loading}
      rowKey="date"
      size="small"
      pagination={{ pageSize: 20, showSizeChanger: true }}
      locale={{ emptyText: '暂无报告数据' }}
    />
  )
}

export default ReportList
