# 代码评审 · 第十轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（P1+P2 再次修复后）
> 对照：第九轮 `CODE_REVIEW_v9.md` 提出的 3 个跨五轮 P1 + 13 个未修复 P2
> 方法：实读源码逐项核验
> 重点：验证 CORS、风控 N+1、money/sentiment 三个 P1 + P2 抽查

---

## 一句话结论

**3 个跨五轮 P1 中修复了 2 个（CORS、风控 N+1），P2 修复率 54%（7/13），整体进展显著**。但 money/sentiment 因子流水线仍未接入（跨六轮），`_check_bollinger_breakdown` 是死代码（DEFAULT_RULES 无此规则），`_batch_get_stock_daily` 缺白名单引入新 SQL 注入风险，`deps.py get_db` 缺 commit 会导致写操作丢失。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY | NOT FIXED | NEW ISSUE |
|------|------|-------|-----------|-----------|-----------|
| 跨六轮 P1 | 3 | 2 | 0 | 1 | — |
| v9 未修复 P2 | 13 | 7 | 3 | 3 | — |
| 新回归 | — | — | — | — | 3 |
| **合计** | **16+3** | **9** | **3** | **4** | **3** |

---

## 三、✅ 已确认修复

### P1 修复（2 项）

| # | 问题 | 文件 | 修复证据 |
|---|------|------|---------|
| 1 | P1-16 CORS 安全漏洞 | [main.py](file:///d:/code/project/trading_tools/backend/app/main.py) L74-81 | `allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"]` 白名单 + `allow_credentials=True` 恢复 |
| 2 | P1-19 风控 N+1 查询 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L440/474/507/542/577 | 5 个 `_check_*` 方法全部改为调用 `_batch_get_factor_values` / `_batch_get_stock_daily`，不再逐股票单条查询 |

### P2 修复（7 项）

| # | v5 编号 | 文件 | 修复证据 |
|---|---------|------|---------|
| 1 | P2-1 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L54-55 | `close_db()` 重置 `engine` 和 `async_session_factory` 为 None |
| 2 | P2-2 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L59-78 | `get_session()` 加 `try/except/rollback/finally` |
| 3 | P2-3 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L41 | `pool_pre_ping=True` 已设置 |
| 4 | P2-6 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L30 | `init_redis()` 加 `await redis_client.ping()` |
| 5 | P2-7 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L55-56 | `get_redis()` 抛 `RuntimeError("Redis 未初始化")` |
| 6 | P2-13 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L12, L111 | `import copy` + `copy.deepcopy(self.DEFAULT_RULES)` |
| 7 | P2-15(部分) | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L248-251 | `_get_stock_daily_value` 加 `VALID_COLUMNS` 白名单 |

---

## 四、🟡 部分修复（3 项）

| # | v5 编号 | 文件 | 修复点 | 未修复点 |
|---|---------|------|--------|---------|
| 1 | P2-15 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | `_get_stock_daily_value` 有白名单 | `_batch_get_stock_daily`（L331-355）**无白名单**，直接 f-string 拼接 column |
| 2 | P2-36 | [risk.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) | `get_alerts`/`update_rule` 已改为 raise HTTPException | `get_rules`（L34-47）仍吞异常返回 DEFAULT_RULES |
| 3 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L16-35 | None 检查 + rollback 已加 | **成功路径无 commit**，ORM 写操作会丢失 |
| 4 | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) L12-20 | `ipo_date`→`list_date` 已改 | `code`/`exchange`/`is_active` 仍不匹配 ORM |

---

## 五、🔴 仍未修复

### P1（1 项）— 跨六轮

#### money/sentiment 因子流水线 — **NOT FIXED**

- [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) L65-84：`compute_all()` 仍只调 `technical.compute_all(df)`
- [money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) L18-70：仍是占位实现，返回全 0
- [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L111-115：仅调 `FactorCalculator.compute_all()`，无 sentiment/money 因子写入
- **影响**：`_check_fund_outflow` 查询的 `net_amount`/`net_amount_ratio` 和 `_check_negative_sentiment` 查询的 `sentiment_score_1d` 永远不会写入数据库，这两条风控规则是死代码

### P2（3 项）

| # | v5 编号 | 文件 | 问题 |
|---|---------|------|------|
| 1 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L42-51 | 仍故意 raise+catch 走 mock |
| 2 | P2-30/31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L73-75, L121-128 | 缓存无锁；`float(row.get("开盘", 0))` 未防御 None |
| 3 | P2-37 | [ai.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L50 | `message` 仍用 `Query()` |
| 4 | P2-38 | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L63 | neutral 仍查 `sentiment_score == 0` |
| 5 | P2-39/41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L154, L176 | 广播仍串行；无心跳 |
| 6 | P2-44 | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L66 | `strategy: dict` 仍无校验 |

---

## 六、🔴 新引入的问题（3 项）

### NEW-09 · `_batch_get_stock_daily` 缺列名白名单 — SQL 注入风险

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L331-355
- **描述**：`_get_stock_daily_value` 已加 `VALID_COLUMNS` 白名单，但新增的批量方法 `_batch_get_stock_daily` 仍用 `text(f"SELECT symbol, {column} FROM ...")` 直接拼接，无白名单校验。
- **影响**：虽当前调用方传入字面量，但防护不一致，属于安全漏洞。
- **修复**：在 `_batch_get_stock_daily` 入口加同样的 `VALID_COLUMNS` 校验。

### NEW-10 · `_check_bollinger_breakdown` 是死代码

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L397, L498-500
- **描述**：`scan_after_hours` L397 无条件调用 `_check_bollinger_breakdown`，但 `DEFAULT_RULES` 中**没有 `bollinger_breakdown` 条目**。方法内部 L498-500 `rule = self._rules.get("bollinger_breakdown", {})` 返回 `{}`，`rule.get("enabled", False)` 为 False，立即 return。
- **影响**：布林带破位检查永远不会执行。
- **修复**：在 `DEFAULT_RULES` 中添加 `bollinger_breakdown` 条目。

### NEW-11 · `deps.py get_db` 成功路径无 commit

- **文件**：[deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L16-35
- **描述**：`get_db()` 加了 None 检查和 rollback，但成功路径（yield 之后）没有 `await session.commit()`。使用此依赖的 API 如果执行了 ORM 写操作（如 `session.add()`），数据不会持久化。
- **影响**：所有用 `Depends(get_db)` 的写操作 API 数据会丢失。
- **修复**：在 `finally` 前或 `yield` 后加 `await session.commit()`。

---

## 七、模块状态总览

| 模块 | v9 状态 | v10 状态 | 变化 |
|------|---------|---------|------|
| CORS 安全 | 🔴 未修复 | 🟢 **已修复** | 白名单 + credentials=True |
| 风控 N+1 查询 | 🔴 未修复 | 🟢 **已修复** | 5 个 _check_* 全部调用批量方法 |
| money/sentiment 管线 | 🔴 未接入 | 🔴 未接入 | 跨六轮 |
| database.py 三件套 | 🔴 未修复 | 🟢 **已修复** | close_db 重置 + rollback + pre_ping |
| redis_client | 🔴 未修复 | 🟢 **已修复** | ping + RuntimeError |
| risk_guard deepcopy | 🔴 未修复 | 🟢 **已修复** | copy.deepcopy |
| risk_guard column 白名单 | 🔴 未修复 | 🟡 部分修复 | 单条方法有，批量方法无（NEW-09） |
| bollinger_breakdown | 🔴 未修复 | 🔴 死代码 | DEFAULT_RULES 无此条目（NEW-10） |
| deps.py | 🔴 未修复 | 🟡 部分修复 | None+rollback 有，commit 无（NEW-11） |
| ws.py gather/heartbeat | 🔴 未修复 | 🔴 未修复 | — |
| akshare 缓存/None | 🔴 未修复 | 🔴 未修复 | — |
| report_service mock | 🔴 未修复 | 🔴 未修复 | — |
| ai.py Query→body | 🔴 未修复 | 🔴 未修复 | — |
| news.py neutral | 🔴 未修复 | 🔴 未修复 | — |
| backtest strategy | 🔴 未修复 | 🔴 未修复 | — |

---

## 八、修复优先级建议

### 第一批：修复新引入问题（阻断性）

1. **NEW-11** deps.py `get_db` 加 `await session.commit()` — 否则所有写操作 API 数据丢失
2. **NEW-09** `_batch_get_stock_daily` 加 `VALID_COLUMNS` 白名单
3. **NEW-10** `DEFAULT_RULES` 中添加 `bollinger_breakdown` 条目

### 第二批：最后一个跨六轮 P1

4. **money/sentiment 管线**：在 `base.compute_all()` 中接入 money/sentiment 计算；在 `data_collect.py` 中持久化到 factor_value 表

### 第三批：剩余 P2

5. report_service mock 路径
6. akshare 缓存锁 + float None 防御
7. ai.py message 改 body
8. news.py neutral 改范围查询
9. ws.py gather + heartbeat
10. backtest strategy 改 Pydantic model
11. schemas/stock.py 字段对齐
12. deps.py 加 commit（同 NEW-11）

---

## 九、评审结论

第十轮审查发现：

1. **CORS 安全漏洞和风控 N+1 查询终于修复**，这是跨 v5-v9 六轮积压的两个核心 P1。CORS 改为白名单且恢复了 `allow_credentials=True`；N+1 的 5 个 `_check_*` 方法全部改为调用批量方法，问题真正解决。
2. **P2 修复率 54%**，database.py 三件套、redis_client、risk_guard deepcopy 等关键基础设施问题已修复，较 v9 的 7% 有显著提升。
3. **但 money/sentiment 因子流水线仍未接入**（跨六轮），`_check_fund_outflow` 和 `_check_negative_sentiment` 虽然改用了批量查询，但查询的因子永远不会被写入数据库，这两条规则仍是死代码。
4. **新引入 3 个问题**：NEW-11（deps.py 缺 commit）是阻断性的，会导致所有写操作 API 数据丢失；NEW-09（批量方法缺白名单）是安全漏洞；NEW-10（bollinger 死代码）是功能缺失。
5. **仍有 6 个 P2 未修复**：report_service mock、akshare 缓存/None、ai.py Query、news.py neutral、ws.py gather/heartbeat、backtest strategy dict。

**总体评价**：本轮修复质量是历次最高的一轮，核心 P1 终于解决，P2 修复率过半。但 money/sentiment 管线这一跨六轮 P1 仍未动，且新引入的 deps.py 缺 commit 问题需要立即修复。

---

*评审完成于 2026-07-07*
