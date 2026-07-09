"""
Celery 异步任务应用模块

创建 Celery 应用实例，用于执行定时/异步数据采集、分析和报告生成任务。
"""

from celery import Celery
from app.config import get_settings


def create_celery_app() -> Celery:
    """
    创建并配置 Celery 应用实例

    使用 Redis 作为消息代理和结果后端。

    Returns:
        Celery: 配置完成的 Celery 应用
    """
    settings = get_settings()
    celery_app = Celery(
        "astock_tasks",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
    )

    # Celery 配置
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 单任务最长 30 分钟
        task_soft_time_limit=25 * 60,
        worker_max_tasks_per_child=200,  # 防止内存泄漏
    )

    # 自动发现 tasks 目录下的任务
    celery_app.autodiscover_tasks(["app.tasks"])

    # 定时任务调度配置
    from celery.schedules import crontab

    celery_app.conf.beat_schedule = {
        # 交易日 15:30 计算因子
        "compute-factors-at-1530": {
            "task": "app.tasks.data_collect.compute_and_store_factors",
            "schedule": crontab(hour=15, minute=30, day_of_week="1-5"),
        },
        # 交易日 16:00 盘后风控扫描
        "risk-scan-at-1600": {
            "task": "app.tasks.data_collect.scan_risk_after_hours",
            "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
        },
        # 新闻抓取（测试期每 30 分钟，正式环境按设计文档频率）
        "crawl-cls-every-30min": {
            "task": "app.tasks.news_tasks.crawl_cls",
            "schedule": crontab(minute="*/30"),
        },
        "crawl-eastmoney-every-30min": {
            "task": "app.tasks.news_tasks.crawl_eastmoney",
            "schedule": crontab(minute="*/30"),
        },
        "crawl-xueqiu-every-60min": {
            "task": "app.tasks.news_tasks.crawl_xueqiu",
            "schedule": crontab(minute="*/60"),
        },
    }

    return celery_app


# 全局 Celery 应用实例
celery_app = create_celery_app()
