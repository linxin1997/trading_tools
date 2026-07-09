"""
持仓 Pydantic 校验模型模块

定义持仓相关的请求/响应数据结构，包括创建、更新、响应和盈亏汇总模型。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    """创建持仓请求模型"""

    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    shares: float = Field(..., gt=0, description="持有股数")
    cost_price: float = Field(..., gt=0, description="成本价（元）")
    current_price: float = Field(0, description="当前价（元）")
    group_id: Optional[int] = Field(None, description="分组 ID")


class PositionUpdate(BaseModel):
    """修改持仓请求模型"""

    shares: Optional[float] = Field(None, gt=0, description="持有股数")
    cost_price: Optional[float] = Field(None, gt=0, description="成本价（元）")
    current_price: Optional[float] = Field(None, description="当前价（元）")
    group_id: Optional[int] = Field(None, description="分组 ID")


class PositionResponse(BaseModel):
    """持仓响应模型"""

    id: int = Field(..., description="持仓 ID")
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    shares: float = Field(..., description="持有股数")
    cost_price: float = Field(..., description="成本价（元）")
    current_price: float = Field(..., description="当前价（元）")
    market_value: float = Field(..., description="市值（元）")
    profit_loss: float = Field(..., description="盈亏金额（元）")
    profit_loss_pct: float = Field(..., description="盈亏百分比（%）")
    group_id: Optional[int] = Field(None, description="分组 ID")
    added_at: Optional[datetime] = Field(None, description="添加时间")


class PnlSummary(BaseModel):
    """盈亏汇总模型"""

    total_market_value: float = Field(..., description="总市值（元）")
    total_cost: float = Field(..., description="总成本（元）")
    total_profit_loss: float = Field(..., description="总盈亏（元）")
    total_profit_loss_pct: float = Field(..., description="总盈亏百分比（%）")
    position_count: int = Field(..., description="持仓数量")


class GroupCreate(BaseModel):
    """创建分组请求模型"""

    name: str = Field(..., description="分组名称")
    description: Optional[str] = Field(None, description="分组描述")
