"""
Redis 客户端模块

提供全局 Redis 连接池实例，用于缓存和消息队列。
"""

from redis.asyncio import Redis
from loguru import logger

from app.config import get_settings


# Redis 客户端实例（运行时赋值）
redis_client: Redis | None = None


async def init_redis():
    """
    初始化 Redis 连接池

    根据配置创建异步 Redis 客户端。
    """
    global redis_client
    settings = get_settings()
    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()
    logger.info("Redis 客户端已初始化")


async def close_redis():
    """
    关闭 Redis 连接池
    """
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
        logger.info("Redis 客户端已关闭")


async def get_redis() -> Redis:
    """
    获取 Redis 客户端实例（用于依赖注入）

    Returns:
        Redis: Redis 异步客户端

    Raises:
        RuntimeError: Redis 未初始化时抛出
    """
    if redis_client is None:
        raise RuntimeError("Redis 未初始化")
    return redis_client
