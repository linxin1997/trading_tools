import { useState, useCallback } from 'react'
import { Typography, Divider, message } from 'antd'
import ConditionBuilder from './components/ConditionBuilder'
import ResultTable from './components/ResultTable'
import ScoreChart from './components/ScoreChart'
import { screenStocks } from '../../services/api'
import type { ConditionGroup, ScreenResultItem } from './types'

/**
 * 选股器页面
 * 提供多维度条件筛选 A 股标的的工具
 * 组合条件构建器 + 评分结果 + 柱状图分布
 */
function StockPicker() {
  const [results, setResults] = useState<ScreenResultItem[]>([])
  const [screening, setScreening] = useState(false)

  /** 执行筛选回调 */
  const handleScreen = useCallback(
    async (groups: ConditionGroup[], weights: Record<string, number>, _compareMode: boolean) => {
      setScreening(true)
      try {
        const data = await screenStocks({
          groups,
          weights,
          compareMode: _compareMode,
        })
        setResults(data.items || [])
        if (data.items.length === 0) {
          message.info('未找到符合条件的标的')
        } else {
          message.success(`共找到 ${data.total} 个标的`)
        }
      } catch {
        message.error('筛选请求失败，请稍后重试')
      } finally {
        setScreening(false)
      }
    },
    [],
  )

  return (
    <div>
      <Typography.Title level={4}>选股器</Typography.Title>

      {/* 条件构建区域 */}
      <ConditionBuilder onScreen={handleScreen} loading={screening} />

      <Divider />

      {/* 结果区域 */}
      <Typography.Title level={5}>结果区域 (Top {results.length})</Typography.Title>
      <ResultTable dataSource={results} loading={screening} />
      <ScoreChart dataSource={results} />
    </div>
  )
}

export default StockPicker
