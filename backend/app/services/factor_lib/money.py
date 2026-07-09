"""
资金面因子模块

实现与资金流向相关的因子计算，包括北向资金、主力资金等。
当前为占位实现，实际数据需要 Tushare/AkShare 等数据源配合。

函数列表：
    compute_north_flow() — 北向资金因子（占位）
    compute_main_inflow() — 主力资金因子（占位）
"""

from typing import Any

import pandas as pd
from loguru import logger


def compute_north_flow(code: str, days: int = 5) -> dict[str, float]:
    """计算北向资金因子

    北向资金（沪深港通）是外资流入 A 股的重要指标。
    实际使用时需通过 Tushare 的 `moneyflow_hsgt` 接口获取数据。

    Args:
        code: 股票代码（如 "000001"）
        days: 统计天数

    Returns:
        因子值字典，包含以下键（占位返回 0）：
            - NORTH_FLOW_NET: 北向净流入（万元）
            - NORTH_FLOW_5D: 5 日累计净流入
            - NORTH_FLOW_20D: 20 日累计净流入
    """
    logger.info(f"北向资金因子查询: code={code}, days={days}")
    # TODO: 接入 Tushare 后替换为真实数据查询
    # from tushare import pro as ts_pro
    # df = ts_pro.moneyflow_hsgt(start_date=..., end_date=...)
    logger.warning("北向资金因子为占位实现，需配置 TUSHARE_TOKEN 后生效")
    return {
        "NORTH_FLOW_NET": 0.0,
        "NORTH_FLOW_5D": 0.0,
        "NORTH_FLOW_20D": 0.0,
    }


def compute_main_inflow(code: str, days: int = 5) -> dict[str, float]:
    """计算主力资金因子

    主力资金通常指大单（超大单 + 大单）的资金流向。
    实际使用时需通过 Tushare 的 `moneyflow` 接口获取个股资金流数据。

    Args:
        code: 股票代码（如 "000001"）
        days: 统计天数

    Returns:
        因子值字典，包含以下键（占位返回 0）：
            - MAIN_INFLOW_NET: 主力净流入（万元）
            - MAIN_INFLOW_5D: 5 日主力净流入均值
            - MAIN_INFLOW_RATIO: 主力净流入 / 成交额
    """
    logger.info(f"主力资金因子查询: code={code}, days={days}")
    # TODO: 接入 Tushare 后替换为真实数据查询
    # df = ts_pro.moneyflow(ts_code=code, start_date=..., end_date=...)
    logger.warning("主力资金因子为占位实现，需配置 TUSHARE_TOKEN 后生效")
    return {
        "MAIN_INFLOW_NET": 0.0,
        "MAIN_INFLOW_5D": 0.0,
        "MAIN_INFLOW_RATIO": 0.0,
    }


def compute_all_money(code: str) -> dict[str, float]:
    """计算全部资金因子（合并北向 + 主力）

    Args:
        code: 股票代码

    Returns:
        合并后的因子值字典
    """
    result: dict[str, float] = {}
    result.update(compute_north_flow(code))
    result.update(compute_main_inflow(code))
    logger.info(f"资金因子计算完成，共 {len(result)} 项: {list(result.keys())}")
    return result
