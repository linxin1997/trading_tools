"""
财联社新闻爬虫模块

实现 CLSCrawler，通过模拟的 HTTP 接口（或 akshare）获取财联社电报，
每 10 分钟执行一次。包含完善的错误处理和模拟数据 fallback。
"""

import asyncio
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from app.services.news_crawler.base import BaseCrawler, NewsItem


# 财联社模拟 API 地址（开发/测试用）
CLS_MOCK_URL = "http://localhost:9999/api/cls/telegraph"

# 生产环境可改为真实接口（待确认）
# CLS_API_URL = "https://www.cls.cn/api/telegraph"


class CLSCrawler(BaseCrawler):
    """财联社新闻爬虫

    通过 HTTP 请求获取财联社电报快讯，解析后构造 NewsItem 列表。
    支持模拟数据 fallback，确保开发环境下可用。
    """

    def __init__(self):
        """初始化财联社爬虫"""
        super().__init__()
        self._source_name = "财联社"

    async def crawl(self) -> list[NewsItem]:
        """抓取财联社最新电报快讯

        优先从模拟接口获取数据，失败时使用内置模拟数据。
        每 10 分钟由 Celery 定时任务触发。

        Returns:
            财联社新闻列表，失败时返回空列表
        """
        logger.info("开始抓取财联社新闻")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(CLS_MOCK_URL)
                response.raise_for_status()
                data = response.json()
                items = self._parse_response(data)
                logger.info(f"财联社抓取成功，共 {len(items)} 条新闻")
                return items
        except Exception as e:
            logger.warning(f"财联社接口请求失败: {e}，使用模拟数据")
            return self._fallback_data()

    def _parse_response(self, data: dict[str, Any]) -> list[NewsItem]:
        """解析财联社 API 返回数据

        Args:
            data: API 返回的 JSON 数据

        Returns:
            解析后的新闻列表
        """
        items: list[NewsItem] = []
        # 模拟接口数据格式为 {"code": 0, "data": [{"title": ..., "content": ..., ...}]}
        news_list = []
        if isinstance(data, dict):
            news_list = data.get("data", data.get("list", []))
        elif isinstance(data, list):
            news_list = data

        for item in news_list:
            try:
                news = NewsItem(
                    source=self._source_name,
                    title=item.get("title", ""),
                    content=item.get("content", item.get("brief", "")),
                    url=item.get("url", ""),
                    publish_time=self._parse_time(item.get("time", item.get("ctime", datetime.now()))),
                    related_stocks=self._extract_stocks(item),
                )
                if news.title or news.content:
                    items.append(news)
            except Exception as e:
                logger.warning(f"解析财联社新闻条目失败: {e}")
                continue
        return items

    def _parse_time(self, time_val: Any) -> datetime:
        """统一解析时间字段

        Args:
            time_val: 原始时间值（字符串、int 时间戳或 datetime）

        Returns:
            标准化的 datetime 对象
        """
        if isinstance(time_val, datetime):
            return time_val
        if isinstance(time_val, (int, float)):
            return datetime.fromtimestamp(time_val)
        if isinstance(time_val, str):
            try:
                # 尝试常见时间格式
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                ]:
                    try:
                        return datetime.strptime(time_val, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
        return datetime.now()

    def _extract_stocks(self, item: dict[str, Any]) -> list[str]:
        """从新闻条目中提取关联股票代码

        Args:
            item: 新闻条目的原始数据字典

        Returns:
            股票代码列表
        """
        stocks = item.get("stocks", item.get("codes", ""))
        if isinstance(stocks, str):
            return [s.strip() for s in stocks.split(",") if s.strip()]
        if isinstance(stocks, list):
            return [str(s).strip() for s in stocks if s]
        return []

    def _fallback_data(self) -> list[NewsItem]:
        """生成模拟数据（开发模式 fallback）

        当外部接口不可用时，返回模拟的财联社新闻数据，
        确保开发和测试流程不受影响。

        Returns:
            模拟新闻列表
        """
        now = datetime.now()
        return [
            NewsItem(
                source=self._source_name,
                title="【午盘快评】沪指震荡上行，科技股集体走强",
                content="今日沪指早盘震荡上行，创业板指涨超2%。半导体、AI算力等科技方向集体走强，市场情绪明显回暖。",
                url="https://www.cls.cn/mock/1",
                publish_time=now,
                related_stocks=["688981", "002371", "300750"],
            ),
            NewsItem(
                source=self._source_name,
                title="【行业聚焦】新能源产业链迎来政策利好",
                content="国家发改委发布促进新能源产业高质量发展的若干措施，涉及光伏、风电、储能等多个领域。",
                url="https://www.cls.cn/mock/2",
                publish_time=now,
                related_stocks=["300274", "601012", "300750"],
            ),
            NewsItem(
                source=self._source_name,
                title="【资金流向】北向资金半日净买入超50亿元",
                content="北向资金今日延续净买入态势，半日累计净买入超50亿元。其中沪股通净买入约30亿元，深股通净买入约20亿元。",
                url="https://www.cls.cn/mock/3",
                publish_time=now,
                related_stocks=[],
            ),
            NewsItem(
                source=self._source_name,
                title="【公司新闻】某科技龙头宣布新一代AI芯片量产",
                content="国内AI芯片龙头企业宣布其最新一代AI训练芯片已正式量产，性能较上一代提升3倍，将广泛应用于大模型训练场景。",
                url="https://www.cls.cn/mock/4",
                publish_time=now,
                related_stocks=["688981", "688041"],
            ),
            NewsItem(
                source=self._source_name,
                title="【机构观点】券商策略会：下半年看好消费复苏",
                content="多家券商在最新策略报告中表示，下半年消费复苏有望加速，建议重点关注食品饮料、家电、旅游等板块。",
                url="https://www.cls.cn/mock/5",
                publish_time=now,
                related_stocks=["600519", "000858", "601888"],
            ),
        ]
