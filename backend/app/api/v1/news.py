"""
新闻资讯接口模块

提供新闻流、新闻详情等 REST API。
支持按来源、情感倾向、关联股票等维度筛选。
数据库不可用时返回空列表，不报错。
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from loguru import logger

from app.models.news import News

router = APIRouter()


@router.get("/stream")
async def get_news_stream(
    source: Optional[str] = Query(None, description="新闻来源筛选（如 财联社、东方财富、雪球）"),
    sentiment: Optional[str] = Query(None, description="情感倾向筛选（positive / negative / neutral）"),
    symbol: Optional[str] = Query(None, description="关联股票代码筛选"),
    limit: int = Query(50, ge=1, le=200, description="返回条数上限（1-200）"),
):
    """获取新闻流

    按发布时间倒序返回新闻列表，支持多维度筛选。
    所有筛选条件均为可选，不传则返回全部新闻。

    Args:
        source: 新闻来源，如 "财联社"、"东方财富"、"雪球"
        sentiment: 情感倾向，可选 "positive"、"negative"、"neutral"
        symbol: 关联的股票代码
        limit: 返回条数上限

    Returns:
        新闻列表及总数
    """
    logger.info(f"查询新闻流: source={source}, sentiment={sentiment}, symbol={symbol}, limit={limit}")
    try:
        from app.core.database import async_session_factory
        import sqlalchemy as sa

        if async_session_factory is None:
            logger.warning("数据库未初始化，返回空新闻列表")
            return {"total": 0, "items": [], "message": "数据库未初始化"}

        async with async_session_factory() as session:
            query = sa.select(News)

            # 按来源筛选
            if source:
                query = query.where(News.source == source)

            # 按情感倾向筛选
            if sentiment == "positive":
                query = query.where(News.sentiment_score > 0)
            elif sentiment == "negative":
                query = query.where(News.sentiment_score < 0)
            elif sentiment == "neutral":
                query = query.where(News.sentiment_score.is_(None))

            # 按关联股票筛选
            if symbol:
                query = query.where(News.related_stocks.like(f"%{symbol}%"))

            # 按发布时间倒序排列
            query = query.order_by(News.publish_time.desc().nullslast()).limit(limit)

            result = await session.execute(query)
            news_list = result.scalars().all()

            logger.info(f"查询到 {len(news_list)} 条新闻")
            return {
                "total": len(news_list),
                "items": [_news_to_dict(n) for n in news_list],
            }

    except ImportError as e:
        logger.warning(f"数据库模块导入失败: {e}")
        return {"total": 0, "items": [], "message": "数据库模块不可用"}
    except Exception as e:
        logger.warning(f"查询新闻流失败: {e}")
        return {"total": 0, "items": [], "message": str(e)}


@router.get("/{news_id}")
async def get_news_detail(news_id: int):
    """获取新闻详情

    根据新闻 ID 查询单条新闻的完整信息。

    Args:
        news_id: 新闻 ID

    Returns:
        新闻详情字典，不存在时返回 404 风格响应
    """
    logger.info(f"查询新闻详情: id={news_id}")
    try:
        from app.core.database import async_session_factory
        import sqlalchemy as sa

        if async_session_factory is None:
            logger.warning("数据库未初始化，无法查询新闻详情")
            return {"code": 503, "message": "数据库未初始化"}

        async with async_session_factory() as session:
            query = sa.select(News).where(News.id == news_id)
            result = await session.execute(query)
            news = result.scalar_one_or_none()

            if news is None:
                logger.warning(f"新闻不存在: id={news_id}")
                return {"code": 404, "message": f"新闻 #{news_id} 不存在"}

            logger.info(f"新闻详情查询成功: id={news_id}")
            return _news_to_dict(news)

    except ImportError as e:
        logger.warning(f"数据库模块导入失败: {e}")
        return {"code": 503, "message": "数据库模块不可用"}
    except Exception as e:
        logger.warning(f"查询新闻详情失败: {e}")
        return {"code": 500, "message": str(e)}


def _news_to_dict(news: News) -> dict:
    """将 News ORM 对象转换为字典

    Args:
        news: News ORM 实例

    Returns:
        序列化后的字典
    """
    return {
        "id": news.id,
        "title": news.title,
        "summary": news.content[:100] if news.content else None,
        "content": news.content,
        "source": news.source,
        "url": news.url,
        "published_at": news.publish_time.isoformat() if news.publish_time else None,
        "related_stocks": news.related_stocks if news.related_stocks else [],
        "sentiment_score": news.sentiment_score,
        "sentiment_label": _score_to_label(news.sentiment_score),
        "created_at": news.crawl_time.isoformat() if news.crawl_time else None,
    }


def _score_to_label(score: float | None) -> str:
    """将情感分数转换为标签

    Args:
        score: 情感分数（-1 到 1）

    Returns:
        情感标签: positive / negative / neutral
    """
    if score is None:
        return "neutral"
    if score > 0.1:
        return "positive"
    if score < -0.1:
        return "negative"
    return "neutral"
