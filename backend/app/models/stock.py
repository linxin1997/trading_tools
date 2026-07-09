"""
股票信息模型模块

定义 A 股股票基本信息、行业分类、上市状态等 ORM 模型。
所有列名与 init.sql 保持一致。
"""

from sqlalchemy import Column, String, Date, DateTime, func
from app.core.database import Base


class StockInfo(Base):
    """A 股股票基本信息表"""

    __tablename__ = "stock_info"

    symbol = Column(String(16), primary_key=True, comment="股票代码（如 000001.SZ）")
    name = Column(String(32), nullable=False, comment="股票名称")
    sector = Column(String(32), comment="所属板块")
    list_date = Column(Date, comment="上市日期")
    delist_date = Column(Date, comment="退市日期")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
