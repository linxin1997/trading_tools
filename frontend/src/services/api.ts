import axios from 'axios'
import type { Quote } from '../hooks/useWebSocket'
import type { Index, Sector } from '../stores/useMarketStore'

/**
 * Axios 实例
 * 配置基础 URL 和通用请求拦截器，统一管理 API 请求
 */
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

/** 请求拦截器：附加通用参数 */
api.interceptors.request.use(
  (config) => {
    // 个人工具，无需鉴权
    return config
  },
  (error) => Promise.reject(error),
)

/** 响应拦截器：统一处理错误 */
api.interceptors.response.use(
  (response) => {
    // 业务码校验：非 0 时按错误处理
    if (response.data?.code !== undefined && response.data.code !== 0) {
      return Promise.reject(new Error(response.data.message || '请求失败'))
    }
    return response.data
  },
  (error) => {
    const message = error.response?.data?.message || error.message || '网络错误'
    console.error('API 请求失败:', message)
    return Promise.reject(error)
  },
)

/** API 响应格式 */
interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

/**
 * 获取大盘指数行情
 * @returns 指数列表
 */
export async function getIndices(): Promise<Index[]> {
  const res = await api.get<unknown, ApiResponse<Index[]>>('/market/indices')
  return res.data
}

/**
 * 获取涨幅榜
 * @param topN - 返回前 N 只，默认 10
 * @returns 涨幅榜股票列表
 */
export async function getTopGainers(topN = 10): Promise<Quote[]> {
  const res = await api.get<unknown, ApiResponse<Quote[]>>('/market/top-gainers', {
    params: { topN },
  })
  return res.data
}

/**
 * 获取板块数据
 * @returns 板块列表
 */
export async function getSectors(): Promise<Sector[]> {
  const res = await api.get<unknown, ApiResponse<Sector[]>>('/market/sectors')
  return res.data
}

// =============================================
// 选股器类型定义
// =============================================

/** 选股因子 */
export interface Factor {
  key: string
  label: string
  type: 'number' | 'boolean' | 'enum'
  options?: { label: string; value: string | number }[]
}

/** 选股请求参数 */
export interface ScreenRequest {
  groups: {
    id: string
    logic: 'AND' | 'OR'
    conditions: {
      id: string
      factorKey: string
      operator: string
      value: string | number | boolean
      valueEnd?: string | number
    }[]
  }[]
  weights: Record<string, number>
  compareMode: boolean
}

/** 选股结果 */
export interface ScreenResult {
  items: {
    code: string
    name: string
    score: number
    maStatus: string
    macdSignal: string
    factors: Record<string, string | number | boolean>
  }[]
  total: number
}

// =============================================
// 报告类型定义
// =============================================

/** 报告列表（含引申字段） */
export interface ReportRow {
  date: string
  summary: string
  pdf_url: string
  marketChange: number
  limitUpCount: number
  northFlow: number
}

/** 报告详情 */
export interface ReportDetail {
  date: string
  html_content: string
  summary: string
}

// =============================================
// 选股器 API
// =============================================

/**
 * 获取选股因子列表
 * @returns 因子列表
 */
export async function getFactors(): Promise<Factor[]> {
  const res = await api.get<unknown, ApiResponse<Factor[]>>('/v1/factors')
  return res.data
}

/**
 * 执行选股筛选
 * @param params - 筛选条件参数
 * @returns 筛选结果
 */
export async function screenStocks(params: ScreenRequest): Promise<ScreenResult> {
  const res = await api.post<unknown, ApiResponse<ScreenResult>>('/v1/stock-picker/screen', params)
  return res.data
}

// =============================================
// 报告 API
// =============================================

/**
 * 获取报告列表
 * @returns 报告列表，按日期倒序
 */
export async function getReportList(): Promise<ReportRow[]> {
  const res = await api.get<unknown, ApiResponse<ReportRow[]>>('/v1/reports')
  return res.data
}

/**
 * 获取指定日期的报告详情
 * @param date - 报告日期，格式 YYYY-MM-DD
 * @returns 报告详情
 */
export async function getReportDetail(date: string): Promise<ReportDetail> {
  const res = await api.get<unknown, ApiResponse<ReportDetail>>(`/v1/reports/${encodeURIComponent(date)}`)
  return res.data
}

// =============================================
// 新闻 API
// =============================================

/** 新闻条目（source 使用宽松 string 类型，消费端可按需 cast） */
export interface NewsItem {
  id: number
  source: string
  title: string
  content: string
  url: string
  publish_time: string
  sentiment_label: 'positive' | 'negative' | 'neutral'
  sentiment_score: number
  related_stocks: string[]
}

/** 新闻流请求参数 */
export interface NewsStreamParams {
  sources?: string[]
  sentiments?: string[]
  stock_code?: string
  cursor?: string
  limit?: number
}

/**
 * 获取新闻流数据
 * @param params - 筛选与分页参数
 * @returns 新闻列表，按发布时间倒序
 */
export async function getNewsStream(params?: NewsStreamParams): Promise<NewsItem[]> {
  const res = await api.get<unknown, ApiResponse<NewsItem[]>>('/v1/news/stream', {
    params,
  })
  return res.data
}

/**
 * 获取新闻详情
 * @param id - 新闻 ID
 * @returns 新闻完整信息
 */
export async function getNewsDetail(id: number): Promise<NewsItem> {
  const res = await api.get<unknown, ApiResponse<NewsItem>>(`/v1/news/${id}`)
  return res.data
}

// =============================================
// 持仓管理 API
// =============================================

/** 持仓记录 */
export interface Position {
  id: number
  code: string
  name: string
  cost_price: number
  current_price: number
  shares: number
  group_id: number
}

/** 盈亏汇总 */
export interface PnlSummary {
  total_market_value: number
  total_pnl: number
  today_pnl: number
}

/** 新增持仓请求 */
export interface PositionInput {
  code: string
  name: string
  cost_price: number
  shares: number
  group_id?: number
}

/**
 * 获取持仓列表
 * @returns 持仓列表
 */
export async function getPositions(): Promise<Position[]> {
  const res = await api.get<unknown, ApiResponse<Position[]>>('/v1/portfolio')
  return res.data
}

/**
 * 新增持仓
 * @param data - 持仓数据
 * @returns 新增的持仓记录
 */
export async function createPosition(data: PositionInput): Promise<Position> {
  const res = await api.post<unknown, ApiResponse<Position>>('/v1/portfolio', data)
  return res.data
}

/**
 * 更新持仓
 * @param id - 持仓 ID
 * @param data - 更新的持仓数据
 * @returns 更新后的持仓记录
 */
export async function updatePosition(id: number, data: Partial<PositionInput>): Promise<Position> {
  const res = await api.put<unknown, ApiResponse<Position>>(`/v1/portfolio/${id}`, data)
  return res.data
}

/**
 * 删除持仓
 * @param id - 持仓 ID
 */
export async function deletePosition(id: number): Promise<void> {
  await api.delete<unknown, ApiResponse<void>>(`/v1/portfolio/${id}`)
}

/**
 * 获取持仓盈亏汇总
 * @returns 盈亏汇总数据
 */
export async function getPnlSummary(): Promise<PnlSummary> {
  const res = await api.get<unknown, ApiResponse<PnlSummary>>('/v1/portfolio/pnl')
  return res.data
}

// =============================================
// 风控 API
// =============================================

/** 风控告警记录 */
export interface Alert {
  id: number
  time: string
  stock_code: string
  stock_name: string
  rule_name: string
  message: string
  level: 'critical' | 'warning' | 'info'
}

/** 风控规则 */
export interface RiskRule {
  id: string
  name: string
  type: string
  enabled: boolean
  params: Record<string, number | string | boolean>
}

/**
 * 获取告警列表
 * @returns 告警列表
 */
export async function getAlerts(): Promise<Alert[]> {
  const res = await api.get<unknown, ApiResponse<Alert[]>>('/v1/risk/alerts')
  return res.data
}

/**
 * 获取风控规则列表
 * @returns 规则列表
 */
export async function getRiskRules(): Promise<RiskRule[]> {
  const res = await api.get<unknown, ApiResponse<RiskRule[]>>('/v1/risk/rules')
  return res.data
}

/**
 * 更新风控规则
 * @param id - 规则 ID
 * @param data - 更新的规则数据
 * @returns 更新后的规则
 */
export async function updateRiskRule(id: string, data: Partial<RiskRule>): Promise<RiskRule> {
  const res = await api.put<unknown, ApiResponse<RiskRule>>(`/v1/risk/rules/${id}`, data)
  return res.data
}

// =============================================
// 策略回测 API
// =============================================

/** 回测请求参数 */
export interface BacktestRequest {
  strategy_id?: string
  conditions: Record<string, unknown>[]
  start_date: string
  end_date: string
  rebalance_freq: 'daily' | 'weekly' | 'monthly'
}

/** 回测结果 */
export interface BacktestResult {
  total_return: number
  annual_return: number
  sharpe_ratio: number
  max_drawdown: number
  nav: { date: string; strategy: number; benchmark: number }[]
  monthly_returns: { month: string; value: number }[]
}

/** 策略预设 */
export interface StrategyPreset {
  id: string
  name: string
  description: string
}

/**
 * 执行策略回测
 * @param params - 回测请求参数
 * @returns 回测结果
 */
export async function runBacktest(params: BacktestRequest): Promise<BacktestResult> {
  const res = await api.post<unknown, ApiResponse<BacktestResult>>('/v1/backtest', params)
  return res.data
}

/**
 * 获取策略预设列表
 * @returns 策略预设列表
 */
export async function getStrategies(): Promise<StrategyPreset[]> {
  const res = await api.get<unknown, ApiResponse<StrategyPreset[]>>('/v1/backtest/strategies')
  return res.data
}

// =============================================
// AI 助手 API
// =============================================

/** AI 聊天消息 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

/**
 * 发送 AI 聊天消息（SSE 流式）
 * @param messages - 历史消息列表
 * @param onMessage - 每收到一段文本的回调
 * @param onDone - 流结束回调
 * @returns 中止函数
 */
export function sendChatMessage(
  messages: ChatMessage[],
  onMessage: (text: string) => void,
  onDone: () => void,
): () => void {
  const controller = new AbortController()
  // 30 秒超时
  const timeoutId = setTimeout(() => {
    controller.abort()
    onDone()
  }, 30000)

  fetch('/api/v1/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
    signal: controller.signal,
  })
    .then(async (response) => {
      clearTimeout(timeoutId)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const reader = response.body?.getReader()
      if (!reader) {
        onDone()
        return
      }
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue
            try {
              const parsed = JSON.parse(data)
              onMessage(parsed.text || '')
            } catch {
              onMessage(data)
            }
          }
        }
      }
      onDone()
    })
    .catch((error) => {
      if (error.name !== 'AbortError') {
        console.error('AI 聊天请求失败:', error)
        onDone()
      }
    })

  return () => controller.abort()
}

// =============================================
// K 线数据 API
// =============================================

/** K 线数据条目 */
export interface KLineData {
  /** 时间戳（毫秒） */
  timestamp: number
  /** 开盘价 */
  open: number
  /** 最高价 */
  high: number
  /** 最低价 */
  low: number
  /** 收盘价 */
  close: number
  /** 成交量 */
  volume: number
  /** 成交额 */
  turnover?: number
}

/**
 * 获取 K 线数据
 * @param symbol - 股票代码
 * @param period - K 线周期，默认 1d
 * @returns K 线数据列表
 */
export async function getKLine(symbol: string, period = '1d'): Promise<KLineData[]> {
  const res = await api.get<unknown, ApiResponse<KLineData[]>>('/v1/kline', {
    params: { symbol, period },
  })
  return res.data
}

export default api
