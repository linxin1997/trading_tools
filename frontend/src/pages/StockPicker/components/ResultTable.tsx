import { useState } from 'react'
import { Table, Button, Modal, Tag, Space, Typography } from 'antd'
import { BarChartOutlined, RobotOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import KLineChart from '../../../components/KLineChart'
import type { ScreenResultItem } from '../types'
import { getScoreColor } from '../types'

const { Text } = Typography

/** 选股结果表格属性 */
interface ResultTableProps {
  dataSource: ScreenResultItem[]
  loading?: boolean
}

/**
 * 评分结果表格组件
 * 展示选股结果，支持 K 线弹窗查看和 AI 解释
 */
function ResultTable({ dataSource = [], loading = false }: ResultTableProps) {
  const [klineStock, setKlineStock] = useState<{ code: string; name: string } | null>(null)
  const [aiExplain, setAiExplain] = useState<ScreenResultItem | null>(null)

  /** 列定义 */
  const columns: ColumnsType<ScreenResultItem> = [
    {
      title: '代码',
      dataIndex: 'code',
      key: 'code',
      width: 90,
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
    },
    {
      title: '评分',
      dataIndex: 'score',
      key: 'score',
      width: 80,
      sorter: (a, b) => b.score - a.score,
      render: (score: number) => (
        <Text strong style={{ color: getScoreColor(score) }}>
          {score.toFixed(1)}
        </Text>
      ),
    },
    {
      title: '均线',
      dataIndex: 'maStatus',
      key: 'maStatus',
      width: 90,
      render: (val: string) => {
        const isBullish = val.includes('多头')
        return (
          <Tag color={isBullish ? '#f5222d' : '#52c41a'}>
            {val}
          </Tag>
        )
      },
    },
    {
      title: 'MACD',
      dataIndex: 'macdSignal',
      key: 'macdSignal',
      width: 90,
      render: (val: string) => {
        const isGolden = val.includes('金叉')
        return (
          <Tag color={isGolden ? '#f5222d' : '#52c41a'}>
            {val}
          </Tag>
        )
      },
    },
    {
      title: '详情',
      key: 'action',
      width: 140,
      render: (_: unknown, record: ScreenResultItem) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<BarChartOutlined />}
            onClick={() => setKlineStock({ code: record.code, name: record.name })}
          >
            K线
          </Button>
          <Button
            type="link"
            size="small"
            icon={<RobotOutlined />}
            onClick={() => setAiExplain(record)}
          >
            AI解释
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <>
      <Table
        columns={columns}
        dataSource={dataSource}
        loading={loading}
        rowKey="code"
        size="small"
        pagination={{ pageSize: 20, showSizeChanger: true }}
        locale={{ emptyText: '点击"筛选"查看结果' }}
      />

      {/* K 线弹窗 */}
      <Modal
        title={klineStock ? `${klineStock.name} (${klineStock.code})` : 'K 线图'}
        open={!!klineStock}
        onCancel={() => setKlineStock(null)}
        footer={null}
        width={800}
        destroyOnClose
      >
        {klineStock && (
          <KLineChart
            symbol={klineStock.code}
            width="100%"
            height={500}
          />
        )}
      </Modal>

      {/* AI 解释弹窗 */}
      <Modal
        title={aiExplain ? `${aiExplain.name} (${aiExplain.code}) - AI 解释` : 'AI 解释'}
        open={!!aiExplain}
        onCancel={() => setAiExplain(null)}
        footer={null}
        width={600}
        destroyOnClose
      >
        {aiExplain && (
          <div>
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>综合评分：</Text>
                <Text style={{ color: getScoreColor(aiExplain.score), fontSize: 20, fontWeight: 600 }}>
                  {aiExplain.score.toFixed(1)}
                </Text>
              </div>
              <div>
                <Text strong>均线状态：</Text>
                <Tag color={aiExplain.maStatus.includes('多头') ? '#f5222d' : '#52c41a'}>
                  {aiExplain.maStatus}
                </Tag>
              </div>
              <div>
                <Text strong>MACD 信号：</Text>
                <Tag color={aiExplain.macdSignal.includes('金叉') ? '#f5222d' : '#52c41a'}>
                  {aiExplain.macdSignal}
                </Tag>
              </div>
              <div>
                <Text strong>因子详情：</Text>
                {Object.entries(aiExplain.factors).map(([key, val]) => (
                  <div key={key} style={{ paddingLeft: 16, marginTop: 4 }}>
                    <Text type="secondary">{key}：</Text>
                    <Text>{String(val)}</Text>
                  </div>
                ))}
              </div>
              <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 6 }}>
                <Text type="secondary">
                  该标的评分 {aiExplain.score.toFixed(1)} 分，均线呈{aiExplain.maStatus}，
                  MACD 信号为{aiExplain.macdSignal}，建议结合市场整体情况综合判断。
                </Text>
              </div>
            </Space>
          </div>
        )}
      </Modal>
    </>
  )
}

export default ResultTable
