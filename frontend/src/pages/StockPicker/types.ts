/** A 股涨跌颜色配置 */
export const COLORS = {
  up: '#f5222d',
  down: '#52c41a',
  flat: '#d9d9d9',
}

/** 选股因子定义 */
export interface Factor {
  key: string
  label: string
  type: 'number' | 'boolean' | 'enum'
  options?: { label: string; value: string | number }[]
}

/** 条件运算符 */
export type Operator = 'equals' | 'notEquals' | 'greaterThan' | 'lessThan' | 'gte' | 'lte' | 'between'

/** 运算符中文映射 */
export const OPERATOR_LABELS: Record<Operator, string> = {
  equals: '等于',
  notEquals: '不等于',
  greaterThan: '大于',
  lessThan: '小于',
  gte: '大于等于',
  lte: '小于等于',
  between: '介于',
}

/** 单条筛选条件 */
export interface Condition {
  id: string
  factorKey: string
  operator: Operator
  value: string | number | boolean
  valueEnd?: string | number
}

/** 条件逻辑组 */
export interface ConditionGroup {
  id: string
  logic: 'AND' | 'OR'
  conditions: Condition[]
}

/** 选股请求参数 */
export interface ScreenRequest {
  groups: ConditionGroup[]
  weights: Record<string, number>
  compareMode: boolean
}

/** 选股结果条目 */
export interface ScreenResultItem {
  code: string
  name: string
  score: number
  maStatus: string
  macdSignal: string
  factors: Record<string, string | number | boolean>
}

/** 选股结果 */
export interface ScreenResult {
  items: ScreenResultItem[]
  total: number
}

/** 获取评分对应颜色 */
export function getScoreColor(score: number): string {
  if (score >= 80) return COLORS.up
  if (score >= 60) return '#fa8c16'
  if (score >= 40) return '#d9d9d9'
  return COLORS.down
}
