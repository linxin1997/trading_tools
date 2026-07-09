/** 报告概要 */
export interface ReportSummary {
  date: string
  summary: string
  pdf_url: string
}

/** 报告详情 */
export interface ReportDetail {
  date: string
  html_content: string
  summary: string
}

/** 报告列表行（含引申字段） */
export interface ReportRow {
  date: string
  summary: string
  pdf_url: string
  marketChange: number
  limitUpCount: number
  northFlow: number
}
