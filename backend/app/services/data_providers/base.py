"""
数据提供商基类模块

定义行情数据提供商的抽象接口，所有数据源类需继承此类。
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseDataProvider(ABC):
    """数据提供商抽象基类，定义统一的数据获取接口"""

    @abstractmethod
    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """
        获取个股实时行情

        Args:
            code: 股票代码

        Returns:
            包含实时行情数据的字典
        """
        ...

    @abstractmethod
    async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:
        """
        获取 K 线数据

        Args:
            code: 股票代码
            period: K 线周期（daily/weekly/monthly/1m/5m）

        Returns:
            K 线数据列表
        """
        ...
