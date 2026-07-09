# 代码评审 · 第六轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（修复后代码状态）
> 对照：第五轮 `CODE_REVIEW_v5.md` 提出的全部 P1/P2 问题逐项核验
> 方法：实读源码（后端 22 文件 + 前端 22 文件）+ 交叉验证 init.sql / ORM / 因子注册表
> 重点：验证 v5 问题修复状态 + 识别回归性问题

---

## 一句话结论

**修复完成度严重不足**：v5 提出的 21 个 P1 + 56 个 P2 问题中，仅修复了 13 项（14%），部分修复 6 项，未修复 58 项，且引入了 4 个回归性新问题。最严重的是：①后端 ORM 模型修复不彻底且 news API 未同步更新字段名，调用即 AttributeError 崩溃；②`data_collect.py` 新增 `from app.config import settings` 导入不存在的符号，整个 Celery 任务模块无法加载。前端 P1 修复较好（7/10 已修复），但 P2 几乎未动（2/12）。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY FIXED | NOT FIXED | NEW ISSUE |
|------|------|-------|-----------------|-----------|-----------|
| 后端 P1 | 21 | 5 | 2 | 14 | — |
| 后端 P2 | 34 | 1 | 0 | 33 | — |
| 前端 P1 | 8 | 5 | 3 | 0 | — |
| 前端 P2 | 12 | 2 | 0 | 10 | — |
| 新问题 | — | — | — | — | 4 |
| **合计** | **75+4** | **13** | **5** | **57** | **4** |

---

## 三、✅ 已确认修复的问题

### 后端（6 项）

| # | v5 编号 | 文件 | 修复证据 |
|---|---------|------|---------|
| 1 | P1-01 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L76-84, L94-98, L388 | `_query_factor_data` 单独从 `stock_daily` 表查 `pct_change` 并 merge 进宽表；`_get_stock_return` 取真实涨跌幅，不再恒为 0 |
| 2 | P1-03 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L204-244 | 用 `prev_holdings` 计算当日收益，调仓日只更新 holdings，T+1 日起算，前视偏差已消除 |
| 3 | P1-04 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L316, L191 | `_get_tradable_stocks` 失败返回 `None`，调用方 `if tradable is not None:` 才过滤 |
| 4 | P1-05 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L53-60 | 用 `FactorCalculator.list_factors()` 做白名单校验，未知因子抛 `ValueError` |
| 5 | P1-02 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L484 | `if sentiment < -threshold and pct_change is not None and pct_change < -2:` 方向已修正 |
| 6 | P1-17 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L46-54 | `_get_async_session()` 返回新建未关闭 session，调用方在 finally 中 close |

### 前端（7 项）

| # | v5 编号 | 文件 | 修复证据 |
|---|---------|------|---------|
| 1 | P1-08 | [useTTS.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useTTS.ts) L24 | `speak` 已用 `useCallback([])` 包裹，引用稳定，无限循环已消除 |
| 2 | P1-09 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L90, L97 | `connect()` 和 `onopen` 重置 `reconnectCountRef.current = 0`；`disconnect()` 不再永久置满计数器 |
| 3 | P1-10 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L83-87 | 创建新连接前先 `wsRef.current.close()` 并置 null，防止 CONNECTING 状态泄漏 |
| 4 | P1-12 | [useAIChat.ts](file:///d:/code/project/trading_tools/frontend/src/components/AIAssistant/hooks/useAIChat.ts) L16-17, L29-37, L61-65 | 发送前 abort 旧流；函数式 `setMessages`；卸载 cleanup abort |
| 5 | P1-14 | [KLineChart/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/KLineChart/index.tsx) L27-48 | `useEffect([symbol])` 调用 `getKLine(symbol)` 加载数据并 `applyNewData` |
| 6 | P2-50 | [useTTS.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useTTS.ts) L40-44 | 卸载时 `window.speechSynthesis?.cancel()` |
| 7 | P2-56 | [useBacktest.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Backtest/hooks/useBacktest.ts) L13, L29-34 | 增加 `error` state，catch 中 setError 并对外暴露 |

---

## 四、🟡 部分修复的问题

### 后端（2 项）

#### P1-06 · query_router SQL 注入 — **部分修复**

- **文件**：[query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py)
- **修复点**：screener_query 已加因子白名单（L110-115）；backtest_query 已加白名单（L168-174），factor_names 改用 `?` 占位符（L178）。
- **未修复点**：`table` 参数**仍用 f-string 直接插值**（L124 `FROM {table} fv`，L181 `FROM '{table}'`），无白名单校验。L181 的单引号包裹在 DuckDB 中会当字面量字符串处理，是 SQL 错误。
- **修复建议**：增加 `table` 白名单 `{"factor_value", "stock_daily"}`，校验后再拼接。

#### P2-4 · DuckDB 单连接并发 — **部分修复**

- **文件**：[query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py)
- **修复点**：`backtest_query` 每次新建并关闭连接（L162, L195）。
- **未修复点**：`QueryRouter.__init__` 仍保留 `self._duck_conn`（L36），`query_duckdb`（L72）仍用 `self._duck_conn.execute`，并发调用会冲突。该连接在 backtest 路径未被使用，属死代码+残留隐患。

### 前端（3 项）

#### P1-11 · useNewsStream 重连+游标 — **部分修复 / 引入新问题**

- **文件**：[useNewsStream.ts](file:///d:/code/project/trading_tools/frontend/src/pages/News/hooks/useNewsStream.ts)
- **修复点**：重连逻辑已添加（L130-166 指数退避）；游标已修复（L76-80 取最旧时间作为下一页 cursor）。
- **新问题**：重连的 `newWs.onclose`（L144-146）仅 `setIsConnected(false)`，**未递归再次调度重连**。第二次断开后永久失联。

#### P1-13 · useBacktest/usePortfolio 未处理拒绝 — **部分修复**

- **修复点**：useBacktest 已加 try/catch + setError。
- **未修复点**：[usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L46-73 的 `addPosition`/`editPosition`/`removePosition` **仍无 try/catch**，`createPosition` 等 API 调用抛错时形成未处理 Promise 拒绝。

#### P1-15 · vite.config WebSocket 代理 — **部分修复 / 引入新问题**

- **修复点**：[vite.config.ts](file:///d:/code/project/trading_tools/frontend/vite.config.ts) L14-17 已添加 `/ws` 代理。
- **新问题**：① API 代理目标 `localhost:8080`（L11）与 WS 代理目标 `localhost:8000`（L15）**端口不一致**。② `useWebSocket.ts` L92 和 `useNewsStream.ts` L122,137 均**硬编码直连** `ws://localhost:8000`，完全绕过 Vite 代理，代理形同虚设。

---

## 五、🔴 未修复的 P1 问题（14 项）

### 后端 P1（14 项）

| # | v5 编号 | 文件 | 行号 | 问题概述 |
|---|---------|------|------|---------|
| 1 | P1-07 | [models/stock.py](file:///d:/code/project/trading_tools/backend/app/models/stock.py) | L19-29 | ORM 仍有 5 个 init.sql 不存在的字段（`full_name`, `exchange`, `total_shares`, `is_active`, `updated_at`）；`industry` 和 `sector` 同义重复 |
| 2 | P1-07 | [models/portfolio.py](file:///d:/code/project/trading_tools/backend/app/models/portfolio.py) | L29-41 | `PortfolioHolding` 幽灵表仍存在（init.sql 无此表），字段全部不匹配 |
| 3 | P1-07 | [models/news.py](file:///d:/code/project/trading_tools/backend/app/models/news.py) | L28 | 多余 `created_at` 字段（init.sql 的 news_raw 无此列） |
| 4 | P1-07 | [models/timescale.py](file:///d:/code/project/trading_tools/backend/app/models/timescale.py) | L25, L45 | `StockMinute` 和 `StockDaily` 多余 `created_at`（init.sql 无此列） |
| 5 | P1-06 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) | L124, L181 | `table` 仍 f-string 拼接，无白名单 |
| 6 | P1-16 | [main.py](file:///d:/code/project/trading_tools/backend/app/main.py) | L75-81 | CORS 仍 `allow_origins=["*"]` + `allow_credentials=True` |
| 7 | P1-18 | [tushare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tushare.py) | L53, L92 | async 方法仍直接同步调用 `self._pro.realtime_quote()`/`self._pro.daily()`，阻塞事件循环 |
| 8 | P1-19 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | L218-260, L367-479 | N+1 查询未修复，每只股票每次检查新建 session，全市场 ~50000 次查询 |
| 9 | P1-20 | [news_tasks.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_tasks.py) | L116 | 仍 `__import__("sqlalchemy")` 动态导入 + 循环内逐条 SELECT |
| 10 | P1-21 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) | L28 | `DATABASE_URL` 默认值仍含弱口令 `postgres:postgres` |
| 11 | v5 遗留 | [factor_lib/base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) | L65-84 | `compute_all()` 仍只调 `technical.compute_all()`，未调 money/sentiment |
| 12 | v5 遗留 | [factor_lib/money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) | 全文件 | 仍是 stub，返回 `NORTH_FLOW_NET` 等与下游期望的 `net_amount` 不匹配 |
| 13 | v5 遗留 | [factor_lib/sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) | L27, L46, L69 | 仍用 `asyncio.run()` 包装异步查询，无法在 async 上下文中运行 |
| 14 | v5 遗留 | sentiment 持久化 | — | `sentiment_score_1d` 从未写入 `factor_value` 表 |

### 前端 P1（0 项完全未修复，3 项部分修复见上）

---

## 六、🔴 未修复的 P2 问题（43 项）

### 后端 P2（33 项）

| # | v5 编号 | 文件 | 问题概述 |
|---|---------|------|---------|
| 1 | P2-1 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L46-53 | `close_db()` 未重置 engine/async_session_factory 为 None |
| 2 | P2-2 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L56-64 | `get_session()` 缺少显式 rollback |
| 3 | P2-3 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) L36-41 | 缺少 `pool_pre_ping=True` |
| 4 | P2-5 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) L110, L169 | core 反向依赖 services（`from app.services...`） |
| 5 | P2-6 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L17-30 | `init_redis()` 无 ping 健康检查 |
| 6 | P2-7 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) L44-51 | `get_redis()` 返回 None 而非抛 RuntimeError |
| 7 | P2-9 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) + [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) | config.yaml 仍未被任何 Python 代码加载，双轨配置 |
| 8 | P2-10 | [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) L19 | `/tmp/duckdb` 在 Windows 不存在 |
| 9 | P2-11 | [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) L14 | dbname `trading` 与 config.py `astock` 不一致 |
| 10 | P2-12 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) | 缺少 SECRET_KEY/CORS 配置入口 |
| 11 | P2-13 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L110, L134 | `update_rule` 浅拷贝，修改阈值污染类变量 |
| 12 | P2-14 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L328-330 | bollinger_breakdown 无 enabled 开关 |
| 13 | P2-15 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L256 | `column` 参数 f-string 拼接无白名单 |
| 14 | P2-16 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L377 | `momentum_20d` 依赖未注册因子 |
| 15 | P2-17 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L308 | `list_date IS NULL` 仍当作可交易 |
| 16 | P2-18 | [quote_gateway.py](file:///d:/code/project/trading_tools/backend/app/services/quote_gateway.py) L66-69 | 数据源切换无日志 |
| 17 | P2-19 | [redis_stream.py](file:///d:/code/project/trading_tools/backend/app/services/redis_stream.py) L89-99 | `xack` 在 finally 中，消费失败仍确认（数据丢失） |
| 18 | P2-20 | [llm_service.py](file:///d:/code/project/trading_tools/backend/app/services/llm_service.py) L65-93 | `stream_generate` 缺 temperature/max_tokens |
| 19 | P2-21 | [ai_explainer.py](file:///d:/code/project/trading_tools/backend/app/services/ai_explainer.py) L140-145 | 引用未注册因子 `pe_ttm`/`change_pct` |
| 20 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L42-51 | 故意 raise+catch 走 mock 路径 |
| 21 | P2-27 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L108-124 | 因子写入无 FACTOR_REGISTRY 白名单校验 |
| 22 | P2-28 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L130-150 | 逐行 INSERT 而非批量 |
| 23 | P2-30 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L49-75 | 缓存并发无锁 |
| 24 | P2-31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L121-128 | `float(row.get("开盘", 0))` 未防御 None |
| 25 | P2-33 | [screener.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/screener.py) L27 | 路由 `/api/v1/screener/screener` 双重冗余 |
| 26 | P2-34 | [portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) L127-132 | SQL 仍引用不存在的 `portfolio_holding` 表；`ph.group_name` 列不存在 |
| 27 | P2-35 | [portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) L142-147 | 查询失败仍回退 `_MOCK_POSITIONS` 模拟数据 |
| 28 | P2-36 | [risk.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) L29-31 | `get_alerts` 吞异常返回空列表 |
| 29 | P2-37 | [ai.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L50-51 | `chat` 仍用 Query 参数传 message，无长度限制 |
| 30 | P2-38 | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L59, L63 | neutral 查询 `sentiment_score == 0` 与标签定义 -0.1~0.1 不一致 |
| 31 | P2-39 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L153-158 | 广播仍逐个 send_text，未用 asyncio.gather |
| 32 | P2-41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) 全局 | 无心跳/ping-pong 机制 |
| 33 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L16-24 | `async_session_factory` 未判 None；无 commit/rollback |
| — | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) L15-20 | `ipo_date` 仍未改为 `list_date`；`code`/`exchange`/`industry`/`is_active` 均不匹配 |
| — | P2-44 | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L64-68 | `strategy: dict` 无结构校验；日期未校验格式 |

### 前端 P2（10 项）

| # | v5 编号 | 文件 | 问题概述 |
|---|---------|------|---------|
| 1 | P2-45 | [App.tsx](file:///d:/code/project/trading_tools/frontend/src/App.tsx) | 仍无 ErrorBoundary |
| 2 | P2-46 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L27-34 | 响应拦截器未校验业务 code |
| 3 | P2-47 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L427-475 | sendChatMessage 无超时；`!reader` 提前 return 不调 onDone |
| 4 | P2-48 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L70 | quotes 仍为 useState<Map>，高频无意义重渲染 |
| 5 | P2-49 | useWebSocket.ts L92, useNewsStream.ts L122 | 仍硬编码 `ws://localhost:8000` |
| 6 | P2-51 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L46-73 | 变更操作无 try/catch，无错误回滚 |
| 7 | P2-52 | [useReports.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Reports/hooks/useReports.ts) L29-39 | fetchDetail 无竞态保护 |
| 8 | P2-53 | [StockTable/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/StockTable/index.tsx) L47 | toFixed 未判空 |
| 9 | P2-54 | [useUserStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useUserStore.ts) L40-46 | addWatchlistCode 无去重 |
| 10 | P2-55 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L178 | getReportDetail 未 encodeURIComponent |

---

## 七、🔴 新引入的回归性问题（4 项）

### NEW-01 · news API 引用已重命名的 ORM 字段 — **运行时 AttributeError 崩溃**

- **文件**：[news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py)
- **行号**：L67, L70, L142, L146, L147, L150
- **描述**：News ORM 模型字段已重命名（`related_codes`→`related_stocks`，`published_at`→`publish_time`），但 `api/v1/news.py` 仍引用旧字段名：
  - L67: `News.related_codes.like(...)` → ORM 中已无 `related_codes`
  - L70: `News.published_at.desc()` → ORM 中已无 `published_at`
  - L142: `news.summary` → ORM 中无此字段
  - L146: `news.published_at.isoformat()` → 应为 `publish_time`
  - L147: `news.related_codes.split(",")` → 应为 `related_stocks`
  - L150: `news.created_at.isoformat()` → init.sql 的 news_raw 表无 `created_at` 列
- **影响**：调用 `/news/stream` 或 `/news/{id}` 接口会直接 `AttributeError` 崩溃。
- **根因**：模型修复与 API 修复未协同联动。
- **修复**：将 news.py API 中所有 ORM 字段引用更新为当前字段名。

### NEW-02 · data_collect.py 导入不存在的符号 — **Celery 任务模块无法加载**

- **文件**：[data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py)
- **行号**：L18
- **描述**：`from app.config import settings` —— 但 `app/config.py` 只导出 `get_settings()` 函数和 `Settings` 类，**没有 `settings` 模块级变量**。该 import 在模块加载时抛 `ImportError`，整个 data_collect 模块无法被 `celery_app.autodiscover_tasks()` 加载，**所有定时任务（行情同步、因子计算）全部失效**。
- **修复**：改为 `from app.config import get_settings` 然后 `settings = get_settings()`，或直接在 config.py 中添加 `settings = get_settings()` 模块级变量。

### NEW-03 · useNewsStream 重连仅生效一次

- **文件**：[useNewsStream.ts](file:///d:/code/project/trading_tools/frontend/src/pages/News/hooks/useNewsStream.ts)
- **行号**：L144-146
- **描述**：重连的 `newWs.onclose` 仅 `setIsConnected(false)`，未递归再次调度 setTimeout 重连。第二次断开后永久失联。
- **修复**：将重连逻辑提取为可递归调用的函数，`newWs.onclose` 中也调度重连。

### NEW-04 · useWebSocket 回调依赖不稳定导致重连风暴（潜在）

- **文件**：[useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts)
- **行号**：L154
- **描述**：`connect` 的依赖为 `[getReconnectDelay, onQuote, onAlert, onIndex, onSector]`（L154），而 `onQuote` 等回调若调用方未用 `useCallback` 包裹，每次渲染引用变化 → `connect` 变化 → L182-188 `useEffect` 重新执行 → 每次渲染都重连 WebSocket。当前 Dashboard 虽做了 `useCallback` 稳定化，但模式脆弱。
- **修复**：将回调存入 ref，`connect` 依赖改为 `[]`，在内部通过 ref 读取最新回调。

---

## 八、模块状态总览

| 模块 | v5 状态 | v6 状态 | 变化说明 |
|------|---------|---------|---------|
| 回测引擎 | 🔴 三连失效 | 🟢 **已修复** | change_pct / 前视偏差 / 降级清空 三项均已修复 |
| 风控-负面舆情方向 | 🔴 方向反了 | 🟢 **已修复** | `sentiment < -threshold` |
| 风控-资金流因子 | 🔴 no-op | 🔴 未修复 | money.py 仍是 stub，因子名不匹配 |
| 风控-舆情因子 | 🔴 no-op | 🔴 未修复 | sentiment.py 未改，未写入 factor_value |
| 风控-N+1 查询 | 🔴 ~50000 次 | 🔴 未修复 | 每次检查新建 session |
| ORM 模型 | 🔴 大面积不匹配 | 🟡 **部分修复** | 列名基本对齐但残留多余字段；PortfolioHolding 幽灵表仍在 |
| news API | 🟡 不一致 | 🔴 **回归崩溃** | ORM 改了字段名但 API 未跟改，调用即 AttributeError |
| data_collect 任务 | 🟡 session 泄漏 | 🔴 **回归崩溃** | 新增 import 错误，模块无法加载 |
| CORS 安全 | 🔴 漏洞 | 🔴 未修复 | 仍 `*` + credentials |
| 前端 useRisk | 🔴 无限循环 | 🟢 **已修复** | speak 已 useCallback |
| 前端 WebSocket | 🔴 重连失效 | 🟢 **已修复** | 重置计数器 + 先关闭旧连接 |
| 前端 KLineChart | 🔴 功能缺失 | 🟢 **已修复** | 已加载数据 |
| 前端 AI 聊天 | 🔴 闭包/串流 | 🟢 **已修复** | 函数式更新 + abort + cleanup |
| 前端 useNewsStream | 🔴 无重连 | 🟡 部分修复 | 重连仅一次；游标已修 |
| 前端 usePortfolio | 🟡 无 catch | 🟡 部分修复 | fetchPositions 有 catch；变更操作仍无 catch |
| 前端 ErrorBoundary | 🟡 缺失 | 🟡 未修复 | — |
| 前端 api.ts | 🟡 未校验 code | 🟡 未修复 | — |

---

## 九、修复优先级建议

### 第一批：修复回归性崩溃（阻断性）

1. **NEW-01** news.py API 字段对齐 — 调用即 AttributeError
2. **NEW-02** data_collect.py import 修复 — Celery 任务全部失效
3. **NEW-03** useNewsStream 重连递归 — 第二次断连不恢复

### 第二批：完成未修复的 P1

4. **P1-07** ORM 模型彻底修复（删除多余字段、删除 PortfolioHolding 幽灵表）
5. **P1-16** CORS 白名单
6. **P1-18** Tushare asyncio.to_thread
7. **P1-19** 风控 N+1 查询批量化
8. **P1-20** news_tasks 动态 import 消除
9. **P1-21** 弱口令移除
10. **v5 遗留** money.py / sentiment.py 接入因子计算流水线

### 第三批：修复 P2

11. 按 v5 P2 清单逐项修复

### 第四批：修复 P3

12. 代码质量改进

---

## 十、评审结论

第六轮审查发现：

1. **回测引擎三连失效已修复**（P1-01/03/04/05），这是本轮最大亮点。
2. **前端 P1 修复较好**（7/10 已修复），useRisk 无限循环、WebSocket 重连/泄漏、KLineChart 数据加载、AI 聊天闭包/abort 等关键问题都已解决。
3. **但整体修复率仅 17%**（13/75），远未达到"修复完毕"的声明。特别是：
   - 后端 P2 几乎全部未动（1/33 已修复）
   - ORM 模型修复不彻底且未联动 API 层，引入 news.py 运行时崩溃
   - data_collect.py 新增 import 错误，Celery 任务全部失效
4. **4 个回归性新问题**中，NEW-01 和 NEW-02 是阻断性崩溃，必须立即修复。

**建议**：优先修复 NEW-01/02/03 三个回归性问题，然后继续完成未修复的 P1 项。在修复 ORM 模型时务必同步更新所有引用该模型的 API 代码，避免再次出现"改了模型没改 API"的联动遗漏。

---

*评审完成于 2026-07-07*
