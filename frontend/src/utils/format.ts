/**
 * 格式化股票代码
 * @param code - 原始股票代码，如 '000001.SH'
 * @returns 格式化后的代码，如 '000001'
 */
export function formatStockCode(code: string): string {
  return code.replace(/\.(SH|SZ|BJ)$/, '')
}

/**
 * 格式化涨跌幅显示
 * @param value - 涨跌幅数值
 * @returns 格式化字符串，如 '+2.50%'
 */
export function formatChangePercent(value: number): string {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

/**
 * 格式化金额（元）
 * @param value - 金额数值
 * @returns 格式化字符串，如 '1.23亿'
 */
export function formatAmount(value: number): string {
  if (value >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`
  }
  if (value >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`
  }
  return value.toFixed(2)
}

/**
 * 格式化成交量
 * @param value - 成交量数值
 * @returns 格式化字符串，如 '1.23万手'
 */
export function formatVolume(value: number): string {
  if (value >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万手`
  }
  return `${value.toFixed(0)}手`
}

/**
 * 格式化时间戳为时间字符串
 * @param timestamp - 时间戳（毫秒）
 * @returns 格式化字符串，如 '14:30:00'
 */
export function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}
