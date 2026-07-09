"""
Tencent 实时行情提供商

使用腾讯免费行情接口（qt.gtimg.cn），无鉴权，支持批量查询。
作为 AKShare 实时行情的替代源。

用法:
    provider = TencentProvider()
    quotes = await provider.get_realtime_quotes(["000001", "600519"])
"""

import re
from datetime import datetime
from typing import Any

import httpx
from loguru import logger

from .base import BaseDataProvider


# 腾讯行情返回格式索引
QT_INDEX = {
    "market": 0,
    "name": 1,
    "code": 2,
    "open": 5,
    "yesterday_close": 4,
    "price": 3,
    "high": 6,
    "low": 7,
    "volume": 11,
    "amount": 12,
    "bid1": 13,
    "ask1": 14,
    "high_limit": 49,
    "low_limit": 50,
    "change_pct": 33,
    "change_amount": 32,
    "turnover": 38,
    "pe": 39,
    "amplitude": 43,
    "circulating_market_cap": 44,
    "total_market_cap": 45,
    "update_time": 30,
}


def _to_tencent_code(symbol: str) -> str:
    """转为腾讯格式（000001 → sz000001, 600519.SH → sh600519）"""
    s = symbol.upper().replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
    if s.startswith("6") or s.startswith("9"):
        return f"sh{s}"
    elif s.startswith("0") or s.startswith("3"):
        return f"sz{s}"
    return f"sz{s}"


def _from_tencent_code(tc: str) -> str:
    """腾讯代码转统一格式（sz000001 → 000001.SZ）"""
    exchange = tc[:2].upper()
    code = tc[2:]
    return f"{code}.{exchange}"


def _safe_float(fields: list[str], idx: int) -> float | None:
    if idx < len(fields):
        try:
            v = fields[idx].strip()
            return float(v) if v else None
        except (ValueError, IndexError):
            pass
    return None


def _safe_int(fields: list[str], idx: int) -> int | None:
    if idx < len(fields):
        try:
            v = fields[idx].strip()
            return int(float(v)) if v else None
        except (ValueError, IndexError):
            pass
    return None


def _parse_tencent_response(text: str) -> list[dict[str, Any]]:
    """解析腾讯行情响应"""
    quotes = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        match = re.search(r'"(.*)"', line)
        if not match:
            continue
        fields = match.group(1).split("~")
        if len(fields) < 50:
            continue
        raw_code = line.split("=")[0].strip()
        tc = raw_code[2:] if raw_code.startswith("v_") else raw_code
        try:
            name = fields[QT_INDEX["name"]]
            code = fields[QT_INDEX["code"]]
            if not code or not name:
                continue
            quotes.append({
                "symbol": _from_tencent_code(tc),
                "name": name,
                "code": code,
                "price": _safe_float(fields, QT_INDEX["price"]),
                "open": _safe_float(fields, QT_INDEX["open"]),
                "high": _safe_float(fields, QT_INDEX["high"]),
                "low": _safe_float(fields, QT_INDEX["low"]),
                "yesterday_close": _safe_float(fields, QT_INDEX["yesterday_close"]),
                "volume": _safe_int(fields, QT_INDEX["volume"]),
                "amount": _safe_float(fields, QT_INDEX["amount"]),
                "change_pct": _safe_float(fields, QT_INDEX["change_pct"]),
                "change_amount": _safe_float(fields, QT_INDEX["change_amount"]),
                "turnover": _safe_float(fields, QT_INDEX["turnover"]),
                "amplitude": _safe_float(fields, QT_INDEX["amplitude"]),
                "high_limit": _safe_float(fields, QT_INDEX["high_limit"]),
                "low_limit": _safe_float(fields, QT_INDEX["low_limit"]),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
        except (ValueError, IndexError):
            continue
    return quotes


class TencentProvider(BaseDataProvider):
    """腾讯实时行情提供商"""

    BASE_URL = "http://qt.gtimg.cn/q="
    MAX_SYMBOLS_PER_REQUEST = 100
    TIMEOUT = 5

    async def get_realtime_quote(self, code: str) -> dict[str, Any]:
        """获取单只股票实时行情"""
        quotes = await self.get_realtime_quotes([code])
        return quotes[0] if quotes else {}

    async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:
        """腾讯行情不提供 K 线，返回空"""
        return []

    async def get_realtime_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """获取批量实时行情，支持最多 100 只"""
        if not symbols:
            return []
        all_quotes = []
        for i in range(0, len(symbols), self.MAX_SYMBOLS_PER_REQUEST):
            batch = symbols[i: i + self.MAX_SYMBOLS_PER_REQUEST]
            tc_codes = ",".join([_to_tencent_code(s) for s in batch])
            url = self.BASE_URL + tc_codes
            try:
                async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                    resp = await client.get(url, headers={"Accept": "*/*"})
                    resp.raise_for_status()
                    resp.encoding = "gbk"
                    all_quotes.extend(_parse_tencent_response(resp.text))
            except Exception as e:
                logger.error(f"腾讯行情请求失败（批次 {i}）: {e}")
        return all_quotes
