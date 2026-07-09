import { Row, Col, Card, Statistic } from 'antd'
import type { BacktestResult } from '../../../services/api'

interface MetricsCardsProps {
  result: BacktestResult | null
}

/** 绩效指标配色 */
const positiveColor = '#f5222d'
const negativeColor = '#52c41a'

/**
 * 回测绩效指标卡片
 * 展示累计收益、年化收益、夏普比率、最大回撤四项关键指标
 */
function MetricsCards({ result }: MetricsCardsProps) {
  if (!result) return null

  const totalColor = result.total_return >= 0 ? positiveColor : negativeColor
  const annualColor = result.annual_return >= 0 ? positiveColor : negativeColor

  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="累计收益"
            value={result.total_return}
            precision={2}
            suffix="%"
            valueStyle={{ color: totalColor }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="年化收益"
            value={result.annual_return}
            precision={2}
            suffix="%"
            valueStyle={{ color: annualColor }}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="夏普比率"
            value={result.sharpe_ratio}
            precision={2}
          />
        </Card>
      </Col>
      <Col span={6}>
        <Card size="small">
          <Statistic
            title="最大回撤"
            value={result.max_drawdown}
            precision={2}
            suffix="%"
            valueStyle={{ color: negativeColor }}
          />
        </Card>
      </Col>
    </Row>
  )
}

export default MetricsCards
