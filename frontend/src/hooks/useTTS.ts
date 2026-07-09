import { useCallback, useEffect } from 'react'

/**
 * 浏览器语音播报 Hook
 * 使用 Web Speech API 实现中文语音播报，不依赖后端
 * 内部使用单例 SpeechSynthesisUtterance，避免每次播报重复创建
 */

// 单例 SpeechSynthesisUtterance，复用实例避免 GC 压力
let _utterance: SpeechSynthesisUtterance | null = null
function getUtterance(): SpeechSynthesisUtterance {
  if (!_utterance) {
    _utterance = new SpeechSynthesisUtterance()
  }
  return _utterance
}

export function useTTS() {
  /**
   * 播报文本
   * @param text 播报内容
   * @param lang 语言，默认 zh-CN
   */
  const speak = useCallback((text: string, lang = 'zh-CN') => {
    if (!window.speechSynthesis) {
      console.warn('浏览器不支持 SpeechSynthesis API')
      return
    }
    // 取消当前播报，避免重叠
    window.speechSynthesis.cancel()
    const utterance = getUtterance()
    utterance.text = text
    utterance.lang = lang
    utterance.rate = 1.0
    utterance.pitch = 1.0
    window.speechSynthesis.speak(utterance)
  }, [])

  // 组件卸载时取消所有播报
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel()
    }
  }, [])

  return { speak }
}
