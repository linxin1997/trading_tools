import { useRef, useEffect } from 'react'
import { Input, Button, Space, Typography } from 'antd'
import { SendOutlined, StopOutlined, ClearOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons'
import type { ChatMessage } from '../../../services/api'

const { TextArea } = Input

interface ChatPanelProps {
  messages: ChatMessage[]
  loading: boolean
  inputValue: string
  onInputChange: (val: string) => void
  onSend: () => void
  onStop: () => void
  onClear: () => void
}

/**
 * AI 对话面板组件
 * 展示消息列表和输入框，支持发送、中止和清空操作
 */
function ChatPanel({
  messages,
  loading,
  inputValue,
  onInputChange,
  onSend,
  onStop,
  onClear,
}: ChatPanelProps) {
  const listRef = useRef<HTMLDivElement>(null)

  /** 新消息时自动滚动到底部 */
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!loading && inputValue.trim()) onSend()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 消息列表 */}
      <div
        ref={listRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 12px',
          background: '#f5f5f5',
        }}
      >
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', color: '#999', marginTop: 60 }}>
            <RobotOutlined style={{ fontSize: 32, marginBottom: 8 }} />
            <Typography.Text type="secondary" style={{ display: 'block' }}>
              AI 投资助手已就绪，请输入您的问题
            </Typography.Text>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: 'flex',
              marginBottom: 12,
              justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
            }}
          >
            <div
              style={{
                maxWidth: '80%',
                padding: '8px 12px',
                borderRadius: 8,
                background: msg.role === 'user' ? '#1677ff' : '#fff',
                color: msg.role === 'user' ? '#fff' : '#333',
                fontSize: 13,
                lineHeight: 1.6,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
              }}
            >
              <div style={{ marginBottom: 4, fontSize: 12, opacity: 0.7 }}>
                {msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                <span style={{ marginLeft: 4 }}>{msg.role === 'user' ? '您' : 'AI'}</span>
              </div>
              {msg.content || (loading && <span style={{ opacity: 0.5 }}>思考中...</span>)}
            </div>
          </div>
        ))}
      </div>

      {/* 输入区域 */}
      <div style={{ padding: '8px 12px', borderTop: '1px solid #f0f0f0' }}>
        <TextArea
          value={inputValue}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入消息..."
          autoSize={{ minRows: 2, maxRows: 4 }}
          disabled={loading}
        />
        <Space style={{ marginTop: 8, justifyContent: 'flex-end', width: '100%' }}>
          <Button size="small" icon={<ClearOutlined />} onClick={onClear}>
            清空
          </Button>
          {loading ? (
            <Button size="small" icon={<StopOutlined />} danger onClick={onStop}>
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              size="small"
              icon={<SendOutlined />}
              onClick={onSend}
              disabled={!inputValue.trim()}
            >
              发送
            </Button>
          )}
        </Space>
      </div>
    </div>
  )
}

export default ChatPanel
