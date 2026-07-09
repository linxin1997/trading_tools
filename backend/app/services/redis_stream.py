"""
Redis Stream 消息队列模块

提供基于 Redis Stream 的生产者/消费者模式，用于实时行情的分发。
"""

import json
from typing import Any, AsyncIterator

from loguru import logger

from app.core.redis_client import redis_client


# Redis Stream 名称
STREAM_NAME = "QUOTE_STREAM"


async def publish_quote(quote_data: dict[str, Any]) -> str | None:
    """
    将行情字典推送到 Redis Stream

    Args:
        quote_data: 行情数据字典

    Returns:
        消息 ID，推送失败时返回 None
    """
    if redis_client is None:
        logger.warning("Redis 客户端未初始化，无法推送行情")
        return None

    try:
        # 将字典序列化为 JSON 字符串后再写入 Stream
        message_id = await redis_client.xadd(
            STREAM_NAME,
            {"data": json.dumps(quote_data, ensure_ascii=False)},
            maxlen=10000,  # 限制 Stream 最大长度，防止内存溢出
        )
        return message_id
    except Exception as e:
        logger.error(f"推送行情到 Redis Stream 失败: {e}")
        return None


async def subscribe_quotes(block_ms: int = 1000) -> AsyncIterator[dict[str, Any]]:
    """
    阻塞读取 QUOTE_STREAM 新消息，返回异步迭代器

    每次读取一批新消息并逐个 yield 给调用方，适用于后台消费协程。

    Args:
        block_ms: 阻塞等待时间（毫秒），默认 1000ms

    Yields:
        行情数据字典
    """
    if redis_client is None:
        logger.warning("Redis 客户端未初始化，无法消费行情")
        return

    # 消费者组名称
    group_name = "quote_consumers"
    consumer_name = "ws_broadcaster"

    # 尝试创建消费者组（如果已存在则忽略）
    try:
        await redis_client.xgroup_create(
            STREAM_NAME, group_name, id="0", mkstream=True
        )
    except Exception:
        # 消费者组已存在，忽略
        pass

    while True:
        try:
            # 阻塞读取新消息
            results = await redis_client.xreadgroup(
                group_name,
                consumer_name,
                {STREAM_NAME: ">"},
                count=10,
                block=block_ms,
            )

            if not results:
                continue

            for stream_name, messages in results:
                for msg_id, msg_data in messages:
                    raw = msg_data.get("data", "{}")
                    try:
                        quote = json.loads(raw)
                        yield quote
                    except json.JSONDecodeError:
                        logger.warning(f"反序列化行情消息失败: {raw}")
                    finally:
                        # 确认消息已处理
                        await redis_client.xack(STREAM_NAME, group_name, msg_id)
        except Exception as e:
            logger.error(f"消费 Redis Stream 出错: {e}")
            import asyncio

            await asyncio.sleep(1)
