"""计算因子并写入数据库"""
import sys; sys.path.insert(0,'.')
import asyncio, re
from datetime import date
import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.services.factor_lib.base import FactorCalculator
from app.services.data_providers.baostock_provider import BaostockProvider

DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/trading"

async def main():
    engine = create_async_engine(DB_URL)
    bs = BaostockProvider()
    total = 0

    async with engine.connect() as conn:
        r = await conn.execute(text("SELECT DISTINCT symbol FROM stock_daily"))
        symbols = [row[0] for row in r.fetchall()]
        print(f"Stocks: {len(symbols)}")

        for symbol in symbols:
            df = await bs.get_kline(symbol, start_date="2024-12-01", end_date="2025-06-30")
            if df is None or df.empty:
                continue
            factor_df = FactorCalculator.compute_all(pd.DataFrame(df))
            if factor_df is None or factor_df.empty:
                continue

            latest = factor_df.iloc[-1]
            td = latest["trade_date"]
            if isinstance(td, str):
                td = date.fromisoformat(td)

            skip_cols = {"symbol","trade_date","open","high","low","close","volume",
                        "amount","pre_close","turn","pct_change","adjustflag","trade_status","is_st"}
            for col in factor_df.columns:
                if col in skip_cols:
                    continue
                val = latest[col]
                if pd.isna(val):
                    continue
                fn = col.lower()
                fn = re.sub(r"(MA)(\d+)", r"ma_\2", fn)
                fn = re.sub(r"(MA)(\d+)_(MA)(\d+)", r"ma_\2_ma_\4", fn)
                fn = re.sub(r"(BIAS)(\d+)", r"bias_\2", fn)
                fn = re.sub(r"(RSI)(\d+)", r"rsi_\2", fn)
                fn = re.sub(r"(ATR)(\d+)", r"atr_\2", fn)
                fn = fn.lower()
                await conn.execute(
                    text("INSERT INTO factor_value (symbol,trade_date,factor_name,value) VALUES (:s,:d,:f,:v) ON CONFLICT (symbol,trade_date,factor_name) DO UPDATE SET value=EXCLUDED.value"),
                    {"s": symbol, "d": td, "f": fn, "v": float(val)},
                )
                total += 1
            print(f"  {symbol} done (total factors: {total})")

        await conn.commit()
    await engine.dispose()
    bs.logout()
    print(f"\nTotal factor values stored: {total}")

asyncio.run(main())
