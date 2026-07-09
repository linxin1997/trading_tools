"""
个股信息接口模块

提供个股详情、K 线数据、财务数据、资金流向等 REST API。
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/{code}")
async def get_stock_detail(code: str):
    """获取个股详细信息"""
    return {"code": 501, "message": "Not Implemented"}


@router.get("/{code}/kline")
async def get_stock_kline(code: str):
    """获取个股 K 线数据"""
    return {"code": 501, "message": "Not Implemented"}


@router.get("/{code}/financial")
async def get_stock_financial(code: str):
    """获取个股财务数据"""
    return {"code": 501, "message": "Not Implemented"}


@router.get("/{code}/moneyflow")
async def get_stock_moneyflow(code: str):
    """获取个股资金流向"""
    return {"code": 501, "message": "Not Implemented"}
