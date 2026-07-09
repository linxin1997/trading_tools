import { Typography, Space, Empty } from 'antd'
import useBacktest from './hooks/useBacktest'
import BacktestForm from './components/BacktestForm'
import MetricsCards from './components/MetricsCards'
import NavChart from './components/NavChart'
import MonthlyHeatmap from './components/MonthlyHeatmap'

/**
 * 策略回测页面
 * 组合参数表单、绩效指标、净值曲线和月度热力图，评估策略表现
 */
function BacktestPage() {
  const { result, strategies, running, submitBacktest } = useBacktest()

  return (
    <div>
      <Typography.Title level={3}>策略回测</Typography.Title>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <BacktestForm strategies={strategies} running={running} onSubmit={submitBacktest} />
        {result ? (
          <>
            <MetricsCards result={result} />
            <NavChart result={result} />
            <MonthlyHeatmap result={result} />
          </>
        ) : (
          !running && <Empty description="请配置参数并开始回测" style={{ marginTop: 48 }} />
        )}
      </Space>
    </div>
  )
}

export default BacktestPage
