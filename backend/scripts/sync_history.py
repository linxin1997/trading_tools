"""
历史 K 线数据全量/增量同步脚本

数据源优先级：
  1. baostock（主源，无需鉴权，量化专用，前复权支持好）
  2. AKShare（备源，当 baostock 无数据时兜底）

用法：
    # 全量同步（全市场近 5 年日 K）
    python scripts/sync_history.py --start 2021-01-01 --end 2026-06-30

    # 单只股票
    python scripts/sync_history.py --code 000001.SZ --start 2024-01-01

    # 增量（仅同步缺失日期）
    python scripts/sync_history.py --incremental
"""

import argparse
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional

import akshare as ak
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.services.data_providers.baostock_provider import BaostockProvider

settings = get_settings()

# 常量
BATCH_SIZE = 50            # 每批并发拉取的股票数（baostock 并发压力小）
MAX_RETRIES = 2            # 单只股票最大重试次数
DAYS_PER_REQUEST = 365     # 每次请求的最大天数

# baostock 全局实例
_bs_provider: BaostockProvider | None = None


def get_bs_provider() -> BaostockProvider:
    """获取 BaostockProvider 单例"""
    global _bs_provider
    if _bs_provider is None:
        _bs_provider = BaostockProvider()
    return _bs_provider


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="历史 K 线数据同步脚本")
    parser.add_argument("--code", type=str, help="股票代码（可选，不传则全量同步）")
    parser.add_argument("--start", type=str, help="开始日期（YYYY-MM-DD，默认 5 年前）")
    parser.add_argument("--end", type=str, help="结束日期（YYYY-MM-DD，默认今天）")
    parser.add_argument("--incremental", action="store_true", help="增量模式：仅同步缺失日期")
    return parser.parse_args()


async def get_stock_list() -> list[str]:
    """
    获取 A 股全市场股票代码列表

    优先使用 baostock.query_all_stock，失败时回退 AKShare。

    Returns:
        股票代码列表，格式如 ['000001.SZ', '600519.SH']
    """
    logger.info("正在获取全市场股票列表...")
    try:
        provider = get_bs_provider()
        stocks = await provider.get_all_stock_codes()
        if stocks:
            codes = [s["symbol"] for s in stocks]
            logger.info(f"baostock 获取到 {len(codes)} 只股票")
            return codes
    except Exception as e:
        logger.warning(f"baostock 获取股票列表失败: {e}")

    # 备源：AKShare
    try:
        logger.info("回退 AKShare 获取股票列表...")
        df = await asyncio.to_thread(ak.stock_zh_a_spot_em)
        codes = df["代码"].tolist()
        logger.info(f"AKShare 获取到 {len(codes)} 只股票")
        return codes
    except Exception as e:
        logger.error(f"获取股票列表失败: {e}")
        return []


async def fetch_kline_baostock(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    使用 baostock 拉取日 K 线

    Args:
        symbol: 股票代码（如 000001.SZ）
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        DataFrame 或 None，列：symbol, trade_date, open, high, low, close,
        pre_close, volume, amount, pct_change, turn
    """
    try:
        provider = get_bs_provider()
        df = await provider.get_kline(symbol, start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            return df
    except Exception as e:
        logger.debug(f"baostock 拉取 {symbol} 失败: {e}")
    return None


async def fetch_kline_akshare(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    使用 AKShare 拉取日 K 线（备源）

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        DataFrame 或 None
    """
    for attempt in range(MAX_RETRIES):
        try:
            df = await asyncio.to_thread(
                ak.stock_zh_a_hist,
                symbol=symbol.split(".")[0],
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq",
            )
            if df is None or df.empty:
                return None

            df = df.rename(columns={
                "日期": "trade_date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
                "涨跌额": "change",
                "换手率": "turn",
            })
            df["symbol"] = symbol
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            return df

        except Exception as e:
            logger.warning(f"AKShare 第 {attempt + 1} 次拉取 {symbol} 失败: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)
    return None


async def fetch_kline(symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    拉取单只股票的日 K 线数据（主源 baostock → 备源 AKShare）

    Args:
        symbol: 股票代码
        start_date: 开始日期
        end_date: 结束日期

    Returns:
        DataFrame 或 None
    """
    # 主源：baostock
    df = await fetch_kline_baostock(symbol, start_date, end_date)
    if df is not None and not df.empty:
        return df

    # 备源：AKShare
    return await fetch_kline_akshare(symbol, start_date, end_date)


async def write_batch(session: AsyncSession, rows: list[dict]):
    """
    批量写入 TimescaleDB

    Args:
        session: 数据库会话
        rows: 数据行列表
    """
    if not rows:
        return

    sub_batch_size = 500
    for i in range(0, len(rows), sub_batch_size):
        sub = rows[i: i + sub_batch_size]
        for row in sub:
            await session.execute(
                text("""
                    INSERT INTO stock_daily
                        (symbol, trade_date, open, high, low, close,
                         pre_close, volume, amount, pct_change, turn)
                    VALUES (:symbol, :trade_date, :open, :high, :low, :close,
                            :pre_close, :volume, :amount, :pct_change, :turn)
                    ON CONFLICT (symbol, trade_date) DO NOTHING
                """),
                row,
            )
    await session.commit()
    logger.info(f"写入 {len(rows)} 条数据")


async def sync_all(codes: list[str], start_date: str, end_date: str, session: AsyncSession):
    """
    全量同步所有股票的日 K 线

    Args:
        codes: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
        session: 数据库会话
    """
    total = len(codes)
    success = 0
    failed = 0
    total_rows = 0

    for i in range(0, total, BATCH_SIZE):
        batch = codes[i: i + BATCH_SIZE]
        tasks = [fetch_kline(code, start_date, end_date) for code in batch]
        results = await asyncio.gather(*tasks)

        for code, df in zip(batch, results):
            if df is not None and not df.empty:
                rows = df.to_dict("records")
                await write_batch(session, rows)
                success += 1
                total_rows += len(rows)
            else:
                failed += 1
                logger.debug(f"{code}: 无数据")

        await asyncio.sleep(0.3)

        processed = min(i + BATCH_SIZE, total)
        logger.info(f"进度: {processed}/{total} | 成功: {success} | 失败: {failed} | 总行数: {total_rows}")

    logger.info(f"同步完成。成功: {success}, 失败: {failed}, 总行数: {total_rows}")


async def get_db_session() -> AsyncSession:
    """创建数据库异步会话"""
    if settings.DATABASE_URL:
        db_url = settings.DATABASE_URL
    else:
        db_url = (
            f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        )
    engine = create_async_engine(db_url, pool_size=5, max_overflow=10)
    session = AsyncSession(bind=engine)
    return session


async def sync_stock_info():
    """
    同步股票基本信息（含上市日期）

    优先使用 baostock 的 query_all_stock 获取代码和名称。
    上市日期取自 baostock（需要单独的季频查询）。
    """
    logger.info("正在同步股票基本信息...")
    try:
        provider = get_bs_provider()
        stocks = await provider.get_all_stock_codes()
        if not stocks:
            logger.warning("baostock 股票列表为空，跳过 stock_info 同步")
            return

        session = await get_db_session()
        try:
            for s in stocks:
                await session.execute(
                    text("""
                        INSERT INTO stock_info (symbol, name)
                        VALUES (:symbol, :name)
                        ON CONFLICT (symbol) DO UPDATE
                        SET name = EXCLUDED.name
                    """),
                    {"symbol": s["symbol"], "name": s["name"]},
                )
            await session.commit()
            logger.info(f"同步 stock_info 完成，共 {len(stocks)} 条")
        except Exception as e:
            await session.rollback()
            logger.error(f"写入 stock_info 失败: {e}")
        finally:
            await session.close()

    except Exception as e:
        logger.error(f"同步 stock_info 失败: {e}")


async def main_async():
    """异步主入口"""
    args = parse_args()

    end = args.end or date.today().strftime("%Y-%m-%d")
    if args.start:
        start = args.start
    elif args.incremental:
        start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    else:
        start = (date.today() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")

    logger.info(f"同步范围: {start} ~ {end}")

    # 同步股票基本信息
    await sync_stock_info()

    # 获取股票列表
    if args.code:
        codes = [args.code]
    else:
        codes = await get_stock_list()

    if not codes:
        logger.error("股票列表为空，退出")
        return

    session = await get_db_session()
    try:
        await sync_all(codes, start, end, session)
    finally:
        await session.close()
        get_bs_provider().logout()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
