import { Card, Form, Select, DatePicker, Button, Space } from 'antd'
import type { BacktestRequest, StrategyPreset } from '../../../services/api'

const { RangePicker } = DatePicker

interface BacktestFormProps {
  strategies: StrategyPreset[]
  running: boolean
  onSubmit: (params: BacktestRequest) => void
}

/** 调仓频率选项 */
const freqOptions = [
  { label: '每日', value: 'daily' as const },
  { label: '每周', value: 'weekly' as const },
  { label: '每月', value: 'monthly' as const },
]

/**
 * 回测参数表单
 * 提供策略选择、时间范围、调仓频率等参数配置
 */
function BacktestForm({ strategies, running, onSubmit }: BacktestFormProps) {
  const [form] = Form.useForm()

  const handleSubmit = async () => {
    const values = await form.validateFields()
    onSubmit({
      strategy_id: values.strategy_id,
      conditions: [],
      start_date: values.dateRange[0].format('YYYY-MM-DD'),
      end_date: values.dateRange[1].format('YYYY-MM-DD'),
      rebalance_freq: values.rebalance_freq,
    })
  }

  return (
    <Card title="回测参数">
      <Form form={form} layout="inline" initialValues={{ rebalance_freq: 'monthly' }}>
        <Form.Item label="预置策略" name="strategy_id">
          <Select style={{ width: 180 }} placeholder="选择策略" allowClear>
            {strategies.map((s) => (
              <Select.Option key={s.id} value={s.id}>
                {s.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item
          label="时间范围"
          name="dateRange"
          rules={[{ required: true, message: '请选择回测时间范围' }]}
        >
          <RangePicker />
        </Form.Item>
        <Form.Item label="调仓频率" name="rebalance_freq">
          <Select style={{ width: 100 }} options={freqOptions} />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" onClick={handleSubmit} loading={running}>
              开始回测
            </Button>
            <Button onClick={() => form.resetFields()}>重置</Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  )
}

export default BacktestForm
