"""
AI 智能分析接口模块

提供 AI 选股解释、智能对话（SSE 流式响应）和快速建议等 REST API。
数据库/LLM 不可用时返回友好的降级信息，不报错崩溃。
"""

import json
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger

from app.services.ai_explainer import ai_explainer

router = APIRouter()


@router.get("/explain/{symbol}")
async def explain_stock(
    symbol: str,
    date: Optional[str] = Query(None, description="查询日期（YYYY-MM-DD，默认当天）"),
):
    """
    AI 选股解释

    查询指定股票的因子数据，调用 LLM 生成自然语言选股理由。
    LLM 不可用时返回基于因子数据的降级解释。
    """
    try:
        result = await ai_explainer.explain_stock(symbol, date)
        logger.info("选股解释完成: symbol={}", symbol)
        return {"code": 0, "message": "success", "data": result}
    except Exception as e:
        logger.error("选股解释异常: {}", e)
        return {
            "code": 0,
            "message": "success（降级）",
            "data": {
                "symbol": symbol,
                "explanation": f"AI 服务暂时不可用，请稍后再试。错误：{str(e)}",
                "factors": [],
            },
        }


@router.post("/chat")
async def chat(
    message: str = Body(..., embed=True, description="用户消息"),
    context: Optional[str] = Body(None, description="上下文 JSON 字符串（可选）"),
):
    """
    AI 对话（返回 SSE 流式响应）

    使用 Server-Sent Events 格式逐 token 返回 AI 回复。
    SSE 格式：data: {"text": "..."}\n\n

    Args:
        message: 用户输入的消息
        context: 可选上下文 JSON（如 {"market_summary": "...", "sector_summary": "..."}）
    """
    # 解析上下文 JSON
    context_dict = {}
    if context:
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            logger.warning("上下文 JSON 解析失败，忽略: {}", context)

    async def event_generator():
        """SSE 事件生成器"""
        try:
            async for token in ai_explainer.stream_chat(message, context_dict):
                yield f"data: {json.dumps({'text': token}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("流式对话异常: {}", e)
            yield f"data: {json.dumps({'text': f'AI 服务暂时不可用：{str(e)}'}, ensure_ascii=False)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    logger.info("AI 流式对话开始: message={}", message[:50])
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/suggest/{symbol}")
async def suggest_reason(symbol: str):
    """
    快速建议（轻量版，不调 LLM）

    基于因子数据直接生成简洁的建议文本，响应速度快，适合频繁调用。
    """
    try:
        result = await ai_explainer.suggest_reason(symbol)
        logger.info("快速建议完成: symbol={}", symbol)
        return {"code": 0, "message": "success", "data": result}
    except Exception as e:
        logger.error("快速建议异常: {}", e)
        return {
            "code": 0,
            "message": "success（降级）",
            "data": {
                "symbol": symbol,
                "suggestion": "暂无足够数据生成建议",
                "factors": [],
            },
        }
