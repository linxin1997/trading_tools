"""
因子计算基类模块

定义 FactorCalculator 统一接口，所有具体因子通过此入口调用。
"""

import pandas as pd
from loguru import logger

from app.services.factor_lib import technical


_REGISTRY_OVERRIDES = {
    # money（资金因子，需要 Tushare 积分，当前为占位）
    "net_amount": {"category": "资金", "type": "数值", "description": "主力净流入额（万元，需 Tushare 积分）"},
    "net_amount_ratio": {"category": "资金", "type": "数值", "description": "主力净流入 / 成交额（需 Tushare 积分）"},
}


class FactorCalculator:
    """因子计算器，统一调度各因子计算模块

    提供 compute_all() 和 compute_single() 两个对外入口，
    分别用于批量计算全部因子和按名称计算单个因子。
    """

    # 因子元信息注册表
    FACTOR_REGISTRY: dict[str, dict[str, str]] = {
        # ---- 均线类 ----
        "ma_5": {"category": "均线", "type": "数值", "description": "5 日移动均线"},
        "ma_10": {"category": "均线", "type": "数值", "description": "10 日移动均线"},
        "ma_20": {"category": "均线", "type": "数值", "description": "20 日移动均线"},
        "ma_60": {"category": "均线", "type": "数值", "description": "60 日移动均线"},
        "ma_5_ma_20_ratio": {"category": "均线", "type": "数值", "description": "短期（MA5）与中期（MA20）均线比值"},
        "ma_cross": {"category": "均线", "type": "分类", "description": "均线排列状态：多头排列=1 / 空头排列=-1 / 交叉=0"},
        # ---- 动量类 ----
        "macd_dif": {"category": "动量", "type": "数值", "description": "MACD DIF 线（快线）"},
        "macd_dea": {"category": "动量", "type": "数值", "description": "MACD DEA 线（慢线）"},
        "macd_hist": {"category": "动量", "type": "数值", "description": "MACD 柱状图"},
        "rsi_6": {"category": "动量", "type": "数值", "description": "6 日相对强弱指标"},
        "rsi_14": {"category": "动量", "type": "数值", "description": "14 日相对强弱指标"},
        "kdj_k": {"category": "动量", "type": "数值", "description": "KDJ 指标 K 值"},
        "kdj_d": {"category": "动量", "type": "数值", "description": "KDJ 指标 D 值"},
        "kdj_j": {"category": "动量", "type": "数值", "description": "KDJ 指标 J 值"},
        "williams_r": {"category": "动量", "type": "数值", "description": "威廉指标（Williams %R）"},
        "bias_5": {"category": "动量", "type": "数值", "description": "5 日乖离率"},
        "bias_10": {"category": "动量", "type": "数值", "description": "10 日乖离率"},
        # ---- 波动类 ----
        "boll_up": {"category": "波动", "type": "数值", "description": "布林带上轨"},
        "boll_mid": {"category": "波动", "type": "数值", "description": "布林带中轨（20 日均线）"},
        "boll_dn": {"category": "波动", "type": "数值", "description": "布林带下轨"},
        "boll_width": {"category": "波动", "type": "数值", "description": "布林带带宽比（(UP-DN)/MID）"},
        "atr_14": {"category": "波动", "type": "数值", "description": "14 日平均真实波幅"},
        # ---- 量能类 ----
        "volume_ratio": {"category": "量能", "type": "数值", "description": "量比（当日成交量 / 5 日均量）"},
        "volume_ma5": {"category": "量能", "type": "数值", "description": "5 日平均成交量"},
        "turnover_rate": {"category": "量能", "type": "数值", "description": "换手率（%）"},
        "amount_ma5": {"category": "量能", "type": "数值", "description": "5 日平均成交额"},
        # ---- 形态类 ----
        "doji": {"category": "形态", "type": "分类", "description": "十字星形态：是=1 / 否=0"},
        "hammer": {"category": "形态", "type": "分类", "description": "锤子线形态：是=1 / 否=0"},
        "engulfing": {"category": "形态", "type": "分类", "description": "吞噬形态：看涨吞噬=1 / 看跌吞噬=-1 / 无=0"},
        "three_white": {"category": "形态", "type": "分类", "description": "三白兵形态（连续三根大阳线）：是=1 / 否=0"},
        "three_black": {"category": "形态", "type": "分类", "description": "三乌鸦形态（连续三根大阴线）：是=1 / 否=0"},
        # ---- 舆情类 ----
        "positive_news_1d": {"category": "舆情", "type": "数值", "description": "当日正面新闻数量"},
        "negative_news_1d": {"category": "舆情", "type": "数值", "description": "当日负面新闻数量"},
        "sentiment_score_1d": {"category": "舆情", "type": "数值", "description": "当日情感综合评分 [-1, 1]"},
        # ---- 资金类 ----
        **_REGISTRY_OVERRIDES,
    }

    @staticmethod
    def compute_all(df: pd.DataFrame) -> pd.DataFrame:
        """计算全部注册的因子

        输入 DataFrame 必须包含以下列：
            open, high, low, close, volume

        可选列：
            amount（成交额）, turnover（换手率）

        Args:
            df: 包含 OHLCV 数据的 DataFrame

        Returns:
            新增因子列后的 DataFrame
        """
        logger.info(f"开始计算全部因子，数据行数: {len(df)}")
        result = technical.compute_all(df)
        # money/sentiment 因子在 compute_and_store 阶段通过 DB 查询单独写入 factor_value 表
        logger.info(f"因子计算完成，新增 {len([c for c in result.columns if c not in df.columns])} 列")
        return result

    @staticmethod
    async def compute_sentiment(symbol: str) -> dict[str, float]:
        """计算舆情因子（从数据库查询新闻数据）"""
        from app.services.factor_lib.sentiment import get_positive_news_1d, get_negative_news_1d, get_sentiment_score_1d
        pos = await get_positive_news_1d(symbol)
        neg = await get_negative_news_1d(symbol)
        score = await get_sentiment_score_1d(symbol)
        return {"positive_news_1d": pos, "negative_news_1d": neg, "sentiment_score_1d": score}

    @staticmethod
    def compute_money(symbol: str) -> dict[str, float]:
        """计算资金因子（占位，需 Tushare 积分）"""
        from app.services.factor_lib.money import compute_all_money
        raw = compute_all_money(symbol)
        return {
            "net_amount": raw.get("MAIN_INFLOW_NET", 0.0),
            "net_amount_ratio": raw.get("MAIN_INFLOW_RATIO", 0.0),
        }

    @staticmethod
    def compute_single(df: pd.DataFrame, factor_name: str) -> pd.Series:
        """计算单个指定名称的因子"""
        if factor_name not in FactorCalculator.FACTOR_REGISTRY:
            available = list(FactorCalculator.FACTOR_REGISTRY.keys())
            raise ValueError(f"未知因子 '{factor_name}'，可用因子: {available}")
        full = FactorCalculator.compute_all(df)
        if factor_name not in full.columns:
            raise ValueError(f"因子 '{factor_name}' 计算后未返回，可能缺少必要输入列")
        return full[factor_name]

    @staticmethod
    def list_factors(category: str | None = None) -> dict[str, dict[str, str]]:
        """列出可用的因子及其元信息"""
        if category is None:
            return dict(FactorCalculator.FACTOR_REGISTRY)
        return {name: info for name, info in FactorCalculator.FACTOR_REGISTRY.items() if info["category"] == category}
