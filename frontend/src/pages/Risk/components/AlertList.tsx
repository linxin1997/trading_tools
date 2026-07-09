import { Table, Tag } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import type { Alert } from '../../../services/api'

/** 告警级别对应的颜色映射 */
const levelColorMap: Record<string, string> = {
  critical: '#f5222d',
  warning: '#fa8c16',
  info: '#1677ff',
}

/** 告警级别中文名 */
const levelLabelMap: Record<string, string> = {
  critical: '严重',
  warning: '警告',
  info: '提示',
}

interface AlertListProps {
  alerts: Alert[]
  loading: boolean
}

/**
 * 告警列表组件
 * 展示所有触发的风控告警记录，按级别着色
 */
function AlertList({ alerts, loading }: AlertListProps) {
  const columns: ColumnsType<Alert> = [
    { title: '时间', dataIndex: 'time', key: 'time', width: 80 },
    { title: '股票', key: 'stock', width: 140, render: (_: unknown, r: Alert) => `${r.stock_code} ${r.stock_name}` },
    { title: '规则', dataIndex: 'rule_name', key: 'rule_name', width: 120 },
    { title: '消息', dataIndex: 'message', key: 'message' },
    {
      title: '级别',
      dataIndex: 'level',
      key: 'level',
      width: 80,
      render: (level: string) => (
        <Tag color={levelColorMap[level] || '#999'}>{levelLabelMap[level] || level}</Tag>
      ),
    },
  ]

  return (
    <Table
      columns={columns}
      dataSource={alerts}
      rowKey="id"
      loading={loading}
      pagination={{ pageSize: 10, showSizeChanger: false }}
      size="small"
      bordered
    />
  )
}

export default AlertList
