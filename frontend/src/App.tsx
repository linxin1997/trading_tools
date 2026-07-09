import React from 'react'
import { Routes, Route } from 'react-router-dom'
import MainLayout from './layouts/MainLayout'
import Dashboard from './pages/Dashboard'
import StockPicker from './pages/StockPicker'
import Reports from './pages/Reports'
import Risk from './pages/Risk'
import Portfolio from './pages/Portfolio'
import Backtest from './pages/Backtest'
import News from './pages/News'
import NotFound from './pages/NotFound'
import AIAssistant from './components/AIAssistant'

/**
 * 错误边界组件
 * 捕获子组件渲染异常，展示友好提示并允许刷新恢复
 */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return <div style={{ padding: 40, textAlign: 'center' }}>
        <h1>页面出错</h1>
        <p>{this.state.error?.message}</p>
        <button onClick={() => window.location.reload()}>刷新页面</button>
      </div>
    }
    return this.props.children
  }
}

/**
 * 根路由组件
 * 配置所有前端路由映射，并挂载全局级组件（AI 助手浮窗）
 * 外层包裹 ErrorBoundary 以捕获渲染异常
 */
function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route element={<MainLayout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/stock-picker" element={<StockPicker />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/risk" element={<Risk />} />
          <Route path="/portfolio" element={<Portfolio />} />
          <Route path="/backtest" element={<Backtest />} />
          <Route path="/news" element={<News />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <AIAssistant />
    </ErrorBoundary>
  )
}

export default App
