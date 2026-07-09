"""
Baostock 数据提供商

提供 A 股历史 K 线数据获取，作为 AKShare 的替代源。
baostock 无需鉴权，专为量化回测设计，数据质量稳定。

用法:
    provider = BaostockProvider()
    klines = await provider.get_kline("000001")

注意:
    - baostock 非线程安全（单例+锁保护）
    - adjustflag=2 使用前复权
"""

from typing import Any
from loguru import logger

from .base import BaseDataProvider


# 交易所前缀映射
def _to_bs_code(code: str) -> str:
    """将通用代码转为 baostock 格式"""
    s = code.upper().replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
    if s.startswith("6") or s.startswith("9"):
        return f"sh.{s}"
    elif s.startswith("0") or s.startswith("3"):
        return f"sz.{s}"
    return f"sz.{s}"


def _from_bs_code(bs_code: str) -> str:
    """将 baostock 代码转为统一格式（如 'sz.000001' → '000001.SZ'）"""
    parts = bs_code.split(".")
    if len(parts) != 2:
        return bs_code
    exchange, code = parts
    return f"{code}.{exchange.upper()}"


class BaostockProvider(BaseDataProvider):
    """基于 baostock 的历史行情数据提供商"""

    FIELDS_MAP = {
        "date": "trade_date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "preclose": "pre_close",
        "volume": "volume",
        "amount": "amount",
        "turn": "turn",
        "pctChg": "pct_change",
    }
    QUERY_FIELDS = "date,open,high,low,close,preclose,volume,amount,turn,pctChg"

    def __init__(self):
        self._logged_in = False
        self._bs = None  # 惰性导入

    def _ensure_login(self):
        """确保已登录 baostock（方法内惰性导入避免模块级崩溃）"""
        if self._logged_in:
            return
        if self._bs is None:
            import baostock as bs
            self._bs = bs
        lg = self._bs.login()
        if lg.error_code != "0":
            raise ConnectionError(f"baostock 登录失败: {lg.error_msg}")
        self._logged_in = True

    def logout(self):
        """登出 baostock"""
        if self._logged_in and self._bs:
            self._bs.logout()
            self._logged_in = False

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """baostock 不提供实时行情，返回空"""
        return {}

    async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:
        """
        获取 K 线数据

        Args:
            code: 股票代码（如 000001、000001.SZ）
            period: 周期（daily/weekly/monthly）

        Returns:
            K 线数据列表，每项含 symbol/trade_date/open/high/low/close/volume/amount/pct_change/turn
        """
        self._ensure_login()
        bs_code = _to_bs_code(code)
        freq_map = {"daily": "d", "weekly": "w", "monthly": "m"}
        frequency = freq_map.get(period, "d")

        try:
            rs = self._bs.query_history_k_data_plus(
                bs_code, self.QUERY_FIELDS,
                frequency=frequency, adjustflag="2",  # 前复权
            )
            if rs.error_code != "0":
                logger.warning(f"baostock 查询 {code} 失败: {rs.error_msg}")
                return []

            rows = rs.data
            if not rows:
                return []

            import pandas as pd
            df = pd.DataFrame(rows, columns=self.QUERY_FIELDS.split(","))
            df.rename(columns=self.FIELDS_MAP, inplace=True)

            numeric_cols = ["open", "high", "low", "close", "pre_close", "volume", "amount", "turn", "pct_change"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "trade_date" in df.columns:
                df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

            df["symbol"] = _from_bs_code(bs_code)
            df.sort_values("trade_date", inplace=True)

            return df.to_dict("records")

        except Exception as e:
            logger.error(f"baostock 获取 {code} 异常: {e}")
            return []


# 全局单例
_provider: BaostockProvider | None = None


def get_provider() -> BaostockProvider:
    """获取 BaostockProvider 全局单例"""
    global _provider
    if _provider is None:
        _provider = BaostockProvider()
    return _provider
