import { useState } from 'react'
import { Typography, Button, Space } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import usePortfolio from './hooks/usePortfolio'
import PortfolioTable from './components/PortfolioTable'
import AddPositionModal from './components/AddPositionModal'
import PnlSummaryCard from './components/PnlSummary'
import type { Position, PositionInput } from '../../services/api'

/**
 * 持仓管理页面
 * 组合盈亏汇总、持仓表格、添加弹窗，管理投资组合
 */
function PortfolioPage() {
  const { positions, pnl, loading, addPosition, editPosition, removePosition } = usePortfolio()
  const [modalOpen, setModalOpen] = useState(false)
  const [editRecord, setEditRecord] = useState<Position | null>(null)

  const handleAdd = () => {
    setEditRecord(null)
    setModalOpen(true)
  }

  /** 打开编辑弹窗 */
  const handleEdit = (record: Position) => {
    setEditRecord(record)
    setModalOpen(true)
  }

  /** 提交新增/修改 */
  const handleModalOk = async (values: PositionInput) => {
    if (editRecord) {
      await editPosition(editRecord.id, values)
    } else {
      await addPosition(values)
    }
    setModalOpen(false)
    setEditRecord(null)
  }

  /** 删除持仓 */
  const handleDelete = (id: number) => {
    removePosition(id)
  }

  return (
    <div>
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', width: '100%' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>持仓管理</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加持仓
        </Button>
      </Space>
      <PnlSummaryCard data={pnl} />
      <PortfolioTable
        positions={positions}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />
      <AddPositionModal
        open={modalOpen}
        editRecord={editRecord}
        onOk={handleModalOk}
        onCancel={() => { setModalOpen(false); setEditRecord(null) }}
      />
    </div>
  )
}

export default PortfolioPage
