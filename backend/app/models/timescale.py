"""
K 线及因子超表模型模块

定义 TimescaleDB 超表（Hypertable），用于存储分钟级 K 线和计算因子值。
所有列名与 init.sql 保持一致。
"""

from sqlalchemy import Column, String, Float, DateTime, Integer, func
from app.core.database import Base


class StockMinute(Base):
    """1 分钟 K 线超表，按时间分区，映射到 stock_minute 表"""

    __tablename__ = "stock_minute"

    symbol = Column(String(16), primary_key=True, comment="股票代码")
    trade_time = Column(DateTime, primary_key=True, comment="K 线时间")
    open = Column(Float, comment="开盘价")
    high = Column(Float, comment="最高价")
    low = Column(Float, comment="最低价")
    close = Column(Float, comment="收盘价")
    volume = Column(Float, comment="成交量（股数）")
    amount = Column(Float, comment="成交额（元）")


class StockDaily(Base):
    """日 K 线超表，映射到 stock_daily 表"""

    __tablename__ = "stock_daily"

    symbol = Column(String(16), primary_key=True, comment="股票代码")
    trade_date = Column(DateTime, primary_key=True, comment="交易日")
    open = Column(Float, comment="开盘价")
    high = Column(Float, comment="最高价")
    low = Column(Float, comment="最低价")
    close = Column(Float, comment="收盘价")
    pre_close = Column(Float, comment="昨收价")
    volume = Column(Float, comment="成交量（股数）")
    amount = Column(Float, comment="成交额（元）")
    amplitude = Column(Float, comment="振幅（%）")
    pct_change = Column(Float, comment="涨跌幅（%）")
    turn = Column(Float, comment="换手率")


class FactorValue(Base):
    """因子值超表，存储每日各股票的因子计算结果"""

    __tablename__ = "factor_value"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录 ID")
    symbol = Column(String(16), comment="股票代码")
    trade_date = Column(DateTime, comment="计算日期")
    factor_name = Column(String(64), comment="因子名称")
    value = Column(Float, comment="因子值")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
