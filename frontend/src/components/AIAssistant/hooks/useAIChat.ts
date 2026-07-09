import { useCallback, useEffect, useRef, useState } from 'react'
import { sendChatMessage } from '../../../services/api'
import type { ChatMessage } from '../../../services/api'

/**
 * AI 聊天流式管理 Hook
 * 支持 SSE 流式消息接收、打字机效果和请求中止
 */
function useAIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const abortRef = useRef<() => void>()

  /** 发送消息并接收流式回复 */
  const sendMessage = useCallback(async (content: string) => {
    // 中止上一次未完成的请求
    abortRef.current?.()

    const userMsg: ChatMessage = { role: 'user', content }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    const assistantMsg: ChatMessage = { role: 'assistant', content: '' }

    const abort = sendChatMessage(
      [...messages, userMsg],
      (text) => {
        assistantMsg.content += text
        setMessages((prev) => {
          const next = [...prev]
          if (next[next.length - 1]?.role === 'assistant') {
            next[next.length - 1] = { ...assistantMsg }
          } else {
            next.push({ ...assistantMsg })
          }
          return next
        })
      },
      () => {
        setLoading(false)
      },
    )

    abortRef.current = abort
  }, [messages])

  /** 中止当前请求 */
  const stop = useCallback(() => {
    abortRef.current?.()
    setLoading(false)
  }, [])

  /** 清空对话 */
  const clearMessages = useCallback(() => {
    abortRef.current?.()
    setMessages([])
    setLoading(false)
  }, [])

  // 组件卸载时中止未完成的请求
  useEffect(() => {
    return () => {
      abortRef.current?.()
    }
  }, [])

  return { messages, loading, sendMessage, stop, clearMessages }
}

export default useAIChat
