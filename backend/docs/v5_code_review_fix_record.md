# 后端 P1 问题修复对照记录

## P1-01：backtester 回测收益恒 0

**问题**：`_get_stock_return` 和 `_calc_benchmark_return` 从 `day_data` 取 `change_pct`，但 `day_data` 来自 `factor_value` 长表（只有注册因子），`change_pct` 不是注册因子，始终返回 0。

**修复**：
- 修改 `_query_factor_data`：增加从 `stock_daily` 查询 `pct_change` 的 SQL，通过 pandas merge 合并到返回的 DataFrame
- 返回类型由 `list[dict]` 改为 `pd.DataFrame`（宽表格式）
- `run` 方法中 Step 1 改为直接遍历 DataFrame
- `_get_stock_return` / `_calc_benchmark_return` / `_score_stock` 中的 `change_pct` 统一改为 `pct_change`

**涉及文件**：`backend/app/services/backtester.py`

---

## P1-02：risk_guard sentiment 方向反了

**问题**：`sentiment_score_1d` 取值范围 [-1, 1]，负值为负面，正值为正面。原条件 `sentiment > threshold` 错误地触发正面舆情。

**修复**：
- 将 `sentiment > threshold` 改为 `sentiment < -threshold`
- 在 `_get_factor_value` 文档串中说明 `sentiment_score_1d` 取值范围

**涉及文件**：`backend/app/services/risk_guard.py`

---

## P1-03：backtester 前视偏差复查

**问题**：原代码在调仓日（T）用当天因子选股后，同一循环迭代中立即用新持仓计算当日收益（T 日持仓在 T 日即获利），产生前视偏差。`next_day` 变量定义但未使用（死代码）。

**修复**：
- 移除 `next_day` 死代码及其嵌套 if 判断
- 引入 `prev_holdings`：调仓日用 T 日因子选股存入 `prev_holdings`，T+1 日起用 `prev_holdings` 计算收益
- 交易成本在调仓日从旧持仓收益中扣除（卖出旧 + 买入新）

**涉及文件**：`backend/app/services/backtester.py`

---

## P1-04：backtester 幸存者过滤降级清空

**问题**：`_get_tradable_stocks` 异常时返回 `[]`，调用方 `if tradable:` 为 False，跳过过滤。但随后 `s.get("symbol","") in tradable` 将 `[]` 视为空集合，所有股票都被过滤掉。

**修复**：
- `_get_tradable_stocks` 返回类型改为 `list[str] | None`
- 异常时返回 `None`（降级为不过滤）
- 调用方改为 `if tradable is not None:`

**涉及文件**：`backend/app/services/backtester.py`

---

## P1-05/06：backtester SQL 注入修复

**问题**：`_query_factor_data` 中因子名通过 f-string 拼接 SQL，存在注入风险。`query_router.py` 中 `backtest_query` 的日期参数也通过 f-string 拼接。

**修复**：
- `_query_factor_data`：增加白名单校验（`FactorCalculator.list_factors()`），拒绝未知因子名
- `query_router.py` 的 `backtest_query`：日期和因子名改用 `?` 占位符参数化
- `query_router.py` 的 `screener_query`：已有白名单校验，维持不变

**涉及文件**：`backend/app/services/backtester.py`、`backend/app/core/query_router.py`

---

## P1-07：ORM 对齐 init.sql

**问题**：ORM 模型列名与 init.sql 定义不一致（如 `code` vs `symbol`、`change_pct` vs `pct_change` 等）。

**修复**（以 init.sql 为准）：

| 表名 | 修改内容 |
|------|---------|
| `timescale.py` | StockDaily：`code`→`symbol`，`date`→`trade_date`，`change_pct`→`pct_change`，`turnover`→`turn`，新增 `amplitude` |
| `timescale.py` | StockMinute：`code`→`symbol`，`time`→`trade_time` |
| `timescale.py` | FactorValue：`code`→`symbol`，`date`→`trade_date`，新增 `id` 主键 |
| `stock.py` | StockInfo：`code`→`symbol`，新增 `delist_date`、`sector` |
| `portfolio.py` | Portfolio：完全对齐 init.sql，新增 `user_id`、`symbol`、`cost_price`、`volume`、`group_id`、`add_time` |
| `news.py` | `__tablename__`：`news`→`news_raw`，新增 `publish_time`、`crawl_time`、`sentiment_label`、`is_duplicate` |
| `api/v1/portfolio.py` | SQL 中 `si.code`→`si.symbol`（与 ORM 对齐） |

**涉及文件**：
- `backend/app/models/timescale.py`
- `backend/app/models/stock.py`
- `backend/app/models/portfolio.py`
- `backend/app/models/news.py`
- `backend/app/api/v1/portfolio.py`

---

## P1-17：data_collect session 已关闭

**问题**：`_get_async_session` 使用 `async with async_session_factory() as session: return session`，退出 `async with` 块时 session 自动关闭，后续 SQL 操作报错。

**修复**：
- 移除 `async with`，改为直接 `session = async_session_factory()`
- 调用方已使用 try/finally + `await session.close()` 管理生命周期

**涉及文件**：`backend/app/tasks/data_collect.py`
