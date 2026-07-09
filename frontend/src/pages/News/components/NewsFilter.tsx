import { useCallback } from 'react'
import { Card, Select, Input, Space, Typography, Button } from 'antd'
import { FilterOutlined, ReloadOutlined } from '@ant-design/icons'
import type { NewsSource, SentimentLabel, NewsFilterParams } from '../types'
import { NEWS_SOURCE_OPTIONS, SENTIMENT_OPTIONS } from '../types'

const { Title } = Typography

/** 来源全部选项 */
const ALL_SOURCE_OPTION = { value: '', label: '全部' }

/** 情感全部选项 */
const ALL_SENTIMENT_OPTION = { value: '', label: '全部' }

/** 新闻筛选面板属性 */
interface NewsFilterProps {
  /** 当前筛选参数 */
  filter: NewsFilterParams
  /** 筛选条件变更回调 */
  onFilterChange: (filter: NewsFilterParams) => void
  /** 手动刷新回调 */
  onRefresh?: () => void
  /** 是否正在刷新 */
  refreshing?: boolean
}

/**
 * 新闻筛选面板组件
 * 支持按来源、情感分类、关联标的进行筛选
 */
function NewsFilter({ filter, onFilterChange, onRefresh, refreshing }: NewsFilterProps) {
  /** 来源变更 */
  const handleSourceChange = useCallback(
    (values: string[]) => {
      onFilterChange({
        ...filter,
        sources: values.length > 0 ? (values as NewsSource[]) : undefined,
      })
    },
    [filter, onFilterChange],
  )

  /** 情感变更 */
  const handleSentimentChange = useCallback(
    (values: string[]) => {
      onFilterChange({
        ...filter,
        sentiments: values.length > 0 ? (values as SentimentLabel[]) : undefined,
      })
    },
    [filter, onFilterChange],
  )

  /** 标的输入 */
  const handleStockChange = useCallback(
    (value: string) => {
      onFilterChange({
        ...filter,
        stock_code: value || undefined,
      })
    },
    [filter, onFilterChange],
  )

  return (
    <Card
      size="small"
      title={
        <Space>
          <FilterOutlined />
          <span>筛选面板</span>
        </Space>
      }
      extra={
        onRefresh && (
          <Button
            type="text"
            size="small"
            icon={<ReloadOutlined />}
            loading={refreshing}
            onClick={onRefresh}
          >
            刷新
          </Button>
        )
      }
    >
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* 来源筛选 */}
        <div>
          <Title level={5} style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
            新闻来源
          </Title>
          <Select
            mode="multiple"
            placeholder="全部来源"
            style={{ width: '100%' }}
            options={[ALL_SOURCE_OPTION, ...NEWS_SOURCE_OPTIONS]}
            value={filter.sources || []}
            onChange={handleSourceChange}
            allowClear
            maxTagCount={2}
            size="small"
          />
        </div>

        {/* 情感筛选 */}
        <div>
          <Title level={5} style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
            情感分类
          </Title>
          <Select
            mode="multiple"
            placeholder="全部情感"
            style={{ width: '100%' }}
            options={[ALL_SENTIMENT_OPTION, ...SENTIMENT_OPTIONS]}
            value={filter.sentiments || []}
            onChange={handleSentimentChange}
            allowClear
            maxTagCount={2}
            size="small"
          />
        </div>

        {/* 标的筛选 */}
        <div>
          <Title level={5} style={{ marginTop: 0, marginBottom: 4, fontSize: 13 }}>
            关联标的
          </Title>
          <Input
            placeholder="输入股票代码筛选"
            value={filter.stock_code || ''}
            onChange={(e) => handleStockChange(e.target.value)}
            allowClear
            size="small"
          />
        </div>
      </Space>
    </Card>
  )
}

export default NewsFilter
