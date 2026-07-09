"""
AKShare 数据提供商模块

封装 AKShare 库的接口，提供 A 股行情数据的获取能力。
AKShare 为开源免费接口，无需 API Key。
"""

import asyncio
from typing import Any

import akshare as ak
import pandas as pd

from app.services.data_providers.base import BaseDataProvider


def _map_code_to_symbol(code: str) -> str:
    """
    将 6 位数字代码转换为带交易所后缀的完整代码

    Args:
        code: 6 位数字股票代码

    Returns:
        带 .SZ 或 .SH 后缀的完整代码
    """
    code = code.strip()
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    return f"{code}.SZ"


def _clean_code(raw_code: str) -> str:
    """
    从完整代码中提取 6 位数字代码，去除交易所后缀

    Args:
        raw_code: 可能带后缀的股票代码（如 "000001.SZ"）

    Returns:
        6 位数字代码
    """
    return raw_code.split(".")[0].strip()


def _safe_float(row: dict, key: str) -> float | None:
    """安全提取浮点数，None 时返回 None"""
    v = row.get(key)
    if v is not None:
        try:
            return float(v)
        except (ValueError, TypeError):
            pass
    return None


def _safe_int(row: dict, key: str) -> int | None:
    """安全提取整数，None 时返回 None"""
    v = row.get(key)
    if v is not None:
        try:
            return int(float(v))
        except (ValueError, TypeError):
            pass
    return None


class AKShareProvider(BaseDataProvider):
    """AKShare 数据提供商，通过 akshare 库获取实时行情和 K 线数据"""

    # 全市场快照缓存（类级别，所有实例共享）
    _cached_quotes: dict[str, Any] | None = None
    _cache_time: float = 0
    _CACHE_TTL = 1.0  # 缓存有效期 1 秒
    _cache_lock = asyncio.Lock()  # 缓存刷新锁，避免并发重复拉取

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取个股实时行情（带全市场快照缓存）

        1 秒内重复查询不重新拉取全市场数据，直接从缓存中过滤目标股票。
        首次调用或缓存过期时自动调用 get_batch_quotes() 刷新全市场快照。

        Args:
            code: 股票代码（支持 "000001.SZ" 或 "000001" 格式）

        Returns:
            包含 price/open/high/low/volume/amount/pct_change 等字段的字典；
            未找到时返回空字典
        """
        import time
        target_code = _clean_code(code)

        # 缓存过期或不存在时刷新全市场快照（带锁防并发）
        now = time.time()
        if self._cached_quotes is None or (now - self._cache_time) > self._CACHE_TTL:
            async with self._cache_lock:
                # 双重检查：拿到锁后可能已被其他协程刷新
                if self._cached_quotes is None or (now - self._cache_time) > self._CACHE_TTL:
                    self._cached_quotes = await self.get_batch_quotes()
                    self._cache_time = time.time()

        # 从缓存中过滤指定股票
        if self._cached_quotes:
            for quote in self._cached_quotes:
                if _clean_code(quote.get("symbol", "")) == target_code:
                    return quote
        return {}

    async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:
        """
        获取 K 线数据

        根据 period 调用不同的 akshare 接口：
        - daily：ak.stock_zh_a_hist(symbol=code, period="daily")
        - weekly：ak.stock_zh_a_hist(symbol=code, period="weekly")

        Args:
            code: 股票代码
            period: K 线周期，支持 "daily" / "weekly"

        Returns:
            K 线数据列表，每项包含 date/open/close/high/low/volume/amount 等字段
        """
        target_code = _clean_code(code)
        # 将 period 映射为 akshare 接受的参数
        period_map = {"daily": "daily", "weekly": "weekly", "monthly": "monthly"}
        ak_period = period_map.get(period, "daily")

        df: pd.DataFrame = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: ak.stock_zh_a_hist(
                symbol=target_code,
                period=ak_period,
                adjust="qfq",  # 前复权（量化场景必须前复权，避免除权除息造出假缺口）
            ),
        )

        if df is None or df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "date": str(row.get("日期", "")),
                    "open": _safe_float(row, "开盘"),
                    "close": _safe_float(row, "收盘"),
                    "high": _safe_float(row, "最高"),
                    "low": _safe_float(row, "最低"),
                    "volume": _safe_int(row, "成交量"),
                    "amount": _safe_float(row, "成交额"),
                    "pct_change": _safe_float(row, "涨跌幅"),
                }
            )

        return records

    async def get_batch_quotes(self) -> list[dict[str, Any]]:
        """
        获取全市场批量实时行情

        调用 ak.stock_zh_a_spot_em() 返回全市场快照，用于批量轮询处理。

        Returns:
            全市场所有股票的行情字典列表
        """
        df: pd.DataFrame = await asyncio.get_event_loop().run_in_executor(
            None, ak.stock_zh_a_spot_em
        )

        if df is None or df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            symbol = _map_code_to_symbol(str(row["代码"]))
            records.append(
                {
                    "symbol": symbol,
                    "name": str(row.get("名称", "")),
                    "price": float(row.get("最新价", 0)),
                    "open": float(row.get("今开", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "pre_close": float(row.get("昨收", 0)),
                    "volume": int(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                    "pct_change": float(row.get("涨跌幅", 0)),
                    "timestamp": "",
                }
            )

        return records
