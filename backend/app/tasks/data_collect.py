"""
数据采集与因子计算任务模块

定义 Celery 定时任务：采集行情、计算因子、盘后风控、数据质量检查。
"""

import asyncio
import re
from datetime import date
from typing import Any

import pandas as pd
from celery import shared_task
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.factor_lib.base import FactorCalculator
from app.services.data_providers.akshare import AKShareProvider

settings = get_settings()


def _normalize_factor_name(name: str) -> str:
    """
    标准化因子名：MA20 → ma_20, MACD_DIF → macd_dif, BOLLUP → bollup

    Args:
        name: 原始因子列名（来自 DataFrame 列名）

    Returns:
        标准化后的小写+下划线因子名
    """
    # 处理 MA5 → ma_5, MA20 → ma_20 这类模式
    name = re.sub(r'(MA)(\d+)', r'ma_\2', name)
    name = re.sub(r'(MA)(\d+)_(MA)(\d+)', r'ma_\2_ma_\4', name)
    # 处理 BIAS5 → bias_5, BIAS10 → bias_10
    name = re.sub(r'(BIAS)(\d+)', r'bias_\2', name)
    # 处理 RSI6 → rsi_6, RSI14 → rsi_14, ATR14 → atr_14
    name = re.sub(r'(RSI)(\d+)', r'rsi_\2', name)
    name = re.sub(r'(ATR)(\d+)', r'atr_\2', name)
    # 处理 KDJ_K → kdj_k, BOLL_UP → boll_up 等（下划线分隔）
    name = name.lower()
    return name


async def _get_async_session() -> AsyncSession:
    """
    创建异步数据库会话（由调用方负责手动 close）

    注意：调用方使用完毕后必须调用 await session.close() 关闭会话。
    """
    from app.core.database import async_session_factory
    session = async_session_factory()
    return session


async def _compute_and_store_factors(trade_date: str = None):
    """
    计算并存储当日因子值

    Args:
        trade_date: 交易日，默认今天
    """
    if trade_date is None:
        trade_date = date.today().isoformat()

    provider = AKShareProvider()

    # 1. 从 stock_daily 获取当日有行情的股票列表
    session = await _get_async_session()
    try:
        result = await session.execute(
            text("SELECT DISTINCT symbol FROM stock_daily WHERE trade_date = :d"),
            {"d": trade_date},
        )
        symbols = [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"查询当日股票列表失败: {e}")
        return
    finally:
        await session.close()

    if not symbols:
        logger.warning(f"{trade_date} 无行情数据，跳过因子计算")
        return

    logger.info(f"开始计算 {trade_date} 因子，股票数: {len(symbols)}")

    # 2. 分批计算因子（每批 50 只）
    batch_size = 50
    total_rows = 0
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        batch_rows = []

        for symbol in batch:
            try:
                # 拉取近 60 日 K 线（足够计算全部因子）
                df = await provider.get_kline(symbol, period="daily")
                if df is None or df.empty:
                    continue

                # 转为 DataFrame 格式供 FactorCalculator 使用
                kline_df = pd.DataFrame(df)
                if kline_df.empty:
                    continue

                # 计算全部技术因子
                factor_df = FactorCalculator.compute_all(kline_df)

                # 提取最新一天的因子值
                latest = factor_df.iloc[-1]
                for col in factor_df.columns:
                    if col in ("symbol", "trade_date", "open", "high", "low", "close", "volume"):
                        continue
                    val = latest[col]
                    if pd.isna(val):
                        continue
                    batch_rows.append({
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "factor_name": _normalize_factor_name(col),
                        "value": float(val),
                    })

                # 计算资金因子（占位，需 Tushare 积分）
                money_factors = FactorCalculator.compute_money(symbol)
                for name, val in money_factors.items():
                    batch_rows.append({
                        "symbol": symbol,
                        "trade_date": trade_date,
                        "factor_name": name,
                        "value": val,
                    })

                # 计算舆情因子（从新闻表查询）
                try:
                    sentiment_factors = await FactorCalculator.compute_sentiment(symbol)
                    for name, val in sentiment_factors.items():
                        batch_rows.append({
                            "symbol": symbol,
                            "trade_date": trade_date,
                            "factor_name": name,
                            "value": float(val),
                        })
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"计算 {symbol} 因子异常: {e}")
                continue

        # 3. 批量写入
        if batch_rows:
            session = await _get_async_session()
            try:
                for row in batch_rows:
                    await session.execute(
                        text("""
                            INSERT INTO factor_value (symbol, trade_date, factor_name, value)
                            VALUES (:symbol, :trade_date, :factor_name, :value)
                            ON CONFLICT (symbol, trade_date, factor_name) DO UPDATE
                            SET value = EXCLUDED.value
                        """),
                        row,
                    )
                await session.commit()
                total_rows += len(batch_rows)
                logger.info(f"批次 {i // batch_size + 1}: 写入 {len(batch_rows)} 条因子")
            except Exception as e:
                await session.rollback()
                logger.error(f"批次写入失败: {e}")
            finally:
                await session.close()

        # 避免触发数据源限流
        await asyncio.sleep(0.5)

    logger.info(f"因子计算完成，共写入 {total_rows} 条因子")
    return total_rows


@shared_task(bind=True, max_retries=3)
def compute_and_store_factors(self, trade_date: str = None):
    """
    计算并存储因子（定时任务：交易日 15:30 触发）

    Args:
        trade_date: 交易日，默认今天
    """
    logger.info(f"开始因子计算任务: trade_date={trade_date or 'today'}")
    try:
        result = asyncio.run(_compute_and_store_factors(trade_date))
        logger.info(f"因子计算任务完成: {result}")
        return result
    except Exception as e:
        logger.error(f"因子计算任务失败: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def scan_risk_after_hours(self):
    """盘后风控扫描（定时任务：交易日 16:00 触发）"""
    from app.services.risk_guard import RiskGuard
    try:
        guard = RiskGuard()
        alerts = asyncio.run(guard.scan_after_hours())
        logger.info(f"盘后风控扫描完成，发现 {len(alerts)} 条告警")
        return [a.to_dict() for a in alerts]
    except Exception as e:
        logger.error(f"盘后风控扫描失败: {e}")
        raise self.retry(exc=e, countdown=120)
