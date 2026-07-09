"""
行情接口模块

提供 A 股大盘指数行情、板块行情、实时行情等 REST API。
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/index")
async def get_index_market():
    """获取大盘指数实时行情"""
    return {"code": 501, "message": "Not Implemented"}


@router.get("/sector")
async def get_sector_market():
    """获取板块行情数据"""
    return {"code": 501, "message": "Not Implemented"}


@router.get("/realtime")
async def get_realtime_quotes():
    """获取个股实时行情"""
    return {"code": 501, "message": "Not Implemented"}


@router.get("/depth")
async def get_order_book():
    """获取盘口深度数据"""
    return {"code": 501, "message": "Not Implemented"}
