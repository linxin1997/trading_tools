"""
SQLAlchemy 数据库引擎模块

提供异步 PostgreSQL 引擎与会话工厂，以及 DuckDB 连接管理。
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from loguru import logger

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类"""
    pass


# 异步引擎和会话工厂（运行时赋值）
engine = None
async_session_factory = None


async def init_db():
    """
    初始化数据库引擎和会话工厂

    根据配置创建 asyncpg 引擎，并建立连接池。
    """
    global engine, async_session_factory
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DATABASE_ECHO,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    logger.info("数据库引擎已初始化")


async def close_db():
    """
    关闭数据库引擎，释放连接池资源
    """
    global engine, async_session_factory
    if engine:
        await engine.dispose()
        engine = None
        async_session_factory = None
        logger.info("数据库引擎已关闭")


async def get_session() -> AsyncSession:
    """
    获取异步数据库会话（用于依赖注入）

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
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.__aexit__(None, None, None)
