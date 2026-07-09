import { useState, useCallback } from 'react'
import { Typography, message } from 'antd'
import ReportList from './components/ReportList'
import ReportViewer from './components/ReportViewer'
import { getReportList, getReportDetail } from '../../services/api'
import type { ReportRow, ReportDetail } from './types'

/**
 * 复盘报告页面
 * 展示每日/每周的复盘分析报告，包含涨跌统计、板块轮动等
 * 支持在线阅读和 PDF 下载
 */
function Reports() {
  const [reports, setReports] = useState<ReportRow[]>([])
  const [loading, setLoading] = useState(false)
  const [viewerVisible, setViewerVisible] = useState(false)
  const [viewerDate, setViewerDate] = useState('')
  const [viewerContent, setViewerContent] = useState('')
  const [viewerLoading, setViewerLoading] = useState(false)
  const [initialized, setInitialized] = useState(false)

  /** 初始化加载报告列表 */
  const loadReports = useCallback(async () => {
    if (initialized) return
    setLoading(true)
    try {
      const data = await getReportList()
      setReports(data)
      setInitialized(true)
    } catch {
      message.error('加载报告列表失败')
    } finally {
      setLoading(false)
    }
  }, [initialized])

  /** 阅读报告 */
  const handleRead = useCallback(async (date: string) => {
    setViewerDate(date)
    setViewerLoading(true)
    setViewerVisible(true)
    setViewerContent('')
    try {
      const detail: ReportDetail = await getReportDetail(date)
      setViewerContent(detail.html_content || '')
    } catch {
      message.error('加载报告详情失败')
      setViewerContent('')
    } finally {
      setViewerLoading(false)
    }
  }, [])

  /** 下载报告 PDF */
  const handleDownload = useCallback((_date: string) => {
    // 通过构造链接直接触发下载
    const link = document.createElement('a')
    link.href = `/api/v1/reports/${_date}/pdf`
    link.download = `复盘报告-${_date}.pdf`
    link.click()
  }, [])

  /** 关闭查看器 */
  const handleCloseViewer = useCallback(() => {
    setViewerVisible(false)
    setViewerContent('')
  }, [])

  // 页面挂载时加载
  if (!initialized) {
    loadReports()
  }

  return (
    <div>
      <Typography.Title level={4}>复盘报告</Typography.Title>

      {/* 报告列表 */}
      <ReportList
        dataSource={reports}
        loading={loading}
        onRead={handleRead}
        onDownload={handleDownload}
      />

      {/* 报告查看器模态框 */}
      <ReportViewer
        date={viewerDate}
        htmlContent={viewerContent}
        visible={viewerVisible}
        loading={viewerLoading}
        onClose={handleCloseViewer}
      />
    </div>
  )
}

export default Reports
