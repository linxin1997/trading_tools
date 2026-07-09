import { Layout, Typography } from 'antd'
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'

const { Header: AntHeader } = Layout

interface HeaderProps {
  collapsed: boolean
  onToggle: () => void
}

/**
 * 顶部导航栏组件
 * 包含侧边栏折叠/展开按钮和页面标题
 */
function Header({ collapsed, onToggle }: HeaderProps) {
  return (
    <AntHeader
      style={{
        padding: '0 24px',
        background: '#fff',
        display: 'flex',
        alignItems: 'center',
        borderBottom: '1px solid #f0f0f0',
      }}
    >
      {collapsed ? (
        <MenuUnfoldOutlined style={{ fontSize: 18, cursor: 'pointer' }} onClick={onToggle} />
      ) : (
        <MenuFoldOutlined style={{ fontSize: 18, cursor: 'pointer' }} onClick={onToggle} />
      )}
      <Typography.Text style={{ marginLeft: 16, fontSize: 16 }}>
        A股盯盘与复盘系统
      </Typography.Text>
    </AntHeader>
  )
}

export default Header
