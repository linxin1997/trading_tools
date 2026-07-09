"""
风控接口模块

提供告警列表查询、止损规则列表查询和规则参数更新等 REST API。
TTS（文字转语音）放在前端用 Web Speech API 实现，后端不播报语音。
后端只推送告警事件到 WebSocket。
"""

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from app.services.risk_guard import risk_guard

router = APIRouter()


@router.get("/alerts")
async def get_alerts():
    """
    获取告警列表

    触发盘后风控扫描，返回所有触发的告警。
    数据库不可用时返回空列表。
    """
    try:
        alerts = await risk_guard.scan_after_hours()
        logger.info("获取告警列表完成，共 {} 条", len(alerts))
        return {"code": 0, "message": "success", "data": [a.to_dict() for a in alerts]}
    except Exception as e:
        logger.error(f"获取告警列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_rules():
    """
    获取止损规则列表

    返回所有预设止损规则及其当前参数配置。
    """
    rules = risk_guard.get_rules()
    logger.info("获取规则列表完成，共 {} 条", len(rules))
    return {"code": 0, "message": "success", "data": rules}


@router.put("/rules/{rule_id}")
async def update_rule(
    rule_id: int,
    threshold: float = Query(..., description="新的阈值"),
):
    """
    更新止损规则参数

    Args:
        rule_id: 规则 ID
        threshold: 新的阈值（根据规则类型不同含义不同）
    """
    try:
        updated = risk_guard.update_rule(rule_id, threshold)
        if updated is None:
            raise HTTPException(status_code=404, detail=f"规则 ID={rule_id} 不存在")
        logger.info("更新规则成功: id={}, threshold={}", rule_id, threshold)
        return {"code": 0, "message": "success", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("更新规则异常: {}", e)
        raise HTTPException(status_code=500, detail=f"更新规则失败: {str(e)}")
