"""
新闻爬虫基类模块

定义统一新闻数据模型 NewsItem 和爬虫抽象基类 BaseCrawler，
所有新闻源爬虫需继承 BaseCrawler 并实现 crawl() 方法。
"""

from abc import ABC, abstractmethod
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class NewsItem:
    """统一新闻数据模型

    标准化各新闻源返回的数据结构，供后续存储和分析使用。

    Attributes:
        source: 新闻来源名称（如 "财联社"、"东方财富"、"雪球"）
        title: 新闻标题
        content: 新闻正文/摘要内容
        url: 原文链接
        publish_time: 发布时间
        related_stocks: 关联股票代码列表（可选）
    """

    source: str
    title: str
    content: str
    url: str
    publish_time: datetime
    related_stocks: list[str] = field(default_factory=list)


class BaseCrawler(ABC):
    """新闻爬虫抽象基类

    定义新闻抓取的标准接口，所有新闻源爬虫需实现 crawl() 方法。
    爬虫应包含完善的错误处理，失败时记录日志并返回空列表。
    """

    def __init__(self):
        """初始化爬虫实例

        子类可在此进行 HTTP 客户端等资源的初始化。
        """
        self._source_name: str = self.__class__.__name__

    @abstractmethod
    async def crawl(self) -> list[NewsItem]:
        """抓取最新的新闻列表

        子类需实现具体的抓取逻辑，包括：
        1. 调用目标数据源接口获取原始数据
        2. 解析并转换为 NewsItem 列表
        3. 异常时记录日志，返回空列表

        Returns:
            抓取到的新闻列表，失败时返回空列表
        """
        ...
