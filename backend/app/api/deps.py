"""
FastAPI 依赖注入模块

提供可复用的依赖项，例如数据库会话、Redis 客户端等。
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.core.database import async_session_factory
from app.core.redis_client import redis_client as global_redis


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话的依赖项

    Yields:
        AsyncSession: 数据库会话对象

    Raises:
        RuntimeError: 数据库未初始化时抛出
    """
    if async_session_factory is None:
        raise RuntimeError("数据库未初始化")
    session = async_session_factory()
    try:
        yield await session.__aenter__()
        await session.commit()  # 请求成功后提交事务
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.__aexit__(None, None, None)


async def get_redis() -> Redis:
    """
    获取 Redis 客户端的依赖项

    Returns:
        Redis: Redis 异步客户端

    Raises:
        RuntimeError: Redis 未初始化时抛出
    """
    if global_redis is None:
        raise RuntimeError("Redis 未初始化")
    return global_redis
