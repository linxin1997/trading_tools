"""
通用 Pydantic 校验模型模块

定义统一的分页、响应格式等通用模式。
"""

from pydantic import BaseModel
from typing import Any, TypeVar, Generic

T = TypeVar("T")


class ApiResponse(BaseModel):
    """统一 API 响应格式"""

    code: int = 0
    message: str = "success"
    data: Any = None


class PaginationParams(BaseModel):
    """分页参数"""

    page: int = 1
    page_size: int = 20


class PaginatedResult(BaseModel, Generic[T]):
    """分页结果"""

    total: int
    page: int
    page_size: int
    items: list[T]
