import { useState, useCallback } from 'react'
import { Card, Typography, Tag, Space, Row, Col } from 'antd'
import {
  CaretUpOutlined,
  CaretDownOutlined,
  MinusOutlined,
} from '@ant-design/icons'
import type { NewsItem, SentimentLabel } from '../types'
import { NEWS_SOURCE_MAP } from '../types'

const { Text, Paragraph } = Typography

/** A 股情感配色：涨=红，跌=绿，平=灰 */
const SENTIMENT_COLORS: Record<SentimentLabel, string> = {
  positive: '#f5222d',
  negative: '#52c41a',
  neutral: '#d9d9d9',
}

/** 情感图标 */
const SENTIMENT_ICONS: Record<SentimentLabel, React.ReactNode> = {
  positive: <CaretUpOutlined />,
  negative: <CaretDownOutlined />,
  neutral: <MinusOutlined />,
}

/** 新闻卡片属性 */
interface NewsCardProps {
  /** 新闻数据 */
  news: NewsItem
  /** 点击关联股票的回调 */
  onStockClick?: (stockCode: string) => void
}

/**
 * 单条新闻卡片组件
 * 展示新闻的标题、来源、情感色标及关联股票信息
 * 点击可展开查看全文
 */
function NewsCard({ news, onStockClick }: NewsCardProps) {
  const [expanded, setExpanded] = useState(false)

  /** 切换展开/收起 */
  const toggleExpand = useCallback(() => {
    setExpanded((prev) => !prev)
  }, [])

  /** 格式化发布时间为 HH:mm */
  const formatPublishTime = (timeStr: string): string => {
    try {
      const date = new Date(timeStr)
      const hh = String(date.getHours()).padStart(2, '0')
      const mm = String(date.getMinutes()).padStart(2, '0')
      return `${hh}:${mm}`
    } catch {
      return timeStr
    }
  }

  /** 情感色标对应的边框样式 */
  const borderColor = SENTIMENT_COLORS[news.sentiment_label]
  const sentimentIcon = SENTIMENT_ICONS[news.sentiment_label]

  return (
    <Card
      size="small"
      style={{
        marginBottom: 8,
        borderLeft: `4px solid ${borderColor}`,
        cursor: 'pointer',
      }}
      onClick={toggleExpand}
      hoverable
    >
      {/* 标题行 */}
      <Row align="middle" gutter={8}>
        <Col>
          <Tag
            color="default"
            style={{
              color: borderColor,
              borderColor: borderColor,
              fontWeight: 500,
            }}
          >
            {NEWS_SOURCE_MAP[news.source] || news.source}
          </Tag>
        </Col>
        <Col>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {formatPublishTime(news.publish_time)}
          </Text>
        </Col>
        <Col flex="auto">
          <Text strong style={{ fontSize: 14 }}>
            {news.title}
          </Text>
        </Col>
      </Row>

      {/* 展开后显示正文 */}
      {expanded && (
        <div style={{ marginTop: 8 }}>
          <Paragraph style={{ fontSize: 13, marginBottom: 8, whiteSpace: 'pre-wrap' }}>
            {news.content}
          </Paragraph>

          {/* 情感标签和相关股票 */}
          <Space size={[8, 4]} wrap>
            <Text style={{ fontSize: 12, color: borderColor }}>
              {sentimentIcon}{' '}
              情感：{news.sentiment_label === 'positive' ? '正面' :
                    news.sentiment_label === 'negative' ? '负面' : '中性'}
              {' '}({news.sentiment_score.toFixed(2)})
            </Text>

            {news.related_stocks.length > 0 && (
              <Text style={{ fontSize: 12 }} type="secondary">
                相关：
                {news.related_stocks.map((stock, idx) => (
                  <Text
                    key={stock}
                    style={{
                      fontSize: 12,
                      color: '#1890ff',
                      cursor: 'pointer',
                      marginLeft: idx > 0 ? 4 : 0,
                    }}
                    onClick={(e) => {
                      e.stopPropagation()
                      onStockClick?.(stock)
                    }}
                  >
                    {stock}
                    {idx < news.related_stocks.length - 1 ? '、' : ''}
                  </Text>
                ))}
              </Text>
            )}
          </Space>
        </div>
      )}
    </Card>
  )
}

export default NewsCard
