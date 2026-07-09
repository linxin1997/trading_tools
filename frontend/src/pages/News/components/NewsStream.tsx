import { useRef, useCallback, useState, useEffect } from 'react'
import { Spin, Empty, Typography } from 'antd'
import NewsCard from './NewsCard'
import type { NewsItem } from '../types'

const { Text } = Typography

/** 虚拟滚动预估的卡片高度（含间隔） */
const ITEM_HEIGHT = 56

/** 可视区域上方/下方额外渲染的缓冲行数 */
const BUFFER_ROWS = 3

/** 新闻流组件属性 */
interface NewsStreamProps {
  /** 新闻列表数据 */
  newsList: NewsItem[]
  /** 是否正在加载中 */
  loading: boolean
  /** 是否还有更多数据可加载 */
  hasMore: boolean
  /** 加载更多回调（滚动到底部触发） */
  onLoadMore: () => void
  /** 点击关联股票的回调 */
  onStockClick?: (stockCode: string) => void
}

/**
 * 实时新闻流组件（虚拟滚动）
 * 新消息自动出现在顶部，滚动到底部自动加载更多历史数据
 */
function NewsStream({
  newsList,
  loading,
  hasMore,
  onLoadMore,
  onStockClick,
}: NewsStreamProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(600)

  /** 总内容高度 */
  const totalHeight = newsList.length * ITEM_HEIGHT

  /** 计算可视范围内的起始和结束索引 */
  const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - BUFFER_ROWS)
  const endIndex = Math.min(
    newsList.length,
    Math.ceil((scrollTop + containerHeight) / ITEM_HEIGHT) + BUFFER_ROWS,
  )

  /** 当前可视列表 */
  const visibleItems = newsList.slice(startIndex, endIndex)

  /** 顶部偏移量 */
  const topOffset = startIndex * ITEM_HEIGHT

  /** 滚动事件处理 */
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return
    const { scrollTop: st, scrollHeight, clientHeight } = containerRef.current
    setScrollTop(st)

    // 滚动到底部触发加载更多
    if (scrollHeight - st - clientHeight < 100 && hasMore && !loading) {
      onLoadMore()
    }
  }, [hasMore, loading, onLoadMore])

  /** 监听容器尺寸变化 */
  useEffect(() => {
    if (!containerRef.current) return
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerHeight(entry.contentRect.height)
      }
    })
    observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={containerRef}
      style={{
        height: '100%',
        overflowY: 'auto',
        overflowX: 'hidden',
        position: 'relative',
      }}
      onScroll={handleScroll}
    >
      {/* 空数据状态 */}
      {!loading && newsList.length === 0 && (
        <div style={{ paddingTop: 80 }}>
          <Empty description="暂无新闻数据" />
        </div>
      )}

      {/* 虚拟滚动容器 */}
      <div style={{ height: totalHeight, position: 'relative' }}>
        {/* 偏移占位，使可视区域项目排列正确 */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            transform: `translateY(${topOffset}px)`,
          }}
        >
          {visibleItems.map((news) => (
            <div key={news.id} style={{ height: ITEM_HEIGHT - 8 }}>
              <NewsCard news={news} onStockClick={onStockClick} />
            </div>
          ))}
        </div>
      </div>

      {/* 加载更多提示 */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <Spin size="small" />
          <Text type="secondary" style={{ marginLeft: 8 }}>
            加载中...
          </Text>
        </div>
      )}

      {/* 没有更多数据 */}
      {!hasMore && newsList.length > 0 && !loading && (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <Text type="secondary">已加载全部历史新闻</Text>
        </div>
      )}
    </div>
  )
}

export default NewsStream
