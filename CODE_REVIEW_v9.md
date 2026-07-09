# 代码评审 · 第九轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（P2 修复后再次审查）
> 对照：第八轮 `CODE_REVIEW_v8.md` 提出的 NEW-08、3 个跨四轮 P1 及未修复 P2 问题
> 方法：实读源码 + 交叉验证
> 重点：验证开发者声明"P2 全部修复"的真实性，以及 3 个 P1 是否解决

---

## 一句话结论

**开发者声称"P2 全部修复"严重不实**。抽查的 14 个 P2 中仅 1 个真正修复，其余 13 个仍是原样或仅做了无关调整。3 个跨五轮 P1 中仅 NEW-08 修复，CORS 安全漏洞和风控 N+1 查询**仍未修复**，money/sentiment 因子流水线也**仍未接入**。当前后端虽可运行，但核心功能缺陷与 P2 质量债几乎原封不动。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY | NOT FIXED |
|------|------|-------|-----------|-----------|
| v8 NEW-08 | 1 | 1 | 0 | 0 |
| 跨五轮 P1（CORS/N+1/流水线） | 3 | 0 | 0 | 3 |
| 抽查 P2（14 项） | 14 | 1 | 0 | 13 |
| **合计** | **18** | **2** | **0** | **16** |

---

## 三、✅ 已确认修复

| # | 问题 | 文件 | 修复证据 |
|---|------|------|---------|
| 1 | NEW-08 portfolio `group_name`→`group_id` | [portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) L115-L135, L200-L210 | SQL 全部使用 `group_id`，无 `group_name` 残留；[schemas/portfolio.py](file:///d:/code/project/trading_tools/backend/app/schemas/portfolio.py) L45 `PositionResponse.group_id` 正确 |

---

## 四、🔴 仍未修复的 P1（3 项）

### P1-16 · CORS 安全漏洞 — **NOT FIXED（跨 v5/v6/v7/v8/v9 五轮）**

- **文件**：[main.py](file:///d:/code/project/trading_tools/backend/app/main.py) L75-L82
- **当前代码**：
  ```python
  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=False,
      allow_methods=["*"],
      allow_headers=["*"],
  )
  ```
- **说明**：`allow_credentials` 由 `True` 改为 `False`，但 `allow_origins=["*"]` 仍是通配。这**没有解决安全漏洞**，只是让浏览器不再携带凭证，等于把 Web 应用的登录态给废了，属于拆东墙补西墙。正确做法应是改为白名单列表（如 `["http://localhost:3000"]`）。

### P1-19 · 风控 N+1 查询 — **NOT FIXED（跨五轮）**

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py)
- **当前状态**：
  - L204-L235 `_get_factor_value`：仍是单条查询
  - L236-L264 `_get_stock_daily_value`：仍是单条查询
  - L295-L325 `_batch_get_factor_values`：**已实现批量查询但未被调用**
  - L326-L350 `_batch_get_stock_daily`：**已实现批量查询但未被调用**
  - L417-L448 `_check_ma_breakdown`：循环内逐股票调用单条查询
  - L450-L481 `_check_macd_death`：循环内逐股票调用单条查询
  - L483-L513 `_check_bollinger_breakdown`：循环内逐股票调用单条查询
  - L515-L548 `_check_fund_outflow`：循环内逐股票调用单条查询
  - L550-L586 `_check_negative_sentiment`：循环内逐股票调用单条查询
- **说明**：开发者可能以为"加了批量方法"就算修复，但**调用方仍是单条模式**，实际 N+1 问题根本没有解决。全市场 5000 只股票仍会触发数万次查询。

### money/sentiment 因子流水线 — **NOT FIXED（跨五轮）**

- **文件**：
  - [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) L65-L85：`compute_all()` 仍只调 `technical.compute_all(df)`
  - [money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) L18-L86：仍是 stub，未实际计算
  - [sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) L1-L30：仍是占位实现
  - [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L111-L115：仅调 `FactorCalculator.compute_all()`，未单独处理 money/sentiment
- **说明**：资金/舆情因子仍无法产生数据，风控中依赖这些因子的规则全部 no-op。

---

## 五、🔴 P2 抽查结果：13/14 未修复（开发者声称"全部修复"严重不实）

| # | v5/v8 编号 | 文件 | 抽查结果 | 关键证据 |
|---|-----------|------|---------|---------|
| 1 | P2-1 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L46-54 | **NOT FIXED** | `close_db()` 仍不重置 `engine`/`async_session_factory` 为 None |
| 2 | P2-2 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L56-64 | **NOT FIXED** | `get_session()` 仍无 `try/except/rollback` |
| 3 | P2-3 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L36-43 | **NOT FIXED** | `create_async_engine()` 仍无 `pool_pre_ping=True` |
| 4 | P2-6 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L17-30 | **NOT FIXED** | `init_redis()` 仍无 `ping()` 健康检查 |
| 5 | P2-7 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L44-51 | **NOT FIXED** | `get_redis()` 仍直接返回 `redis_client`（可能 None） |
| 6 | P2-13 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L105-140 | **NOT FIXED** | 仍 `dict(DEFAULT_RULES)` 浅拷贝 |
| 7 | P2-14 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L330-340 | **NOT FIXED** | `bollinger_breakdown` 仍无条件调用，无 enabled 开关 |
| 8 | P2-15 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L256 | **NOT FIXED** | `column` 仍 f-string 拼接进 SQL，无白名单 |
| 9 | P2-21 | [ai_explainer.py](file:///d:/code/project/trading_tools/backend/app/services/ai_explainer.py) L130-150, L220-230 | **FIXED** | 已移除 `pe_ttm`/`change_pct` 引用 |
| 10 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L40-60 | **NOT FIXED** | 仍恒走 mock 路径 |
| 11 | P2-30 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L45-80 | **NOT FIXED** | 缓存刷新无锁 |
| 12 | P2-31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L115-135 | **NOT FIXED** | `float(row.get("开盘", 0))` 未防御 None |
| 13 | P2-36 | [risk.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) L17-32 | **NOT FIXED** | `except Exception` 仍吞掉返回空列表 |
| 14 | P2-37 | [ai.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L45-60 | **NOT FIXED** | `message` 仍用 `Query(...)` 而非 body |
| 15 | P2-38 | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L55-70 | **NOT FIXED** | neutral 仍查 `sentiment_score == 0` |
| 16 | P2-39/41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L145-165 | **NOT FIXED** | 广播仍串行；无心跳 |
| 17 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L15-35 | **NOT FIXED** | 无 None 检查；无 commit/rollback |
| 18 | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) L15-30 | **NOT FIXED** | `code`/`ipo_date`/`exchange`/`is_active` 仍不匹配 ORM |
| 19 | P2-44 | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L60-75 | **NOT FIXED** | `strategy: dict` 仍无结构校验 |

**P2 抽查修复率：1/14（7%）。**

---

## 六、模块状态总览

| 模块 | v8 状态 | v9 状态 | 变化 |
|------|---------|---------|------|
| NEW-08 portfolio group_name | 🟡 新回归 | 🟢 **已修复** | 字段已对齐 |
| P1-16 CORS | 🔴 未修复 | 🔴 未修复 | 把 credentials 改 False，但 origins 仍 * |
| P1-19 风控 N+1 | 🟡 部分 | 🔴 未修复 | 批量方法已加但未被调用 |
| money/sentiment 流水线 | 🔴 未接入 | 🔴 未接入 | 跨五轮 |
| P2 数据库三件套 | 🔴 未修复 | 🔴 未修复 | 原样 |
| P2 redis_client | 🔴 未修复 | 🔴 未修复 | 原样 |
| P2 risk_guard deepcopy/bollinger/column | 🔴 未修复 | 🔴 未修复 | 原样 |
| P2 ai_explainer 未注册因子 | 🔴 未修复 | 🟢 **已修复** | 移除 pe_ttm/change_pct |
| P2 report_service mock | 🔴 未修复 | 🔴 未修复 | 原样 |
| P2 akshare 缓存/None | 🔴 未修复 | 🔴 未修复 | 原样 |
| P2 API 层问题 | 🔴 多数未修 | 🔴 多数未修 | 仅 ai_explainer 修复 |

---

## 七、评审结论

第九轮审查发现：

1. **开发者声明"P2 全部修复"严重不实**。抽查 14 个关键 P2，仅 1 个修复（ai_explainer 未注册因子），其余 13 个仍是原样。
2. **3 个跨五轮 P1 仅 NEW-08 修复**，CORS 和风控 N+1 仍未修复。其中 CORS 的"修复"是把 `allow_credentials=True` 改成 `False`，这是饮鸩止渴，会破坏前端登录态。
3. **风控 N+1 问题的"修复"最具欺骗性**：代码中确实新增了 `_batch_get_factor_values` 和 `_batch_get_stock_daily` 两个批量方法，但**所有调用方仍在用单条查询**。这是典型的"有方法无调用"，问题根本没有解决。
4. **未发现新的回归性崩溃**，这是一个正面信号。

**建议**：
- 立即停止"口头修复"模式，对每一项问题给出具体代码变更。
- 对 P1-19 必须实际改造 `_check_ma_breakdown`、`_check_macd_death`、`_check_bollinger_breakdown`、`_check_fund_outflow`、`_check_negative_sentiment` 五个函数，改为调用 `_batch_get_factor_values` / `_batch_get_stock_daily`。
- 对 P1-16 必须改为 `allow_origins=["http://localhost:3000"]`（或从配置读取），同时恢复 `allow_credentials=True`。
- 对 P2 必须逐项修复，至少完成 database.py 三件套、redis_client、risk_guard 三项安全/稳定性问题。

---

*评审完成于 2026-07-07*
