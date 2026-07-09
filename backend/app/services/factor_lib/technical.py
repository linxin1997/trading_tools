"""
技术面因子模块

基于 pandas_ta 库计算 30+ 种常见技术分析因子。
明确不依赖 TA-Lib，全部使用 pandas_ta 实现。

主要入口函数：
    compute_all(df) -> pd.DataFrame：输入 OHLCV DataFrame，返回含全部因子列的 DataFrame

因子分类：
    均线类（6）：MA5, MA10, MA20, MA60, MA5_MA20_RATIO, MA_CROSS
    动量类（10）：MACD_DIF, MACD_DEA, MACD_HIST, RSI_6, RSI_14, KDJ_K, KDJ_D, KDJ_J, WILLIAMS_R, BIAS_5, BIAS_10
    波动类（5）：BOLL_UP, BOLL_MID, BOLL_DN, BOLL_WIDTH, ATR_14
    量能类（4）：VOLUME_RATIO, VOLUME_MA5, AMOUNT_MA5, TURNOVER_RATE（透传）
    形态类（5）：DOJI, HAMMER, ENGULFING, THREE_WHITE, THREE_BLACK
"""

import pandas as pd
import numpy as np
import pandas_ta as ta
from loguru import logger


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> None:
    """检查 DataFrame 是否包含必要的列，缺失则抛出异常

    Args:
        df: 输入的 DataFrame
        columns: 必需的列名列表

    Raises:
        ValueError: 缺少必要列时抛出
    """
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"缺少必要列: {missing}，可用列: {list(df.columns)}")


def compute_ma(df: pd.DataFrame) -> pd.DataFrame:
    """计算均线类因子：MA5, MA10, MA20, MA60, MA5_MA20_RATIO, MA_CROSS

    Args:
        df: 包含 close 列的 DataFrame

    Returns:
        新增均线因子列的 DataFrame
    """
    _ensure_columns(df, ["close"])
    close = df["close"]

    # MA5, MA10, MA20, MA60
    df["MA5"] = close.rolling(window=5).mean()
    df["MA10"] = close.rolling(window=10).mean()
    df["MA20"] = close.rolling(window=20).mean()
    df["MA60"] = close.rolling(window=60).mean()

    # MA5_MA20_RATIO：短中期均线比值
    df["MA5_MA20_RATIO"] = df["MA5"] / df["MA20"]

    # MA_CROSS：均线排列状态判断
    # 多头排列：MA5 > MA10 > MA20（短期 > 中期 > 长期）
    # 空头排列：MA5 < MA10 < MA20
    # 交叉（不满足前两者）
    cond_bull = (df["MA5"] > df["MA10"]) & (df["MA10"] > df["MA20"])
    cond_bear = (df["MA5"] < df["MA10"]) & (df["MA10"] < df["MA20"])
    df["MA_CROSS"] = np.select([cond_bull, cond_bear], [1, -1], default=0)

    return df


def compute_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """计算动量类因子：MACD, RSI, KDJ, WILLIAMS_R, BIAS

    Args:
        df: 包含 high, low, close 列的 DataFrame

    Returns:
        新增动量因子列的 DataFrame
    """
    _ensure_columns(df, ["high", "low", "close"])
    high, low, close = df["high"], df["low"], df["close"]

    # ---- MACD ----
    macd_result = ta.macd(close)
    if macd_result is not None:
        # 列名示例：MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
        for col in macd_result.columns:
            if "MACD_" in col and "MACDs" not in col and "MACDh" not in col:
                df["MACD_DIF"] = macd_result[col].values
            elif "MACDs" in col:
                df["MACD_DEA"] = macd_result[col].values
            elif "MACDh" in col:
                df["MACD_HIST"] = macd_result[col].values
    else:
        logger.warning("MACD 计算返回空值")

    # ---- RSI ----
    rsi_14 = ta.rsi(close, length=14)
    if rsi_14 is not None:
        df["RSI_14"] = rsi_14.values
    rsi_6 = ta.rsi(close, length=6)
    if rsi_6 is not None:
        df["RSI_6"] = rsi_6.values

    # ---- KDJ ----
    kdj_result = ta.kdj(high, low, close)
    if kdj_result is not None:
        for col in kdj_result.columns:
            if col.startswith("K_"):
                df["KDJ_K"] = kdj_result[col].values
            elif col.startswith("D_"):
                df["KDJ_D"] = kdj_result[col].values
            elif col.startswith("J_"):
                df["KDJ_J"] = kdj_result[col].values

    # ---- WILLIAMS_R ----
    willr = ta.willr(high, low, close, length=14)
    if willr is not None:
        df["WILLIAMS_R"] = willr.values

    # ---- BIAS（乖离率） ----
    ma5 = close.rolling(window=5).mean()
    ma10 = close.rolling(window=10).mean()
    df["BIAS_5"] = (close - ma5) / ma5 * 100
    df["BIAS_10"] = (close - ma10) / ma10 * 100

    return df


def compute_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """计算波动类因子：布林带（BOLL）、ATR

    Args:
        df: 包含 high, low, close 列的 DataFrame

    Returns:
        新增波动因子列的 DataFrame
    """
    _ensure_columns(df, ["high", "low", "close"])
    high, low, close = df["high"], df["low"], df["close"]

    # ---- 布林带 ----
    bbands = ta.bbands(close, length=20, std=2)
    if bbands is not None:
        for col in bbands.columns:
            if col.startswith("BBU_"):
                df["BOLL_UP"] = bbands[col].values
            elif col.startswith("BBM_"):
                df["BOLL_MID"] = bbands[col].values
            elif col.startswith("BBL_"):
                df["BOLL_DN"] = bbands[col].values

        # BOLL_WIDTH：带宽比 (UP - DN) / MID
        if "BOLL_UP" in df.columns and "BOLL_DN" in df.columns and "BOLL_MID" in df.columns:
            df["BOLL_WIDTH"] = (df["BOLL_UP"] - df["BOLL_DN"]) / df["BOLL_MID"]

    # ---- ATR ----
    atr = ta.atr(high, low, close, length=14)
    if atr is not None:
        df["ATR_14"] = atr.values

    return df


def compute_volume(df: pd.DataFrame) -> pd.DataFrame:
    """计算量能类因子：VOLUME_RATIO, VOLUME_MA5, AMOUNT_MA5, TURNOVER_RATE（透传）

    Args:
        df: 包含 volume 列的 DataFrame，可选 amount、turnover

    Returns:
        新增量能因子列的 DataFrame
    """
    _ensure_columns(df, ["volume"])

    # VOLUME_MA5：5 日平均成交量
    df["VOLUME_MA5"] = df["volume"].rolling(window=5).mean()

    # VOLUME_RATIO：量比 = 当日成交量 / 5 日均量
    # 为避免除零，将 VOLUME_MA5 为 0 的位置用 NaN 替换
    vol_ma5_safe = df["VOLUME_MA5"].replace(0, np.nan)
    df["VOLUME_RATIO"] = df["volume"] / vol_ma5_safe

    # AMOUNT_MA5：5 日平均成交额（需要 amount 列）
    if "amount" in df.columns:
        df["AMOUNT_MA5"] = df["amount"].rolling(window=5).mean()

    # TURNOVER_RATE：透传，如有此列则原样保留
    if "turnover" in df.columns:
        df["TURNOVER_RATE"] = df["turnover"]

    return df


def compute_candlestick_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """计算 K 线形态类因子：十字星、锤子线、吞噬、三白兵、三乌鸦

    形态识别使用简单的规则逻辑，无需外部库。

    Args:
        df: 包含 open, high, low, close 列的 DataFrame

    Returns:
        新增形态因子列的 DataFrame
    """
    _ensure_columns(df, ["open", "high", "low", "close"])
    open_p, high, low, close = df["open"], df["high"], df["low"], df["close"]

    # K 线实体的上下影线长度辅助计算
    body = (close - open_p).abs()
    upper_shadow = high - close.where(close >= open_p, open_p)
    lower_shadow = open_p.where(close >= open_p, close) - low
    total_range = high - low

    # ---- DOJI（十字星）：实体极小，上下影线较长 ----
    # 实体占总波幅比例 < 10%，且上下影线都存在
    body_ratio = body / total_range.replace(0, np.nan)
    df["DOJI"] = ((body_ratio < 0.1) & (upper_shadow > 0) & (lower_shadow > 0)).astype(int)

    # ---- HAMMER（锤子线）：下影线很长，实体在上部 ----
    # 出现在下跌后，下影线 >= 实体的 2 倍，上影线很短
    is_hammer_down = (close < open_p)  # 阴线锤子更常见
    # 下影线长度 >= 实体 * 2，且上影线 <= 实体
    cond_hammer = (
        (lower_shadow >= body * 2)
        & (upper_shadow <= body * 0.5)
        & (lower_shadow > 0)
        & (total_range > 0)
    )
    df["HAMMER"] = cond_hammer.astype(int)

    # ---- ENGULFING（吞噬形态） ----
    # 当前实体完全吞噬前一日实体
    prev_body = body.shift(1)
    prev_open = open_p.shift(1)
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    # 看涨吞噬：今日阳线吞噬昨日阴线
    bull_engulfing = (
        (close > open_p)  # 今日阳线
        & (prev_close < prev_open)  # 昨日阴线
        & (open_p < prev_close)  # 今日开盘低于昨日收盘
        & (close > prev_open)  # 今日收盘高于昨日开盘
    )
    # 看跌吞噬：今日阴线吞噬昨日阳线
    bear_engulfing = (
        (close < open_p)  # 今日阴线
        & (prev_close > prev_open)  # 昨日阳线
        & (open_p > prev_close)  # 今日开盘高于昨日收盘
        & (close < prev_open)  # 今日收盘低于昨日开盘
    )
    df["ENGULFING"] = np.select(
        [bull_engulfing, bear_engulfing], [1, -1], default=0
    )

    # ---- THREE_WHITE（三白兵）：连续三根大阳线，每根收盘高于前一根 ----
    # 三根连续阳线，涨幅逐渐加大或稳定
    is_up = close > open_p
    # 阳线实体幅度（相对于开盘价）
    up_strength = (close - open_p) / open_p
    three_white = (
        is_up
        & is_up.shift(1)
        & is_up.shift(2)
        & (up_strength > 0.01)  # 每根涨幅 > 1%
        & (close > close.shift(1))
        & (close.shift(1) > close.shift(2))
    )
    df["THREE_WHITE"] = three_white.astype(int)

    # ---- THREE_BLACK（三乌鸦）：连续三根大阴线，每根收盘低于前一根 ----
    is_down = close < open_p
    down_strength = (open_p - close) / open_p
    three_black = (
        is_down
        & is_down.shift(1)
        & is_down.shift(2)
        & (down_strength > 0.01)  # 每根跌幅 > 1%
        & (close < close.shift(1))
        & (close.shift(1) < close.shift(2))
    )
    df["THREE_BLACK"] = three_black.astype(int)

    return df


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """主入口函数：计算全部技术因子

    输入 DataFrame 必须包含以下列：
        open, high, low, close, volume

    可选列（缺失时跳过相关因子）：
        amount（成交额）, turnover（换手率）

    返回的 DataFrame 新增以下因子列：
        均线类: MA5, MA10, MA20, MA60, MA5_MA20_RATIO, MA_CROSS
        动量类: MACD_DIF, MACD_DEA, MACD_HIST, RSI_6, RSI_14, KDJ_K, KDJ_D, KDJ_J,
                WILLIAMS_R, BIAS_5, BIAS_10
        波动类: BOLL_UP, BOLL_MID, BOLL_DN, BOLL_WIDTH, ATR_14
        量能类: VOLUME_RATIO, VOLUME_MA5, AMOUNT_MA5, TURNOVER_RATE
        形态类: DOJI, HAMMER, ENGULFING, THREE_WHITE, THREE_BLACK

    Args:
        df: 包含 OHLCV 数据的原始 DataFrame

    Returns:
        新增全部因子列后的 DataFrame（不修改原始数据）
    """
    logger.info("技术因子 compute_all 开始计算")
    # 复制以避免修改原始数据
    result = df.copy()

    # 确保数据按时间排序（如有 date 列）
    if "date" in result.columns:
        result = result.sort_values("date").reset_index(drop=True)

    # 按类别依次计算
    result = compute_ma(result)
    result = compute_momentum(result)
    result = compute_volatility(result)
    result = compute_volume(result)
    result = compute_candlestick_patterns(result)

    # 获取新增的因子列（原始列之外的新列）
    original_columns = set(df.columns)
    new_columns = [c for c in result.columns if c not in original_columns]
    logger.info(f"技术因子计算完成，新增 {len(new_columns)} 个因子列: {new_columns}")

    return result
