"""
选股定时任务模块

定义 Celery 定时任务，每日收盘后执行选股策略并记录结果。
"""

from celery import shared_task


@shared_task
def run_screening():
    """
    收盘后自动运行选股策略

    计算多因子得分，筛选符合条件的股票，结果写入数据库供前端查询。
    """
    # TODO: 调用 StockPicker 执行选股策略
    pass
