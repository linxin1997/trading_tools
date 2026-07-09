"""
每日复盘报告生成任务模块

定义 Celery 定时任务，在收盘后自动生成复盘报告。
"""

import asyncio

from celery import shared_task
from loguru import logger

from app.services.report_service import ReportService


@shared_task(bind=True, max_retries=3)
def generate_daily_report(self, report_date: str = None):
    """
    收盘后自动生成日度复盘报告

    默认在交易日下午 18:00 触发。
    聚合当日行情、板块、资金等数据，调用 LLM 生成分析文本并渲染 HTML 报告。
    由于 Celery 任务默认运行在同步 worker 中，使用 asyncio.run() 包装异步调用。

    Args:
        report_date: 报告日期，格式 YYYY-MM-DD，为 None 时默认为当日

    Returns:
        dict: 包含报告日期、数据概要和 HTML 内容的字典

    Raises:
        Exception: 重试超过 max_retries 次后仍失败则抛出异常
    """
    try:
        logger.info(f"Celery 任务启动：生成 {report_date or '当日'} 复盘报告")
        service = ReportService()
        # Celery 任务默认是同步的，使用 asyncio.run() 包装异步调用
        result = asyncio.run(service.generate_daily(report_date))
        logger.info(f"复盘报告生成完成，日期：{result['date']}")
        return {
            "date": result["date"],
            "status": "success",
            "html_length": len(result["html"]),
        }
    except Exception as e:
        logger.error(f"复盘报告生成失败: {e}")
        # 重试机制，最多重试 3 次
        try:
            self.retry(countdown=60 * 5)  # 5 分钟后重试
        except self.MaxRetriesExceededError:
            logger.error("复盘报告生成任务超过最大重试次数")
            raise
