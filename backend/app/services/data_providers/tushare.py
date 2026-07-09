"""
Tushare 数据提供商模块

封装 Tushare Pro 接口，提供更全面的 A 股数据（需注册获取 token）。
"""

import asyncio
from typing import Any

import pandas as pd

from app.services.data_providers.base import BaseDataProvider
from app.config import get_settings


class TushareProvider(BaseDataProvider):
    """Tushare Pro 数据提供商，需配置 API Token"""

    def __init__(self):
        """
        初始化 Tushare 客户端，从配置读取 token

        如果 token 未配置，则 _pro 保持为 None；
        后续所有接口调用将自动返回空数据（不报错）。
        """
        settings = get_settings()
        self.token = settings.TUSHARE_TOKEN
        self._pro = None
        if self.token:
            try:
                import tushare as ts

                ts.set_token(self.token)
                self._pro = ts.pro_api()
            except Exception:
                self._pro = None

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取个股实时行情

        调用 pro.realtime_quote(ts_code=code) 获取实时行情数据。

        Args:
            code: 股票代码（如 "000001.SZ"）

        Returns:
            实时行情字典；token 未配置或出错时返回空字典
        """
        if self._pro is None:
            return {}

        try:
            df: pd.DataFrame = await asyncio.to_thread(self._pro.realtime_quote, ts_code=code)
            if df is None or df.empty:
                return {}

            row = df.iloc[0]
            return {
                "symbol": str(row.get("ts_code", code)),
                "name": str(row.get("name", "")),
                "price": float(row.get("price", 0)),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "pre_close": float(row.get("pre_close", 0)),
                "volume": int(row.get("vol", row.get("volume", 0))),
                "amount": float(row.get("amount", 0)),
                "pct_change": float(row.get("pct_change", 0)),
                "timestamp": str(row.get("trade_date", "")),
            }
        except Exception:
            return {}

    async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:
        """
        获取 K 线数据

        调用 pro.daily(ts_code=code) 获取日线数据。
        仅支持 daily 周期。

        Args:
            code: 股票代码（如 "000001.SZ"）
            period: K 线周期（tushare 仅支持 daily，其他周期返回空列表）

        Returns:
            K 线数据列表；token 未配置或出错时返回空列表
        """
        if self._pro is None or period != "daily":
            return []

        try:
            df: pd.DataFrame = await asyncio.to_thread(self._pro.daily, ts_code=code)
            if df is None or df.empty:
                return []

            records = []
            for _, row in df.iterrows():
                records.append(
                    {
                        "date": str(row.get("trade_date", "")),
                        "open": float(row.get("open", 0)),
                        "close": float(row.get("close", 0)),
                        "high": float(row.get("high", 0)),
                        "low": float(row.get("low", 0)),
                        "volume": int(row.get("vol", row.get("volume", 0))),
                        "amount": float(row.get("amount", 0)),
                        "pct_change": float(row.get("pct_change", 0)),
                    }
                )

            return records
        except Exception:
            return []
