"""
新闻分析任务模块

定义 Celery 定时任务，对已采集的新闻进行情感分析和关联股票识别。
数据库不可用时仅记录日志，不阻塞任务执行。
"""

import asyncio

from celery import shared_task
from loguru import logger

from app.services.nlp.sentiment import SentimentAnalyzer


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def analyze_news_sentiment(self):
    """批量分析未处理新闻的情感

    从数据库查询 sentiment_score 和 sentiment_label 均为 NULL 的新闻，
    调用 SentimentAnalyzer 进行情感分析，并将结果更新回数据库。
    每次最多处理 50 条未分析新闻，避免任务执行时间过长。

    执行步骤：
    1. 查询未分析的新闻记录
    2. 调用情感分析器（Qwen2.5-3B via Ollama）
    3. 将情感结果更新到 news 表
    """
    logger.info("Celery 任务: 开始批量新闻情感分析")

    async def _run():
        try:
            from app.core.database import async_session_factory
            from app.models.news import News
            import sqlalchemy as sa

            if async_session_factory is None:
                logger.warning("数据库未初始化，跳过情感分析")
                return 0

            async with async_session_factory() as session:
                # 查询未分析的新闻（sentiment_score IS NULL）
                # 使用 sentinel 字段判断是否已分析
                query = (
                    sa.select(News)
                    .where(News.sentiment_score.is_(None))
                    .limit(50)
                )
                result = await session.execute(query)
                news_list = list(result.scalars().all())

                if not news_list:
                    logger.info("没有未分析的新闻")
                    return 0

                logger.info(f"共发现 {len(news_list)} 条待分析新闻")

                # 准备待分析文本（优先使用标题+摘要）
                texts = []
                for news in news_list:
                    text = news.title or ""
                    if news.content:
                        text = f"{text}。{news.content[:200]}" if text else news.content[:200]
                    if news.content and len(text) < 50:
                        text = news.content[:200]
                    texts.append(text or "无内容")

                # 调用情感分析器
                analyzer = SentimentAnalyzer()
                sentiments = await analyzer.analyze_batch(texts)

                # 更新数据库
                updated = 0
                for news, sentiment in zip(news_list, sentiments):
                    try:
                        label = sentiment.get("label", "neutral")
                        score = sentiment.get("score", 0.5)

                        # 将 label 映射为数值分数（-1 到 1）
                        if label == "positive":
                            numeric_score = score
                        elif label == "negative":
                            numeric_score = -score
                        else:
                            numeric_score = 0.0

                        news.sentiment_score = numeric_score
                        updated += 1
                    except Exception as e:
                        logger.warning(f"更新新闻 #{news.id} 情感分析失败: {e}")
                        continue

                await session.commit()
                logger.info(f"成功更新 {updated}/{len(news_list)} 条新闻的情感标签")
                return updated

        except ImportError as e:
            logger.warning(f"数据库模块导入失败，跳过情感分析: {e}")
            return 0
        except Exception as e:
            logger.warning(f"情感分析任务执行失败: {e}")
            return 0

    try:
        count = asyncio.run(_run())
        logger.info(f"新闻情感分析任务完成，共处理 {count} 条")
        return count
    except Exception as e:
        logger.error(f"新闻情感分析任务异常: {e}")
        raise self.retry(exc=e)
