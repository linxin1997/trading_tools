"""
策略回测引擎模块

实现 Backtester 回测引擎，支持多因子选股策略的历史回测。
关键设计：避免前视偏差（信号日 T 日收盘计算，T+1 日开盘成交）
和幸存者偏差（按上市/退市日期过滤历史可交易集合）。

因子数据从 TimescaleDB 的 factor_value 长表查询，使用小写+下划线因子名规范。
数据库不可用时返回模拟回测数据（开发模式友好）。
"""

import math
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from loguru import logger


class Backtester:
    """策略回测引擎"""

    def __init__(self):
        """初始化回测引擎"""
        self.mock_on_error = False
        logger.info("回测引擎初始化完成")

    async def _query_factor_data(self, start_date: str, end_date: str, factor_names: list[str]) -> pd.DataFrame:
        """
        查询因子数据 + 涨跌幅

        从 factor_value 长表查询因子数据，同时从 stock_daily 获取 pct_change。
        返回宽表 DataFrame（列为 symbol, trade_date, factor1, factor2, ..., pct_change）。

        Args:
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            factor_names: 需要查询的因子名称列表

        Returns:
            包含因子值和涨跌幅的 DataFrame
        """
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import text

            if async_session_factory is None:
                logger.warning("数据库未初始化，无法查询因子数据")
                return pd.DataFrame()

            # 白名单校验因子名
            from app.services.factor_lib.base import FactorCalculator

            FACTOR_REGISTRY = FactorCalculator.list_factors()
            valid_factors = set(FACTOR_REGISTRY.keys())
            for f in factor_names:
                if f not in valid_factors:
                    raise ValueError(f"未知因子: {f}")

            factor_list = ", ".join([f"'{f}'" for f in factor_names])

            async with async_session_factory() as session:
                # 1. 查询因子值
                sql = f"""
                    SELECT symbol, trade_date, factor_name, value
                    FROM factor_value
                    WHERE trade_date BETWEEN :start AND :end
                      AND factor_name IN ({factor_list})
                    ORDER BY symbol, trade_date, factor_name
                """
                result = await session.execute(text(sql), {"start": start_date, "end": end_date})
                rows = result.fetchall()

                # 2. 额外查询涨跌幅（从 stock_daily 获取）
                pct_sql = """
                    SELECT symbol, trade_date, pct_change
                    FROM stock_daily
                    WHERE trade_date BETWEEN :start AND :end
                    ORDER BY symbol, trade_date
                """
                pct_result = await session.execute(text(pct_sql), {"start": start_date, "end": end_date})
                pct_rows = pct_result.fetchall()

            # 3. 构造因子 DataFrame（长表→宽表 pivot）
            df = pd.DataFrame(rows, columns=["symbol", "trade_date", "factor_name", "value"])
            if df.empty:
                return pd.DataFrame()

            df_pivot = df.pivot_table(index=["symbol", "trade_date"], columns="factor_name", values="value").reset_index()

            # 4. 合并涨跌幅
            df_pct = pd.DataFrame(pct_rows, columns=["symbol", "trade_date", "pct_change"])
            df_pct["trade_date"] = pd.to_datetime(df_pct["trade_date"])
            df_pivot["trade_date"] = pd.to_datetime(df_pivot["trade_date"])

            df_pivot = df_pivot.merge(df_pct, on=["symbol", "trade_date"], how="left")

            logger.info("回测因子数据查询完成，共 {} 条记录", len(df_pivot))
            return df_pivot

        except Exception as e:
            logger.error("回测因子数据查询异常: {}", e)
            return pd.DataFrame()

    async def run(self, strategy: dict, start_date: str, end_date: str) -> dict:
        """
        执行回测

        回测流程：
        1. 按日/周遍历时间窗口
        2. 按上市/退市日期过滤每个交易日可交易集合（避免幸存者偏差）
        3. 信号日在 t 日收盘计算，t+1 日开盘成交（避免前视偏差）
        4. 从 factor_value 筛选符合条件的股票
        5. 等权买入 Top N
        6. 下个窗口日调仓
        7. 计算每日组合净值，扣除交易成本（佣金 0.03% + 印花税 0.05%）

        Args:
            strategy: 策略参数，需包含 conditions（筛选条件列表）、
                      top_n（选股数量）、rebalance_freq（调仓频率：daily/weekly）
            start_date: 回测开始日期 "YYYY-MM-DD"
            end_date: 回测结束日期 "YYYY-MM-DD"

        Returns:
            {
                "summary": {
                    "total_return": 85.32,
                    "annual_return": 22.15,
                    "sharpe_ratio": 1.85,
                    "max_drawdown": -12.5,
                },
                "nav_series": [{"date", "strategy", "benchmark"}, ...],
                "monthly_returns": {"2023-01": 3.2, ...}
            }
        """
        logger.info("开始执行回测: start={}, end={}, strategy={}", start_date, end_date, strategy.get("name", ""))

        # 提取策略参数
        conditions = strategy.get("conditions", [])
        top_n = int(strategy.get("top_n", 10))
        rebalance_freq = strategy.get("rebalance_freq", "weekly")

        # 交易成本参数
        commission_rate = 0.0003  # 佣金 0.03%
        stamp_tax_rate = 0.0005   # 印花税 0.05%

        try:
            # 从 conditions 中提取需要查询的因子名称
            factor_names = set()
            for cond in conditions:
                factor_names.add(cond.get("factor", ""))
            factor_names.discard("")

            if not factor_names:
                logger.warning("回测条件中未指定任何因子，返回模拟数据")
                return self._mock_result(start_date, end_date)

            # 从 TimescaleDB 查询因子数据 + 涨跌幅（返回宽表 DataFrame）
            raw_df = await self._query_factor_data(start_date, end_date, list(factor_names))

            if raw_df.empty:
                logger.warning("回测查询无数据，返回模拟数据")
                return self._mock_result(start_date, end_date)

            # ---- Step 1: 按日期组织数据 ----
            # raw_df 为宽表格式（列: symbol, trade_date, factor1, factor2, ..., pct_change）
            daily_data: dict[str, list[dict]] = defaultdict(list)
            for _, row in raw_df.iterrows():
                record = {"symbol": row["symbol"], "trade_date": str(row["trade_date"])[:10]}
                for col in raw_df.columns:
                    if col in ("symbol", "trade_date"):
                        continue
                    val = row[col]
                    if pd.notna(val):
                        record[col] = val
                daily_date_str = str(row["trade_date"])[:10]
                daily_data[daily_date_str].append(record)

            # 获取所有交易日并按序排列
            trading_days = sorted(daily_data.keys())

            if not trading_days:
                return self._mock_result(start_date, end_date)

            # ---- Step 2: 过滤幸存者偏差 ----
            # 从 stock_info 表查询每个交易日可交易的股票，剔除未上市和已退市的
            for day in trading_days:
                tradable = await self._get_tradable_stocks(day)
                if tradable is not None:  # None 表示降级，不过滤
                    daily_data[day] = [s for s in daily_data[day] if s.get("symbol", "") in tradable]

            # ---- Step 3: 确定调仓日 ----
            rebalance_days = self._get_rebalance_days(trading_days, rebalance_freq)

            # ---- Step 4: 模拟回测 ----
            nav_series = []
            strategy_nav = 1.0
            benchmark_nav = 1.0
            daily_returns = []
            prev_holdings: list[dict] = []  # 上一周期持仓，用于当日收益计算

            for day_idx, day in enumerate(trading_days):
                day_data = daily_data[day]

                # 计算基准收益（全市场等权）
                benchmark_return = self._calc_benchmark_return(day_data)
                benchmark_nav *= (1 + benchmark_return)

                # 用上一周期持仓计算当日收益（T 日选股，T+1 日起算，避免前视偏差）
                if prev_holdings:
                    holding_returns = []
                    for h in prev_holdings:
                        code = h.get("symbol", "")
                        day_return = self._get_stock_return(day_data, code)
                        holding_returns.append(day_return)

                    if holding_returns:
                        strategy_return = sum(holding_returns) / len(holding_returns)

                        # 扣除交易成本（调仓日：卖出旧持仓 + 买入新持仓）
                        if day in rebalance_days:
                            turnover = 1.0  # 完全调仓
                            strategy_return -= turnover * (commission_rate + stamp_tax_rate)

                        strategy_nav *= (1 + strategy_return)
                        daily_returns.append(strategy_return)
                    else:
                        daily_returns.append(0.0)
                else:
                    daily_returns.append(0.0)

                # 调仓日用 T 日因子筛选股票，T+1 日起用新持仓计算收益
                if day in rebalance_days and day_idx > 0:
                    candidates = self._filter_stocks(day_data, conditions)
                    candidates.sort(key=lambda x: self._score_stock(x), reverse=True)
                    prev_holdings = candidates[:top_n]

                nav_series.append({
                    "date": day,
                    "strategy": round(strategy_nav, 4),
                    "benchmark": round(benchmark_nav, 4),
                })

            # ---- Step 5: 计算绩效指标 ----
            total_return = round((strategy_nav - 1.0) * 100, 2)
            annual_return = self._calc_annual_return(strategy_nav, len(trading_days))
            sharpe = self._calc_sharpe(daily_returns)
            max_dd = self._calc_max_drawdown([n["strategy"] for n in nav_series])
            monthly_returns = self._calc_monthly_returns(nav_series, trading_days)

            logger.info(
                "回测完成: 总收益={}%, 年化={}%, 夏普={}, 最大回撤={}%",
                total_return, annual_return, sharpe, max_dd,
            )

            return {
                "summary": {
                    "total_return": total_return,
                    "annual_return": round(annual_return, 2),
                    "sharpe_ratio": round(sharpe, 2),
                    "max_drawdown": round(max_dd, 2),
                },
                "nav_series": nav_series,
                "monthly_returns": monthly_returns,
            }

        except Exception as e:
            logger.error("回测执行异常: {}", e)
            if self.mock_on_error:
                logger.warning("回测返回模拟数据！MOCK_ON_ERROR=True")
                return self._mock_result(start_date, end_date)
            raise

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------

    async def _get_tradable_stocks(self, trade_date: str) -> list[str] | None:
        """
        获取指定日期可交易的股票列表（过滤幸存者偏差）

        从 stock_info 表查询：
        - list_date <= trade_date（已上市）
        - delist_date IS NULL OR delist_date > trade_date（未退市）

        如果查询失败，返回 None（降级为不过滤，不阻塞回测流程）。

        Args:
            trade_date: 交易日 YYYY-MM-DD

        Returns:
            可交易的股票代码列表，异常时返回 None
        """
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import text

            if async_session_factory is None:
                logger.warning("数据库未初始化，跳过幸存者偏差过滤")
                return None

            async with async_session_factory() as session:
                result = await session.execute(
                    text("""
                        SELECT symbol FROM stock_info
                        WHERE (list_date <= :trade_date OR list_date IS NULL)
                        AND (delist_date IS NULL OR delist_date > :trade_date)
                    """),
                    {"trade_date": trade_date},
                )
                return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"获取可交易股票列表失败（降级为不过滤）: {e}")
            return None

    def _get_rebalance_days(self, trading_days: list[str], freq: str) -> set[str]:
        """根据调仓频率确定调仓日"""
        if freq == "daily":
            # 每日调仓，跳过第一天（T+1 规则）
            return set(trading_days[1:])
        elif freq == "weekly":
            # 每周一调仓
            rebalance = set()
            for day in trading_days:
                dt = datetime.strptime(day, "%Y-%m-%d")
                if dt.weekday() == 0:  # 周一
                    rebalance.add(day)
            return rebalance
        else:
            # 默认每周
            return self._get_rebalance_days(trading_days, "weekly")

    def _filter_stocks(self, day_data: list[dict], conditions: list[dict]) -> list[dict]:
        """根据筛选条件过滤股票"""
        result = []
        for row in day_data:
            match = True
            for cond in conditions:
                factor = cond.get("factor", "")
                op = cond.get("op", "")
                value = cond.get("value", 0)
                actual = row.get(factor)
                if actual is None:
                    match = False
                    break
                try:
                    actual = float(actual)
                    value = float(value)
                    if op == ">" and not (actual > value):
                        match = False
                        break
                    elif op == ">=" and not (actual >= value):
                        match = False
                        break
                    elif op == "<" and not (actual < value):
                        match = False
                        break
                    elif op == "<=" and not (actual <= value):
                        match = False
                        break
                    elif op == "==" and not (actual == value):
                        match = False
                        break
                except (ValueError, TypeError):
                    match = False
                    break
            if match:
                result.append(row)
        return result

    def _score_stock(self, stock: dict) -> float:
        """对股票进行综合评分（用于排序选 Top N）"""
        score = 0.0
        # 用动量因子（如果有）作为评分依据
        momentum = stock.get("momentum_20d") or stock.get("pct_change") or 0
        try:
            score += float(momentum)
        except (ValueError, TypeError):
            pass
        return score

    def _get_stock_return(self, day_data: list[dict], code: str) -> float:
        """获取个股当日收益率"""
        for row in day_data:
            if row.get("symbol") == code:
                pct_change = row.get("pct_change", 0)
                try:
                    return float(pct_change) / 100.0
                except (ValueError, TypeError):
                    return 0.0
        return 0.0

    def _calc_benchmark_return(self, day_data: list[dict]) -> float:
        """计算基准收益（全市场等权平均）"""
        returns = []
        for row in day_data:
            pct_change = row.get("pct_change", 0)
            try:
                returns.append(float(pct_change))
            except (ValueError, TypeError):
                continue
        if not returns:
            return 0.0
        return sum(returns) / len(returns) / 100.0

    @staticmethod
    def _calc_annual_return(final_nav: float, trading_days: int) -> float:
        """
        计算年化收益率

        Args:
            final_nav: 最终净值
            trading_days: 交易天数

        Returns:
            年化收益率（百分比）
        """
        if trading_days <= 0 or final_nav <= 0:
            return 0.0
        years = trading_days / 252.0  # 一年约 252 个交易日
        if years <= 0:
            return 0.0
        return (final_nav ** (1.0 / years) - 1.0) * 100.0

    @staticmethod
    def _calc_sharpe(returns: list[float]) -> float:
        """
        计算夏普比率

        Sharpe = (平均收益率 - 无风险利率) / 收益率标准差
        年化处理：日夏普 * sqrt(252)

        Args:
            returns: 每日收益率列表

        Returns:
            年化夏普比率
        """
        if len(returns) < 2:
            return 0.0

        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance)

        if std_dev == 0:
            return 0.0

        # 无风险利率取 2%（年化），换算为日
        risk_free_daily = 0.02 / 252.0
        daily_sharpe = (avg_return - risk_free_daily) / std_dev
        return daily_sharpe * math.sqrt(252.0)

    @staticmethod
    def _calc_max_drawdown(nav: list[float]) -> float:
        """
        计算最大回撤

        MDD = max(1 - 当前净值/历史最高净值)

        Args:
            nav: 净值序列

        Returns:
            最大回撤百分比（负数）
        """
        if not nav:
            return 0.0

        max_drawdown = 0.0
        peak = nav[0]

        for value in nav:
            if value > peak:
                peak = value
            drawdown = (value - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown

        return round(max_drawdown * 100, 2)

    @staticmethod
    def _calc_monthly_returns(
        nav_series: list[dict],
        trading_days: list[str],
    ) -> dict[str, float]:
        """计算月度收益率"""
        monthly_returns = {}
        monthly_start_nav = None
        current_month = None

        for i, entry in enumerate(nav_series):
            day = entry["date"]
            month = day[:7]  # "YYYY-MM"
            nav_val = entry["strategy"]

            if month != current_month:
                if current_month and monthly_start_nav is not None and monthly_start_nav > 0:
                    monthly_return = round((nav_series[i - 1]["strategy"] / monthly_start_nav - 1) * 100, 2)
                    monthly_returns[current_month] = monthly_return
                current_month = month
                monthly_start_nav = nav_val

        # 最后一个月
        if current_month and monthly_start_nav and monthly_start_nav > 0:
            monthly_return = round((nav_series[-1]["strategy"] / monthly_start_nav - 1) * 100, 2)
            monthly_returns[current_month] = monthly_return

        return monthly_returns

    def _mock_result(self, start_date: str, end_date: str) -> dict:
        """生成模拟回测结果（开发模式友好）"""
        logger.warning("回测返回模拟数据！MOCK_ON_ERROR=True")
        logger.info("生成模拟回测数据: {} ~ {}", start_date, end_date)

        # 生成模拟净值序列
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        days = (end_dt - start_dt).days

        nav_series = []
        strategy_nav = 1.0
        benchmark_nav = 1.0
        daily_returns = []
        current = start_dt

        while current <= end_dt:
            if current.weekday() < 5:  # 只生成交易日
                # 模拟策略收益（年化约 18%）
                strategy_ret = random.gauss(0.0007, 0.015)
                # 模拟基准收益（年化约 8%）
                benchmark_ret = random.gauss(0.0003, 0.012)

                strategy_nav *= (1 + strategy_ret)
                benchmark_nav *= (1 + benchmark_ret)
                daily_returns.append(strategy_ret)

                nav_series.append({
                    "date": current.strftime("%Y-%m-%d"),
                    "strategy": round(strategy_nav, 4),
                    "benchmark": round(benchmark_nav, 4),
                })
            current += timedelta(days=1)

        total_return = round((strategy_nav - 1.0) * 100, 2)
        annual_return = self._calc_annual_return(strategy_nav, len(daily_returns))
        sharpe = self._calc_sharpe(daily_returns)
        max_dd = self._calc_max_drawdown([n["strategy"] for n in nav_series])

        return {
            "summary": {
                "total_return": total_return,
                "annual_return": round(annual_return, 2),
                "sharpe_ratio": round(sharpe, 2),
                "max_drawdown": round(max_dd, 2),
            },
            "nav_series": nav_series,
            "monthly_returns": {"2025-01": 2.5, "2025-02": -1.2, "2025-03": 3.8},
        }


# 全局回测引擎单例
backtester = Backtester()
