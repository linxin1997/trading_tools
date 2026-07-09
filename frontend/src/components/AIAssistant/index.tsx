import { useState } from 'react'
import { FloatButton, Badge, Drawer } from 'antd'
import { RobotOutlined } from '@ant-design/icons'
import useAIChat from './hooks/useAIChat'
import ChatPanel from './components/ChatPanel'

/**
 * AI 助手浮窗组件
 * 右下角浮动按钮，点击展开对话面板，支持流式对话
 */
function AIAssistant() {
  const [open, setOpen] = useState(false)
  const [inputValue, setInputValue] = useState('')
  const { messages, loading, sendMessage, stop, clearMessages } = useAIChat()

  const handleSend = () => {
    if (!inputValue.trim() || loading) return
    sendMessage(inputValue.trim())
    setInputValue('')
  }

  return (
    <>
      <Badge count={messages.length} size="small" offset={[-4, 4]}>
        <FloatButton
          icon={<RobotOutlined />}
          type="primary"
          tooltip="AI 投资助手"
          onClick={() => setOpen(true)}
          style={{ right: 24, bottom: 24 }}
        />
      </Badge>
      <Drawer
        title="AI 投资助手"
        placement="right"
        width={380}
        open={open}
        onClose={() => setOpen(false)}
        styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
      >
        <ChatPanel
          messages={messages}
          loading={loading}
          inputValue={inputValue}
          onInputChange={setInputValue}
          onSend={handleSend}
          onStop={stop}
          onClear={clearMessages}
        />
      </Drawer>
    </>
  )
}

export default AIAssistant
