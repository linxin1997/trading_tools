"""
回测接口模块

提供策略回测执行和预置回测策略列表查询等 REST API。
数据库不可用时返回模拟回测数据（开发模式友好）。
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from app.services.backtester import backtester

router = APIRouter()


class Condition(BaseModel):
    """筛选条件"""
    factor: str
    op: str
    value: Any


class StrategyInput(BaseModel):
    """回测策略输入参数"""
    conditions: list[Condition]
    top_n: int = 10
    rebalance_freq: str = "daily"
    weights: dict[str, float] = {}

# 预置回测策略
_PRESET_STRATEGIES = [
    {
        "id": 1,
        "name": "低估值选股",
        "description": "选择市盈率低、市净率低的股票，等权持有",
        "conditions": [
            {"factor": "pe_ttm", "op": "<", "value": 15},
            {"factor": "pb", "op": "<", "value": 1.5},
        ],
        "top_n": 10,
        "rebalance_freq": "weekly",
    },
    {
        "id": 2,
        "name": "高动量选股",
        "description": "选择 20 日涨幅最高的股票，追强势股",
        "conditions": [
            {"factor": "momentum_20d", "op": ">", "value": 5},
        ],
        "top_n": 10,
        "rebalance_freq": "weekly",
    },
    {
        "id": 3,
        "name": "均线多头排列",
        "description": "选择 MA5 > MA10 > MA20 的股票，趋势跟随",
        "conditions": [
            {"factor": "ma_5", "op": ">", "value": 0},
            {"factor": "ma_10", "op": ">", "value": 0},
        ],
        "top_n": 10,
        "rebalance_freq": "weekly",
    },
    {
        "id": 4,
        "name": "资金流入选股",
        "description": "选择主力资金净流入最大的股票",
        "conditions": [
            {"factor": "net_amount", "op": ">", "value": 0},
        ],
        "top_n": 10,
        "rebalance_freq": "daily",
    },
]


@router.post("")
async def run_backtest(
    strategy: StrategyInput,
    start_date: str = Query(..., description="回测开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="回测结束日期 YYYY-MM-DD"),
):
    """
    执行策略回测

    传入策略参数（筛选条件、选股数量、调仓频率），执行历史回测。
    返回包含总收益、年化收益、夏普比率、最大回撤、净值序列和月度收益的结果。

    Args:
        strategy: 策略参数字典，需包含 conditions, top_n, rebalance_freq
        start_date: 回测开始日期
        end_date: 回测结束日期
    """
    logger.info("回测请求: start={}, end={}", start_date, end_date)

    # 参数校验
    if not strategy.conditions:
        raise HTTPException(status_code=400, detail="策略条件不能为空")
    if start_date >= end_date:
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    try:
        result = await backtester.run(strategy.model_dump(), start_date, end_date)
        logger.info("回测执行完成")
        return {"code": 0, "message": "success", "data": result}
    except Exception as e:
        logger.error("回测执行异常: {}", e)
        raise HTTPException(status_code=500, detail=f"回测执行失败: {str(e)}")


@router.get("/strategies")
async def list_backtest_strategies():
    """
    获取预置回测策略列表

    返回系统内置的几种常用回测策略，用户可直接使用或在此基础上修改。
    """
    logger.info("查询预置策略列表")
    return {"code": 0, "message": "success", "data": _PRESET_STRATEGIES}
