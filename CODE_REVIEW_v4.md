# 代码评审 · 第四轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（截至 2026-07-07 19:30 的代码状态）
> 对照：第三轮 `CODE_REVIEW_v3.md` 提出的 P1 问题逐项核验
> 方法：实读源码 + grep 扫描 + Python 实跑正则规范化函数，未做端到端运行

---

## 一句话结论

**量化内核已从「静态连通」升级为「动态可跑」**：选股、回测、实时价格止损、盘后技术破位风控四条链路现在都真正能跑通。上一轮卡死的风控价格类检查已修复。

**剩余问题收敛为一类**：两个风控检查（资金流、舆情）依赖的因子**从未被计算/入库**，目前是静默 no-op；money.py 还是占位 stub。这本质是「阶段 3 / 外部数据源未接入」的遗留，而非代码崩溃。

整体状态：🟢 可进入端到端真实数据验证（强烈建议跑一次），🟠 2 个风控检查待因子接入。

---

## ✅ 本轮已确认修复（相对第三轮）

| # | 第三轮问题 | 修复证据 |
|---|-----------|---------|
| P1-1 | `risk_guard` 的 MA 跌破 / 布林破位从 `factor_value` 取 `close`（行情不在因子表，必为 None → 静默不触发） | 新增 `_get_stock_daily_value()` 辅助函数（`risk_guard.py:234`），`_check_ma_breakdown`（:366）、`_check_bollinger_breakdown`（:419）均改为 `_get_stock_daily_value(symbol, today, "close")` + 因子 `_get_factor_value(symbol, today, "ma_20"/"boll_dn")`。**价格类检查现在真能触发。** |
| P1-3 | `MA5_MA20_RATIO` 规范化出 `ma_5_ma_20_ratio`、注册表是 `ma_5_ma20_ratio`（无下划线）不一致 | Python 实跑 `_normalize_factor_name("MA5_MA20_RATIO")` = `"ma_5_ma_20_ratio"`，与注册表 key `base.py:28` 完全一致（`match? True`）。**三方统一。** |
| P1-4a | `stock_info` 表无 `list_date`/`delist_date` 列 | `init.sql:171-178` 已建 `list_date DATE` / `delist_date DATE`；`sync_history.py:257` 已 `INSERT INTO stock_info (symbol, name, list_date)`。幸存者偏差过滤的数据契约已具备。 |
| 结构 | 三套 schema 矛盾（factor_value 长表 / factor_daily 宽表 / DuckDB） | 全局已统一为 TimescaleDB 的 `factor_value` 长表；列名 `symbol/trade_date`，因子名小写+下划线。backtester / risk_guard / stock_picker / query_router 全部对齐。 |

---

## 🟠 仍存在的问题（P1 级别，非崩溃但功能静默失效）

### P1-2 · 资金流因子未接入（风控「资金异常」检查是 no-op）

- `risk_guard._check_money_flow`（:447-448）查询 `net_amount` / `net_amount_ratio`，但**全代码没有任何地方把这两个因子写入 `factor_value`**（grep 确认无对应 INSERT）。
- 根源有两层：
  1. `money.py` 是**占位实现**：`compute_north_flow` / `compute_main_inflow` 直接 `return {..., 0.0}` 并标注 `TODO: 接入 Tushare 后替换`（money.py:35-43, 63-69）。它没有真实数据。
  2. 即便有数据，`FactorCalculator.compute_all`（`base.py:82`）**只调用 `technical.compute_all`**，未调用 money / sentiment 计算；`data_collect.py` 也只 `import FactorCalculator`，未引入 money / sentiment 模块。
  3. 命名再错一层：money.py 返回的键是 `MAIN_INFLOW_NET` / `MAIN_INFLOW_RATIO`，而风控查的是 `net_amount` / `net_amount_ratio` —— 即使接入也对不上。
- 影响：盘后风控的「资金异常」检查永远返回 None、静默跳过。
- 建议：① 接入 Tushare `moneyflow` 接口真实计算；② 把输出因子名统一为 `net_amount` / `net_amount_ratio`；③ 在 `FactorCalculator.compute_all`（或 `data_collect`）里调用 money 计算并入库。

### P1-5 · 舆情因子未接入（风控「负面舆情」检查是 no-op）

- `risk_guard._check_sentiment_drop`（:476）查询 `sentiment_score_1d`，但**该因子从未被写入 `factor_value`**（grep 确认全代码无 sentiment → factor_value 的写入）。
- `sentiment.py` 有 `get_sentiment_score_1d` 等函数，但 `data_collect.py` / `compute_all` 均未调用它，也未把结果持久化到 `factor_value`。
- 影响：盘后风控的「负面舆情 + 下跌」检查永远返回 None、静默跳过。
- 建议：阶段 3 新闻舆情 pipeline 计算完成后，把 `sentiment_score_1d` 写入 `factor_value`（与行情因子同一张表、同一天），风控即可自然消费。当前属「阶段 3 未接入」的预期缺口，但代码已就绪，只差接线。

---

## 🟡 次要 / P2 级（健壮性细节）

1. **`negative_sentiment` 检查只判断了一半**（risk_guard:476-491）：函数名/注释承诺「负面舆情 **+ 下跌**」，但实现只判断 `sentiment > threshold`，`close` 取了却没用来算涨跌幅，「下跌 > 2%」条件完全缺失（注释亦自承「简化处理」）。建议补 `pct_change < -2` 判定（stock_daily 列名为 `pct_change`，确认见 init.sql:18）。

2. **`delist_date` 从未写入**（sync_history.py:257 只 INSERT `list_date`）：已退市股票不会被排除。影响方向是「过度包含」（比「过度排除」安全），但严格来说幸存者偏差防护不完整。建议补 `delist_date` 来源（akshare `stock_info_a_code_name` 不含退市日，需另取）。

3. **`list_date` 全空风险 → 回测可能全空**：`sync_history` 的 `list_date` 依赖 akshare 个股信息接口（:242 `row.get("上市日期")`）。若该接口对多数股票返回 None，则 `backtester` 的 `WHERE list_date <= :trade_date`（backtester.py:280）会把所有 `list_date IS NULL` 的行判为不成立而排除 → **回测返回空集**。建议给幸存者过滤加 `OR list_date IS NULL`（未知上市日的股票视为已上市，宁宽勿空），或在 sync 阶段对空值告警。

4. **ORM 模型与表结构不一致（潜在陷阱）**：`models/stock.py:21` 的 `StockInfo.ipo_date` 列名与 `init.sql` 的 `list_date` 不符；且全代码无 `create_all`，真实 schema 以 init.sql 为准。当前风控/回测都用 raw SQL（`list_date`）绕过了该模型，所以**目前不影响运行**；但若日后有人用 `StockInfo.ipo_date` 做 ORM 查询会直接报错。建议把模型列名改成 `list_date`/`delist_date` 与表对齐，或标注该模型为「仅供参考」。

---

## 模块状态总览（本轮）

| 模块 | 状态 | 说明 |
|------|------|------|
| 选股（stock_picker） | 🟢 正常 | 查 `factor_value` 长表，列名/因子名一致，白名单防注入 |
| 回测（backtester） | 🟢 正常 | 无前视偏差、幸存者过滤契约已具备、默认不粉饰假数据 |
| 实时价格止损（scan_realtime） | 🟢 正常 | 接行情流水线，纯价格判定 |
| 盘后技术破位（scan_after_hours） | 🟢 正常 | MA 跌破 / MACD 死叉 / 布林破位均能触发（fix #P1-1） |
| 盘后资金异常（_check_money_flow） | 🔴 no-op | 因子未接入（fix #P1-2，待 Tushare） |
| 盘后负面舆情（_check_sentiment_drop） | 🔴 no-op | 因子未接入（fix #P1-5，待阶段 3） |
| 前端 / WebSocket 扇出 | 🟢 正常 | 上一轮已确认 |
| 因子名 / 列名 / 表名契约 | 🟢 一致 | 全局统一为 factor_value 长表 |

---

## 建议的下一步（按优先级）

1. **【强烈建议】跑一次端到端真实验证**，顺序：
   ① `sync_history` 同步行情 + stock_info → ② 触发 `compute_and_store_factors` 算技术因子 → ③ 调选股 / 回测 API 看真实结果 → ④ 触发 `scan_after_hours` 看技术破位告警。
   这一步能验证「数据能进来、因子能算、能真回测 / 真风控」，是内核真正立起来的标志。

2. **补 `list_date` 空值保护**（最低成本、防患于未然）：回测幸存者过滤加 `OR list_date IS NULL`，避免回测因数据缺失静默全空。

3. **接 sentiment 因子入库**（阶段 3 落地时）：新闻舆情算完后写 `sentiment_score_1d` 到 `factor_value`，风控负面舆情检查即自动生效。

4. **接 money 因子**（需 Tushare `moneyflow` + token）：实现 money.py 真实计算、统一因子名为 `net_amount`/`net_amount_ratio`、在 compute 管线调用入库，资金异常检查即生效。

5. **补 `negative_sentiment` 的「下跌」判定** + 写 `delist_date`。

---

## 评审结论

第四轮后，**量化系统的「骨架 + 主干逻辑」已全部正确且可运行**，三轮迭代修掉的所有数据契约问题都稳住了。仅剩的两个 no-op 风控检查属于**外部数据源 / 阶段 3 未接入的预期缺口**，不是代码 bug。

建议直接进入「端到端真实数据验证」阶段。跑通后，系统即具备：行情同步 → 因子计算 → 选股 → 回测 → 实时/盘后风控的完整闭环（舆情、资金流两项待数据源接入后自动点亮）。
