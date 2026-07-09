# 代码评审 · 第五轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（截至 2026-07-07 的完整代码状态）
> 对照：第四轮 `CODE_REVIEW_v4.md` 提出的问题逐项核验 + 全量深度审查
> 方法：实读源码（后端 40+ 文件 + 前端 22 文件）+ 交叉验证 init.sql / ORM / 因子注册表
> 范围：后端 core / services / factor_lib / tasks / api / models / schemas + 前端全部

---

## 一句话结论

**v4 遗留的两个 P1 问题（资金流因子、舆情因子未接入）仍未修复，且全量审查发现了更多系统性缺陷**：回测引擎三连失效（收益恒 0 + 前视偏差 + 降级清空）、ORM 模型与 init.sql 大面积不匹配、前端 useRisk 无限循环等 P1 问题。整体状态从 v4 的 🟢 下调为 🔴 —— 当前代码**不可用于生产**，需优先修复本轮发现的 P1 问题。

---

## 一、v4 遗留问题修复状态

| v4 编号 | 问题 | 状态 | 说明 |
|---------|------|------|------|
| P1-2 | 资金流因子未接入（`net_amount`/`net_amount_ratio` 从未写入） | ❌ **未修复** | `money.py` 仍是占位 stub，返回 `NORTH_FLOW_NET` 等大写因子名与下游期望的 `net_amount` 不匹配；`compute_all()` 仍未调用 money 计算 |
| P1-5 | 舆情因子未接入（`sentiment_score_1d` 从未写入） | ❌ **未修复** | `sentiment.py` 函数无人调用；且 `asyncio.run()` 包装在异步上下文中会抛 `RuntimeError`，即便接入也无法工作 |
| P2-1 | `negative_sentiment` 检查只判一半（缺下跌判定） | ⚠️ **部分修复** | 补了 `pct_change < -2` 条件，但**情感方向判定反了**（见本轮 P1-02） |
| P2-2 | `delist_date` 从未写入 | ❌ **未修复** | `sync_history.py` 仍只 INSERT `list_date` |
| P2-3 | `list_date` 全空 → 回测全空 | ❌ **未修复** | `backtester.py:280` 加了 `OR list_date IS NULL`，但降级返回 `[]` 反而清空所有股票（见本轮 P1-11） |
| P2-4 | ORM 模型与表结构不一致 | ❌ **未修复且更严重** | 本轮发现不匹配范围远超 v4 认知，涉及全部 4 个 ORM 模型（见本轮 P1-36） |

---

## 二、🔴 P1 级问题（严重，必须立即修复）

### P1-01 · 回测引擎：个股收益永远为 0（回测完全失效）

- **文件**：[backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py)
- **行号**：L349, L360-362, L371-373
- **描述**：`_get_stock_return` 和 `_calc_benchmark_return` 从 `day_data` 取 `change_pct`，但 `day_data` 来源于 `_query_factor_data` 查询的 `factor_value` 长表，只包含 `conditions` 中声明的因子。`change_pct` **不是注册因子**（不在 `FACTOR_REGISTRY`），也**不会被写入 `factor_value`**。因此 `row.get("change_pct", 0)` 永远命中默认值 `0`，策略与基准净值恒为 1.0。
- **影响**：回测结果完全失真——任何策略都近似"零收益扣手续费"，总收益/夏普/最大回撤全部无意义。
- **修复**：`_query_factor_data` 同时关联 `stock_daily` 表取 `pct_change`，或把日涨跌幅作为内置因子注册计算。

### P1-02 · 风控引擎：负面舆情检查情感方向判定反了

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py)
- **行号**：L481
- **描述**：`sentiment_score_1d` 取值范围 `[-1, 1]`，负值=负面、正值=正面。规则名 `negative_sentiment`，阈值 `threshold=0.6`，但判定条件为 `if sentiment > threshold`，实际匹配的是**正面情绪强烈**的股票，方向完全相反。
- **影响**：即使舆情因子接入，负面舆情风控也永不触发。
- **修复**：改为 `if sentiment < -threshold`。

### P1-03 · 回测引擎：调仓当日用 T 日数据算收益（前视偏差）

- **文件**：[backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py)
- **行号**：L176-208
- **描述**：注释声称"T 日信号 → T+1 日成交"，但实际在调仓日 `for day` 循环中用 `daily_data[day]`（T 日因子/收盘价）选股后**立即**用同一日数据计算组合收益。`next_day` 变量被计算后从未使用（死代码）。
- **影响**：回测净值高估策略表现。
- **修复**：调仓日只更新 `current_holdings`，收益从 `trading_days[day_idx+1]` 起算。

### P1-04 · 回测引擎：幸存者过滤降级返回空列表清空所有股票

- **文件**：[backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py)
- **行号**：L152-156, L274, L287-288
- **描述**：`_get_tradable_stocks` 在异常或 `async_session_factory is None` 时返回 `[]`（注释写"降级为不过滤"），但 154-156 行的过滤逻辑 `if s.get("symbol","") in tradable` 当 `tradable=[]` 时**清空当日所有股票**，回测在第一次循环后就没有数据了。
- **修复**：失败时返回 `None`，调用方 `if tradable is not None:` 才过滤。

### P1-05 · 回测引擎：`_query_factor_data` SQL 注入

- **文件**：[backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py)
- **行号**：L50-57
- **描述**：`factor_list = ", ".join([f"'{f}'" for f in factor_names])` 把用户输入的因子名直接拼进 `IN (...)`，未做白名单校验（对比 `stock_picker.py` 有校验）。攻击者可构造 `x') OR 1=1 --` 实施注入。
- **修复**：复用 `stock_picker` 的白名单逻辑校验 `FACTOR_REGISTRY`。

### P1-06 · 查询路由器：SQL 注入（backtest_query / screener_query）

- **文件**：[query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py)
- **行号**：L178-184, L121-128
- **描述**：`backtest_query` 中 `start`/`end`/`table`/`factor_names` 全部通过 f-string 拼接进 SQL，无参数化、无白名单校验。`screener_query` 中 `table` 同样未做白名单即拼接进 `FROM {table}`。
- **修复**：DuckDB 用 `?` 占位符 + params 列表；`table` 增加白名单 `{"factor_value"}`。

### P1-07 · ORM 模型与 init.sql 大面积不匹配（系统性根因）

- **文件**：[models/timescale.py](file:///d:/code/project/trading_tools/backend/app/models/timescale.py), [models/stock.py](file:///d:/code/project/trading_tools/backend/app/models/stock.py), [models/portfolio.py](file:///d:/code/project/trading_tools/backend/app/models/portfolio.py), [models/news.py](file:///d:/code/project/trading_tools/backend/app/models/news.py)
- **描述**：ORM 模型与实际表结构（`init.sql`）存在大面积字段名/表名不匹配：

| ORM 模型 | ORM 表名/列名 | init.sql 实际表名/列名 |
|----------|--------------|----------------------|
| `News` | 表名 `news` | `news_raw` |
| `News.published_at` | `published_at` | `publish_time` |
| `News.related_codes` (String) | `related_codes` | `related_stocks` (TEXT[]) |
| `News.created_at` | `created_at` | `crawl_time` |
| `StockDaily.code` | `code` | `symbol` |
| `StockDaily.date` | `date` | `trade_date` |
| `StockDaily.change_pct` | `change_pct` | `pct_change` |
| `StockDaily.turnover` | `turnover` | `turn` |
| `FactorValue.code` | `code` | `symbol` |
| `FactorValue.date` | `date` | `trade_date` |
| `StockInfo.code` | `code` | `symbol` |
| `StockInfo.industry` | `industry` | `sector` |
| `PortfolioHolding` | 表名 `portfolio_holding` | **表不存在**（init.sql 只有 `portfolio`） |

- **影响**：服务层用 `text()` 原生 SQL 走 init.sql 真实列名（暂时正确），但任何使用 ORM `select()` 的代码都会失败。`news.py` API 导入 `News` ORM 查询 `news` 表会直接报错。
- **修复**：以 `init.sql` 为准重写全部 ORM 模型。

### P1-08 · 前端 useRisk 无限循环（持续打接口 + 语音播报风暴）

- **文件**：[useRisk.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Risk/hooks/useRisk.ts), [useTTS.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useTTS.ts)
- **行号**：useRisk.ts: L14, L36, L57-60；useTTS.ts: L22
- **描述**：`useTTS.speak` 未用 `useCallback` 包裹，每次渲染返回新函数引用 → `useRisk.fetchAlerts`（依赖 `[speak]`）每次渲染变更 → `useEffect`（依赖 `[fetchAlerts]`）每次渲染重跑 → `setAlerts`/`setLoading` 触发再次渲染 → **无限循环**，持续打后端接口并触发语音播报。
- **修复**：`useTTS` 的 `speak` 用 `useCallback` 包裹。

### P1-09 · 前端 useWebSocket 重连失效（断线后永不重连）

- **文件**：[useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts)
- **行号**：L152
- **描述**：`disconnect()` 将 `reconnectCountRef.current = maxReconnects` 永久置满。当 `connect` 因依赖变更重新执行时，新连接若失败，`onclose` 检查 `reconnectCountRef < maxReconnects` 为 false，**不再重连**，WebSocket 永久死亡。
- **修复**：`disconnect` 不应永久置满计数器；`connect` 时应重置 `reconnectCountRef.current = 0`。

### P1-10 · 前端 useWebSocket 连接泄漏

- **文件**：[useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts)
- **行号**：L83
- **描述**：`if (wsRef.current?.readyState === WebSocket.OPEN) return` 仅拦截 OPEN 状态。若处于 `CONNECTING` 状态会创建新连接并覆盖 `wsRef.current`，旧连接无法关闭，回调仍触发。
- **修复**：同时拦截 `CONNECTING` 状态，或先 `wsRef.current?.close()` 再创建新连接。

### P1-11 · 前端 useNewsStream 无重连 + 分页游标错误

- **文件**：[useNewsStream.ts](file:///d:/code/project/trading_tools/frontend/src/pages/News/hooks/useNewsStream.ts)
- **行号**：L116-152（无重连），L72-75（游标错误）
- **描述**：① WebSocket `onclose` 仅 `setIsConnected(false)` 无重连逻辑，断开后永不恢复。② `loadMore` 时新数据为更旧新闻，但代码将 `latestTimeRef` 更新为本批最新时间（比已有更早），后续 `loadMore` 会从该更早时间拉取，导致漏数据或重复。
- **修复**：① 加指数退避重连。② 游标应使用本批最旧时间，且不覆盖首次 latestTime。

### P1-12 · 前端 useAIChat 闭包陈旧 + 未 abort 旧流 + 卸载内存泄漏

- **文件**：[useAIChat.ts](file:///d:/code/project/trading_tools/frontend/src/components/AIAssistant/hooks/useAIChat.ts)
- **行号**：L15-42
- **描述**：① `sendMessage` 闭包捕获 `messages`，连续快速发送时第二条不含第一条（异步 setState），上下文丢失。② 发送新消息时未 abort 上一次流，旧流 `onMessage` 持续 mutate 旧 `assistantMsg`，新消息被旧流内容覆盖。③ 组件卸载时无 cleanup 调用 `abortRef.current?.()`，流未结束时 `onMessage`/`onDone` 仍 setState 已卸载组件。
- **修复**：① 用 `setMessages` 函数式更新。② 发送前 `abortRef.current?.()`。③ `useEffect` cleanup 中 abort。

### P1-13 · 前端 useBacktest / usePortfolio 未处理 Promise 拒绝

- **文件**：[useBacktest.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Backtest/hooks/useBacktest.ts), [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts)
- **行号**：useBacktest.ts: L25-34；usePortfolio.ts: L21-29
- **描述**：`submitBacktest` / `fetchPositions` 仅有 `try/finally` 无 `catch`，失败时 Promise 拒绝向调用方传播，产生未处理 Promise 拒绝。
- **修复**：补 `catch` 块并设置 `error` state 供 UI 展示。

### P1-14 · 前端 KLineChart 不加载数据（功能缺失）

- **文件**：[KLineChart/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/KLineChart/index.tsx)
- **行号**：L15
- **描述**：`symbol` prop 被解构为 `_symbol` 完全未使用。组件初始化图表后不加载任何数据，图表永远空白。
- **修复**：根据 `symbol` 调用 API 加载 K 线数据并 `applyNewData`。

### P1-15 · 前端 vite.config.ts 未配 WebSocket 代理 + 端口不一致

- **文件**：[vite.config.ts](file:///d:/code/project/trading_tools/frontend/vite.config.ts)
- **行号**：L9-14
- **描述**：仅代理 `/api` 到 `localhost:8080`，未配置 WebSocket 代理。而 `useWebSocket` 指向 `ws://localhost:8000`，`useNewsStream` 也指向 `ws://localhost:8000`，端口与 REST(8080) 不一致且不走代理，**生产部署必然失败**。
- **修复**：统一通过 `/ws` 路径走代理并使用环境变量。

### P1-16 · CORS 安全漏洞（allow_origins=["*"] + allow_credentials=True）

- **文件**：[main.py](file:///d:/code/project/trading_tools/backend/app/main.py)
- **行号**：L77-78
- **描述**：`allow_origins=["*"]` 配合 `allow_credentials=True` 是**严重安全漏洞**——任意网站都能携带凭证访问 API，存在 CSRF 和数据泄露风险。
- **修复**：指定明确的白名单域名，或 `allow_credentials=False`。

### P1-17 · data_collect.py `_get_async_session()` 返回已关闭的 session

- **文件**：[data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py)
- **行号**：L46-50
- **描述**：`async with async_session_factory() as session: return session` —— `async with` 退出时 session 已被 `close()`，调用方拿到的是已关闭的 session，后续 `session.execute()` 会抛 `StatementError`。
- **修复**：直接 `return async_session_factory()`，由调用方管理生命周期。

### P1-18 · Tushare Provider 的 async 方法实际是同步阻塞

- **文件**：[tushare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tushare.py)
- **行号**：L53, L92
- **描述**：方法声明为 `async`，但内部直接调用同步阻塞 API `self._pro.realtime_quote()` / `self._pro.daily()`，会阻塞整个事件循环。
- **修复**：用 `await asyncio.to_thread(self._pro.daily, ...)` 包装。

### P1-19 · 风控 N+1 查询（盘后扫描约 50000 次查询）

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py)
- **行号**：L204-232, L234-261, L354-462
- **描述**：`_get_factor_value` / `_get_stock_daily_value` 内部各自新建 session。每只股票每项检查 2 次查询 + 2 次会话创建，五项检查合计约 **10N 次查询**（全市场 ~50000 次）。
- **影响**：盘后扫描可能从秒级退化到数十分钟。
- **修复**：复用 `scan_after_hours` 的 session；用 `factor_name IN (...)` + `GROUP BY symbol` 批量取回。

### P1-20 · news_tasks.py 动态导入 + N+1 查询

- **文件**：[news_tasks.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_tasks.py)
- **行号**：L116
- **描述**：`__import__("sqlalchemy").select(News).where(News.url == item.url)` 在循环内动态导入并逐条查询，N 条新闻发 N 次 SELECT。
- **修复**：文件顶部 `import sqlalchemy as sa`；批量 INSERT ... ON CONFLICT DO NOTHING。

### P1-21 · 硬编码弱口令

- **文件**：[config.py](file:///d:/code/project/trading_tools/backend/app/config.py) L28, [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) L13
- **描述**：`DATABASE_URL` 默认值 `postgresql+asyncpg://postgres:postgres@localhost:5432/astock`；`config.yaml` 明文 `password: postgres`。
- **修复**：默认值设为空并强制要求环境变量；config.yaml 用 `${DB_PASSWORD}` 占位。

---

## 三、🟠 P2 级问题（重要，应尽快修复）

### 后端核心

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| P2-1 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) | L46-53 | `close_db()` 未重置全局变量为 None，重复调用或重 init 导致资源泄漏 |
| P2-2 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) | L56-64 | `get_session()` 缺少显式 `rollback()`，异常时挂起事务可能未回滚 |
| P2-3 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) | L36-41 | 缺少 `pool_pre_ping=True` 和 `pool_recycle`，长连接断开风险 |
| P2-4 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) | L36, L197-198 | 全局 DuckDB 单连接在多并发请求下复用 `execute()` 存在竞态 |
| P2-5 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) | L110-112 | core 反向依赖 services（`from app.services.factor_lib.base import ...`），分层违规 |
| P2-6 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) | L17-30 | `init_redis()` 未做连接健康检查（`await redis_client.ping()`） |
| P2-7 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) | L44-51 | `get_redis()` 未初始化时返回 None，调用方拿到 None 后 AttributeError |
| P2-8 | [celery_app.py](file:///d:/code/project/trading_tools/backend/app/core/celery_app.py) | L46-70 | beat 中新闻爬取间隔(*/30)与 Settings 中的间隔配置完全不一致，双轨配置 |
| P2-9 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) + [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) | — | config.yaml 未被任何 Python 代码加载，双轨配置且互不读取 |
| P2-10 | [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) | L19 | `temp_directory: /tmp/duckdb` 是 Unix 路径，**Windows 11 上不存在** |
| P2-11 | [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) | L14 | dbname `trading` 与 config.py 默认 `astock` 不一致 |
| P2-12 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) | — | 缺少 SECRET_KEY / CORS allow_origins 配置入口 |

### 后端服务

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| P2-13 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | L110, L132-134 | `update_rule` 浅拷贝 `DEFAULT_RULES`，修改阈值污染类变量（所有实例受影响） |
| P2-14 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | L328-330 | 布林带破位检查无 enabled 开关，且 DEFAULT_RULES 中无此规则项 |
| P2-15 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | L254 | `_get_stock_daily_value` 的 `column` 参数通过 f-string 拼接进 SQL（防御性注入面） |
| P2-16 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) | L349 | `_score_stock` 依赖未注册因子 `momentum_20d`，Top N 排序退化为按原始顺序取前 N |
| P2-17 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) | L280 | `list_date IS NULL` 被当作"随时可交易"，可能纳入上市前股票（幸存者偏差） |
| P2-18 | [quote_gateway.py](file:///d:/code/project/trading_tools/backend/app/services/quote_gateway.py) | L66-69 | 主备数据源切换无日志，akshare 失败原因完全未记录 |
| P2-19 | [redis_stream.py](file:///d:/code/project/trading_tools/backend/app/services/redis_stream.py) | L90-99 | `xack` 放在 `finally` 中，消费端处理失败的消息仍被确认（数据丢失） |
| P2-20 | [llm_service.py](file:///d:/code/project/trading_tools/backend/app/services/llm_service.py) | L64-93 | `stream_generate` 缺少 `temperature`/`max_tokens` 参数 |
| P2-21 | [ai_explainer.py](file:///d:/code/project/trading_tools/backend/app/services/ai_explainer.py) | L140-145 | 引用未注册因子 `pe_ttm`、`change_pct`，永远不会生效 |
| P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) | L42-51 | 故意 raise 再 catch 走 mock 路径（反模式），掩盖真实异常 |
| P2-23 | 服务层多文件 | — | 普遍"数据库异常即降级返回空"，掩盖错误，运维难以发现 |

### 因子库与数据采集

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| P2-24 | [technical.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/technical.py) | L58 | `MA5_MA20_RATIO` 除零未保护（与 `VOLUME_RATIO` 的处理不一致） |
| P2-25 | [technical.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/technical.py) | L124-125 | `BIAS_5`/`BIAS_10` 计算 `ma5=0` 时产生 inf |
| P2-26 | [technical.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/technical.py) | L222 | `is_hammer_down` 计算后从未使用（死代码） |
| P2-27 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) | L109-120 | 遍历所有列写入因子，未用 `FACTOR_REGISTRY` 白名单校验，额外列会被错误写入 |
| P2-28 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) | L129-138 | 逐行 INSERT 而非批量，对 5000 股票 × 30+ 因子性能差 |
| P2-29 | [sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) | L92-182 | LIKE 查询未转义 SQL 通配符（`%`/`_`）；3 次 SQL 可合并为 1 次聚合 |
| P2-30 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) | L50-52 | `_cached_quotes` 类级别属性但实例级赋值造成阴影；多协程并发刷新无锁 |
| P2-31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) | L121-128 | `float(row.get("开盘", 0))` 未防御 None/NaN（停牌场景） |
| P2-32 | [news_analysis.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_analysis.py) | L87 | 只更新 `sentiment_score`，`sentiment_label` 从未设置（文档与实现不符） |

### API 层

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| P2-33 | [screener.py](file:///d:/code/project/trading_tools/backend/app/api/v1/screener.py) | L27 | 路由 `/api/v1/screener/screener` 冗余，应为 `@router.post("")` |
| P2-34 | [portfolio.py](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) | L127-132 | SQL 引用 `portfolio_holding` 表（不存在）；`si.code` 应为 `si.symbol`；`ph.group_name` 列不存在 |
| P2-35 | [portfolio.py](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) | L142-147 | 查询失败回退 `_MOCK_POSITIONS` 模拟数据并返回 code:0，掩盖故障 |
| P2-36 | [risk.py](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) | L29-31 | `get_alerts` 吞异常返回空列表，伪装成"成功但无告警" |
| P2-37 | [ai.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) | L48-51 | `chat` 用 Query 参数传 message（应使用请求体），无长度限制 |
| P2-38 | [news.py](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) | L59, L63 | `sentiment == "neutral"` 查 `sentiment_score == 0`，但标签定义 -0.1~0.1 为 neutral，不一致 |
| P2-39 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) | L156 | 广播逐个 `send_text`，慢客户端阻塞其他客户端；遍历 set 期间可能被修改触发 RuntimeError |
| P2-40 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) | L282-291 | `scan_realtime` 在消费循环中同步 await，风控检查耗时长会阻塞行情广播 |
| P2-41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) | 全局 | 无心跳/ping-pong 机制，半开连接不被检测，积累僵尸连接 |
| P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) | L23-24 | `async_session_factory` 未判 None；`yield session` 后无 commit/rollback |
| P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) | L19 | `StockInfoResponse.ipo_date` 与 ORM `list_date` 不匹配，接口返回上市日期永远 None |
| P2-44 | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) | L66-68 | `strategy: dict` 无结构校验；`start_date`/`end_date` 未校验日期格式 |

### 前端

| # | 文件 | 行号 | 问题 |
|---|------|------|------|
| P2-45 | [App.tsx](file:///d:/code/project/trading_tools/frontend/src/App.tsx) | L18-34 | 路由树未包裹 ErrorBoundary，任一页面抛错即白屏 |
| P2-46 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) | L27-34 | 响应拦截器未校验业务 `code`，后端返回 code!=0 时错误体被当作成功数据 |
| P2-47 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) | L434-475 | `sendChatMessage` 用原生 fetch 绕过拦截器，无超时控制；`!reader` 提前返回不调 `onDone` |
| P2-48 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) | L70, L117-121 | 维护 `quotes` state 每条行情 setQuotes，但 Dashboard 不消费 quotes，高频无意义重渲染 |
| P2-49 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) | L85 | URL 硬编码 `ws://localhost:8000/ws/market`，不可配置 |
| P2-50 | [useTTS.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useTTS.ts) | L16-37 | 无 unmount 清理，组件卸载时语音仍在播放 |
| P2-51 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) | L42-69 | 串行操作任一步失败则后续不执行，前步已生效但状态不一致；无错误回滚 |
| P2-52 | [useReports.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Reports/hooks/useReports.ts) | L29-39 | `fetchDetail` 无竞态保护，快速点击不同日期可能旧请求覆盖新结果 |
| P2-53 | [StockTable/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/StockTable/index.tsx) | L47 | `price.toFixed(2)` 未判空，null/undefined 时抛错 |
| P2-54 | [useUserStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useUserStore.ts) | L40-46 | `addWatchlistCode` 未做重复校验 |
| P2-55 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) | L178 | `getReportDetail(date)` 未 `encodeURIComponent`，路径穿越风险 |
| P2-56 | [useBacktest.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Backtest/hooks/useBacktest.ts) | 全文 | 无 error 状态暴露，回测失败时 UI 无法感知 |

---

## 四、🟡 P3 级问题（次要，建议改进）

### 后端

| # | 文件 | 问题简述 |
|---|------|---------|
| P3-1 | [celery_app.py](file:///d:/code/project/trading_tools/backend/app/core/celery_app.py) | `crontab(minute="*/60")` 语义错误，应为 `minute=0`；未排除 A 股法定节假日 |
| P3-2 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) | `env_file=".env"` 为相对路径；`TUSHARE_TOKEN` 应为 `SecretStr` |
| P3-3 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) | `set()` 去重顺序不固定影响查询计划缓存；模块导入即创建 DuckDB 连接 |
| P3-4 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) | `max_connections=20` 硬编码；与 deps.py 中 `get_redis()` 重复定义 |
| P3-5 | [technical.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/technical.py) | 子函数就地修改传入 df；MACD 列名匹配用字符串包含逻辑 |
| P3-6 | [money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) | `days` 参数未使用；`from typing import Any` 未使用 |
| P3-7 | [sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) | `datetime.combine` 用服务器本地时区，可能与交易日边界不一致 |
| P3-8 | [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) | `compute_single()` 调用整个 `compute_all()` 再取一列，效率极低 |
| P3-9 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) | 每批 sleep(0.5) 对 5000 股票需 50 秒纯 sleep；未做并发控制 |
| P3-10 | [screening.py](file:///d:/code/project/trading_tools/backend/app/tasks/screening.py) | `run_screening` 是空 `pass`，未实现 |
| P3-11 | [data_quality.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_quality.py) | 两个函数均为 TODO 占位 |
| P3-12 | [daily_report.py](file:///d:/code/project/trading_tools/backend/app/tasks/daily_report.py) | `self.retry()` 未传 `exc=e`，原始异常信息丢失 |
| P3-13 | [tushare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tushare.py) | `except Exception: return {}` 静默吞掉所有异常；无分页 |
| P3-14 | [stock_picker.py](file:///d:/code/project/trading_tools/backend/app/services/stock_picker.py) | 因子白名单校验失败被 `except Exception` 吞掉返回空 |
| P3-15 | [llm_service.py](file:///d:/code/project/trading_tools/backend/app/services/llm_service.py) | 模型名硬编码为默认参数，未走 settings |
| P3-16 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) | `datetime.now()` 返回 naive datetime 无时区 |
| P3-17 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) | `_mock_result` 的 monthly_returns 是硬编码 2025 年数据 |

### 前端

| # | 文件 | 问题简述 |
|---|------|---------|
| P3-18 | [main.tsx](file:///d:/code/project/trading_tools/frontend/src/main.tsx) | `getElementById('root')!` 非空断言；全局无 ErrorBoundary |
| P3-19 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) | StrictMode 双挂载下开发环境频繁重连 |
| P3-20 | [useMarketStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useMarketStore.ts) | `updateQuote` 每次 `new Map()`，高频行情开销显著 |
| P3-21 | [Dashboard/index.tsx](file:///d:/code/project/trading_tools/frontend/src/pages/Dashboard/index.tsx) | 连接状态文字颜色红 vs Badge 绿语义冲突 |
| P3-22 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) | SSE 解析未处理 `\r\n`；未实现多行 `data:` 拼接 |
| P3-23 | [useNewsStream.ts](file:///d:/code/project/trading_tools/frontend/src/pages/News/hooks/useNewsStream.ts) | `newsList` 无上限增长，长时间运行内存线性上升 |
| P3-24 | [vite.config.ts](file:///d:/code/project/trading_tools/frontend/vite.config.ts) | 后端地址硬编码，无 env 变量化 |
| P3-25 | [package.json](file:///d:/code/project/trading_tools/frontend/package.json) | `build` 未指定 `--noEmit`；无 ESLint/Prettier/测试框架 |
| P3-26 | [format.ts](file:///d:/code/project/trading_tools/frontend/src/utils/format.ts) | `formatAmount/formatVolume` 未处理 NaN/Infinity/null |

---

## 五、模块状态总览

| 模块 | v4 状态 | v5 状态 | 变化说明 |
|------|---------|---------|---------|
| 选股（stock_picker） | 🟢 正常 | 🟢 正常 | 白名单防注入有效 |
| 回测（backtester） | 🟢 正常 | 🔴 **失效** | 收益恒 0 + 前视偏差 + 降级清空（P1-01/03/04） |
| 实时价格止损 | 🟢 正常 | 🟢 正常 | — |
| 盘后技术破位 | 🟢 正常 | 🟢 正常 | — |
| 盘后资金异常 | 🔴 no-op | 🔴 no-op | 未修复（money.py 仍是 stub） |
| 盘后负面舆情 | 🔴 no-op | 🔴 no-op | 未修复 + 方向判定反了（P1-02） |
| ORM 模型 | 🟡 不一致 | 🔴 **大面积不匹配** | 范围远超 v4 认知（P1-07） |
| 前端 useRisk | — | 🔴 **无限循环** | speak 未 memo 导致 useEffect 风暴（P1-08） |
| 前端 WebSocket | 🟢 正常 | 🔴 **重连失效 + 连接泄漏** | P1-09/10 |
| 前端 KLineChart | — | 🔴 **功能缺失** | symbol 未使用，图表空白（P1-14） |
| 前端 AI 聊天 | — | 🔴 **闭包/串流/泄漏** | P1-12 |
| 因子名/列名/表名契约 | 🟢 一致 | 🟡 部分不一致 | ORM 层仍有大面积不匹配 |

---

## 六、建议的修复优先级

### 第一批：阻断性 P1（不修则系统不可用）

1. **P1-07 统一 ORM 模型与 init.sql** — 系统性根因，几乎所有 ORM 操作都因此失败
2. **P1-08 useRisk 无限循环** — 前端持续打接口 + 语音风暴，影响用户体验和服务器
3. **P1-01/03/04 回测引擎三连失效** — 当前任何回测结果都不可信
4. **P1-16 CORS 安全漏洞** — 任意网站可携带凭证访问 API
5. **P1-17 _get_async_session 返回已关闭 session** — 因子写入永远失败
6. **P1-15 vite 未配 WebSocket 代理** — 生产环境前端 WS 必断

### 第二批：功能性 P1（不修则关键功能缺失）

7. **P1-02 负面舆情方向反了** — 即使因子接入也永不触发
8. **P1-09/10 useWebSocket 重连失效 + 连接泄漏** — 断线后前端行情永久中断
9. **P1-11 useNewsStream 无重连 + 游标错误** — 新闻流断线不恢复 + 分页数据错误
10. **P1-12 useAIChat 闭包/串流/泄漏** — AI 对话连续发送消息时上下文丢失
11. **P1-14 KLineChart 不加载数据** — K 线图功能完全缺失
12. **P1-13 useBacktest/usePortfolio 未处理拒绝** — 未处理 Promise 拒绝

### 第三批：安全性 P1

13. **P1-05/06 SQL 注入** — backtester + query_router
14. **P1-19 风控 N+1 查询** — 盘后扫描可能数十分钟
15. **P1-20 news_tasks 动态导入 + N+1** — 新闻去重性能
16. **P1-18 Tushare 同步阻塞** — 阻塞事件循环
17. **P1-21 硬编码弱口令**

### 第四批：P2 级问题

18. 按模块逐个修复 P2 列表中的 56 项

### 第五批：P3 级问题

19. 代码质量改进、配置统一、测试工具链建设

---

## 七、评审结论

第五轮审查发现，**v4 遗留的两个 P1 问题（资金流/舆情因子未接入）仍未修复，且全量深度审查暴露了更多系统性缺陷**。最严重的是：

1. **回测引擎三连失效**（收益恒 0 + 前视偏差 + 降级清空）—— 意味着当前所有回测结果都不可信
2. **ORM 模型与 init.sql 大面积不匹配** —— 影响所有使用 ORM 的代码路径
3. **前端 useRisk 无限循环** —— 持续打接口 + 语音播报风暴
4. **前端 WebSocket 重连失效** —— 断线后行情永久中断

建议**在开始任何新功能开发前，先修复第一批 + 第二批 P1 问题**（共 12 项），确保系统的基础功能可用。修复顺序建议从 P1-07（ORM 统一）和 P1-08（useRisk 循环）开始，因为它们是其他问题的根因或放大器。

---

*评审完成于 2026-07-07*
