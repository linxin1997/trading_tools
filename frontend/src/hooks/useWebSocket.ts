import { useCallback, useEffect, useRef, useState } from 'react'

/** 单只股票行情数据 */
export interface Quote {
  code: string
  name: string
  price: number
  changePercent: number
  open: number
  high: number
  low: number
  volume: number
  amount: number
}

/** 异动告警数据 */
export interface Alert {
  code: string
  name: string
  price: number
  changePercent: number
  /** 异动类型：拉升 | 跳水 | 放量 */
  type: 'surge' | 'plunge' | 'volume'
  /** 异动描述 */
  message: string
  /** 发生时间戳（毫秒） */
  timestamp: number
}

/** WebSocket 返回的消息格式 */
interface WsMessage {
  type: 'quote' | 'alert' | 'index' | 'sector' | 'connected'
  data: unknown
}

/** useWebSocket 返回值 */
interface UseWebSocketReturn {
  /** 实时行情映射，key 为股票代码 */
  quotes: Map<string, Quote>
  /** 连接状态 */
  isConnected: boolean
  /** 订阅一组股票代码 */
  subscribe: (symbols: string[]) => void
  /** 退订一组股票代码 */
  unsubscribe: (symbols: string[]) => void
  /** 手动建立连接 */
  connect: () => void
  /** 手动断开连接 */
  disconnect: () => void
}

/**
 * WebSocket 实时行情 Hook
 * 自动连接 ws://localhost:8000/ws/market，支持订阅/退订、自动重连（指数退避）
 *
 * @param onQuote - 收到行情数据的回调
 * @param onAlert - 收到异动告警的回调
 * @param onIndex - 收到指数数据的回调
 * @param onSector - 收到板块数据的回调
 */
function useWebSocket(
  onQuote?: (quote: Quote) => void,
  onAlert?: (alert: Alert) => void,
  onIndex?: (index: { code: string; name: string; point: number; changePercent: number }) => void,
  onSector?: (sector: { name: string; amount: number; changePercent: number }) => void,
): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCountRef = useRef(0)
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const [quotes, setQuotes] = useState<Map<string, Quote>>(new Map())
  const [isConnected, setIsConnected] = useState(false)
  const maxReconnects = 10

  /** 获取重连延迟（指数退避） */
  const getReconnectDelay = useCallback((attempt: number): number => {
    // 1s, 2s, 4s, 8s, 16s, 32s ...  capped at 60s
    const delay = Math.min(1000 * Math.pow(2, attempt), 60000)
    return delay
  }, [])

  /** 建立 WebSocket 连接 */
  const connect = useCallback(() => {
    // 先关闭旧连接（防止 CONNECTING 状态下的泄漏）
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    // 重置重连计数器
    reconnectCountRef.current = 0

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/v1/ws/market`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      reconnectCountRef.current = 0
      setIsConnected(true)
    }

    ws.onclose = () => {
      setIsConnected(false)
      // 自动重连（指数退避）
      if (reconnectCountRef.current < maxReconnects) {
        const delay = getReconnectDelay(reconnectCountRef.current)
        reconnectTimerRef.current = setTimeout(() => {
          reconnectCountRef.current += 1
          connect()
        }, delay)
      }
    }

    ws.onerror = () => {
      ws.close()
    }

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg: WsMessage = JSON.parse(event.data)

        switch (msg.type) {
          case 'quote': {
            const q = msg.data as Quote
            setQuotes((prev) => {
              const next = new Map(prev)
              next.set(q.code, q)
              return next
            })
            onQuote?.(q)
            break
          }
          case 'alert': {
            const a = msg.data as Alert
            onAlert?.(a)
            break
          }
          case 'index': {
            const idx = msg.data as { code: string; name: string; point: number; changePercent: number }
            onIndex?.(idx)
            break
          }
          case 'sector': {
            const s = msg.data as { name: string; amount: number; changePercent: number }
            onSector?.(s)
            break
          }
          default:
            break
        }
      } catch {
        console.warn('WebSocket 消息解析失败')
      }
    }
  }, [getReconnectDelay, onQuote, onAlert, onIndex, onSector])

  /** 断开连接 */
  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimerRef.current)
    wsRef.current?.close()
    wsRef.current = null
    setIsConnected(false)
  }, [])

  /** 发送订阅消息 */
  const subscribe = useCallback((symbols: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'subscribe', symbols }),
      )
    }
  }, [])

  /** 发送退订消息 */
  const unsubscribe = useCallback((symbols: string[]) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: 'unsubscribe', symbols }),
      )
    }
  }, [])

  useEffect(() => {
    // 组件挂载时自动连接
    connect()
    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return { quotes, isConnected, subscribe, unsubscribe, connect, disconnect }
}

export default useWebSocket
