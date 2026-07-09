import { useCallback, useEffect, useState } from 'react'
import { runBacktest, getStrategies } from '../../../services/api'
import type { BacktestRequest, BacktestResult, StrategyPreset } from '../../../services/api'

/**
 * 策略回测 Hook
 * 管理回测请求提交、结果展示和策略预设列表
 */
function useBacktest() {
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [strategies, setStrategies] = useState<StrategyPreset[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /** 获取策略预设列表 */
  const fetchStrategies = useCallback(async () => {
    try {
      const data = await getStrategies()
      setStrategies(data)
    } catch {
      // 无预设策略时不处理
    }
  }, [])

  /** 提交回测请求 */
  const submitBacktest = useCallback(async (params: BacktestRequest) => {
    setRunning(true)
    setResult(null)
    setError(null)
    try {
      const data = await runBacktest(params)
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '回测执行失败')
    } finally {
      setRunning(false)
    }
  }, [])

  useEffect(() => {
    fetchStrategies()
  }, [fetchStrategies])

  return { result, strategies, running, error, submitBacktest }
}

export default useBacktest
