"""
报告生成接口模块

提供日/周/月度复盘报告、PDF 导出的 REST API。
支持列表查询和详情查看。
"""

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------


class ApiResponse(BaseModel):
    """通用 API 响应"""
    code: int = 0
    message: str = "success"
    data: object = None


class ReportRow(BaseModel):
    """报告列表中的一行"""
    date: str
    title: str
    summary: str
    type: str  # daily / weekly / monthly
    has_detail: bool = True


class ReportDetail(BaseModel):
    """报告详情"""
    date: str
    title: str
    html_content: str


# ---------------------------------------------------------------------------
# 接口
# ---------------------------------------------------------------------------


@router.get("", response_model=ApiResponse)
async def list_reports(
    days: int = Query(30, description="返回最近 N 天的报告列表"),
):
    """
    获取报告列表

    返回最近 N 天的报告列表，实际数据由 report_service 生成。
    当前返回模拟数据展示格式。
    """
    reports = []
    today = date.today()
    for i in range(min(days, 30)):
        d = today - timedelta(days=i)
        # 跳过周末
        if d.weekday() >= 5:
            continue
        date_str = d.isoformat()
        report_type = "daily"
        if i == 0:
            title = f"{date_str} 日度复盘"
            summary = f"今日 A 股市场概况、板块轮动、资金流向分析"
        elif i == 6:
            report_type = "weekly"
            title = f"{date_str} 周度复盘"
            summary = f"本周市场回顾、行业表现、后市展望"
        elif i % 30 == 0:
            report_type = "monthly"
            title = f"{date_str} 月度复盘"
            summary = f"本月市场运行情况、重点板块、投资策略"
        else:
            title = f"{date_str} 日度复盘"
            summary = f"A 股市场每日复盘报告"

        reports.append(ReportRow(
            date=date_str,
            title=title,
            summary=summary,
            type=report_type,
        ))

    return ApiResponse(data=reports)


@router.get("/daily", response_model=ApiResponse)
async def get_daily_report():
    """获取最新日度复盘报告"""
    return ApiResponse(code=501, message="Not Implemented")


@router.get("/weekly", response_model=ApiResponse)
async def get_weekly_report():
    """获取最新周度复盘报告"""
    return ApiResponse(code=501, message="Not Implemented")


@router.get("/monthly", response_model=ApiResponse)
async def get_monthly_report():
    """获取最新月度复盘报告"""
    return ApiResponse(code=501, message="Not Implemented")


@router.get("/export", response_model=ApiResponse)
async def export_report():
    """导出复盘报告为 PDF"""
    return ApiResponse(code=501, message="Not Implemented")


@router.get("/{report_date}", response_model=ApiResponse)
async def get_report_detail(report_date: str):
    """
    获取指定日期的报告详情

    Args:
        report_date: 报告日期 YYYY-MM-DD
    """
    return ApiResponse(data=ReportDetail(
        date=report_date,
        title=f"{report_date} 复盘报告",
        html_content=f"<h1>{report_date} 复盘报告</h1><p>报告生成中...</p>",
    ))
