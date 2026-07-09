import { create } from 'zustand'

/** 用户设置 */
interface UserSettings {
  /** 自选股代码列表 */
  watchlistCodes: string[]
  /** 刷新间隔（秒） */
  refreshInterval: number
  /** 是否开启声音提醒 */
  soundAlert: boolean
}

/** 用户状态 */
interface UserState {
  /** 用户设置 */
  settings: UserSettings
  /** 更新设置 */
  updateSettings: (partial: Partial<UserSettings>) => void
  /** 添加自选股 */
  addWatchlistCode: (code: string) => void
  /** 移除自选股 */
  removeWatchlistCode: (code: string) => void
}

/** 默认用户设置 */
const defaultSettings: UserSettings = {
  watchlistCodes: ['000001.SH', '399001.SZ', '399006.SZ'],
  refreshInterval: 3,
  soundAlert: false,
}

/**
 * 用户状态管理
 * 管理用户设置、自选股配置等个人偏好
 */
const useUserStore = create<UserState>((set) => ({
  settings: defaultSettings,
  updateSettings: (partial) =>
    set((state) => ({ settings: { ...state.settings, ...partial } })),
  addWatchlistCode: (code) =>
    set((state) => {
      if (state.settings.watchlistCodes.includes(code)) return state
      return {
        settings: {
          ...state.settings,
          watchlistCodes: [...state.settings.watchlistCodes, code],
        },
      }
    }),
  removeWatchlistCode: (code) =>
    set((state) => ({
      settings: {
        ...state.settings,
        watchlistCodes: state.settings.watchlistCodes.filter((c) => c !== code),
      },
    })),
}))

export default useUserStore
