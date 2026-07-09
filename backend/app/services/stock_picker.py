"""
选股服务模块

基于多因子加权评分模型执行选股策略。

评分引擎逻辑：
1. 解析筛选条件 → 构建 SQL 查询，从 factor_value 表读取因子数据
2. 因子归一化评分：
   - 分类因子（MA_CROSS）：Ordinal 编码（多头=1，空头=-1，交叉=0）
   - 布尔因子：True=1，False=0
   - 数值因子（RSI_14）：Min-max 归一化到 [0,1]
3. score = Σ(wi × norm(factor_i)) × 100 / Σwi
4. 原因生成：拼接命中的因子条件形成自然语言描述
5. 返回 Top N
"""

from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger


class StockPicker:
    """选股器，多因子加权评分筛选目标股票"""

    # 分类因子名 -> 值映射字典（用于 Ordinal 编码）
    _CATEGORICAL_MAP: dict[str, dict[str, float]] = {
        "ma_cross": {"多头排列": 1.0, "空头排列": -1.0, "交叉": 0.0},
        "engulfing": {"看涨吞噬": 1.0, "看跌吞噬": -1.0, "无": 0.0},
    }

    # 布尔因子列表（取值为 True/False 的因子）
    _BOOLEAN_FACTORS: set[str] = {"doji", "hammer", "three_white", "three_black"}

    async def screen(
        self,
        conditions: list[dict],
        weights: dict[str, float],
        top_n: int = 20,
        session: AsyncSession | None = None,
    ) -> dict:
        """执行选股评分

        Args:
            conditions: 筛选条件列表，每项为 {"factor": str, "op": str, "value": Any}
            weights: 因子权重，如 {"RSI_14": 0.3, "MA_CROSS": 0.2}
            top_n: 返回前 N 只
            session: 数据库会话（用于从 factor_value 表读取因子数据）

        Returns:
            {"total": int, "stocks": [{"symbol","name","score","factors":{},"reason"},...]}
        """
        logger.info(
            f"StockPicker.screen: conditions={len(conditions)}条, "
            f"weights={len(weights)}项, top_n={top_n}"
        )

        # 步骤 1：解析条件，获取需要查询的因子列表
        factor_names = set()
        for cond in conditions:
            factor_names.add(cond["factor"])
        for fname in weights:
            factor_names.add(fname)

        if not factor_names:
            raise ValueError("未指定任何因子条件或权重")

        factor_names_list = list(factor_names)
        logger.info(f"需要查询的因子: {factor_names_list}")

        # 步骤 2：从数据库查询因子数据
        # 如果提供了 session，则查询 factor_value 表；否则使用模拟数据
        if session is not None:
            factor_df = await self._query_factor_data(
                session, factor_names_list, conditions
            )
        else:
            logger.warning("未提供数据库 session，使用空因子数据")
            factor_df = pd.DataFrame()

        if factor_df.empty:
            logger.warning("未查询到任何因子数据，返回空结果")
            return {"total": 0, "stocks": []}

        # 步骤 3：因子归一化评分
        scored_df = self._normalize_and_score(factor_df, conditions, weights)

        if scored_df.empty:
            return {"total": 0, "stocks": []}

        # 步骤 4：排序并取 Top N
        scored_df = scored_df.sort_values("score", ascending=False).head(top_n)

        # 步骤 5：构建结果
        stocks = []
        for _, row in scored_df.iterrows():
            # 生成原因描述
            reason_parts = []
            for cond in conditions:
                fname = cond["factor"]
                if fname in row and pd.notna(row[fname]):
                    reason_parts.append(
                        f"{fname}{self._op_display(cond['op'])}{cond['value']}"
                    )

            # 提取各因子原始值
            factors_dict: dict[str, Any] = {}
            for fname in factor_names_list:
                if fname in row and pd.notna(row[fname]):
                    val = row[fname]
                    factors_dict[fname] = round(float(val), 4) if isinstance(val, (int, float)) else val

            stocks.append({
                "symbol": str(row.get("symbol", "")),
                "name": str(row.get("name", "")),
                "score": round(float(row["score"]), 2),
                "factors": factors_dict,
                "reason": "；".join(reason_parts) if reason_parts else "综合评分靠前",
            })

        total_count = len(scored_df)
        logger.info(f"选股完成，返回 {len(stocks)} 只（共 {total_count} 只符合条件）")

        return {
            "total": total_count,
            "stocks": stocks,
        }

    async def _query_factor_data(
        self,
        session: AsyncSession,
        factor_names: list[str],
        conditions: list[dict],
    ) -> pd.DataFrame:
        """从 factor_value 表查询因子数据

        查询逻辑：
        - 获取最新交易日中指定因子的所有股票数据
        - 通过 SQL 行转列（pivot），将因子名展开为列
        - 对因子名做白名单校验，防止 SQL 注入

        Args:
            session: 数据库会话
            factor_names: 需要查询的因子名称列表
            conditions: 筛选条件（用于获取日期等）

        Returns:
            包含 symbol 和各因子列的 DataFrame

        Raises:
            ValueError: 包含未注册的因子名
        """
        try:
            # 白名单校验：拒绝未知因子名，防止 SQL 注入
            from app.services.factor_lib.base import FactorCalculator

            FACTOR_REGISTRY = FactorCalculator.FACTOR_REGISTRY
            for fname in factor_names:
                if fname not in FACTOR_REGISTRY:
                    raise ValueError(f"未知因子: {fname}")

            # 构建行转列查询：将 (code, factor_name, value) 转为 (code, factor1, factor2, ...)
            # 使用 crosstab / filter + conditional aggregation 实现
            factor_list_str = ", ".join([f"'{f}'" for f in factor_names])

            sql = text(f"""
                SELECT
                    fv.symbol,
                    si.name,
                    {', '.join([
                        f"MAX(CASE WHEN fv.factor_name = '{f}' THEN fv.value END) AS \"{f}\""
                        for f in factor_names
                    ])}
                FROM factor_value fv
                LEFT JOIN stock_info si ON si.symbol = fv.symbol
                WHERE fv.factor_name IN ({factor_list_str})
                  AND fv.trade_date = (
                      SELECT MAX(trade_date) FROM factor_value
                  )
                GROUP BY fv.symbol, si.name
            """)

            logger.debug(f"执行因子查询 SQL")
            result = await session.execute(sql)
            rows = result.fetchall()
            col_names = list(result.keys())

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=col_names)

            # 数值列转为 float
            for col in factor_names:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            logger.info(f"因子数据查询完成: {len(df)} 条记录")
            return df

        except Exception as e:
            logger.error(f"因子数据查询失败: {e}", exc_info=True)
            return pd.DataFrame()

    def _normalize_and_score(
        self,
        df: pd.DataFrame,
        conditions: list[dict],
        weights: dict[str, float],
    ) -> pd.DataFrame:
        """因子归一化并计算综合评分

        归一化策略：
        - 分类因子：Ordinal 编码（已在 _CATEGORICAL_MAP 中定义）
        - 布尔因子：True=1，False=0
        - 数值因子：Min-max 归一化到 [0,1]

        Args:
            df: 包含因子列的 DataFrame
            conditions: 筛选条件
            weights: 因子权重

        Returns:
            新增 score 列后的 DataFrame（已过滤不符合条件的行）
        """
        if df.empty:
            return df

        result_df = df.copy()
        factor_names = list(set([c["factor"] for c in conditions] + list(weights.keys())))

        # ---- 步骤 3a：条件过滤 ----
        mask = pd.Series(True, index=result_df.index)
        for cond in conditions:
            fname = cond["factor"]
            op = cond["op"]
            value = cond["value"]

            if fname not in result_df.columns:
                logger.warning(f"因子 '{fname}' 不在查询结果中，跳过该条件")
                continue

            col = result_df[fname]

            if op == "eq":
                # 分类因子用映射比较，数值因子直接比较
                if fname in self._CATEGORICAL_MAP and isinstance(value, str):
                    mapped_val = self._CATEGORICAL_MAP[fname].get(value, value)
                    mask &= (col == mapped_val)
                else:
                    try:
                        mask &= (col == float(value))
                    except (ValueError, TypeError):
                        mask &= (col == value)
            elif op == "neq":
                try:
                    mask &= (col != float(value))
                except (ValueError, TypeError):
                    mask &= (col != value)
            elif op == "gt":
                mask &= (col > float(value))
            elif op == "gte":
                mask &= (col >= float(value))
            elif op == "lt":
                mask &= (col < float(value))
            elif op == "lte":
                mask &= (col <= float(value))
            elif op == "in":
                if isinstance(value, list):
                    mask &= col.isin(value)

        result_df = result_df[mask].copy()
        logger.info(f"条件过滤后剩余 {len(result_df)} 条")

        if result_df.empty:
            return result_df

        # ---- 步骤 3b：因子归一化 ----
        for fname in factor_names:
            if fname not in result_df.columns:
                continue

            col = result_df[fname]

            if fname in self._CATEGORICAL_MAP:
                # 分类因子已为 Ordinal 编码值，直接使用（值域固定）
                # MA_CROSS 值域 {-1, 0, 1} → 映射到 [0, 1]
                # -1 → 0, 0 → 0.5, 1 → 1
                result_df[f"{fname}_norm"] = (col + 1) / 2

            elif fname in self._BOOLEAN_FACTORS:
                # 布尔因子：值已为 0/1
                result_df[f"{fname}_norm"] = col.astype(float)

            else:
                # 数值因子：Min-max 归一化到 [0,1]
                min_val = col.min()
                max_val = col.max()
                if pd.isna(min_val) or pd.isna(max_val) or max_val == min_val:
                    # 无波动时归一化为 0.5
                    result_df[f"{fname}_norm"] = 0.5
                else:
                    result_df[f"{fname}_norm"] = (col - min_val) / (max_val - min_val)

        # ---- 步骤 4：计算加权评分 ----
        total_weight = sum(weights.values())
        if total_weight == 0:
            logger.warning("权重总和为 0，所有股票评分设为 0")
            result_df["score"] = 0.0
            return result_df

        # score = Σ(wi × norm(factor_i)) × 100 / Σwi
        result_df["score"] = 0.0
        for fname, w in weights.items():
            norm_col = f"{fname}_norm"
            if norm_col in result_df.columns:
                result_df["score"] += w * result_df[norm_col].fillna(0.5)

        result_df["score"] = result_df["score"] / total_weight * 100

        # 移除归一化辅助列
        norm_cols = [c for c in result_df.columns if c.endswith("_norm")]
        result_df = result_df.drop(columns=norm_cols, errors="ignore")

        return result_df

    def _op_display(self, op: str) -> str:
        """将操作符转为中文显示

        Args:
            op: 操作符（eq, neq, gt, gte, lt, lte, in）

        Returns:
            中文描述
        """
        op_map = {
            "eq": "=",
            "neq": "≠",
            "gt": ">",
            "gte": "≥",
            "lt": "<",
            "lte": "≤",
            "in": "∈",
        }
        return op_map.get(op, op)
