import { useCallback, useEffect, useState } from 'react'
import {
  getPositions,
  createPosition,
  updatePosition,
  deletePosition,
  getPnlSummary,
} from '../../../services/api'
import type { Position, PnlSummary, PositionInput } from '../../../services/api'

/**
 * 持仓管理 Hook
 * 提供持仓列表的 CRUD 操作和盈亏汇总查询
 */
function usePortfolio() {
  const [positions, setPositions] = useState<Position[]>([])
  const [pnl, setPnl] = useState<PnlSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  /** 获取持仓列表 */
  const fetchPositions = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getPositions()
      setPositions(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '获取持仓列表失败')
    } finally {
      setLoading(false)
    }
  }, [])

  /** 获取盈亏汇总 */
  const fetchPnl = useCallback(async () => {
    try {
      const data = await getPnlSummary()
      setPnl(data)
    } catch {
      // 无汇总数据时不处理
    }
  }, [])

  /** 新增持仓 */
  const addPosition = useCallback(
    async (input: PositionInput) => {
      try {
        await createPosition(input)
      } catch {
        // 静默失败
      }
      await fetchPositions()
      await fetchPnl()
    },
    [fetchPositions, fetchPnl],
  )

  /** 更新持仓 */
  const editPosition = useCallback(
    async (id: number, input: Partial<PositionInput>) => {
      try {
        await updatePosition(id, input)
      } catch {
        // 静默失败
      }
      await fetchPositions()
      await fetchPnl()
    },
    [fetchPositions, fetchPnl],
  )

  /** 删除持仓 */
  const removePosition = useCallback(
    async (id: number) => {
      try {
        await deletePosition(id)
      } catch {
        // 静默失败
      }
      await fetchPositions()
      await fetchPnl()
    },
    [fetchPositions, fetchPnl],
  )

  useEffect(() => {
    fetchPositions()
    fetchPnl()
  }, [fetchPositions, fetchPnl])

  return {
    positions,
    pnl,
    loading,
    error,
    addPosition,
    editPosition,
    removePosition,
    refresh: () => {
      fetchPositions()
      fetchPnl()
    },
  }
}

export default usePortfolio
