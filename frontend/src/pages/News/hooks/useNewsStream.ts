import { useState, useCallback, useRef, useEffect } from 'react'
import { getNewsStream } from '../../../services/api'
import type { NewsItem, NewsFilterParams, NewsWsMessage } from '../types'

/** useNewsStream 返回值 */
interface UseNewsStreamReturn {
  /** 当前新闻列表（最新在前） */
  newsList: NewsItem[]
  /** 是否正在加载 */
  loading: boolean
  /** 是否有更多历史数据 */
  hasMore: boolean
  /** 加载更多历史数据 */
  loadMore: () => void
  /** 更新筛选条件并重置列表 */
  setFilter: (filter: NewsFilterParams) => void
  /** 当前筛选条件 */
  filter: NewsFilterParams
  /** WebSocket 连接状态 */
  isConnected: boolean
}

/** 最大重连次数 */
const MAX_RECONNECTS = 10

/**
 * 实时新闻流 Hook
 * - 通过 WebSocket 接收实时新闻推送
 * - 每 30 秒轮询 REST API 获取新新闻
 * - 支持按来源/情感/标的筛选
 *
 * @param initialFilter - 初始筛选条件
 */
function useNewsStream(initialFilter: NewsFilterParams = {}): UseNewsStreamReturn {
  const [newsList, setNewsList] = useState<NewsItem[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [filter, setFilterState] = useState<NewsFilterParams>(initialFilter)
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setInterval>>()
  const cursorRef = useRef<string>('')
  const reconnectCountRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()

  /** 更新筛选条件并重置列表 */
  const setFilter = useCallback((newFilter: NewsFilterParams) => {
    setFilterState(newFilter)
    setNewsList([])
    setHasMore(true)
    cursorRef.current = ''
  }, [])

  /** 从 REST API 拉取历史新闻 */
  const fetchNews = useCallback(
    async (cursor?: string) => {
      setLoading(true)
      try {
        const params: NewsFilterParams = {
          ...filter,
          cursor,
          limit: 20,
        }
        const raw = await getNewsStream(params)
        const data = raw as unknown as NewsItem[]
        if (data.length === 0) {
          setHasMore(false)
        } else {
          if (cursor) {
            // 加载更多：追加到列表尾部
            setNewsList((prev) => [...prev, ...data])
          } else {
            // 首次加载或筛选变更：替换列表
            setNewsList(data)
          }
          // 游标使用本批最旧时间（数据按最新在前排列，排序后首个为最旧）
          const times = data.map((n) => n.publish_time).sort()
          if (times.length > 0) {
            cursorRef.current = times[0]
          }
        }
      } catch {
        // 静默失败，下次轮询会重试
      } finally {
        setLoading(false)
      }
    },
    [filter],
  )

  /** 加载更多历史数据 */
  const loadMore = useCallback(() => {
    if (!loading && hasMore) {
      fetchNews(cursorRef.current)
    }
  }, [loading, hasMore, fetchNews])

  /** 轮询新新闻 */
  const pollLatest = useCallback(async () => {
    try {
      const params: NewsFilterParams = {
        ...filter,
        limit: 10,
      }
      const raw = await getNewsStream(params)
      const data = raw as unknown as NewsItem[]
      if (data.length > 0) {
        // 将新数据合并到列表头部，去重
        setNewsList((prev) => {
          const existingIds = new Set(prev.map((n) => n.id))
          const newItems = data.filter((n) => !existingIds.has(n.id))
          return [...newItems, ...prev]
        })
      }
    } catch {
      // 静默失败
    }
  }, [filter])

  /** 用 ref 持有 scheduleReconnect，解决 connectWebSocket 与 scheduleReconnect 的循环引用 */
  const scheduleReconnectRef = useRef<() => void>()

  /** 创建 WebSocket 连接并绑定事件处理器 */
  const connectWebSocket = useCallback(() => {
    // 关闭已有连接
    if (wsRef.current) {
      wsRef.current.close()
    }

    const ws = new WebSocket('ws://localhost:8000/ws/news')
    wsRef.current = ws

    ws.onopen = () => {
      reconnectCountRef.current = 0
      setIsConnected(true)
    }

    ws.onclose = () => {
      setIsConnected(false)
      // 通过 ref 调用 scheduleReconnect，避免循环依赖
      scheduleReconnectRef.current?.()
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: NewsWsMessage = JSON.parse(event.data)
        if (msg.type === 'news') {
          setNewsList((prev) => {
            // 去重处理
            const exists = prev.some((n) => n.id === msg.data.id)
            if (exists) return prev
            return [msg.data, ...prev]
          })
        }
      } catch {
        // 消息解析失败，忽略
      }
    }
  }, [])

  /** 调度指数退避重连 */
  const scheduleReconnect = useCallback(() => {
    if (reconnectCountRef.current >= MAX_RECONNECTS) {
      setIsConnected(false)
      return
    }

    const delay = Math.min(1000 * Math.pow(2, reconnectCountRef.current), 30000)
    reconnectCountRef.current += 1

    reconnectTimerRef.current = window.setTimeout(() => {
      connectWebSocket()
    }, delay)
  }, [connectWebSocket])

  // 保持 ref 与 scheduleReconnect 同步
  scheduleReconnectRef.current = scheduleReconnect

  /** 初始化 WebSocket 连接 */
  useEffect(() => {
    connectWebSocket()

    return () => {
      clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connectWebSocket])

  /** 启动 30 秒轮询 */
  useEffect(() => {
    // 首次加载
    fetchNews()

    // 定时轮询
    pollTimerRef.current = setInterval(() => {
      pollLatest()
    }, 30000)

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current)
      }
    }
  }, [fetchNews, pollLatest])

  return {
    newsList,
    loading,
    hasMore,
    loadMore,
    setFilter,
    filter,
    isConnected,
  }
}

export default useNewsStream
