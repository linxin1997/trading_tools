"""
AI 选股解释与对话服务模块

提供基于 LLM 的选股原因解释和智能问答功能。
当数据库或 LLM 不可用时返回友好的降级信息，不会崩溃。

因子数据统一从 factor_value 长表查询，使用小写+下划线因子名规范。
"""

import json
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from loguru import logger

from app.services.llm_service import LLMService


class AIExplainer:
    """AI 选股解释服务，提供选股原因解释和智能对话"""

    async def explain_stock(self, symbol: str, date: str = None) -> dict:
        """
        解释某只股票的入选理由

        流程：
        1. 从 factor_value 查询该股票因子
        2. 构造解释 Prompt
        3. 调用 LLMService.generate()
        4. 返回因子分析 + 自然语言理由

        Args:
            symbol: 股票代码
            date: 查询日期（默认当天）

        Returns:
            包含因子分析和自然语言解释的字典
        """
        date = date or datetime.now().strftime("%Y-%m-%d")
        logger.info("开始解释股票入选理由: symbol={}, date={}", symbol, date)

        # 1. 查询因子数据
        factors = await self._query_factors(symbol, date)

        # 2. 构造 Prompt
        prompt = self._build_explain_prompt(symbol, factors, date)

        # 3. 调用 LLM
        llm_reason = ""
        try:
            llm_reason = await LLMService.generate(prompt)
            logger.info("LLM 解释生成成功: symbol={}", symbol)
        except Exception as e:
            logger.warning("LLM 调用失败，使用降级解释: {}", e)
            llm_reason = self._fallback_explain(factors)

        # 4. 返回结果
        return {
            "symbol": symbol,
            "date": date,
            "factors": factors,
            "explanation": llm_reason,
        }

    async def chat(self, message: str, context: dict = None) -> str:
        """
        AI 对话接口

        带市场上下文的对话（可查询市场概况、板块逻辑等）。

        Args:
            message: 用户消息
            context: 对话上下文（可选）

        Returns:
            AI 回复文本
        """
        logger.info("AI 对话请求: message={}", message[:50])

        # 构建带上下文的 Prompt
        prompt = self._build_chat_prompt(message, context or {})

        # 调用 LLM
        try:
            reply = await LLMService.generate(prompt)
            logger.info("AI 对话回复生成成功")
            return reply
        except Exception as e:
            logger.warning("AI 对话调用 LLM 失败，使用降级回复: {}", e)
            return self._fallback_chat(message)

    async def stream_chat(self, message: str, context: dict = None) -> AsyncIterator[str]:
        """
        AI 对话流式接口（SSE）

        Args:
            message: 用户消息
            context: 对话上下文（可选）

        Yields:
            str: 逐 token 生成的文本片段
        """
        logger.info("AI 流式对话请求: message={}", message[:50])
        prompt = self._build_chat_prompt(message, context or {})

        try:
            async for token in LLMService.stream_generate(prompt):
                yield token
        except Exception as e:
            logger.warning("AI 流式对话调用 LLM 失败，使用降级回复: {}", e)
            yield self._fallback_chat(message)

    async def suggest_reason(self, symbol: str) -> dict:
        """
        快速建议（轻量版，不调 LLM）

        基于因子数据直接生成简洁的建议文本。

        Args:
            symbol: 股票代码

        Returns:
            建议结果字典
        """
        date = datetime.now().strftime("%Y-%m-%d")
        factors = await self._query_factors(symbol, date)

        if not factors:
            return {
                "symbol": symbol,
                "suggestion": "暂无足够数据生成建议",
                "factors": [],
            }

        # 根据因子数据生成简单建议
        reasons = []
        for f in factors:
            name = f.get("factor_name", "")
            value = f.get("value", 0)
            if name == "pe_ttm" and 0 < value < 15:
                reasons.append(f"市盈率较低（{value:.1f}），估值合理")
            elif name == "change_pct" and value > 3:
                reasons.append(f"当日涨幅 {value:.2f}%，短期强势")
            elif name == "volume_ratio" and value > 2:
                reasons.append(f"放量 {value:.2f} 倍，资金关注度高")

        suggestion = "；".join(reasons) if reasons else "因子表现中性，建议结合技术面综合判断"

        return {
            "symbol": symbol,
            "suggestion": suggestion,
            "factors": factors,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    async def _query_factors(self, symbol: str, date: str) -> list[dict[str, Any]]:
        """
        从 factor_value 长表查询因子数据

        Args:
            symbol: 股票代码
            date: 查询日期

        Returns:
            因子列表，每项包含 factor_name 和 value
        """
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import text

            async with async_session_factory() as session:
                sql = text("""
                    SELECT factor_name, value
                    FROM factor_value
                    WHERE symbol = :symbol AND trade_date = :date
                """)
                rows = await session.execute(sql, {"symbol": symbol, "date": date})
                results = [{"factor_name": r[0], "value": r[1]} for r in rows.fetchall()]
                logger.info("查询到 {} 个因子: symbol={}, date={}", len(results), symbol, date)
                return results

        except Exception as e:
            logger.warning("因子查询失败: {}", e)
            return []

    def _build_explain_prompt(self, symbol: str, factors: list, date: str) -> str:
        """构造选股解释 Prompt"""
        factor_text = json.dumps(factors, ensure_ascii=False, indent=2) if factors else "（无因子数据）"
        return (
            f"你是一名 A 股投资分析师。请分析股票 {symbol} 在 {date} 的因子数据，"
            f"并给出该股票可能被选中的理由。\n\n"
            f"因子数据如下：\n{factor_text}\n\n"
            f"请从基本面、技术面、资金面等角度分析入选理由。"
        )

    def _build_chat_prompt(self, message: str, context: dict) -> str:
        """构造对话 Prompt"""
        context_text = ""
        if context:
            market_summary = context.get("market_summary", "")
            sector_summary = context.get("sector_summary", "")
            if market_summary:
                context_text += f"当前市场概况：{market_summary}\n"
            if sector_summary:
                context_text += f"板块逻辑：{sector_summary}\n"

        if context_text:
            return f"你是一名 A 股投资顾问。以下为当前市场背景：\n{context_text}\n用户提问：{message}"
        else:
            return f"你是一名 A 股投资顾问。请回答用户问题：{message}"

    def _fallback_explain(self, factors: list) -> str:
        """LLM 不可用时的降级解释"""
        if not factors:
            return "暂无因子数据，无法分析入选理由。"
        factor_names = [f.get("factor_name", "") for f in factors if f.get("value")]
        return f"该股票在以下因子上有表现：{', '.join(factor_names)}。建议结合更多数据综合判断。"

    def _fallback_chat(self, message: str) -> str:
        """LLM 不可用时的降级回复"""
        return f"AI 服务暂时不可用。关于「{message[:30]}」的问题，请稍后再试或查阅相关市场数据自行分析。"


# 全局 AI 解释器单例
ai_explainer = AIExplainer()
