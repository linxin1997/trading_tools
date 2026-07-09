import { useEffect, useCallback } from 'react'
import { Row, Col, Typography, Badge } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import IndexCard from './components/IndexCard'
import SectorHeatmap from './components/SectorHeatmap'
import WatchlistTable from './components/WatchlistTable'
import TopGainers from './components/TopGainers'
import useWebSocket from '../../hooks/useWebSocket'
import useMarketStore from '../../stores/useMarketStore'

/** A 股涨跌颜色配置 */
const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

/**
 * 盯盘仪表盘页面
 * 展示大盘指数、板块热力图、自选股、涨幅榜等核心盯盘信息
 */
function Dashboard() {
  const updateQuote = useMarketStore((state) => state.updateQuote)
  const updateIndex = useMarketStore((state) => state.updateIndex)
  const addSector = useMarketStore((state) => state.addSector)
  const addAlert = useMarketStore((state) => state.addAlert)
  const setIndices = useMarketStore((state) => state.setIndices)
  const setSectors = useMarketStore((state) => state.setSectors)
  const setConnected = useMarketStore((state) => state.setConnected)
  const isConnected = useMarketStore((state) => state.isConnected)

  /** WebSocket 消息回调处理 */
  const handleQuote = useCallback(
    (quote: Parameters<typeof updateQuote>[0]) => {
      updateQuote(quote)
    },
    [updateQuote],
  )

  const handleAlert = useCallback(
    (alert: Parameters<typeof addAlert>[0]) => {
      addAlert(alert)
    },
    [addAlert],
  )

  const handleIndex = useCallback(
    (index: { code: string; name: string; point: number; changePercent: number }) => {
      updateIndex(index)
    },
    [updateIndex],
  )

  const handleSector = useCallback(
    (sector: Parameters<typeof addSector>[0]) => {
      addSector(sector)
    },
    [addSector],
  )

  /** 初始化 WebSocket 连接 */
  const { isConnected: wsConnected } = useWebSocket(
    handleQuote,
    handleAlert,
    handleIndex,
    handleSector,
  )

  /** 同步连接状态到 store */
  useEffect(() => {
    setConnected(wsConnected)
  }, [wsConnected, setConnected])

  /** 页面加载时设置默认指数数据（占位用，WebSocket 会覆盖） */
  useEffect(() => {
    setIndices([
      { code: '000001.SH', name: '上证指数', point: 3200.50, changePercent: 0.85 },
      { code: '399001.SZ', name: '深证成指', point: 10200.30, changePercent: 1.20 },
      { code: '399006.SZ', name: '创业板指', point: 2150.80, changePercent: -0.35 },
      { code: '000688.SH', name: '科创50', point: 980.60, changePercent: 0.52 },
    ])

    setSectors([
      { name: '银行', amount: 3.2e9, changePercent: 1.85 },
      { name: '科技', amount: 5.1e9, changePercent: 2.30 },
      { name: '医药', amount: 2.8e9, changePercent: -0.65 },
      { name: '消费', amount: 4.5e9, changePercent: 0.95 },
      { name: '新能源', amount: 3.8e9, changePercent: 1.50 },
      { name: '军工', amount: 1.9e9, changePercent: -1.20 },
      { name: '券商', amount: 2.2e9, changePercent: 0.45 },
      { name: '地产', amount: 1.5e9, changePercent: -0.85 },
      { name: '有色', amount: 2.0e9, changePercent: 1.10 },
      { name: '化工', amount: 1.8e9, changePercent: 0.35 },
      { name: '传媒', amount: 1.2e9, changePercent: -0.55 },
      { name: '建筑', amount: 1.0e9, changePercent: 0.25 },
    ])
  }, [setIndices, setSectors])

  return (
    <div>
      {/* 页面标题和连接状态 */}
      <Row align="middle" style={{ marginBottom: 16 }}>
        <Col flex="auto">
          <Typography.Title level={4} style={{ margin: 0 }}>
            盯盘仪表盘
          </Typography.Title>
        </Col>
        <Col>
          <Badge
            status={isConnected ? 'success' : 'error'}
            text={
              <span style={{ color: isConnected ? COLORS.up : COLORS.down, fontSize: 13 }}>
                {isConnected ? (
                  <>
                    <CheckCircleOutlined /> 已连接
                  </>
                ) : (
                  <>
                    <CloseCircleOutlined /> 未连接
                  </>
                )}
              </span>
            }
          />
        </Col>
      </Row>

      {/* 指数卡片 */}
      <IndexCard />

      {/* 板块热力图 + 自选股（两列布局） */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={14}>
          <SectorHeatmap />
        </Col>
        <Col xs={24} lg={10}>
          <WatchlistTable />
        </Col>
      </Row>

      {/* 涨幅榜 */}
      <TopGainers />
    </div>
  )
}

export default Dashboard
