"""
风控引擎模块

实现 RiskGuard 风控引擎，提供实时止损扫描和盘后技术破位扫描功能。
- scan_realtime: 实时扫描（tick 级），仅检查价格止损
- scan_after_hours: 盘后扫描（15:30 触发），检查技术破位因子
数据库不可用时返回空列表，不报错崩溃。

所有因子数据统一从 factor_value 长表查询，使用小写+下划线因子名规范。
"""

import copy
from datetime import datetime
from typing import Any, Optional

from loguru import logger


class Alert:
    """告警模型"""

    def __init__(
        self,
        symbol: str,
        name: str,
        rule: str,
        message: str,
        severity: str = "warning",
    ):
        """
        初始化告警

        Args:
            symbol: 股票代码
            name: 股票名称
            rule: 触发规则标识（price_stop_loss / ma_breakdown / macd_death /
                  bollinger_breakdown / fund_outflow / negative_sentiment）
            message: 告警消息
            severity: 严重程度（critical / warning / info）
        """
        self.symbol = symbol
        self.name = name
        self.rule = rule
        self.message = message
        self.severity = severity
        self.timestamp = datetime.now().isoformat(sep="T", timespec="seconds")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "rule": self.rule,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp,
        }


class RiskGuard:
    """风控引擎，提供实时与盘后风控扫描"""

    # ------------------------------------------------------------------
    # 预设止损规则（用户只需填参数，不需要自定义 UI）
    # ------------------------------------------------------------------
    DEFAULT_RULES = {
        "price_stop_loss": {
            "id": 1,
            "name": "价格止损",
            "description": "现价跌破止损价时触发",
            "enabled": True,
            "threshold": 5.0,  # 跌幅百分比阈值
            "severity": "critical",
        },
        "ma_breakdown": {
            "id": 2,
            "name": "均线跌破",
            "description": "收盘价跌破 MA20 或 MA60 时触发",
            "enabled": True,
            "threshold": 20,  # 均线周期
            "severity": "warning",
        },
        "macd_death": {
            "id": 3,
            "name": "MACD 死叉",
            "description": "DIF 下穿 DEA 形成死叉时触发",
            "enabled": True,
            "threshold": 0,
            "severity": "warning",
        },
        "fund_outflow": {
            "id": 4,
            "name": "资金流出",
            "description": "主力资金净流出超过阈值时触发",
            "enabled": True,
            "threshold": 5.0,  # 流出百分比阈值
            "severity": "warning",
        },
        "negative_sentiment": {
            "id": 5,
            "name": "负面舆情",
            "description": "负面舆情强度超过阈值且跌幅超过 2% 时触发",
            "enabled": True,
            "threshold": 0.6,  # 舆情强度阈值 [0,1]
            "severity": "info",
        },
        "bollinger_breakdown": {
            "id": 6,
            "name": "布林带破位",
            "description": "收盘价跌破布林带下轨时触发",
            "enabled": True,
            "threshold": 0,
            "severity": "warning",
        },
    }

    def __init__(self):
        """初始化风控引擎"""
        self._rules = copy.deepcopy(self.DEFAULT_RULES)
        logger.info("风控引擎初始化完成，已加载 {} 条预设规则", len(self._rules))

    # ------------------------------------------------------------------
    # 规则管理
    # ------------------------------------------------------------------

    def get_rules(self) -> list[dict[str, Any]]:
        """获取所有止损规则列表"""
        return list(self._rules.values())

    def update_rule(self, rule_id: int, threshold: float) -> Optional[dict[str, Any]]:
        """
        更新止损规则参数

        Args:
            rule_id: 规则 ID
            threshold: 新的阈值

        Returns:
            更新后的规则字典，规则不存在时返回 None
        """
        for rule in self._rules.values():
            if rule["id"] == rule_id:
                rule["threshold"] = threshold
                logger.info("规则已更新: {} threshold={}", rule["name"], threshold)
                return rule
        logger.warning("规则 ID={} 不存在", rule_id)
        return None

    # ------------------------------------------------------------------
    # 实时扫描（tick 级）
    # ------------------------------------------------------------------

    async def scan_realtime(self, position: dict, quote: dict) -> Optional[Alert]:
        """
        实时扫描（tick 级）：仅检查价格止损

        被 WebSocket 消费协程调用，每收到一条行情检查一次。
        当现价跌破止损价时触发告警。

        Args:
            position: 持仓字典，需包含 cost_price 和 stop_loss_price 字段
            quote: 行情字典，需包含 current_price 或 price 字段

        Returns:
            触发告警时返回 Alert 对象，否则返回 None
        """
        rule = self._rules.get("price_stop_loss")
        if not rule or not rule["enabled"]:
            return None

        try:
            # 获取当前价格
            current_price = float(quote.get("current_price", 0) or quote.get("price", 0))
            if current_price <= 0:
                return None

            # 计算止损价：基于成本价和跌幅阈值
            cost_price = float(position.get("cost_price", 0))
            if cost_price <= 0:
                return None

            threshold_pct = float(rule["threshold"])
            stop_loss_price = cost_price * (1 - threshold_pct / 100.0)

            # 判断是否触发止损
            if current_price <= stop_loss_price:
                symbol = str(position.get("code", quote.get("symbol", "unknown")))
                name = str(position.get("name", quote.get("name", "")))
                message = (
                    f"{name}（{symbol}）触发价格止损："
                    f"现价 {current_price:.2f} ≤ 止损价 {stop_loss_price:.2f}，"
                    f"跌幅 {((cost_price - current_price) / cost_price * 100):.2f}%"
                )
                logger.warning(message)
                return Alert(
                    symbol=symbol,
                    name=name,
                    rule="price_stop_loss",
                    message=message,
                    severity=rule["severity"],
                )

            return None

        except (ValueError, TypeError, ZeroDivisionError) as e:
            logger.error("实时止损扫描异常: {}", e)
            return None

    # ------------------------------------------------------------------
    # 内部辅助：从 factor_value 长表查询因子值
    # ------------------------------------------------------------------

    async def _get_factor_value(self, symbol: str, trade_date: str, factor_name: str) -> float | None:
        """
        从 factor_value 长表查询指定因子值

        sentiment_score_1d 取值范围 [-1, 1]，负值为负面，正值为正面。

        Args:
            symbol: 股票代码
            trade_date: 交易日
            factor_name: 因子名（小写+下划线规范）

        Returns:
            因子值，未找到或出错时返回 None
        """
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import text

            if async_session_factory is None:
                return None

            async with async_session_factory() as session:
                result = await session.execute(
                    text("SELECT value FROM factor_value WHERE symbol=:s AND trade_date=:d AND factor_name=:f"),
                    {"s": symbol, "d": trade_date, "f": factor_name},
                )
                row = result.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            logger.warning("查询因子值异常 symbol={}, factor={}: {}", symbol, factor_name, e)
            return None

    async def _get_stock_daily_value(self, symbol: str, trade_date: str, column: str) -> float | None:
        """从 stock_daily 表查询行情数据（close, pct_change, volume 等）

        Args:
            symbol: 股票代码
            trade_date: 交易日
            column: 列名（close / pct_change / volume / amount）

        Returns:
            数值或 None
        """
        VALID_COLUMNS = {"close", "pct_change", "volume", "amount"}
        if column not in VALID_COLUMNS:
            logger.warning("不允许的列名: {}", column)
            return None
        try:
            from app.core.database import async_session_factory
            from sqlalchemy import text

            if async_session_factory is None:
                return None

            async with async_session_factory() as session:
                result = await session.execute(
                    text(f"SELECT {column} FROM stock_daily WHERE symbol=:s AND trade_date=:d"),
                    {"s": symbol, "d": trade_date},
                )
                row = result.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            logger.debug(f"查询 stock_daily.{column} 失败: {e}")
            return None

    async def _get_stock_info(self, session, today: str) -> list[tuple[str, str]]:
        """
        获取当日有行情数据的股票列表（含名称）

        Args:
            session: 数据库会话
            today: 交易日

        Returns:
            (symbol, name) 元组列表
        """
        from sqlalchemy import text
        try:
            result = await session.execute(
                text("""
                    SELECT fv.symbol, si.name
                    FROM (SELECT DISTINCT symbol FROM factor_value WHERE trade_date = :today) fv
                    LEFT JOIN stock_info si ON si.symbol = fv.symbol
                """),
                {"today": today},
            )
            return [(row[0], row[1] or row[0]) for row in result.fetchall()]
        except Exception as e:
            logger.warning("获取股票列表异常: {}", e)
            return []

    # ------------------------------------------------------------------
    # 批量查询辅助方法（将 N+1 优化为 1 次批量查询）
    # ------------------------------------------------------------------

    async def _batch_get_factor_values(self, session, symbols: list[str], today: str, factor_name: str) -> dict[str, float]:
        """
        批量查询指定因子的值

        Args:
            session: 数据库会话
            symbols: 股票代码列表
            today: 交易日
            factor_name: 因子名

        Returns:
            {symbol: value, ...}
        """
        if not symbols:
            return {}
        from sqlalchemy import text
        try:
            result = await session.execute(
                text("""
                    SELECT symbol, value FROM factor_value
                    WHERE symbol = ANY(:symbols)
                    AND trade_date = :trade_date
                    AND factor_name = :factor_name
                """),
                {"symbols": symbols, "trade_date": today, "factor_name": factor_name},
            )
            return {row[0]: float(row[1]) for row in result.fetchall()}
        except Exception as e:
            logger.warning("批量查询因子值异常 factor={}: {}", factor_name, e)
            return {}

    async def _batch_get_stock_daily(self, session, symbols: list[str], today: str, column: str) -> dict[str, float]:
        """
        批量查询 stock_daily 列值

        Args:
            session: 数据库会话
            symbols: 股票代码列表
            today: 交易日
            column: 列名（close / pct_change / volume / amount）

        Returns:
            {symbol: value, ...}
        """
        if not symbols:
            return {}
        # 列名白名单校验（防 SQL 注入）
        VALID_COLUMNS = {"close", "pct_change", "volume", "amount"}
        if column not in VALID_COLUMNS:
            logger.warning("不允许的列名: {}", column)
            return {}
        from sqlalchemy import text
        try:
            result = await session.execute(
                text(f"SELECT symbol, {column} FROM stock_daily WHERE symbol = ANY(:symbols) AND trade_date = :d"),
                {"symbols": symbols, "d": today},
            )
            return {row[0]: float(row[1]) for row in result.fetchall()}
        except Exception as e:
            logger.warning("批量查询 stock_daily.{} 异常: {}", column, e)
            return {}

    # ------------------------------------------------------------------
    # 盘后扫描（15:30 触发）
    # ------------------------------------------------------------------

    async def scan_after_hours(self) -> list[Alert]:
        """
        盘后扫描（15:30 触发）：检查技术破位

        检查项：
        - MA20 跌破
        - MACD 死叉
        - 布林带破位
        - 主力资金流出 > 5%
        - 负面舆情 + 跌 2%

        数据库不可用时返回空列表。

        Returns:
            告警列表
        """
        alerts: list[Alert] = []

        try:
            from sqlalchemy import text
            from app.core.database import async_session_factory

            async with async_session_factory() as session:
                today = datetime.now().strftime("%Y-%m-%d")

                # ---- 检查 MA20 跌破 ----
                if self._rules.get("ma_breakdown", {}).get("enabled", False):
                    ma_alerts = await self._check_ma_breakdown(session, today)
                    alerts.extend(ma_alerts)

                # ---- 检查 MACD 死叉 ----
                if self._rules.get("macd_death", {}).get("enabled", False):
                    macd_alerts = await self._check_macd_death(session, today)
                    alerts.extend(macd_alerts)

                # ---- 检查布林带破位 ----
                bb_alerts = await self._check_bollinger_breakdown(session, today)
                alerts.extend(bb_alerts)

                # ---- 检查主力资金流出 ----
                if self._rules.get("fund_outflow", {}).get("enabled", False):
                    fund_alerts = await self._check_fund_outflow(session, today)
                    alerts.extend(fund_alerts)

                # ---- 检查负面舆情 + 跌 2% ----
                if self._rules.get("negative_sentiment", {}).get("enabled", False):
                    sentiment_alerts = await self._check_negative_sentiment(session, today)
                    alerts.extend(sentiment_alerts)

            logger.info("盘后风控扫描完成，共 {} 条告警", len(alerts))

        except Exception as e:
            logger.warning("盘后风控扫描异常（返回空列表）: {}", e)
            return []

        return alerts

    # ------------------------------------------------------------------
    # 内部辅助：各检查项（全部基于 factor_value 长表）
    # ------------------------------------------------------------------

    async def _check_ma_breakdown(self, session, today: str) -> list[Alert]:
        """
        检查 MA20 跌破

        从 factor_value 表查询收盘价低于 ma_20 的股票。
        """
        alerts = []
        try:
            rule = self._rules.get("ma_breakdown", {})
            if not rule.get("enabled", False):
                return alerts
            threshold = float(rule.get("threshold", 5))
            stocks = await self._get_stock_info(session, today)
            symbols = [s[0] for s in stocks]
            if not symbols:
                return alerts

            # 批量查询因子和行情数据
            ma_values = await self._batch_get_factor_values(session, symbols, today, "ma_20")
            close_values = await self._batch_get_stock_daily(session, symbols, today, "close")

            for symbol, name in stocks:
                ma_20 = ma_values.get(symbol)
                close = close_values.get(symbol)
                if close is not None and ma_20 is not None and close < ma_20:
                    pct = (close - ma_20) / ma_20 * 100
                    message = f"{name}（{symbol}）跌破 MA20：现价 {close:.2f}，MA20 {ma_20:.2f}（{pct:.2f}%）"
                    alerts.append(Alert(
                        symbol=symbol, name=name, rule="ma_breakdown",
                        message=message, severity=rule.get("severity", "warning"),
                    ))
        except Exception as e:
            logger.warning("MA 跌破检查异常: {}", e)
        return alerts

    async def _check_macd_death(self, session, today: str) -> list[Alert]:
        """
        检查 MACD 死叉（DIF 下穿 DEA）

        从 factor_value 表查询 macd_dif < macd_dea 的股票。
        """
        alerts = []
        try:
            rule = self._rules.get("macd_death", {})
            if not rule.get("enabled", False):
                return alerts
            stocks = await self._get_stock_info(session, today)
            symbols = [s[0] for s in stocks]
            if not symbols:
                return alerts

            # 批量查询因子数据
            difs = await self._batch_get_factor_values(session, symbols, today, "macd_dif")
            deas = await self._batch_get_factor_values(session, symbols, today, "macd_dea")

            for symbol, name in stocks:
                dif = difs.get(symbol)
                dea = deas.get(symbol)
                if dif is not None and dea is not None and dif < dea:
                    message = f"{name}（{symbol}）MACD 死叉：DIF {dif:.3f} 下穿 DEA {dea:.3f}"
                    alerts.append(Alert(
                        symbol=symbol, name=name, rule="macd_death",
                        message=message, severity=rule.get("severity", "warning"),
                    ))
        except Exception as e:
            logger.warning("MACD 死叉检查异常: {}", e)
        return alerts

    async def _check_bollinger_breakdown(self, session, today: str) -> list[Alert]:
        """
        检查布林带破位（收盘价跌破下轨）

        从 factor_value 表查询 close < boll_dn 的股票。
        """
        alerts = []
        try:
            rule = self._rules.get("bollinger_breakdown", {})
            if not rule.get("enabled", False):
                return alerts
            stocks = await self._get_stock_info(session, today)
            symbols = [s[0] for s in stocks]
            if not symbols:
                return alerts

            # 批量查询因子和行情数据
            closes = await self._batch_get_stock_daily(session, symbols, today, "close")
            boll_dns = await self._batch_get_factor_values(session, symbols, today, "boll_dn")

            for symbol, name in stocks:
                close = closes.get(symbol)
                boll_dn = boll_dns.get(symbol)
                if close is not None and boll_dn is not None and close < boll_dn:
                    message = f"{name}（{symbol}）布林带破位：收盘价 {close:.2f} < 下轨 {boll_dn:.2f}"
                    alerts.append(Alert(
                        symbol=symbol, name=name, rule="bollinger_breakdown",
                        message=message, severity=rule.get("severity", "warning"),
                    ))
        except Exception as e:
            logger.warning("布林带破位检查异常: {}", e)
        return alerts

    async def _check_fund_outflow(self, session, today: str) -> list[Alert]:
        """
        检查主力资金流出超过阈值

        从 factor_value 表查询主力资金净流出数据。
        资金因子未接入时返回空列表。
        """
        alerts = []
        try:
            rule = self._rules.get("fund_outflow", {})
            if not rule.get("enabled", False):
                return alerts
            threshold = float(rule.get("threshold", 5))
            stocks = await self._get_stock_info(session, today)
            symbols = [s[0] for s in stocks]
            if not symbols:
                return alerts

            # 批量查询因子数据（资金因子暂未接入，预留批量接口）
            net_amounts = await self._batch_get_factor_values(session, symbols, today, "net_amount")
            net_amount_ratios = await self._batch_get_factor_values(session, symbols, today, "net_amount_ratio")

            for symbol, name in stocks:
                net_amount = net_amounts.get(symbol)
                net_amount_ratio = net_amount_ratios.get(symbol)
                if net_amount is not None and net_amount_ratio is not None:
                    if net_amount < 0 and abs(net_amount_ratio) > threshold:
                        message = f"{name}（{symbol}）主力资金流出：净流比 {net_amount_ratio:.2f}%"
                        alerts.append(Alert(
                            symbol=symbol, name=name, rule="fund_outflow",
                            message=message, severity=rule.get("severity", "warning"),
                        ))
        except Exception as e:
            logger.warning("资金流出检查异常: {}", e)
        return alerts

    async def _check_negative_sentiment(self, session, today: str) -> list[Alert]:
        """
        检查负面舆情 + 跌幅超过 2%

        从 factor_value 表查询 sentiment_score_1d，从 stock_daily 取 pct_change。
        """
        alerts = []
        try:
            rule = self._rules.get("negative_sentiment", {})
            if not rule.get("enabled", False):
                return alerts
            threshold = float(rule.get("threshold", 0.6))
            stocks = await self._get_stock_info(session, today)
            symbols = [s[0] for s in stocks]
            if not symbols:
                return alerts

            # 批量查询因子和行情数据
            sentiments = await self._batch_get_factor_values(session, symbols, today, "sentiment_score_1d")
            pct_changes = await self._batch_get_stock_daily(session, symbols, today, "pct_change")

            for symbol, name in stocks:
                sentiment = sentiments.get(symbol)
                if sentiment is None:
                    continue
                pct_change = pct_changes.get(symbol)
                # 舆情强度超阈值（负值表示负面）+ 跌幅超过 2% 时触发
                # sentiment_score_1d 取值范围 [-1, 1]，负值为负面，正值为正面
                if sentiment < -threshold and pct_change is not None and pct_change < -2:
                    message = f"{name}（{symbol}）负面舆情 + 下跌：舆情分 {sentiment:.2f}，跌幅 {pct_change:.2f}%"
                    alerts.append(Alert(
                        symbol=symbol, name=name, rule="negative_sentiment",
                        message=message, severity=rule.get("severity", "info"),
                    ))
        except Exception as e:
            logger.warning("负面舆情检查异常: {}", e)
        return alerts


# 全局风控引擎单例
risk_guard = RiskGuard()
