"""
选股器接口模块

提供基于多因子模型的选股 REST API：
    POST /api/v1/screener  — 执行选股评分
    GET  /api/v1/factors   — 获取因子列表（供前端构建条件选择器）
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.schemas.screener import (
    ScreenerRequest,
    ScreenerResponse,
    FactorListResponse,
    FactorInfo,
)
from app.schemas.common import ApiResponse
from app.services.stock_picker import StockPicker
from app.services.factor_lib.base import FactorCalculator

router = APIRouter()


@router.post("/screener", response_model=ApiResponse)
async def screen_stocks(
    req: ScreenerRequest,
    session: AsyncSession = Depends(get_db),
):
    """执行选股评分

    接收筛选条件和因子权重，返回评分最高的 Top N 股票。

    Args:
        req: 筛选请求体，包含 conditions、weights 和 top_n
        session: 数据库会话（依赖注入）

    Returns:
        统一响应，data 字段为 ScreenerResponse
    """
    try:
        logger.info(
            f"选股请求: conditions={len(req.conditions)}条, "
            f"weights={len(req.weights)}项, top_n={req.top_n}"
        )
        picker = StockPicker()
        # 将 conditions 转为字典列表传给 screen 方法
        conditions_dict = [c.model_dump() for c in req.conditions]
        result = await picker.screen(
            conditions=conditions_dict,
            weights=req.weights,
            top_n=req.top_n,
            session=session,
        )
        return ApiResponse(code=0, message="选股完成", data=result)
    except ValueError as e:
        logger.warning(f"选股参数错误: {e}")
        return ApiResponse(code=400, message=str(e), data=None)
    except Exception as e:
        logger.error(f"选股失败: {e}", exc_info=True)
        return ApiResponse(code=500, message=f"选股服务异常: {str(e)}", data=None)


@router.get("/factors", response_model=ApiResponse)
async def list_factors(category: str | None = None):
    """获取可用因子列表

    供前端构建条件选择器使用，可按类别筛选。

    Args:
        category: 因子类别筛选（可选），如 "均线"、"动量"、"波动"、"量能"、"形态"

    Returns:
        统一响应，data 字段为 FactorListResponse
    """
    try:
        factors = FactorCalculator.list_factors(category=category)
        factor_list = [
            FactorInfo(
                name=name,
                category=info["category"],
                type=info["type"],
                description=info["description"],
            )
            for name, info in factors.items()
        ]
        return ApiResponse(
            code=0,
            message="success",
            data=FactorListResponse(total=len(factor_list), factors=factor_list).model_dump(),
        )
    except Exception as e:
        logger.error(f"获取因子列表失败: {e}", exc_info=True)
        return ApiResponse(code=500, message=f"获取因子列表异常: {str(e)}", data=None)
