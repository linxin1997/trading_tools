import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Layout, theme } from 'antd'
import Sidebar from './components/Sidebar'
import Header from './components/Header'

const { Content } = Layout

/**
 * 主布局组件
 * 使用 Ant Design Layout 实现侧边栏 + 内容区的经典布局结构
 * 侧边栏可折叠，包含路由导航菜单
 */
function MainLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const { token } = theme.useToken()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <Layout>
        <Header collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
        <Content
          style={{
            margin: 16,
            padding: 24,
            background: token.colorBgContainer,
            borderRadius: token.borderRadiusLG,
            minHeight: 280,
          }}
        >
          {/*
           * Outlet 渲染当前路由匹配的子页面组件
           */}
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
