"""
AI 智能问答服务模块

提供基于 LLM 的股票投资问答交互功能。
"""

from typing import Any


class AIChat:
    """AI 智能问答对话服务"""

    async def chat(self, message: str, context: dict = None) -> str:
        """
        处理用户消息并返回 AI 回复

        Args:
            message: 用户输入的消息
            context: 对话上下文

        Returns:
            AI 回复文本
        """
        # TODO: 将用户消息与上下文组合，调用 LLM 返回回复
        return f"收到: {message}"
