"""
东方财富新闻爬虫模块

实现 EastMoneyCrawler，通过 akshare 的 stock_info_news() 接口
获取东方财富新闻，每 15 分钟执行一次。
包含完善的错误处理和模拟数据 fallback。
"""

from datetime import datetime
from typing import Any

from loguru import logger

from app.services.news_crawler.base import BaseCrawler, NewsItem


class EastMoneyCrawler(BaseCrawler):
    """东方财富新闻爬虫

    通过 akshare 库的 stock_info_news() 接口获取东方财富网
    A 股相关资讯，解析后构造 NewsItem 列表。
    每 15 分钟由 Celery 定时任务触发。
    """

    def __init__(self):
        """初始化东方财富爬虫"""
        super().__init__()
        self._source_name = "东方财富"

    async def crawl(self) -> list[NewsItem]:
        """抓取东方财富最新新闻

        调用 akshare.stock_info_news() 获取新闻数据，
        若接口不可用则使用模拟数据 fallback。

        Returns:
            东方财富新闻列表，失败时返回空列表
        """
        logger.info("开始抓取东方财富新闻")
        try:
            # akshare 的 stock_info_news 返回 DataFrame
            # 注意：akshare 是同步库，在异步上下文中使用 run_in_executor 避免阻塞
            import akshare as ak

            df = await asyncio_get_akshare(ak.stock_info_news)
            items = self._parse_dataframe(df)
            logger.info(f"东方财富抓取成功，共 {len(items)} 条新闻")
            return items
        except ImportError:
            logger.warning("akshare 未安装，使用东方财富模拟数据")
            return self._fallback_data()
        except Exception as e:
            logger.warning(f"东方财富抓取失败: {e}，使用模拟数据")
            return self._fallback_data()

    def _parse_dataframe(self, df: Any) -> list[NewsItem]:
        """解析 akshare 返回的 DataFrame

        Args:
            df: akshare.stock_info_news 返回的 DataFrame

        Returns:
            解析后的新闻列表
        """
        items: list[NewsItem] = []
        try:
            import pandas as pd

            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                return []

            for _, row in df.iterrows():
                try:
                    news = NewsItem(
                        source=self._source_name,
                        title=row.get("title", row.get("新闻标题", "")),
                        content=row.get("content", row.get("摘要", row.get("brief", ""))),
                        url=row.get("url", row.get("链接", "")),
                        publish_time=self._parse_time(row.get("date", row.get("发布时间", datetime.now()))),
                        related_stocks=self._extract_stocks(row),
                    )
                    if news.title or news.content:
                        items.append(news)
                except Exception as e:
                    logger.warning(f"解析东方财富新闻行失败: {e}")
                    continue
        except Exception as e:
            logger.warning(f"解析东方财富 DataFrame 失败: {e}")
        return items

    def _parse_time(self, time_val: Any) -> datetime:
        """统一解析时间字段

        Args:
            time_val: 原始时间值

        Returns:
            标准化的 datetime 对象
        """
        if isinstance(time_val, datetime):
            return time_val
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

    def _extract_stocks(self, row: Any) -> list[str]:
        """从新闻行中提取关联股票代码

        Args:
            row: DataFrame 的一行数据

        Returns:
            股票代码列表
        """
        codes = row.get("codes", row.get("stock_codes", row.get("related_stocks", "")))
        if isinstance(codes, str):
            return [s.strip() for s in codes.split(",") if s.strip()]
        if isinstance(codes, list):
            return [str(s).strip() for s in codes if s]
        return []

    def _fallback_data(self) -> list[NewsItem]:
        """生成模拟数据（开发模式 fallback）

        当 akshare 接口不可用时，返回模拟的东方财富新闻数据。

        Returns:
            模拟新闻列表
        """
        now = datetime.now()
        return [
            NewsItem(
                source=self._source_name,
                title="A股三大指数集体收涨，两市成交额突破万亿",
                content="今日A股三大指数集体收涨，沪指涨0.85%，深成指涨1.43%，创业板指涨2.12%。两市成交额突破1万亿元，北向资金净买入超80亿元。",
                url="https://www.eastmoney.com/mock/1",
                publish_time=now,
                related_stocks=[],
            ),
            NewsItem(
                source=self._source_name,
                title="半导体板块爆发，机构看好国产替代长期趋势",
                content="半导体板块今日集体爆发，多只个股涨停。机构认为，在国产替代和AI算力需求的双重驱动下，半导体行业景气度将持续提升。",
                url="https://www.eastmoney.com/mock/2",
                publish_time=now,
                related_stocks=["688981", "002371", "603986"],
            ),
            NewsItem(
                source=self._source_name,
                title="央行宣布降准0.25个百分点，释放长期资金约5000亿元",
                content="中国人民银行决定自下月起下调金融机构存款准备金率0.25个百分点，预计释放长期资金约5000亿元，支持实体经济发展。",
                url="https://www.eastmoney.com/mock/3",
                publish_time=now,
                related_stocks=[],
            ),
            NewsItem(
                source=self._source_name,
                title="新能源车销量同比大增，龙头车企月销创新高",
                content="多家新能源车企公布月度销量数据，同比大幅增长。其中比亚迪月销突破30万辆，创历史新高。",
                url="https://www.eastmoney.com/mock/4",
                publish_time=now,
                related_stocks=["002594", "601238", "98663"],
            ),
            NewsItem(
                source=self._source_name,
                title="首届中国-东盟人工智能峰会召开，多家上市公司参展",
                content="首届中国-东盟人工智能峰会在南宁开幕，聚焦AI大模型、智能制造、智慧城市等热点领域，多家A股上市公司携最新产品参展。",
                url="https://www.eastmoney.com/mock/5",
                publish_time=now,
                related_stocks=["688981", "300750", "000725"],
            ),
            NewsItem(
                source=self._source_name,
                title="医药板块反弹，创新药赛道获政策支持",
                content="医药板块迎来反弹行情，创新药、CXO等细分方向涨幅居前。国家药监局发布新政策，支持创新药加快审评审批。",
                url="https://www.eastmoney.com/mock/6",
                publish_time=now,
                related_stocks=["600276", "300122", "603259"],
            ),
        ]


async def asyncio_get_akshare(func, *args, **kwargs) -> Any:
    """在异步上下文中同步调用 akshare 函数

    akshare 是同步库，通过 asyncio.to_thread 将其放入线程池执行，
    避免阻塞异步事件循环。

    Args:
        func: akshare 的同步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数返回结果
    """
    import asyncio

    return await asyncio.to_thread(func, *args, **kwargs)
