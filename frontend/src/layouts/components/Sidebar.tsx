import { useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  StockOutlined,
  FileTextOutlined,
  SafetyOutlined,
  WalletOutlined,
  ExperimentOutlined,
  BulbOutlined,
} from '@ant-design/icons'

const { Sider } = Layout

/** 侧边栏菜单项配置 */
const menuItems = [
  { key: '/', icon: <DashboardOutlined />, label: '盯盘仪表盘' },
  { key: '/stock-picker', icon: <StockOutlined />, label: '选股器' },
  { key: '/reports', icon: <FileTextOutlined />, label: '复盘报告' },
  { key: '/risk', icon: <SafetyOutlined />, label: '风控监控' },
  { key: '/portfolio', icon: <WalletOutlined />, label: '持仓管理' },
  { key: '/backtest', icon: <ExperimentOutlined />, label: '策略回测' },
  { key: '/news', icon: <BulbOutlined />, label: '舆情新闻' },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

/**
 * 侧边栏导航组件
 * 包含所有功能页面的路由跳转菜单
 */
function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <Sider
      collapsible
      collapsed={collapsed}
      onCollapse={onToggle}
      breakpoint="lg"
      style={{ overflow: 'auto', height: '100vh', position: 'sticky', top: 0, left: 0 }}
    >
      <div
        style={{
          height: 32,
          margin: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          fontWeight: 'bold',
          fontSize: collapsed ? 14 : 18,
          whiteSpace: 'nowrap',
        }}
      >
        {collapsed ? '盯盘' : 'A股盯盘与复盘'}
      </div>
      <Menu
        theme="dark"
        mode="inline"
        selectedKeys={[location.pathname === '/stock-picker' ? '/stock-picker' : location.pathname]}
        items={menuItems}
        onClick={({ key }) => navigate(key)}
      />
    </Sider>
  )
}

export default Sidebar
