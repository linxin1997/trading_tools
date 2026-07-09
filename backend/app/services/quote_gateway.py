"""
行情网关模块

统一聚合多个数据源，对外提供实时行情和 K 线数据的统一接口。
实时行情：Tencent gtimg 主 → 新浪 sinajs 备（替换原来的 AKShare 实时路径）
历史数据：通过 KlineProvider 接入（baostock / akshare）

数据源切换背景：
  AKShare 的实时接口底层爬东方财富 push2，无 SLA、按 IP 封禁风险高。
  腾讯 gtimg 无需鉴权、无封禁风险、支持批量查询，更适合个人开发者。
"""

import asyncio
import random
from datetime import datetime
from typing import Any

from loguru import logger

from app.services.data_providers.tencent_provider import TencentProvider
from app.services.data_providers.akshare import AKShareProvider
from app.services.redis_stream import publish_quote


class QuoteGateway:
    """
    行情网关

    实时行情：TencentProvider 主 → AKShare 备
    历史 K 线：AKShareProvider（保留）
    """

    def __init__(self):
        self._tencent = TencentProvider()
        self._akshare = AKShareProvider()

        self._poll_task: asyncio.Task | None = None
        self._running = False
        self.watched_symbols: set[str] = set()

    def update_watched_symbols(self, symbols: list[str]):
        self.watched_symbols = set(symbols)
        logger.info(f"关注股票列表已更新，共 {len(self.watched_symbols)} 只")

    # ------------------------------------------------------------------
    # REST 查询接口
    # ------------------------------------------------------------------

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取个股实时行情

        数据源优先级：Tencent → AKShare → Tushare
        """
        try:
            result = await self._tencent.get_realtime_quote(code)
            if result:
                return result
        except Exception:
            pass
        try:
            return await self._akshare.get_realtime_quote(code)
        except Exception:
            return {}

    async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:
        """
        获取 K 线数据（使用 AKShareProvider）
        """
        try:
            return await self._akshare.get_kline(code, period)
        except Exception:
            return []

    async def get_batch_quotes(self) -> list[dict[str, Any]]:
        """
        获取批量实时行情（使用 TencentProvider）

        Returns:
            行情列表
        """
        all_quotes = []
        if self.watched_symbols:
            all_quotes = await self._tencent.get_realtime_quotes(list(self.watched_symbols))
        return all_quotes

    # ------------------------------------------------------------------
    # 轮询推送（后台协程）
    # ------------------------------------------------------------------

    async def start(self):
        if self._running:
            return
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("行情网关轮询已启动（TencentProvider 实时源）")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
            logger.info("行情网关轮询已停止")

    async def _poll_loop(self):
        """
        轮询主循环

        使用 TencentProvider 以 2-5 秒间隔轮询关注股票列表的实时行情，
        推送至 Redis Stream。
        """
        logger.info("行情网关轮询循环已开始")

        while self._running:
            try:
                symbols_to_fetch = list(self.watched_symbols) if self.watched_symbols else []

                if not symbols_to_fetch:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    continue

                quotes = await self._tencent.get_realtime_quotes(symbols_to_fetch)

                if not quotes:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    continue

                now_str = datetime.now().isoformat(sep="T", timespec="seconds")
                for q in quotes:
                    q["timestamp"] = now_str

                for q in quotes:
                    await publish_quote(q)

                logger.debug(f"轮询推送 {len(quotes)} 条行情（关注 {len(symbols_to_fetch)} 只）")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"行情网关轮询异常: {e}")

            await asyncio.sleep(random.uniform(2.0, 5.0))

        logger.info("行情网关轮询循环已退出")


# 全局单例
gateway = QuoteGateway()
