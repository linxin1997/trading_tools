"""
查询路由模块

支持 TimescaleDB（超表、连续聚合）和 DuckDB（本地分析）两种查询引擎。
根据查询类型自动路由到合适的数据库执行。

路由策略：
    - screener_query()：选股查询 → 直接查 TimescaleDB（单日简单查询 PG 足够快）
    - backtest_query()：回测查询 → 走 DuckDB（历史全表扫描，DuckDB 列存快 10x）
"""

from typing import Any
from pathlib import Path

import duckdb
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import get_settings


class QueryRouter:
    """
    查询路由类

    自动将查询请求分发到 TimescaleDB 或 DuckDB，
    实现热数据（近期）和冷数据（历史）的分级存储与查询。
    """

    def __init__(self):
        """初始化 DuckDB 本地连接"""
        settings = get_settings()
        db_path = Path(settings.DUCKDB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._duck_conn = duckdb.connect(str(db_path))

    async def query_timescale(
        self, session: AsyncSession, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        在 TimescaleDB 上执行查询

        Args:
            session: 异步数据库会话
            sql: SQL 查询语句
            params: 查询参数

        Returns:
            查询结果列表，每行为一个字典
        """
        result = await session.execute(text(sql), params or {})
        rows = result.fetchall()
        column_names = list(result.keys())
        return [dict(zip(column_names, row)) for row in rows]

    def query_duckdb(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        在本地 DuckDB 上执行查询

        用于历史数据分析、离线计算等场景。

        Args:
            sql: SQL 查询语句
            params: 查询参数列表

        Returns:
            查询结果列表，每行为一个字典
        """
        result = self._duck_conn.execute(sql, params or [])
        column_names = [desc[0] for desc in result.description]
        rows = result.fetchall()
        return [dict(zip(column_names, row)) for row in rows]

    def close(self):
        """关闭 DuckDB 连接"""
        if self._duck_conn:
            self._duck_conn.close()
            logger.info("DuckDB 连接已关闭")

    @staticmethod
    async def screener_query(
        session: AsyncSession,
        table: str,
        conditions: list[dict],
        date: str,
    ) -> list[dict[str, Any]]:
        """选股查询：直接查 TimescaleDB

        单日因子筛选查询直接走 PostgreSQL/TimescaleDB，
        PG 的索引和行存对单日点查足够快。

        Args:
            session: 数据库会话
            table: 表名（如 "factor_value"）
            conditions: 筛选条件列表，每项为 {"factor": str, "op": str, "value": Any}
            date: 查询日期 "YYYY-MM-DD"

        Returns:
            符合条件的股票列表
        """
        # 表名白名单校验，防止 SQL 注入
        VALID_TABLES = {"factor_value", "stock_daily"}
        if table not in VALID_TABLES:
            raise ValueError(f"无效的表名: {table}")

        logger.info(f"选股查询路由到 TimescaleDB: table={table}, date={date}, conditions={len(conditions)}条")

        # 从 conditions 提取 factor 名称列表
        factor_names = [c["factor"] for c in conditions]

        # 白名单校验：拒绝未知因子名，防止 SQL 注入
        from app.services.factor_lib.base import FactorCalculator

        FACTOR_REGISTRY = FactorCalculator.FACTOR_REGISTRY
        for fname in set(factor_names):
            if fname not in FACTOR_REGISTRY:
                raise ValueError(f"未知因子: {fname}")

        factor_list_str = ", ".join([f"'{f}'" for f in set(factor_names)])

        # 长表查询：直接返回 (code, name, factor_name, value) 四列
        # 由调用方用 Pandas pivot_table 转为宽表用于评分计算
        sql = text(f"""
            SELECT fv.symbol, si.name, fv.factor_name, fv.value
            FROM {table} fv
            LEFT JOIN stock_info si ON si.symbol = fv.symbol
            WHERE fv.trade_date = :query_date
              AND fv.factor_name IN ({factor_list_str})
            ORDER BY fv.symbol, fv.factor_name
        """)

        result = await session.execute(sql, {"query_date": date})
        rows = result.fetchall()
        column_names = list(result.keys())
        logger.info(f"选股查询完成，返回 {len(rows)} 条记录（长表格式）")
        return [dict(zip(column_names, row)) for row in rows]

    @staticmethod
    def backtest_query(
        table: str,
        conditions: list[dict],
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """回测查询：走 DuckDB

        历史全表扫描对 PG 压力大，DuckDB 列存格式在聚合分析场景快 10 倍以上。
        此方法创建 DuckDB 连接并加载数据执行查询。

        Args:
            table: 表名
            conditions: 筛选条件
            start: 开始日期 "YYYY-MM-DD"
            end: 结束日期 "YYYY-MM-DD"

        Returns:
            查询结果列表
        """
        # 表名白名单校验，防止 SQL 注入
        VALID_TABLES = {"factor_value", "stock_daily"}
        if table not in VALID_TABLES:
            raise ValueError(f"无效的表名: {table}")

        logger.info(f"回测查询路由到 DuckDB: table={table}, start={start}, end={end}")

        settings = get_settings()
        db_path = Path(settings.DUCKDB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = duckdb.connect(str(db_path))

        try:
            # 构建 DuckDB 查询
            factor_names = list(set([c["factor"] for c in conditions]))

            # 白名单校验：拒绝未知因子名，防止 SQL 注入
            from app.services.factor_lib.base import FactorCalculator

            FACTOR_REGISTRY = FactorCalculator.FACTOR_REGISTRY
            for fname in factor_names:
                if fname not in FACTOR_REGISTRY:
                    raise ValueError(f"未知因子: {fname}")

            # 长表查询：直接返回 (symbol, date, factor_name, value) 四列
            # 由调用方用 Pandas pivot_table 转为宽表用于评分计算
            placeholders = ", ".join(["?" for _ in factor_names])
            sql = f"""
                SELECT symbol, trade_date, factor_name, value
                FROM '{table}'
                WHERE trade_date >= ? AND trade_date <= ?
                  AND factor_name IN ({placeholders})
                ORDER BY trade_date, symbol, factor_name
            """

            params = [start, end] + factor_names
            result = conn.execute(sql, params)
            column_names = [desc[0] for desc in result.description]
            rows = result.fetchall()
            logger.info(f"回测查询完成，返回 {len(rows)} 条记录（长表格式）")
            return [dict(zip(column_names, row)) for row in rows]

        finally:
            conn.close()
            logger.debug("回测 DuckDB 连接已关闭")


# 全局查询路由实例
query_router = QueryRouter()
