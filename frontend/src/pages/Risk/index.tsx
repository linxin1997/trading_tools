import { Typography, Spin, Row, Col } from 'antd'
import useRisk from './hooks/useRisk'
import AlertList from './components/AlertList'
import RuleConfig from './components/RuleConfig'

/**
 * 风控监控页面
 * 展示告警列表和止损规则配置，帮助用户监控持仓风险
 */
function RiskPage() {
  const { alerts, rules, loading, saveRule } = useRisk()

  return (
    <Spin spinning={loading}>
      <Typography.Title level={3}>风控监控</Typography.Title>
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={14}>
          <AlertList alerts={alerts} loading={loading} />
        </Col>
        <Col xs={24} lg={10}>
          <RuleConfig rules={rules} onSave={saveRule} />
        </Col>
      </Row>
    </Spin>
  )
}

export default RiskPage
