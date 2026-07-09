import { useCallback } from 'react'
import { Row, Col, Typography, Badge, message } from 'antd'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import useNewsStream from './hooks/useNewsStream'
import NewsStream from './components/NewsStream'
import NewsFilter from './components/NewsFilter'
import type { NewsFilterParams } from './types'

/** A 股涨跌颜色配置 */
const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

/**
 * 舆情新闻页面
 * 展示与 A 股相关的实时新闻流，支持按来源、情感、标的筛选
 * 布局：左侧为新闻流（虚拟滚动），右侧为筛选面板
 */
function News() {
  const {
    newsList,
    loading,
    hasMore,
    loadMore,
    setFilter,
    filter,
    isConnected,
  } = useNewsStream()

  /** 筛选条件变更 */
  const handleFilterChange = useCallback(
    (newFilter: NewsFilterParams) => {
      setFilter(newFilter)
    },
    [setFilter],
  )

  /** 手动刷新 */
  const handleRefresh = useCallback(() => {
    setFilter(filter)
    message.success('已刷新新闻列表')
  }, [setFilter, filter])

  /** 点击关联股票回调 */
  const handleStockClick = useCallback((stockCode: string) => {
    // 跳转至个股详情页或搜索
    message.info(`跳转至 ${stockCode} 详情页`)
  }, [])

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 页面标题栏 */}
      <Row align="middle" style={{ marginBottom: 16, flexShrink: 0 }}>
        <Col flex="auto">
          <Typography.Title level={4} style={{ margin: 0 }}>
            舆情新闻
          </Typography.Title>
        </Col>
        <Col>
          <Badge
            status={isConnected ? 'success' : 'error'}
            text={
              <span style={{ color: isConnected ? COLORS.up : COLORS.down, fontSize: 13 }}>
                {isConnected ? (
                  <>
                    <CheckCircleOutlined /> 实时连接
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

      {/* 主体内容 */}
      <Row gutter={[16, 16]} style={{ flex: 1, minHeight: 0 }}>
        {/* 左侧：实时新闻流 */}
        <Col xs={24} lg={18} style={{ height: '100%' }}>
          <NewsStream
            newsList={newsList}
            loading={loading}
            hasMore={hasMore}
            onLoadMore={loadMore}
            onStockClick={handleStockClick}
          />
        </Col>

        {/* 右侧：筛选面板 */}
        <Col xs={24} lg={6}>
          <NewsFilter
            filter={filter}
            onFilterChange={handleFilterChange}
            onRefresh={handleRefresh}
            refreshing={loading}
          />
        </Col>
      </Row>
    </div>
  )
}

export default News
