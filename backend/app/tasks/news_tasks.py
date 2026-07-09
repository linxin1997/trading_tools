"""
新闻采集定时任务模块

定义 Celery 定时任务，定时调用各新闻源爬虫抓取最新资讯。
每个爬虫独立运行，单任务失败不影响其他任务。
"""

import asyncio

import sqlalchemy as sa
from celery import shared_task
from loguru import logger

from app.services.news_crawler.cls_crawler import CLSCrawler
from app.services.news_crawler.eastmoney_crawler import EastMoneyCrawler
from app.services.news_crawler.xueqiu_crawler import XueqiuCrawler


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_cls(self):
    """定时抓取财联社电报快讯（每 10 分钟）

    调用 CLSCrawler 抓取财联社最新新闻，
    失败时自动重试最多 3 次，间隔 60 秒。
    """
    logger.info("Celery 任务: 开始抓取财联社新闻")

    async def _run():
        crawler = CLSCrawler()
        items = await crawler.crawl()
        if items:
            await _save_news(items)
        return len(items)

    try:
        count = asyncio.run(_run())
        logger.info(f"财联社新闻抓取完成，共 {count} 条")
    except Exception as e:
        logger.error(f"财联社新闻抓取任务失败: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_eastmoney(self):
    """定时抓取东方财富新闻（每 15 分钟）

    调用 EastMoneyCrawler 抓取东方财富最新资讯，
    失败时自动重试最多 3 次，间隔 60 秒。
    """
    logger.info("Celery 任务: 开始抓取东方财富新闻")

    async def _run():
        crawler = EastMoneyCrawler()
        items = await crawler.crawl()
        if items:
            await _save_news(items)
        return len(items)

    try:
        count = asyncio.run(_run())
        logger.info(f"东方财富新闻抓取完成，共 {count} 条")
    except Exception as e:
        logger.error(f"东方财富新闻抓取任务失败: {e}")
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_xueqiu(self):
    """定时抓取雪球热门帖子（每 30 分钟）

    调用 XueqiuCrawler 抓取雪球社区热门讨论，
    失败时自动重试最多 3 次，间隔 60 秒。
    """
    logger.info("Celery 任务: 开始抓取雪球新闻")

    async def _run():
        crawler = XueqiuCrawler()
        items = await crawler.crawl()
        if items:
            await _save_news(items)
        return len(items)

    try:
        count = asyncio.run(_run())
        logger.info(f"雪球新闻抓取完成，共 {count} 条")
    except Exception as e:
        logger.error(f"雪球新闻抓取任务失败: {e}")
        raise self.retry(exc=e)


async def _save_news(items: list) -> int:
    """将爬取到的新闻批量写入数据库

    使用异步数据库会话将新闻条目写入 news 表。
    数据库不可用时仅记录日志，不抛出异常。

    Args:
        items: 新闻条目列表

    Returns:
        实际写入的条数
    """
    try:
        from app.core.database import async_session_factory
        from app.models.news import News

        if async_session_factory is None:
            logger.warning("数据库未初始化，跳过新闻存储")
            return 0

        async with async_session_factory() as session:
            saved = 0
            for item in items:
                try:
                    # 检查是否已存在相同 URL 的新闻
                    existing = await session.execute(
                        sa.select(News).where(News.url == item.url)
                    )
                    if existing.scalar_one_or_none():
                        continue

                    news = News(
                        title=item.title,
                        content=item.content,
                        source=item.source,
                        url=item.url,
                        publish_time=item.publish_time,
                        related_stocks=",".join(item.related_stocks) if item.related_stocks else [],
                    )
                    session.add(news)
                    saved += 1
                except Exception as e:
                    logger.warning(f"保存单条新闻失败: {e}")
                    continue

            await session.commit()
            logger.info(f"成功保存 {saved}/{len(items)} 条新闻到数据库")
            return saved
    except ImportError as e:
        logger.warning(f"数据库模块导入失败，跳过存储: {e}")
        return 0
    except Exception as e:
        logger.warning(f"数据库写入失败: {e}，新闻将不会被持久化")
        return 0
