import { useCallback, useEffect, useRef, useState } from 'react'
import { getAlerts, getRiskRules, updateRiskRule } from '../../../services/api'
import { useTTS } from '../../../hooks/useTTS'
import type { Alert, RiskRule } from '../../../services/api'

/**
 * 风控管理 Hook
 * 提供告警列表和规则配置的查询与更新，新告警到达时触发语音播报
 */
function useRisk() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [rules, setRules] = useState<RiskRule[]>([])
  const [loading, setLoading] = useState(false)
  const { speak } = useTTS()

  /** 记录上一次告警 ID 集合，用于识别新告警 */
  const prevAlertIdsRef = useRef<Set<number>>(new Set())

  /** 获取告警列表，新告警触发语音播报 */
  const fetchAlerts = useCallback(async () => {
    try {
      const data = await getAlerts()
      // 检测新告警并播报
      const currentIds = new Set(data.map((a) => a.id))
      const prevIds = prevAlertIdsRef.current
      for (const alert of data) {
        if (!prevIds.has(alert.id)) {
          speak(alert.message)
        }
      }
      prevAlertIdsRef.current = currentIds
      setAlerts(data)
    } catch {
      // 无告警数据时不处理
    }
  }, [speak])

  /** 获取规则列表 */
  const fetchRules = useCallback(async () => {
    try {
      const data = await getRiskRules()
      setRules(data)
    } catch {
      // 无规则数据时不处理
    }
  }, [])

  /** 更新单条规则 */
  const saveRule = useCallback(
    async (id: string, data: Partial<RiskRule>) => {
      await updateRiskRule(id, data)
      await fetchRules()
    },
    [fetchRules],
  )

  useEffect(() => {
    setLoading(true)
    Promise.all([fetchAlerts(), fetchRules()]).finally(() => setLoading(false))
  }, [fetchAlerts, fetchRules])

  return { alerts, rules, loading, saveRule, refresh: () => { fetchAlerts(); fetchRules() } }
}

export default useRisk
