import { Card, Row, Col, Statistic } from 'antd'
import type { PnlSummary } from '../../../services/api'

interface PnlSummaryProps {
  data: PnlSummary | null
}

/** A 股盈亏配色 */
const profitColor = '#f5222d'
const lossColor = '#52c41a'

/**
 * 盈亏汇总卡片
 * 显示总市值、总盈亏和今日收益三项指标
 */
function PnlSummaryCard({ data }: PnlSummaryProps) {
  if (!data) return null

  const pnlColor = data.total_pnl >= 0 ? profitColor : lossColor
  const todayColor = data.today_pnl >= 0 ? profitColor : lossColor

  return (
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col span={8}>
        <Card>
          <Statistic
            title="总市值"
            value={data.total_market_value}
            precision={2}
            suffix="元"
          />
        </Card>
      </Col>
      <Col span={8}>
        <Card>
          <Statistic
            title="总盈亏"
            value={data.total_pnl}
            precision={2}
            suffix="元"
            valueStyle={{ color: pnlColor }}
          />
        </Card>
      </Col>
      <Col span={8}>
        <Card>
          <Statistic
            title="今日收益"
            value={data.today_pnl}
            precision={2}
            suffix="元"
            valueStyle={{ color: todayColor }}
          />
        </Card>
      </Col>
    </Row>
  )
}

export default PnlSummaryCard
