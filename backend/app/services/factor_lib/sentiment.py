"""
舆情情感面因子模块

实现基于新闻舆情的情感因子计算函数，从 news 表查询新闻数据并聚合。
数据库不可用时返回 0，不阻塞选股流程。

注意：所有公开函数均为 async 协程，避免 asyncio.run() 嵌套导致 RuntimeError。
"""

from datetime import date, datetime
from typing import Any

from loguru import logger


async def get_positive_news_1d(symbol: str) -> int:
    """获取指定股票当日正面新闻数量

    Args:
        symbol: 股票代码（如 "600519"）

    Returns:
        当日正面新闻数量，数据库不可用时返回 0
    """
    return await _query_positive_news(symbol)


async def get_negative_news_1d(symbol: str) -> int:
    """获取指定股票当日负面新闻数量

    Args:
        symbol: 股票代码（如 "600519"）

    Returns:
        当日负面新闻数量，数据库不可用时返回 0
    """
    return await _query_negative_news(symbol)


async def get_sentiment_score_1d(symbol: str) -> float:
    """获取指定股票当日情感综合评分

    计算当日所有关联新闻的情感得分均值，范围 [-1, 1]。

    Args:
        symbol: 股票代码（如 "600519"）

    Returns:
        当日情感综合评分（-1 到 1），无新闻或数据库不可用时返回 0
    """
    return await _query_sentiment_score(symbol)


async def _query_positive_news(symbol: str) -> int:
    """异步查询当日正面新闻数量"""
    try:
        from app.core.database import async_session_factory
        if async_session_factory is None:
            return 0
        import sqlalchemy as sa
        from app.models.news import News
        today_start = datetime.combine(date.today(), datetime.min.time())
        async with async_session_factory() as session:
            query = (
                sa.select(sa.func.count(News.id))
                .where(News.related_stocks.any(symbol), News.sentiment_score > 0, News.publish_time >= today_start)
            )
            result = await session.execute(query)
            return result.scalar() or 0
    except Exception as e:
        logger.warning(f"查询正面新闻数量异常: {e}")
        return 0


async def _query_negative_news(symbol: str) -> int:
    """异步查询当日负面新闻数量"""
    try:
        from app.core.database import async_session_factory
        if async_session_factory is None:
            return 0
        import sqlalchemy as sa
        from app.models.news import News
        today_start = datetime.combine(date.today(), datetime.min.time())
        async with async_session_factory() as session:
            query = (
                sa.select(sa.func.count(News.id))
                .where(News.related_stocks.any(symbol), News.sentiment_score < 0, News.publish_time >= today_start)
            )
            result = await session.execute(query)
            return result.scalar() or 0
    except Exception as e:
        logger.warning(f"查询负面新闻数量异常: {e}")
        return 0


async def _query_sentiment_score(symbol: str) -> float:
    """异步查询当日情感综合评分"""
    try:
        from app.core.database import async_session_factory
        if async_session_factory is None:
            return 0.0
        import sqlalchemy as sa
        from app.models.news import News
        today_start = datetime.combine(date.today(), datetime.min.time())
        async with async_session_factory() as session:
            count_query = sa.select(sa.func.count(News.id)).where(
                News.related_stocks.any(symbol), News.publish_time >= today_start
            )
            total = (await session.execute(count_query)).scalar() or 0
            if total == 0:
                return 0.0
            positive = (await session.execute(
                sa.select(sa.func.count(News.id)).where(
                    News.related_stocks.any(symbol), News.sentiment_score > 0, News.publish_time >= today_start
                )
            )).scalar() or 0
            negative = (await session.execute(
                sa.select(sa.func.count(News.id)).where(
                    News.related_stocks.any(symbol), News.sentiment_score < 0, News.publish_time >= today_start
                )
            )).scalar() or 0
            score = (positive - negative) / total
            return max(-1.0, min(1.0, score))
    except Exception as e:
        logger.warning(f"查询情感综合评分异常: {e}")
        return 0.0
