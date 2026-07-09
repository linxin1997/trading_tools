import { create } from 'zustand'
import type { Quote, Alert } from '../hooks/useWebSocket'

/** 指数数据 */
export interface Index {
  code: string
  name: string
  point: number
  changePercent: number
}

/** 板块数据 */
export interface Sector {
  name: string
  amount: number
  changePercent: number
}

/** 市场行情状态 */
interface MarketState {
  /** 实时行情映射，key 为股票代码 */
  quotes: Map<string, Quote>
  /** 大盘指数列表 */
  indices: Index[]
  /** 申万一级行业板块数据 */
  sectors: Sector[]
  /** 涨幅榜前 10 */
  topGainers: Quote[]
  /** 自选股代码列表 */
  watchlist: string[]
  /** 异动告警列表 */
  alerts: Alert[]
  /** 连接状态 */
  isConnected: boolean

  /** 设置行情数据 */
  setQuotes: (quotes: Map<string, Quote>) => void
  /** 更新单只行情 */
  updateQuote: (quote: Quote) => void
  /** 设置指数数据 */
  setIndices: (indices: Index[]) => void
  /** 更新单条指数 */
  updateIndex: (index: Index) => void
  /** 设置板块数据 */
  setSectors: (sectors: Sector[]) => void
  /** 添加板块数据 */
  addSector: (sector: Sector) => void
  /** 设置涨幅榜 */
  setTopGainers: (gainers: Quote[]) => void
  /** 设置自选股列表 */
  setWatchlist: (watchlist: string[]) => void
  /** 添加自选股 */
  addToWatchlist: (code: string) => void
  /** 移除自选股 */
  removeFromWatchlist: (code: string) => void
  /** 添加异动告警 */
  addAlert: (alert: Alert) => void
  /** 设置连接状态 */
  setConnected: (connected: boolean) => void
}

/**
 * 市场行情状态管理 Store
 * 管理实时行情、大盘指数、板块数据、涨幅榜、自选股、异动告警等市场核心数据
 */
const useMarketStore = create<MarketState>((set) => ({
  quotes: new Map(),
  indices: [],
  sectors: [],
  topGainers: [],
  watchlist: ['000001.SZ', '600519.SH', '000333.SZ', '601318.SH', '600036.SH'],
  alerts: [],
  isConnected: false,

  setQuotes: (quotes) => set({ quotes }),
  updateQuote: (quote) =>
    set((state) => {
      const next = new Map(state.quotes)
      next.set(quote.code, quote)
      return { quotes: next }
    }),
  setIndices: (indices) => set({ indices }),
  updateIndex: (index) =>
    set((state) => ({
      indices: state.indices.map((i) => (i.code === index.code ? index : i)),
    })),
  setSectors: (sectors) => set({ sectors }),
  addSector: (sector) =>
    set((state) => {
      const exists = state.sectors.findIndex((s) => s.name === sector.name)
      if (exists >= 0) {
        const next = [...state.sectors]
        next[exists] = sector
        return { sectors: next }
      }
      return { sectors: [...state.sectors, sector] }
    }),
  setTopGainers: (gainers) => set({ topGainers: gainers }),
  setWatchlist: (watchlist) => set({ watchlist }),
  addToWatchlist: (code) =>
    set((state) => {
      if (state.watchlist.includes(code)) return state
      return { watchlist: [...state.watchlist, code] }
    }),
  removeFromWatchlist: (code) =>
    set((state) => ({
      watchlist: state.watchlist.filter((c) => c !== code),
    })),
  addAlert: (alert) =>
    set((state) => ({
      alerts: [alert, ...state.alerts].slice(0, 50), // 最多保留 50 条
    })),
  setConnected: (connected) => set({ isConnected: connected }),
}))

export default useMarketStore
