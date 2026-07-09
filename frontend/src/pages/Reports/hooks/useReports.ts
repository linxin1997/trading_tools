import { useState, useEffect, useCallback } from 'react'
import { getReportList, getReportDetail } from '../../../services/api'
import type { ReportRow, ReportDetail } from '../types'

/**
 * 复盘报告数据 Hook
 * 管理报告列表和报告详情的加载状态
 */
export function useReports() {
  const [reports, setReports] = useState<ReportRow[]>([])
  const [loading, setLoading] = useState(false)
  const [currentReport, setCurrentReport] = useState<ReportDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  /** 加载报告列表 */
  const fetchReports = useCallback(async (abortSignal?: AbortSignal) => {
    setLoading(true)
    try {
      const data = await getReportList()
      if (abortSignal?.aborted) return
      setReports(data)
    } catch {
      // 静默失败，保持旧数据
    } finally {
      setLoading(false)
    }
  }, [])

  /** 加载指定日期的报告详情 */
  const fetchDetail = useCallback(async (date: string, abortSignal?: AbortSignal) => {
    setDetailLoading(true)
    try {
      const data = await getReportDetail(date)
      if (abortSignal?.aborted) return
      setCurrentReport(data)
    } catch {
      // 静默失败
    } finally {
      setDetailLoading(false)
    }
  }, [])

  /** 清除当前报告详情 */
  const clearDetail = useCallback(() => {
    setCurrentReport(null)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    fetchReports(controller.signal)
    return () => controller.abort()
  }, [fetchReports])

  return { reports, loading, currentReport, detailLoading, fetchDetail, fetchReports, clearDetail }
}
