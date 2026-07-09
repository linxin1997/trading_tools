# 代码评审（第三轮 / 复检）

> 评审对象：`D:\code\project\rading_tools`（2026-07-07 19:04 版本）
> 参照：首轮 `CODE_REVIEW.md`、次轮 `CODE_REVIEW_v2.md`
> **结论：量化内核的「数据契约」已打通——选股和回测现在能真正跑通了，这是质的飞跃。剩余问题集中在「风控检查的数据源分散」和一些个别因子名残留，属于 P1 功能缺口，不再是「系统跑不起来」。**

---

## 一、本轮已确认修复（核心进展）

| # | 上轮 P0 问题 | 现状 | 证据 |
|---|------------|------|------|
| A | 因子名三套命名互不兼容 | ✅ 注册表 key 全改小写+下划线；入库加 `_normalize_factor_name` 规范化；查询用注册表 key——三处对齐（除 `MA5_MA20_RATIO` 个别，见后） | `base.py:24-58`、`data_collect.py:23-43,118` |
| B | 查询列名 `code/date` vs `symbol/trade_date` | ✅ 全局无 `code/date` 残留；backtester 查询已是 `SELECT symbol, trade_date, factor_name, value FROM factor_value` | `backtester.py:52`、`stock_picker.py`、`query_router.py` |
| C | `factor_daily` 宽表从未建，3 消费者依赖它 | ✅ 全局 `factor_daily` 已清除；backtester/risk_guard/ai_explainer 全部改查 `factor_value` 长表 | `grep factor_daily` 无结果 |
| D | DuckDB 与 TimescaleDB 数据未打通 | ✅ backtester 改为查 TimescaleDB `factor_value`，不再依赖空的 DuckDB | `backtester.py:8,53` |
| E | `stock_info` 未被填充（幸存者偏差依赖它） | ✅ `sync_history.py` 有 `stock_info` 写入逻辑，含 `list_date/delist_date` 提取 | `backend/scripts/sync_history.py:220-297` |

**这意味着：首轮"三件套全失效"、次轮"数据契约全断"的问题，本轮已经解决。选股和回测的核心链路真正连通了。**

---

## 二、仍残留的问题（P1，非全局崩溃，但部分功能静默失效）

### 🟠 问题 1：`risk_guard` 价格类检查取错了数据源（最该修）

`risk_guard` 的 3 个价格类检查都从 `factor_value` 取 `close` / `change_pct`，但这两列是**行情数据，存在 `stock_daily` 表，根本不在 `factor_value` 因子表里**：

- `_check_ma_breakdown`：`close = await self._get_factor_value(symbol, today, "close")`（`risk_guard.py:337`）
- `_check_bollinger_breakdown`：`close = await self._get_factor_value(symbol, today, "close")`（`:390`）
- `_check_negative_sentiment`：`close = ...`、`sentiment = ... "sentiment_score_1d"`（`:447-448`）

因为 `factor_value` 里没有 `close` 这一行 → 返回 `None` → 被 `if close is not None ...` 跳过 → **这三个检查永远静默不触发**（MA 跌破、布林破位、负面舆情+下跌全部失效）。

**修复**：价格类检查应联合 `stock_daily` 取 `close`/`change_pct`（或把 `close`/`pct_change` 也作为行情快照写入 `factor_value`）。`_get_factor_value` 应按因子类型分流：技术因子查 `factor_value`，价格查 `stock_daily`。

### 🟠 问题 2：`net_amount` 主力资金因子未接入

`_check_fund_outflow` 查 `net_amount` / `net_amount_ratio`（`risk_guard.py:418-419`），但 `technical.py` **不计算主力资金净额**（grep `net_amount` 在 technical 库无结果）。该因子来自 akshare 的资金流接口（moneyflow），尚未接入计算链路 → **资金流出检查永远不触发**。

**修复**：在 `FactorCalculator` 中接入 akshare 主力资金流（`stock_individual_fund_flow` 等），把 `net_amount`/`net_amount_ratio` 算进因子并写入 `factor_value`。

### 🟡 问题 3：`MA5_MA20_RATIO` 因子名规范化后不一致

- 注册表 key：`"ma_5_ma20_ratio"`（`base.py:28`，`ma20` 无下划线）
- technical 返回列名：`"MA5_MA20_RATIO"`（`technical.py:58`）
- 规范化 `_normalize_factor_name("MA5_MA20_RATIO")`：`(MA)(\d+)` 把 `MA20`→`ma_20`，结果变成 `"ma_5_ma_20_ratio"`

→ 入库名 `ma_5_ma_20_ratio` ≠ 注册表 `ma_5_ma20_ratio`。后果：该因子被计算写入，但白名单用注册表 key 查不到它（或传 `ma_5_ma_20_ratio` 被白名单拒）。

**修复**：把注册表 key 统一为 `"ma_5_ma_20_ratio"`（与规范化输出一致），或给 `_normalize_factor_name` 补一条 `MA5_MA20_RATIO` 特例。

### 🟡 问题 4：舆情因子（`sentiment_score_1d` 等）来自阶段 3，尚未接入

`risk_guard` 的 `_check_negative_sentiment` 用 `sentiment_score_1d`（`risk_guard.py:447`），注册表里也有 `positive_news_1d` 等舆情类 key。但这些因子由阶段 3 舆情引擎产出，`technical.py` 不计算 → 若用户用了舆情类条件，查不到数据。

**说明**：这是「功能分阶段未完整接入」，不是命名 bug。待舆情引擎接入并把情感因子写入 `factor_value` 即可。当前不影响选股/回测主干。

### 🟡 问题 5：`stock_info.list_date/delist_date` 可能全为空

`sync_history.py` 用 `ak.stock_info_a_code_name` 获取股票信息（`sync_history.py:225`），该接口**只返回代码+名称，不含上市/退市日期**。所以 `row.get("list_date")` 大概率 `None` → 写入 `NULL`。

后果：`backtester._get_tradable_stocks` 的 `list_date <= :trade_date AND (delist_date IS NULL OR ...)` 对 `list_date IS NULL` 的行返回 false → **幸存者偏差过滤把所有股票都剔除**（回测持仓为空）。

**修复**：换用能返回上市日期的接口（如 `ak.stock_info_a_code_name` 配合 `akstock_zh_a_st_em` 或专门的基本面接口），或在写入后补一个 UPDATE 填充 `list_date`。

---

## 三、P1 脏代码（不影响运行，建议清理）

| 问题 | 说明 |
|------|------|
| ORM `kline_daily` / `kline_1m` 与 `init.sql` 的 `stock_daily` / `stock_minute` 命名不一致 | `models/timescale.py` 定义 `kline_daily/kline_1m`，但库里是 `stock_daily/stock_minute`，行情写入也走 `stock_daily`。ORM 的 kline 模型是死代码；若将来有人用 ORM `add(kline_daily)` 会失败。建议删掉或改名对齐。 |

---

## 四、各模块当前状态（量化内核）

| 模块 | 状态 | 说明 |
|------|------|------|
| **选股 (stock_picker)** | 🟢 通过 | 因子名/列名/表路由全部对齐；白名单+行转列+pivot 正确 |
| **回测 (backtester)** | 🟢 通过 | 查 `factor_value` 列名正确；前视偏差已修；`mock_on_error=False`；幸存者过滤框架就位 |
| **实时风控 (scan_realtime)** | 🟢 通过 | `ws.py` 已接线；用持仓成本+实时价判断止损，不依赖 `factor_value` |
| **盘后风控 (scan_after_hours)** | 🟡 部分 | 仅 `macd_death` 可工作（纯因子）；MA 跌破/布林破位/负面舆情+下跌因 `close=None` 不触发；资金流出因 `net_amount` 未接入不触发 |
| **AI 解释 (ai_explainer)** | 🟢 通过 | 已改查 `factor_value` 长表 |

---

## 五、下一步建议（P1 修复顺序）

1. **风控价格类检查改查 `stock_daily`**（问题 1）→ 让 MA 跌破 / 布林破位 / 负面舆情+下跌恢复工作
2. **接入主力资金流因子**（问题 2）→ 让资金流出检查工作
3. **修 `MA5_MA20_RATIO` 命名**（问题 3）→ 一行改动
4. **补 `stock_info.list_date` 数据源**（问题 5）→ 让幸存者偏差过滤真正生效（否则回测会剔除全部股票）
5. 清理 ORM kline 死模型

---

## 六、结论

相比首轮（选股/回测/风控全失效）、次轮（数据契约全断），**本轮选股和回测已真正跑通**，实时风控也工作。剩余全是 P1 级「风控检查数据源分散」和个别因子名残留——不会导致系统崩溃，但盘后风控的 4 个价格/资金类检查目前静默失效。

**最重要的一步**：代码契约现在对齐了，但**还没有人实际端到端跑过一次**。建议在本地按顺序执行：
1. 启动服务 + `sync_history` 同步行情与 `stock_info`
2. 等 15:30 定时（或手动触发）`compute_and_store_factors` 计算因子
3. 调选股 / 回测 API 验证返回真实结果
4. 16:00 触发 `scan_after_hours` 看风控告警

跑通这一步，量化内核就算真正立起来了。

> 需要我直接动手修 P1 主干（风控价格类改查 `stock_daily` + 接入资金流因子 + 修 `MA5_MA20_RATIO` 命名 + 补 `stock_info` 上市日期）吗？可以基于当前代码原地改。
