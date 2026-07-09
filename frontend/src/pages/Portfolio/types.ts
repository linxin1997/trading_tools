import type { Position, PnlSummary } from '../../services/api'

/** 持仓分组 */
export interface PortfolioGroup {
  name: string
  positions: Position[]
  pnl: number
  pnlPercent: number
}

export type { Position, PnlSummary }
