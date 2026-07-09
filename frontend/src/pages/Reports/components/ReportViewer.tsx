import { Modal, Spin, Typography } from 'antd'

const { Text } = Typography

/** 报告查看器属性 */
interface ReportViewerProps {
  /** 报告日期 */
  date: string
  /** HTML 内容 */
  htmlContent: string
  /** 是否可见 */
  visible: boolean
  /** 关闭回调 */
  onClose: () => void
  /** 加载状态 */
  loading?: boolean
}

/**
 * 报告查看器组件
 * 在 iframe 中渲染报告 HTML 内容
 */
function ReportViewer({ date, htmlContent, visible, onClose, loading = false }: ReportViewerProps) {
  /** 生成 iframe 的 srcdoc 内容 */
  const srcdoc = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 16px; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #e8e8e8; padding: 8px; text-align: left; }
        th { background: #fafafa; }
      </style>
    </head>
    <body>${htmlContent}</body>
    </html>
  `

  return (
    <Modal
      title={`复盘报告 - ${date}`}
      open={visible}
      onCancel={onClose}
      footer={null}
      width="90%"
      style={{ top: 20 }}
      destroyOnClose
    >
      <Spin spinning={loading}>
        {htmlContent ? (
          <iframe
            title={`报告-${date}`}
            srcDoc={srcdoc}
            style={{ width: '100%', height: '70vh', border: '1px solid #f0f0f0', borderRadius: 4 }}
          />
        ) : (
          !loading && <Text type="secondary">暂无报告内容</Text>
        )}
      </Spin>
    </Modal>
  )
}

export default ReportViewer
