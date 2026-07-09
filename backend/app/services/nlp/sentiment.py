"""
NLP 情感分析模块

实现基于 Qwen2.5-3B（通过 Ollama API）的零样本情感分析。
采用错峰调度策略，按需加载模型，调用完成后自动卸载（keep_alive=0），
不常驻 GPU，节约显存资源。
"""

import json
from typing import Any

import httpx
from loguru import logger

from app.config import get_settings


# 情感分类的 Prompt 模板
SENTIMENT_PROMPT_TEMPLATE = """你是一个金融文本情感分析助手。请分析以下文本的情感倾向，只返回 JSON 格式结果，不要包含其他内容。

文本：{text}

请判断该文本的情感倾向是 positive（正面）、negative（负面）还是 neutral（中性），并给出置信度分数（0.0-1.0）。

返回格式（严格 JSON，不要包含 ```json 标记）：
{{"label": "positive|negative|neutral", "score": 0.0-1.0}}"""


class SentimentAnalyzer:
    """情感分析器，调用 Qwen2.5-3B 零样本情感分类

    通过 Ollama API 调用 qwen2.5:3b-instruct-q4_K_M 模型，
    以零样本方式对金融新闻文本进行情感分类。
    支持单条分析和批量分析（每批 10 条，串行调用避免 GPU OOM）。
    """

    def __init__(self):
        """初始化情感分析器

        从全局配置读取 Ollama 服务地址和模型名称。
        """
        settings = get_settings()
        self._base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self._model = settings.OLLAMA_SENTIMENT_MODEL
        self._api_url = f"{self._base_url}/api/chat"
        self._batch_size = 10  # 每批最多分析条数
        logger.info(f"情感分析器初始化完成，模型: {self._model}，API: {self._api_url}")

    async def analyze(self, text: str) -> dict[str, Any]:
        """分析单条新闻情感

        调用 Ollama API 执行零样本情感分类，
        失败时返回默认中性结果。

        Args:
            text: 待分析的新闻文本

        Returns:
            情感分析结果字典，包含：
                - label: "positive" | "negative" | "neutral"
                - score: 置信度分数（0.0-1.0）
        """
        if not text or not text.strip():
            return {"label": "neutral", "score": 0.5}

        prompt = SENTIMENT_PROMPT_TEMPLATE.format(text=text[:1000])  # 限制输入长度
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 64},
            "keep_alive": "0s",  # 调用完成后立即卸载模型
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self._api_url, json=payload)
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content", "").strip()
                return self._parse_response(content)
        except httpx.TimeoutException:
            logger.warning(f"情感分析 API 超时（文本长度: {len(text)}），返回默认中性")
            return {"label": "neutral", "score": 0.5}
        except httpx.HTTPStatusError as e:
            logger.warning(f"情感分析 API 返回错误状态码: {e.response.status_code}，返回默认中性")
            return {"label": "neutral", "score": 0.5}
        except Exception as e:
            logger.warning(f"情感分析调用失败: {e}，返回默认中性")
            return {"label": "neutral", "score": 0.5}

    def _parse_response(self, content: str) -> dict[str, Any]:
        """解析模型返回的 JSON 结果

        Args:
            content: 模型返回的原始文本

        Returns:
            解析后的情感分析结果
        """
        # 尝试直接解析 JSON
        try:
            result = json.loads(content)
            label = result.get("label", "neutral")
            score = float(result.get("score", 0.5))
            # 校验 label 合法性
            if label not in ("positive", "negative", "neutral"):
                label = "neutral"
            # 校验 score 范围
            score = max(0.0, min(1.0, score))
            return {"label": label, "score": score}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # 如果直接解析失败，尝试从文本中提取 JSON
        try:
            import re

            json_match = re.search(r"\{[^{}]*\"label\"[^{}]*\}", content)
            if json_match:
                result = json.loads(json_match.group())
                label = result.get("label", "neutral")
                score = float(result.get("score", 0.5))
                if label not in ("positive", "negative", "neutral"):
                    label = "neutral"
                score = max(0.0, min(1.0, score))
                return {"label": label, "score": score}
        except Exception:
            pass

        logger.warning(f"无法解析模型返回内容: {content[:100]}，返回默认中性")
        return {"label": "neutral", "score": 0.5}

    async def analyze_batch(self, texts: list[str]) -> list[dict[str, Any]]:
        """批量分析多条新闻情感

        每批最多处理 10 条，串行调用避免 GPU 显存溢出（OOM）。
        单条失败不影响其他条目的分析。

        Args:
            texts: 待分析的文本列表

        Returns:
            情感分析结果列表，顺序与输入一致
        """
        results: list[dict[str, Any]] = []
        total = len(texts)

        logger.info(f"开始批量情感分析，共 {total} 条（每批 {self._batch_size} 条，串行执行）")

        for i in range(0, total, self._batch_size):
            batch = texts[i : i + self._batch_size]
            logger.debug(f"分析第 {i + 1}-{min(i + self._batch_size, total)} 条（共 {total} 条）")

            for text in batch:
                result = await self.analyze(text)
                results.append(result)

        # 统计结果
        labels = [r.get("label", "neutral") for r in results]
        positive_count = labels.count("positive")
        negative_count = labels.count("negative")
        neutral_count = labels.count("neutral")
        logger.info(
            f"批量情感分析完成: 正面 {positive_count} 条, "
            f"负面 {negative_count} 条, 中性 {neutral_count} 条"
        )

        return results
