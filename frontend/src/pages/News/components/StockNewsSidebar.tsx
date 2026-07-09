import { useState, useEffect, useCallback } from 'react'
import { Card, List, Typography, Spin, Empty, Tag } from 'antd'
import type { NewsItem } from '../types'
import { NEWS_SOURCE_MAP } from '../types'
import { getNewsStream } from '../../../services/api'

const { Text } = Typography

/** 个股相关新闻侧栏属性 */
interface StockNewsSidebarProps {
  /** 股票代码 */
  stockCode: string
  /** 股票名称 */
  stockName?: string
  /** 最大显示条数 */
  maxItems?: number
}

/** A 股情感配色 */
const SENTIMENT_COLORS: Record<string, string> = {
  positive: '#f5222d',
  negative: '#52c41a',
  neutral: '#d9d9d9',
}

/**
 * 个股相关新闻侧栏组件
 * 在个股详情页使用，展示该标的相关的舆情新闻列表
 */
function StockNewsSidebar({ stockCode, stockName, maxItems = 10 }: StockNewsSidebarProps) {
  const [newsList, setNewsList] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)

  /** 加载该股票的相关新闻 */
  const loadStockNews = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getNewsStream({
        stock_code: stockCode,
        limit: maxItems,
      })
      setNewsList(data as unknown as NewsItem[])
    } catch {
      setNewsList([])
    } finally {
      setLoading(false)
    }
  }, [stockCode, maxItems])

  useEffect(() => {
    loadStockNews()
  }, [loadStockNews])

  /** 格式化发布时间 */
  const formatTime = (timeStr: string): string => {
    try {
      const date = new Date(timeStr)
      const hh = String(date.getHours()).padStart(2, '0')
      const mm = String(date.getMinutes()).padStart(2, '0')
      return `${hh}:${mm}`
    } catch {
      return timeStr
    }
  }

  return (
    <Card
      size="small"
      title={
        <Text strong>
          {stockName || stockCode} 相关新闻
        </Text>
      }
      style={{ marginTop: 16 }}
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: '24px 0' }}>
          <Spin size="small" />
        </div>
      ) : newsList.length === 0 ? (
        <Empty description="暂无相关新闻" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <List
          size="small"
          dataSource={newsList}
          renderItem={(item) => (
            <List.Item
              style={{
                borderLeft: `3px solid ${SENTIMENT_COLORS[item.sentiment_label] || '#d9d9d9'}`,
                paddingLeft: 8,
                marginBottom: 4,
              }}
            >
              <div style={{ width: '100%' }}>
                {/* 来源和时间 */}
                <div style={{ marginBottom: 2 }}>
                  <Tag
                    style={{
                      fontSize: 11,
                      color: SENTIMENT_COLORS[item.sentiment_label],
                      borderColor: SENTIMENT_COLORS[item.sentiment_label],
                      padding: '0 4px',
                    }}
                  >
                    {NEWS_SOURCE_MAP[item.source] || item.source}
                  </Tag>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {formatTime(item.publish_time)}
                  </Text>
                </div>
                {/* 新闻标题 */}
                <Text
                  style={{ fontSize: 13, cursor: 'pointer' }}
                  onClick={() => window.open(item.url, '_blank')}
                >
                  {item.title}
                </Text>
              </div>
            </List.Item>
          )}
        />
      )}
    </Card>
  )
}

export default StockNewsSidebar
