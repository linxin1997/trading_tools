"""
选股器 Pydantic 校验模型模块

定义选股请求/响应数据结构，用于 API 参数校验和文档生成。
"""

from pydantic import BaseModel, Field
from typing import Any


class ScreenerCondition(BaseModel):
    """选股筛选条件

    描述一个因子筛选条件，例如 {"factor": "MA_CROSS", "op": "eq", "value": "多头排列"}
    """

    factor: str = Field(..., description="因子名称，如 MA_CROSS、RSI_14")
    op: str = Field(..., description="操作符：eq/neq/gt/gte/lt/lte/in")
    value: Any = Field(..., description="目标值")


class ScreenerRequest(BaseModel):
    """选股筛选请求体"""

    conditions: list[ScreenerCondition] = Field(
        default_factory=list, description="筛选条件列表"
    )
    weights: dict[str, float] = Field(
        default_factory=dict, description="因子权重，如 {'RSI_14': 0.3, 'MA_CROSS': 0.2}"
    )
    top_n: int = Field(default=20, ge=1, le=500, description="返回前 N 只股票")


class StockScoreItem(BaseModel):
    """选股结果条目"""

    symbol: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    score: float = Field(..., description="综合评分（0-100）")
    factors: dict[str, Any] = Field(
        default_factory=dict, description="各因子原始值"
    )
    reason: str = Field(default="", description="入选原因描述")


class ScreenerResponse(BaseModel):
    """选股筛选响应体"""

    total: int = Field(..., description="符合条件的股票总数")
    stocks: list[StockScoreItem] = Field(
        ..., description="评分最高的 Top N 股票列表"
    )


class FactorInfo(BaseModel):
    """因子元信息"""

    name: str = Field(..., description="因子名称")
    category: str = Field(..., description="因子类别：均线/动量/波动/量能/形态")
    type: str = Field(..., description="因子类型：数值/分类")
    description: str = Field(..., description="因子说明")


class FactorListResponse(BaseModel):
    """因子列表响应体"""

    total: int = Field(..., description="因子总数")
    factors: list[FactorInfo] = Field(..., description="因子信息列表")
