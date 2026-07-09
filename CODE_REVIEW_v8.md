# 代码评审 · 第八轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（第三次修复后代码状态）
> 对照：第七轮 `CODE_REVIEW_v7.md` 提出的问题逐项核验
> 方法：实读源码（后端 28 文件 + 前端 15 文件）+ 交叉验证
> 重点：验证 v7 三个回归崩溃修复 + 长期未修复 P1 状态

---

## 一句话结论

**v7 的三个阻断性回归已全部修复**，且长期积压的 5 个 P1 中**Tushare 同步阻塞和数据库弱口令已修复**，但**CORS 安全漏洞、风控 N+1 查询、money/sentiment 因子流水线仍未修复**。后端 ORM 与核心服务模块现已可正常导入，但 portfolio API 改造引入了 SQL 字段不匹配的新问题，前端 P2 仍然 0 修复。整体从 v7 的"后端无法运行"改善为"后端可运行但仍有核心功能未接入"。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY | NOT FIXED | NEW ISSUE |
|------|------|-------|-----------|-----------|-----------|
| v7 回归 NEW | 3 | 3 | 0 | 0 | — |
| 跨 v5/v6/v7 的 5 个 P1 | 5 | 2 | 0 | 3 | — |
| 其他 v7 未修复 P1 | 3 | 2 | 0 | 1 | — |
| v7 未修复 P2（后端） | 28 | 12 | 2 | 14 | 1 |
| v7 未修复 P2（前端） | 10 | 0 | 0 | 10 | — |
| **合计** | **49+1** | **19** | **2** | **28** | **1** |

---

## 三、✅ v7 三个阻断性回归 — 全部修复

| # | v7 编号 | 文件 | 修复证据 |
|---|---------|------|---------|
| 1 | NEW-05 | [sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) L92-95, L120-122, L149-150, L162-164, L173-175 | 全部改为 `News.related_stocks` 和 `News.publish_time` |
| 2 | NEW-06 | [news_analysis.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_analysis.py) L61-65 | 已改为 `news.content`，不再引用 `news.summary` |
| 3 | NEW-07 | [portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) L16-17, L25-32, L115-116 | 已移除 `PortfolioHolding` import；未再出现 `portfolio_holding` 字符串；SQL 使用 `portfolio` 表；`_MOCK_POSITIONS` 已移除 |
| 4 | NEW-07 联动 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L190-205 | 无 `portfolio_holding` 引用 |

---

## 四、✅ 长期积压 P1 修复状态（5 个跨 v5/v6/v7 未修复）

| # | 问题 | 状态 | 修复证据 |
|---|------|------|---------|
| 1 | P1-18 Tushare 同步阻塞 | **FIXED** | [tushare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tushare.py) L54-55, L92-93 已用 `asyncio.to_thread()` 包装同步调用 |
| 2 | P1-21 弱口令 | **FIXED** | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) L28 默认值改为 `postgresql://user:password@localhost:5432/trading_db`（无实际密码） |
| 3 | P1-16 CORS | **NOT FIXED** | [main.py](file:///d:/code/project/trading_tools/backend/app/main.py) L77 仍 `allow_origins=["*"]` + `allow_credentials=True` |
| 4 | P1-19 风控 N+1 | **NOT FIXED** | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L105-140, L285-340, L245-265 —— 虽然 session 参数已传递（这是修复点），但 helper 内仍逐股票逐因子单条查询，未做 `IN (...)` 批量聚合 |
| 5 | money/sentiment 流水线 | **NOT FIXED** | [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) L75-95 仍只调 `technical.compute_all`；[money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) 仍是 stub；[data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L100-140 未写入 sentiment/money 因子 |

---

## 五、✅ 其他 P1 修复

| # | v7 编号 | 文件 | 修复证据 |
|---|---------|------|---------|
| 1 | P1-07 stock.py industry | **FIXED** | [stock.py model](file:///d:/code/project/trading_tools/backend/app/models/stock.py) L15-30 无 `industry` 列 |
| 2 | P1-20 news_tasks N+1 | **FIXED** | [news_tasks.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_tasks.py) L105-125 改为批量 `News.url.in_(...)` 查询 |

---

## 六、🔴 新引入的回归问题（1 项）

### NEW-08 · portfolio API 使用不存在的 `group_name` 字段 — SQL 运行时报错

- **文件**：[portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py)
- **行号**：L115-116
- **描述**：虽然表名改成了 `portfolio`，但 SQL 中仍引用 `ph.group_name`，而 init.sql 的 `portfolio` 表只有 `group_id`（整数外键），没有 `group_name`。
- **影响**：持仓查询 SQL 执行时报 `column "group_name" does not exist`。
- **修复**：将 `ph.group_name` 改为 `ph.group_id`；schema 层 `PositionResponse` 的 `group_name` 也应改为 `group_id`。

---

## 七、🔴 仍未修复的 P1（3 项）

| # | 问题 | 文件 | 行号 | 现状 |
|---|------|------|------|------|
| 1 | P1-16 CORS 安全漏洞 | [main.py](file:///d:/code/project/trading_tools/backend/app/main.py) | L77 | 仍 `allow_origins=["*"]` + `allow_credentials=True` |
| 2 | P1-19 风控 N+1 查询 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | L105-140, L285-340 | session 已复用但未批量聚合 |
| 3 | money/sentiment 因子未接入 | [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) + [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) | L82, L100-140 | 仍只计算技术因子 |

---

## 八、🟠 部分修复的 P2（2 项）

### P2-19 · redis_stream xack 时机

- **状态**：部分修复
- **文件**：[redis_stream.py](file:///d:/code/project/trading_tools/backend/app/services/redis_stream.py) L92-99
- **说明**：xack 仍放在 finally 中，但 yield 之后上游消费成功才执行，**比 v7 有所改善**。严格来说"消费失败仍 ack"的风险仍在，但当前实现可接受为 P2 级别。

### P2-44 · backtest API strategy 校验

- **状态**：部分修复
- **文件**：[backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L60-75
- **说明**：日期校验已加（`start_date >= end_date`），但 `strategy: dict` 仍无 Pydantic 模型校验。

---

## 九、仍未修复的 P2（后端 14 项 + 前端 10 项）

### 后端 P2（14 项）

| # | v5 编号 | 文件 | 问题 |
|---|---------|------|------|
| 1 | P2-1/2/3 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L45-70 | close_db 未重置 None；get_session 无显式 rollback；无 pool_pre_ping |
| 2 | P2-6/7 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L15-55 | 无 ping 健康检查；get_redis 仍返回 None |
| 3 | P2-9 | [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) | 仍未被代码加载 |
| 4 | P2-13 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L105-140 | 仍浅拷贝 `dict(DEFAULT_RULES)` |
| 5 | P2-14 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L330-332 | bollinger_breakdown 仍无 enabled 开关 |
| 6 | P2-15 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L256 | column 参数仍 f-string 拼接，无白名单 |
| 7 | P2-21 | [ai_explainer.py](file:///d:/code/project/trading_tools/backend/app/services/ai_explainer.py) L130-150, L220-230 | 仍引用未注册因子 pe_ttm/change_pct |
| 8 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L40-60 | 仍恒走 mock 路径 |
| 9 | P2-30/31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L45-80, L115-135 | 缓存无锁；float() 未防御 None |
| 10 | P2-34/35 | [portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) L115-116 | 表名已改但 `group_name` 字段不存在（升级为 NEW-08） |
| 11 | P2-36 | [risk.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) L25-35 | 仍吞异常返回空列表 |
| 12 | P2-37 | [ai.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L45-60 | chat 仍用 Query 参数传 message |
| 13 | P2-38 | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L55-70 | neutral 仍查 `sentiment_score == 0` |
| 14 | P2-39/41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L145-165 | 广播仍串行；无心跳 |
| 15 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L15-35 | 无 None 检查；无 commit/rollback |
| 16 | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) L15-30 | `code`/`ipo_date`/`exchange`/`is_active` 仍不匹配 |
| 17 | P2-44 | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L60-75 | strategy 仍 `dict`（日期已校验） |

### 前端 P2（10 项全部未修复）

| # | v6/v7 编号 | 文件 | 问题 |
|---|-----------|------|------|
| 1 | NEW-04 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L154 | connect 仍依赖回调引用，未改为 ref |
| 2 | P1-13 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L40-100 | 变更操作仍无 try/catch |
| 3 | P1-15 | [vite.config.ts](file:///d:/code/project/trading_tools/frontend/vite.config.ts) L9-17 | API 8080 与 WS 8000 端口仍不一致；hooks 仍直连 |
| 4 | P2-45 | [App.tsx](file:///d:/code/project/trading_tools/frontend/src/App.tsx) L1-50 | 仍无 ErrorBoundary |
| 5 | P2-46 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L20-40 | 未校验业务 code |
| 6 | P2-47 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L420-480 | sendChatMessage 无超时；`!reader` 不调 onDone |
| 7 | P2-48 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L65-75 | quotes 仍 useState<Map> |
| 8 | P2-49 | useWebSocket.ts L85-95, useNewsStream.ts L125-135 | 仍硬编码 `ws://localhost:8000` |
| 9 | P2-51 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L40-100 | 变更操作无错误回滚 |
| 10 | P2-52 | [useReports.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Reports/hooks/useReports.ts) L15-50 | 无 AbortController |
| 11 | P2-53 | [StockTable/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/StockTable/index.tsx) L40-85 | toFixed 未判空 |
| 12 | P2-54 | [useUserStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useUserStore.ts) L35-50 | addWatchlistCode 无去重 |
| 13 | P2-55 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L170-185 | getReportDetail 未 encodeURIComponent |

---

## 十、模块状态总览

| 模块 | v7 状态 | v8 状态 | 变化 |
|------|---------|---------|------|
| sentiment.py 字段错配 | 🔴 崩溃 | 🟢 **已修复** | NEW-05 已修 |
| news_analysis.py summary | 🔴 崩溃 | 🟢 **已修复** | NEW-06 已修 |
| portfolio API PortfolioHolding | 🔴 崩溃 | 🟡 基本修复 | NEW-07 已修，但引入 NEW-08 group_name |
| Tushare 同步阻塞 | 🔴 未修复 | 🟢 **已修复** | asyncio.to_thread |
| 数据库弱口令 | 🔴 未修复 | 🟢 **已修复** | 默认值改为占位 |
| CORS 安全 | 🔴 未修复 | 🔴 未修复 | 跨 v5/v6/v7/v8 四 |
| 风控 N+1 | 🔴 未修复 | 🟡 部分修复 | session 已复用但未批量 |
| money/sentiment 因子 | 🔴 未接入 | 🔴 未接入 | 跨四 |
| stock.py industry | 🟡 残留 | 🟢 **已修复** | 已删除 |
| news_tasks N+1 | 🟡 部分 | 🟢 **已修复** | 批量查询 |
| 前端 P2 全部 | 🟡 未修复 | 🔴 零修复 | 0/13 |

---

## 十一、修复优先级建议

### 第一批：修复新回归 NEW-08（阻断性）

1. **NEW-08** portfolio API `group_name` → `group_id`；同步修改 schema 和前端类型

### 第二批：修复跨四轮未修复的 P1

2. **P1-16** CORS 白名单
3. **P1-19** 风控 N+1 批量聚合（在 session 已复用基础上，改用 `symbol = ANY(:symbols) AND factor_name = ANY(:factors)`）
4. **money/sentiment 流水线** — 在 base.compute_all 中接入；在 data_collect 中持久化

### 第三批：前端 P2

5. 至少修复：ErrorBoundary、api.ts 业务码校验、usePortfolio try/catch、StockTable null 检查、硬编码 WS URL/代理

### 第四批：后端 P2

6. database.py 三件套（pool_pre_ping、rollback、close_db 重置）、redis_client ping、risk_guard deepcopy、ws gather/heartbeat 等

---

## 十二、评审结论

第八轮审查发现：

1. **v7 的三个阻断性回归已全部修复**，且长期积压的 5 个 P1 中修复了 2 个（Tushare 同步阻塞、弱口令），后端从"无法运行"改善为"可运行"。
2. **但又引入了 1 个新的回归 NEW-08**：portfolio API 表名改了但字段 `group_name` 未改为 `group_id`，SQL 仍会报错。
3. **仍有 3 个 P1 跨四轮未修复**：CORS 安全漏洞、风控 N+1 查询、money/sentiment 因子流水线。
4. **前端 P2 仍零修复**：13 项前端问题全部未动。
5. **修复质量有所提升**：本次修复更聚焦，没有再出现大范围的"改了模型没改 API"类遗漏（仅 NEW-08 一处字段遗漏），说明开发者的修复精度在提高。

**建议**：先修 NEW-08，然后集中火力解决 CORS、风控 N+1、money/sentiment 三个跨四轮 P1，前端至少补齐 ErrorBoundary 和 API 错误校验。

---

*评审完成于 2026-07-07*
