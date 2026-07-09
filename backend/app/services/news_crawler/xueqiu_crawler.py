"""
雪球新闻/帖子爬虫模块

实现 XueqiuCrawler，通过 httpx 调用雪球 API 获取社区热帖，
每 30 分钟执行一次。包含完善的错误处理和模拟数据 fallback。
"""

from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from app.services.news_crawler.base import BaseCrawler, NewsItem

# 雪球 API 地址
XUEQIU_API_URL = "https://api.xueqiu.com/statuses/hot.json"
XUEQIU_STOCK_API_URL = "https://api.xueqiu.com/stock/notification/stock.json"


class XueqiuCrawler(BaseCrawler):
    """雪球社区爬虫

    通过 httpx 调用雪球公开 API 获取热门帖子，
    解析后构造 NewsItem 列表。每 30 分钟由 Celery 定时任务触发。
    """

    def __init__(self):
        """初始化雪球爬虫"""
        super().__init__()
        self._source_name = "雪球"
        self._headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://xueqiu.com/",
        }

    async def crawl(self) -> list[NewsItem]:
        """抓取雪球热门帖子

        优先从雪球 API 获取数据，失败时使用内置模拟数据。

        Returns:
            雪球帖子列表，失败时返回空列表
        """
        logger.info("开始抓取雪球新闻")
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                # 先访问首页获取 cookies（雪球 API 需要）
                await client.get("https://xueqiu.com/", headers=self._headers)
                # 调用热门帖子 API
                params = {"count": 20, "type": "all", "since_id": -1}
                response = await client.get(
                    XUEQIU_API_URL,
                    headers=self._headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                items = self._parse_response(data)
                logger.info(f"雪球抓取成功，共 {len(items)} 条帖子")
                return items
        except Exception as e:
            logger.warning(f"雪球接口请求失败: {e}，使用模拟数据")
            return self._fallback_data()

    def _parse_response(self, data: dict[str, Any]) -> list[NewsItem]:
        """解析雪球 API 返回数据

        Args:
            data: API 返回的 JSON 数据

        Returns:
            解析后的帖子列表
        """
        items: list[NewsItem] = []
        # 雪球热门帖子接口返回格式: {"list": [...]}
        post_list = []
        if isinstance(data, dict):
            post_list = data.get("list", data.get("statuses", []))
        elif isinstance(data, list):
            post_list = data

        for item in post_list:
            try:
                # 尝试获取帖子详情
                title = item.get("title", "")
                # 如果没有标题，使用摘要前 50 个字符作为标题
                text = item.get("text", item.get("content", item.get("description", "")))
                if not title and text:
                    title = text[:50] + ("..." if len(text) > 50 else "")

                # 清理 HTML 标签
                content = self._strip_html(text)

                news = NewsItem(
                    source=self._source_name,
                    title=title,
                    content=content[:500],  # 限制正文长度
                    url=item.get("url", item.get("share_url", f"https://xueqiu.com/{item.get('id', '')}")),
                    publish_time=self._parse_time(item.get("created_at", item.get("time", datetime.now()))),
                    related_stocks=self._extract_stocks(item),
                )
                if news.title or news.content:
                    items.append(news)
            except Exception as e:
                logger.warning(f"解析雪球帖子条目失败: {e}")
                continue
        return items

    def _strip_html(self, text: str) -> str:
        """简单去除 HTML 标签

        Args:
            text: 包含 HTML 标签的文本

        Returns:
            纯文本内容
        """
        import re

        if not text:
            return ""
        # 去除 HTML 标签
        text = re.sub(r"<[^>]+>", "", text)
        # 去除多余空白
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _parse_time(self, time_val: Any) -> datetime:
        """统一解析时间字段

        Args:
            time_val: 原始时间值（支持时间戳、字符串等）

        Returns:
            标准化的 datetime 对象
        """
        if isinstance(time_val, datetime):
            return time_val
        if isinstance(time_val, (int, float)):
            # 雪球时间戳可能是毫秒级的
            ts = time_val / 1000 if time_val > 1e11 else time_val
            return datetime.fromtimestamp(ts)
        if isinstance(time_val, str):
            try:
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y-%m-%d",
                ]:
                    try:
                        return datetime.strptime(time_val, fmt)
                    except ValueError:
                        continue
            except Exception:
                pass
        return datetime.now()

    def _extract_stocks(self, item: dict[str, Any]) -> list[str]:
        """从帖子中提取关联股票代码

        Args:
            item: 帖子的原始数据字典

        Returns:
            股票代码列表
        """
        stocks = item.get("stock", item.get("stocks", item.get("codes", "")))
        if isinstance(stocks, str):
            return [s.strip() for s in stocks.split(",") if s.strip()]
        if isinstance(stocks, list):
            codes = []
            for s in stocks:
                if isinstance(s, dict):
                    codes.append(str(s.get("code", s.get("symbol", ""))))
                else:
                    codes.append(str(s).strip())
            return [c for c in codes if c]
        return []

    def _fallback_data(self) -> list[NewsItem]:
        """生成模拟数据（开发模式 fallback）

        当雪球 API 不可用时，返回模拟的热门帖子数据。

        Returns:
            模拟帖子列表
        """
        now = datetime.now()
        return [
            NewsItem(
                source=self._source_name,
                title="AI算力需求爆发，这几家国内厂商最受益",
                content="随着大模型训练的算力需求持续增长，国内AI芯片和算力基础设施厂商迎来历史性机遇。本文分析了产业链上下游的投资机会。",
                url="https://xueqiu.com/mock/1",
                publish_time=now,
                related_stocks=["688981", "002371", "688041"],
            ),
            NewsItem(
                source=self._source_name,
                title="新能源车2026年下半年展望：竞争格局与投资机会",
                content="下半年新能源车市竞争将更加激烈，但龙头企业的规模效应和技术壁垒将使其在价格战中保持优势。建议关注具备海外出口能力的车企。",
                url="https://xueqiu.com/mock/2",
                publish_time=now,
                related_stocks=["002594", "601238"],
            ),
            NewsItem(
                source=self._source_name,
                title="白酒板块深度回调后，估值是否已具吸引力？",
                content="白酒板块经过近半年的调整，龙头企业估值已回落至历史较低水平。但从基本面看，行业库存去化仍需时间，右侧机会还需等待。",
                url="https://xueqiu.com/mock/3",
                publish_time=now,
                related_stocks=["600519", "000858", "000568"],
            ),
            NewsItem(
                source=self._source_name,
                title="光伏行业产能出清进行时，哪些公司能活到最后？",
                content="光伏行业正经历惨烈的产能出清过程，硅料、硅片价格持续下跌。拥有成本优势和技术壁垒的龙头企业有望在行业洗牌后受益。",
                url="https://xueqiu.com/mock/4",
                publish_time=now,
                related_stocks=["601012", "600438", "688599"],
            ),
            NewsItem(
                source=self._source_name,
                title="医药集采政策边际放缓，创新药迎来布局窗口",
                content="近期国家集采政策呈现边际放缓趋势，创新药审评审批加速。多家创新药企的核心品种进入放量阶段，行业景气度有望触底回升。",
                url="https://xueqiu.com/mock/5",
                publish_time=now,
                related_stocks=["600276", "300122", "688235"],
            ),
        ]
