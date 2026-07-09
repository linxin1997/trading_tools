import { useEffect } from 'react'
import { Form, Input, InputNumber, Modal } from 'antd'
import type { PositionInput, Position } from '../../../services/api'

interface AddPositionModalProps {
  open: boolean
  editRecord: Position | null
  onOk: (values: PositionInput) => void
  onCancel: () => void
}

/**
 * 添加/编辑持仓弹窗
 */
function AddPositionModal({ open, editRecord, onOk, onCancel }: AddPositionModalProps) {
  const [form] = Form.useForm()

  useEffect(() => {
    if (open) {
      if (editRecord) {
        form.setFieldsValue({
          code: editRecord.code,
          name: editRecord.name,
          cost_price: editRecord.cost_price,
          shares: editRecord.shares,
          group_id: editRecord.group_id,
        })
      } else {
        form.resetFields()
      }
    }
  }, [open, editRecord, form])

  const handleOk = async () => {
    const values = await form.validateFields()
    onOk(values)
  }



  return (
    <Modal
      title={editRecord ? '修改持仓' : '添加持仓'}
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{ group_id: undefined }}>
        <Form.Item label="股票代码" name="code" rules={[{ required: true, message: '请输入股票代码' }]}>
          <Input placeholder="如 000001" />
        </Form.Item>
        <Form.Item label="股票名称" name="name" rules={[{ required: true, message: '请输入股票名称' }]}>
          <Input placeholder="如 平安银行" />
        </Form.Item>
        <Form.Item
          label="成本价"
          name="cost_price"
          rules={[{ required: true, message: '请输入成本价' }]}
        >
          <InputNumber style={{ width: '100%' }} min={0} precision={2} placeholder="10.50" />
        </Form.Item>
        <Form.Item
          label="持股数"
          name="shares"
          rules={[{ required: true, message: '请输入持股数' }]}
        >
          <InputNumber style={{ width: '100%' }} min={1} precision={0} placeholder="1000" />
        </Form.Item>
        <Form.Item label="分组 ID" name="group_id">
          <InputNumber style={{ width: '100%' }} min={1} precision={0} placeholder="可选" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default AddPositionModal
