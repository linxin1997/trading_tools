"""
持仓模型模块

定义自选股、投资组合、交易记录等 ORM 模型。
所有列名与 init.sql 保持一致。
"""

from sqlalchemy import (
    Column, String, Float, Integer, DateTime, func,
)
from app.core.database import Base


class Portfolio(Base):
    """持仓表（对应 init.sql 的 portfolio 表）"""

    __tablename__ = "portfolio"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="持仓 ID")
    user_id = Column(String(64), nullable=False, default="default", comment="用户 ID")
    symbol = Column(String(16), nullable=False, comment="股票代码")
    name = Column(String(64), nullable=False, comment="股票名称")
    cost_price = Column(Float, nullable=False, comment="成本价")
    volume = Column(Integer, nullable=False, comment="持有数量（股）")
    group_id = Column(Integer, comment="所属分组 ID")
    add_time = Column(DateTime, server_default=func.now(), comment="添加时间")



