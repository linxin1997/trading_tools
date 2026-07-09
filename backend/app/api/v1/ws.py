"""
WebSocket 实时行情端点模块

提供实时行情推送、订阅/取消订阅等 WebSocket 功能。
采用"单消费者 + 广播"模式：一个后台协程消费 Redis Stream，
根据订阅表将行情广播给对应客户端。
"""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.services.redis_stream import subscribe_quotes
from app.services.risk_guard import RiskGuard, Alert


def _safe_float(d: dict, key: str) -> float | None:
    """安全提取浮点数"""
    v = d.get(key)
    if v is not None:
        try:
            return float(v)
        except (ValueError, TypeError):
            pass
    return None


def _safe_int(d: dict, key: str) -> int | None:
    """安全提取整数"""
    v = d.get(key)
    if v is not None:
        try:
            return int(float(v))
        except (ValueError, TypeError):
            pass
    return None


router = APIRouter()


class ConnectionManager:
    """
    WebSocket 连接管理器

    维护订阅表和 WebSocket 连接状态，支持按 symbol 广播行情。
    """

    def __init__(self):
        """
        初始化连接管理器

        subscribers: dict[str, set[WebSocket]]
            symbol -> 订阅该 symbol 的所有 WebSocket 连接
        user_subscriptions: dict[WebSocket, set[str]]
            每个 WebSocket 连接 -> 其订阅的 symbol 集合
        holdings: dict[str, dict]
            持仓缓存，symbol -> position dict（用于实时风控）
        """
        self.subscribers: dict[str, set[WebSocket]] = {}
        self.user_subscriptions: dict[WebSocket, set[str]] = {}

        # 持仓缓存与风控引擎
        self.holdings: dict[str, dict] = {}
        self.risk_guard = RiskGuard()
        self._holdings_loaded = False

        # 后台消费任务
        self._consumer_task: asyncio.Task | None = None
        self._running = False

    async def connect(self, websocket: WebSocket):
        """
        接受并注册新的 WebSocket 连接

        Args:
            websocket: WebSocket 连接对象
        """
        await websocket.accept()
        self.user_subscriptions[websocket] = set()
        logger.info(f"WebSocket 客户端已连接，当前连接数: {len(self.user_subscriptions)}")

    def disconnect(self, websocket: WebSocket):
        """
        移除断开的 WebSocket 连接，清理其所有订阅

        Args:
            websocket: WebSocket 连接对象
        """
        # 获取该连接的所有订阅
        subscribed = self.user_subscriptions.pop(websocket, set())

        # 从每个 symbol 的订阅列表中移除该连接
        for symbol in subscribed:
            symbol_subs = self.subscribers.get(symbol)
            if symbol_subs:
                symbol_subs.discard(websocket)
                if not symbol_subs:
                    del self.subscribers[symbol]

        logger.info(
            f"WebSocket 客户端已断开，清理 {len(subscribed)} 个订阅，"
            f"剩余连接数: {len(self.user_subscriptions)}"
        )

    async def subscribe(self, websocket: WebSocket, symbols: list[str]):
        """
        为指定连接订阅一组股票代码

        Args:
            websocket: WebSocket 连接对象
            symbols: 要订阅的股票代码列表
        """
        if websocket not in self.user_subscriptions:
            return

        for symbol in symbols:
            self.user_subscriptions[websocket].add(symbol)
            if symbol not in self.subscribers:
                self.subscribers[symbol] = set()
            self.subscribers[symbol].add(websocket)

        logger.debug(f"客户端订阅: {symbols}")

    async def unsubscribe(self, websocket: WebSocket, symbols: list[str]):
        """
        为指定连接取消订阅一组股票代码

        Args:
            websocket: WebSocket 连接对象
            symbols: 要取消订阅的股票代码列表
        """
        if websocket not in self.user_subscriptions:
            return

        for symbol in symbols:
            self.user_subscriptions[websocket].discard(symbol)
            symbol_subs = self.subscribers.get(symbol)
            if symbol_subs:
                symbol_subs.discard(websocket)
                if not symbol_subs:
                    del self.subscribers[symbol]

        logger.debug(f"客户端取消订阅: {symbols}")

    async def broadcast_quote(self, quote: dict[str, Any]):
        """
        将一条行情广播给所有订阅了对应 symbol 的连接

        将原始行情数据按前端协议格式包装：{ type: "quote", data: { code, name, price, changePercent, ... } }

        Args:
            quote: 行情数据字典，必须包含 "symbol" 键
        """
        symbol = quote.get("symbol", "")
        if not symbol:
            return

        # 检查是否存在订阅者
        symbol_subs = self.subscribers.get(symbol)
        if not symbol_subs:
            return

        # 转换字段名以匹配前端 Quote 接口
        pct = quote.get("pct_change") or quote.get("change_pct") or 0
        try:
            pct = float(pct)
        except (ValueError, TypeError):
            pct = 0

        data = {
            "code": quote.get("symbol", ""),
            "name": quote.get("name", ""),
            "price": _safe_float(quote, "price"),
            "changePercent": round(pct, 2),
            "open": _safe_float(quote, "open"),
            "high": _safe_float(quote, "high"),
            "low": _safe_float(quote, "low"),
            "volume": _safe_int(quote, "volume"),
            "amount": _safe_float(quote, "amount"),
        }

        # 异动检测
        if abs(pct) > 3:
            data["alert"] = "异动提醒"
            logger.info(f"异动检测: {symbol} 涨跌幅 {pct}%")

        message = json.dumps({"type": "quote", "data": data}, ensure_ascii=False)

        # 向所有订阅了该 symbol 的连接发送（并发）
        disconnected = []

        async def _send(ws: WebSocket):
            try:
                await ws.send_text(message)
            except Exception:
                nonlocal disconnected
                disconnected.append(ws)

        tasks = [_send(ws) for ws in symbol_subs]
        if tasks:
            await asyncio.gather(*tasks)

        # 清理已断开的连接
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_alert(self, alert_dict: dict):
        """
        将风控告警广播给所有已连接的客户端

        Args:
            alert_dict: 告警字典（含 symbol、rule、message 等字段）
        """
        message = json.dumps(
            {"type": "alert", "data": alert_dict},
            ensure_ascii=False,
        )
        disconnected = []
        for ws in list(self.user_subscriptions.keys()):
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    async def _load_holdings(self):
        """
        从数据库加载持仓列表到缓存

        加载失败时不阻塞，仅记录警告并跳过风控检查。
        """
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import text

            async with async_session_factory() as session:
                sql = text("""
                    SELECT p.symbol, p.volume, p.cost_price, p.cost_price AS current_price
                    FROM portfolio p
                """)
                result = await session.execute(sql)
                self.holdings.clear()
                for row in result:
                    # symbol 为 6 位数字代码，行情中的 symbol 可能带后缀
                    self.holdings[row.symbol] = {
                        "code": row.symbol,
                        "name": "",
                        "shares": float(row.volume or 0),
                        "cost_price": float(row.cost_price or 0),
                        "current_price": float(row.current_price or 0),
                    }
            self._holdings_loaded = True
            logger.info("持仓列表加载完成，共 {} 条记录", len(self.holdings))
        except Exception as e:
            logger.warning("加载持仓列表失败，跳过实时风控检查: {}", e)
            self._holdings_loaded = True  # 标记已尝试，避免重复加载

    @staticmethod
    def _extract_code(symbol: str) -> str:
        """从 symbol（如 000001.SZ）中提取 6 位数字代码"""
        return symbol.split(".")[0].strip()

    def get_subscribed_symbols(self, websocket: WebSocket) -> set[str]:
        """
        获取指定连接订阅的股票代码集合

        Args:
            websocket: WebSocket 连接对象

        Returns:
            股票代码集合
        """
        return self.user_subscriptions.get(websocket, set())

    # ------------------------------------------------------------------
    # 后台消费者
    # ------------------------------------------------------------------

    async def start_consumer(self):
        """
        启动后台消费协程

        创建一个协程从 Redis Stream 消费行情消息并广播给订阅者。
        """
        if self._running:
            logger.warning("WebSocket 消费者已在运行")
            return

        self._running = True
        self._consumer_task = asyncio.create_task(self._consumer_loop())
        logger.info("WebSocket 后台消费者已启动")

    async def stop_consumer(self):
        """
        停止后台消费协程
        """
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
            logger.info("WebSocket 后台消费者已停止")

    async def _consumer_loop(self):
        """
        消费循环

        从 Redis Stream QUOTE_STREAM 中持续读取行情消息，
        在广播前对持仓标的执行实时风控检查，触发告警后广播给所有客户端。
        """
        logger.info("WebSocket 消费者循环已开始")

        async for quote in subscribe_quotes(block_ms=1000):
            if not self._running:
                break

            # 懒加载持仓列表（仅首次尝试加载，失败不阻塞）
            if not self._holdings_loaded:
                await self._load_holdings()

            # 对持仓标的进行实时风控检查
            if self.holdings:
                symbol = quote.get("symbol", "")
                code = self._extract_code(symbol)
                position = self.holdings.get(code) or self.holdings.get(symbol)
                if position:
                    alert = await self.risk_guard.scan_realtime(position, quote)
                    if alert:
                        logger.warning("风控告警触发: {}", alert.message)
                        await self.broadcast_alert(alert.to_dict())

            await self.broadcast_quote(quote)

        logger.info("WebSocket 消费者循环已退出")


# 全局连接管理器
manager = ConnectionManager()


async def _heartbeat(ws: WebSocket, interval: int = 30):
    """WebSocket 心跳，每 interval 秒发送一次 ping"""
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                await ws.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break
    except asyncio.CancelledError:
        pass


@router.websocket("/market")
async def market_websocket(websocket: WebSocket):
    """
    实时行情 WebSocket 端点

    客户端连接后可通过 JSON 消息订阅/取消订阅行情：
    - 订阅: {"type": "subscribe", "symbols": ["000001.SZ", "600519.SH"]}
    - 取消订阅: {"type": "unsubscribe", "symbols": ["000001.SZ"]}

    Args:
        websocket: WebSocket 连接对象
    """
    await manager.connect(websocket)
    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    try:
        while True:
            # 接收客户端消息
            raw = await websocket.receive_text()

            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")
                symbols = msg.get("symbols", [])

                if msg_type == "subscribe":
                    await manager.subscribe(websocket, symbols)
                    # 返回当前订阅确认
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "subscribed",
                                "symbols": list(
                                    manager.get_subscribed_symbols(websocket)
                                ),
                            },
                            ensure_ascii=False,
                        )
                    )
                elif msg_type == "unsubscribe":
                    await manager.unsubscribe(websocket, symbols)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "unsubscribed",
                                "symbols": list(
                                    manager.get_subscribed_symbols(websocket)
                                ),
                            },
                            ensure_ascii=False,
                        )
                    )
                else:
                    await websocket.send_text(
                        json.dumps(
                            {"type": "error", "message": f"未知消息类型: {msg_type}"},
                            ensure_ascii=False,
                        )
                    )
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {"type": "error", "message": "消息格式错误，请发送 JSON"},
                        ensure_ascii=False,
                    )
                )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket 客户端断开连接")
    except Exception as e:
        manager.disconnect(websocket)
        logger.error(f"WebSocket 连接异常: {e}")
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
