"""
个股 Pydantic 校验模型模块

定义个股相关的请求/响应数据结构。
"""

from pydantic import BaseModel
from typing import Optional
from datetime import date


class StockInfoResponse(BaseModel):
    """个股基本信息响应（对齐 stock_info 表）"""

    symbol: str
    name: str
    list_date: Optional[date] = None


class KlineQuery(BaseModel):
    """K 线查询参数"""

    code: str
    period: str = "daily"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
