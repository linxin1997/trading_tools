"""
大模型调用服务模块

封装 Ollama REST API，提供同步和流式文本生成能力。
"""

import json
from typing import AsyncIterator

import httpx
from loguru import logger

from app.config import get_settings


class LLMService:
    """大模型调用服务，封装 Ollama REST API"""

    @staticmethod
    async def generate(
        prompt: str,
        model: str = "qwen2.5:14b-instruct-q4_K_M",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        调用 LLM 生成文本

        发送 POST 请求到 Ollama /api/generate 接口。
        使用 httpx.AsyncClient 发送请求，超时 60 秒。

        Args:
            prompt: 输入提示词
            model: 模型名称，默认使用 qwen2.5:14b
            temperature: 生成温度，控制随机性（0.0 ~ 2.0）
            max_tokens: 最大生成 token 数

        Returns:
            str: 模型生成的文本内容

        Raises:
            httpx.HTTPError: 当 API 请求失败时抛出
        """
        settings = get_settings()
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"

        # 构造请求体，stream=False 表示非流式返回
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")

    @staticmethod
    async def stream_generate(
        prompt: str,
        model: str = "qwen2.5:3b-instruct-q4_K_M",
    ) -> AsyncIterator[str]:
        """
        流式生成（SSE 模式），用于盘中快问

        逐 token 产出文本，支持实时流式输出。
        使用 httpx.AsyncClient 的流式 API 逐行解析 SSE 响应。

        Args:
            prompt: 输入提示词
            model: 模型名称，默认使用轻量级 qwen2.5:3b

        Yields:
            str: 逐个生成的文本片段

        Raises:
            httpx.HTTPError: 当 API 请求失败时抛出
        """
        settings = get_settings()
        url = f"{settings.OLLAMA_BASE_URL}/api/generate"

        # stream=True 启用流式响应
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                # 逐行解析 SSE 格式响应
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("response", "")
                        if token:
                            yield token
                        # 当 done 为 True 时，表示生成结束
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        logger.warning(f"Ollama 响应 JSON 解析失败: {line}")
