import { Card, Slider, Switch, Checkbox, Typography, Space } from 'antd'
import type { RiskRule } from '../../../services/api'

interface RuleConfigProps {
  rules: RiskRule[]
  onSave: (id: string, data: Partial<RiskRule>) => void
}

/**
 * 预设止损规则配置组件
 * 支持对价格止损、均线跌破、MACD死叉、资金流出、负面舆情等规则参数进行可视化调整
 */
function RuleConfig({ rules, onSave }: RuleConfigProps) {
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      {rules.map((rule) => (
        <Card key={rule.id} size="small" title={rule.name}>
          {renderRuleControl(rule, onSave)}
        </Card>
      ))}
    </Space>
  )
}

/** 根据规则类型渲染对应的控制组件 */
function renderRuleControl(rule: RiskRule, onSave: RuleConfigProps['onSave']) {
  switch (rule.type) {
    case 'price_stop': {
      const val = (rule.params.percent as number) || 5
      return (
        <div>
          <Typography.Text strong>{val}%</Typography.Text>
          <Slider
            min={1}
            max={20}
            value={val}
            onChange={(v) => onSave(rule.id, { params: { ...rule.params, percent: v } })}
          />
        </div>
      )
    }
    case 'ma_break': {
      const selected = (rule.params.periods as unknown as string[]) || []
      return (
        <Checkbox.Group
          options={[
            { label: 'MA5', value: 'MA5' },
            { label: 'MA10', value: 'MA10' },
            { label: 'MA20', value: 'MA20' },
            { label: 'MA60', value: 'MA60' },
          ]}
          value={selected}
          onChange={(values) => onSave(rule.id, { params: { ...rule.params, periods: values as unknown as string | number | boolean } })}
        />
      )
    }
    case 'macd_dead_cross': {
      const enabled = rule.enabled
      return (
        <Switch
          checked={enabled}
          checkedChildren="已启用"
          unCheckedChildren="已禁用"
          onChange={(v) => onSave(rule.id, { enabled: v })}
        />
      )
    }
    case 'capital_outflow': {
      const val = (rule.params.percent as number) || 3
      return (
        <div>
          <Typography.Text strong>{val}%</Typography.Text>
          <Slider
            min={0}
            max={10}
            step={0.5}
            value={val}
            onChange={(v) => onSave(rule.id, { params: { ...rule.params, percent: v } })}
          />
        </div>
      )
    }
    case 'negative_sentiment': {
      const val = (rule.params.threshold as number) || 0.8
      return (
        <div>
          <Typography.Text strong>{val.toFixed(1)}</Typography.Text>
          <Slider
            min={0}
            max={1}
            step={0.1}
            value={val}
            onChange={(v) => onSave(rule.id, { params: { ...rule.params, threshold: v } })}
          />
        </div>
      )
    }
    default: {
      const enabled = rule.enabled
      return (
        <Switch
          checked={enabled}
          checkedChildren="已启用"
          unCheckedChildren="已禁用"
          onChange={(v) => onSave(rule.id, { enabled: v })}
        />
      )
    }
  }
}

export default RuleConfig
