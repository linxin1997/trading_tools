"""
行情 Pydantic 校验模型模块

定义行情相关的请求/响应数据结构。
"""

from pydantic import BaseModel
from typing import Any


class RealtimeQuote(BaseModel):
    """实时行情响应结构"""

    code: str
    name: str
    price: float
    change_pct: float
    volume: float
    amount: float
