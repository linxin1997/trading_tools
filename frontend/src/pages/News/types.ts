/**
 * 舆情新闻类型定义
 */

/** 新闻来源枚举 */
export type NewsSource = 'cls' | 'eastmoney' | 'xueqiu' | 'overseas'

/** 情感标签 */
export type SentimentLabel = 'positive' | 'negative' | 'neutral'

/** 新闻来源映射：key -> 中文名 */
export const NEWS_SOURCE_MAP: Record<NewsSource, string> = {
  cls: '财联社',
  eastmoney: '东财',
  xueqiu: '雪球',
  overseas: '境外',
}

/** 新闻来源选项列表 */
export const NEWS_SOURCE_OPTIONS = Object.entries(NEWS_SOURCE_MAP).map(
  ([value, label]) => ({ value: value as NewsSource, label }),
)

/** 情感标签中文映射 */
export const SENTIMENT_LABEL_MAP: Record<SentimentLabel, string> = {
  positive: '正面',
  negative: '负面',
  neutral: '中性',
}

/** 情感标签选项列表 */
export const SENTIMENT_OPTIONS = Object.entries(SENTIMENT_LABEL_MAP).map(
  ([value, label]) => ({ value: value as SentimentLabel, label }),
)

/** 单条新闻数据 */
export interface NewsItem {
  id: number
  /** 来源标识 */
  source: NewsSource
  /** 新闻标题 */
  title: string
  /** 新闻正文 */
  content: string
  /** 原文链接 */
  url: string
  /** 发布时间，ISO 格式 */
  publish_time: string
  /** 情感分类标签 */
  sentiment_label: SentimentLabel
  /** 情感分数，范围 -1 ~ 1 */
  sentiment_score: number
  /** 关联股票代码列表 */
  related_stocks: string[]
}

/** 新闻筛选条件 */
export interface NewsFilterParams {
  /** 来源筛选，为空表示全部 */
  sources?: NewsSource[]
  /** 情感筛选，为空表示全部 */
  sentiments?: SentimentLabel[]
  /** 关联标的筛选 */
  stock_code?: string
  /** 分页游标（按时间） */
  cursor?: string
  /** 每页条数 */
  limit?: number
}

/** WebSocket 推送的新闻消息 */
export interface NewsWsMessage {
  type: 'news'
  data: NewsItem
}
