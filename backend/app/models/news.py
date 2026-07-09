"""
新闻模型模块

定义新闻资讯、舆情数据相关的 ORM 模型。
所有列名与 init.sql 的 news_raw 表保持一致。
"""

from sqlalchemy import Column, String, Integer, DateTime, func, Text, Float, Boolean
from sqlalchemy.dialects.postgresql import ARRAY
from app.core.database import Base


class News(Base):
    """新闻资讯表"""

    __tablename__ = "news_raw"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="新闻 ID")
    source = Column(String(64), nullable=False, comment="来源（如 财联社、东方财富）")
    title = Column(String(256), nullable=False, comment="新闻标题")
    content = Column(Text, comment="新闻正文")
    url = Column(Text, comment="原文链接")
    publish_time = Column(DateTime, comment="发布时间")
    crawl_time = Column(DateTime, server_default=func.now(), comment="抓取时间")
    related_stocks = Column(ARRAY(String), comment="关联股票代码数组（TEXT[]）")
    sentiment_label = Column(String(32), comment="情感标签（positive/negative/neutral）")
    sentiment_score = Column(Float, comment="情感评分（-1 到 1）")
    is_duplicate = Column(Boolean, default=False, comment="是否重复")
