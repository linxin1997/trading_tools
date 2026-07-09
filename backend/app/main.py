"""
FastAPI 应用入口模块

创建 FastAPI 应用实例，注册所有 v1 路由，配置生命周期事件。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import get_settings
from app.api.v1 import (
    market,
    stock,
    analysis,
    portfolio,
    screener,
    reports,
    news,
    risk,
    ai,
    backtest,
    ws,
)
from app.core.database import init_db, close_db
from app.core.redis_client import init_redis, close_redis
from app.services.quote_gateway import gateway
from app.api.v1.ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时：
    - 初始化数据库连接池和 Redis 连接
    - 启动行情网关的后台轮询协程
    - 启动 WebSocket 后台消费协程
    关闭时清理所有资源。
    """
    settings = get_settings()
    logger.info(f"正在启动 {settings.APP_NAME} v{settings.APP_VERSION}")

    # 启动事件：初始化数据库和 Redis
    await init_db()
    await init_redis()
    logger.info("数据库和 Redis 连接已建立")

    # 启动行情网关后台轮询
    await gateway.start()
    # 启动 WebSocket 后台消费协程
    await manager.start_consumer()

    yield

    # 关闭事件：停止后台任务并清理连接
    await manager.stop_consumer()
    await gateway.stop()
    await close_db()
    await close_redis()
    logger.info("数据库和 Redis 连接已关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    title=get_settings().APP_NAME,
    version=get_settings().APP_VERSION,
    lifespan=lifespan,
)

# 跨域配置（允许前端本地开发访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- 注册 v1 路由 ----
app.include_router(market.router, prefix="/api/v1/market", tags=["行情"])
app.include_router(stock.router, prefix="/api/v1/stock", tags=["个股"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["分析"])
app.include_router(portfolio.router, prefix="/api/v1/portfolio", tags=["持仓"])
app.include_router(screener.router, prefix="/api/v1/screener", tags=["选股"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["报告"])
app.include_router(news.router, prefix="/api/v1/news", tags=["新闻"])
app.include_router(risk.router, prefix="/api/v1/risk", tags=["风控"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(backtest.router, prefix="/api/v1/backtest", tags=["回测"])
app.include_router(ws.router, prefix="/api/v1/ws", tags=["WebSocket"])


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}
