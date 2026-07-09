# 代码评审 · 第七轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（第二次修复后代码状态）
> 对照：第六轮 `CODE_REVIEW_v6.md` 提出的问题逐项核验
> 方法：实读源码（后端 30+ 文件 + 前端 15 文件）+ 交叉验证 init.sql / ORM / 因子注册表
> 重点：验证 v6 回归问题修复 + 识别新引入的回归

---

## 一句话结论

v6 的 4 个回归性问题修复了 3 个（NEW-01/02/03），但 v6 未修复的大量 P1/P2 问题**仍未修复**，且又引入 3 个新的回归性崩溃（sentiment.py 字段错配、news_analysis.py 引用不存在的字段、portfolio API 引用已删除的 PortfolioHolding 类）。整体修复率约 20%，核心阻断性问题仍有 5 个。**当前代码后端无法正常运行**。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY | NOT FIXED | NEW ISSUE |
|------|------|-------|-----------|-----------|-----------|
| v6 回归 NEW | 4 | 3 | 0 | 1 | — |
| v6 未修复 P1 | 10 | 2 | 2 | 5 | 1 |
| v6 未修复 P2（后端） | 33 | 4 | 1 | 28 | — |
| v6 未修复 P2（前端） | 10 | 0 | 0 | 10 | — |
| 新回归 | — | — | — | — | 3 |
| **合计** | **57+3** | **9** | **3** | **44** | **3** |

---

## 三、✅ v6 回归问题修复状态

| # | v6 编号 | 状态 | 修复证据 |
|---|---------|------|---------|
| 1 | NEW-01 news API 字段对齐 | **FIXED** | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L67→`related_stocks`, L70→`publish_time`, L146→`publish_time`, L147→`related_stocks`, L150→`crawl_time` |
| 2 | NEW-02 data_collect import | **FIXED** | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L18 `from app.config import get_settings`, L22 `settings = get_settings()` |
| 3 | NEW-03 useNewsStream 重连递归 | **FIXED** | [useNewsStream.ts](file:///d:/code/project/trading_tools/frontend/src/pages/News/hooks/useNewsStream.ts) L120-121 `scheduleReconnectRef`, L138-141 `ws.onclose` 通过 ref 调用，递归可重复 |
| 4 | NEW-04 useWebSocket 回调依赖 | **NOT FIXED** | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L154 仍 `}, [getReconnectDelay, onQuote, onAlert, onIndex, onSector])` |

---

## 四、✅ 本轮新确认修复的问题

### 后端（8 项）

| # | v5/v6 编号 | 文件 | 修复证据 |
|---|-----------|------|---------|
| 1 | P1-06 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) L104-107 | `VALID_TABLES = {"factor_value", "stock_daily"}` 白名单校验 + 因子名校验 |
| 2 | P1-07(部分) | [models/portfolio.py](file:///d:/code/project/trading_tools/backend/app/models/portfolio.py) | PortfolioHolding 幽灵表已移除 |
| 3 | P1-07(部分) | [models/news.py](file:///d:/code/project/trading_tools/backend/app/models/news.py) | 多余 `created_at` 已移除 |
| 4 | P1-07(部分) | [models/timescale.py](file:///d:/code/project/trading_tools/backend/app/models/timescale.py) | StockMinute/StockDaily 多余 `created_at` 已移除 |
| 5 | P1-20(部分) | [news_tasks.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_tasks.py) L10 | `__import__("sqlalchemy")` 已改为 `import sqlalchemy as sa` |
| 6 | P2-5 | [query_router.py](file:///d:/code/project/trading_tools/backend/app/core/query_router.py) | core→services 反向依赖已移除 |
| 7 | P2-17 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L307-309 | `list_date IS NULL` 视为已上市 + `delist_date` 过滤 |
| 8 | P2-27/28 | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L74-95, L136-149 | 参数化查询 + batch_size=50 分批 + 参数化 INSERT + 每批 commit |

### 前端（1 项）

| # | v6 编号 | 文件 | 修复证据 |
|---|---------|------|---------|
| 1 | NEW-03 | [useNewsStream.ts](file:///d:/code/project/trading_tools/frontend/src/pages/News/hooks/useNewsStream.ts) | 重连递归已修复（见上表） |

---

## 五、🔴 新引入的回归性问题（3 项）

### NEW-05 · sentiment.py 引用已重命名的 ORM 字段 — **调用即 AttributeError**

- **文件**：[sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py)
- **行号**：L92, L94, L120, L122, L149, L150, L162, L164, L173, L175
- **描述**：sentiment.py 仍引用 `News.related_codes`（应为 `related_stocks`）和 `News.published_at`（应为 `publish_time`），与 NEW-01 完全同类的字段错配，但修复 NEW-01 时遗漏了此文件。
- **影响**：一旦 `get_sentiment_score_1d` 等函数被调用，立即抛 `AttributeError`。
- **修复**：将 `related_codes` → `related_stocks`，`published_at` → `publish_time`。

### NEW-06 · news_analysis.py 引用不存在的 `news.summary` — **任务运行即崩**

- **文件**：[news_analysis.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_analysis.py)
- **行号**：L62-63
- **描述**：`if news.summary: text = f"{text}。{news.summary}" if text else news.summary` —— News ORM 模型只有 `content`，无 `summary` 字段。当 `news_list` 非空时立即抛 `AttributeError`。
- **影响**：舆情分析 Celery 任务运行即崩。
- **修复**：改为 `news.content`。

### NEW-07 · portfolio API 引用已删除的 PortfolioHolding 类 — **import 即崩溃**

- **文件**：[portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py)
- **行号**：L161 `from app.models.portfolio import PortfolioHolding`
- **描述**：v6 审查后开发者移除了 `models/portfolio.py` 中的 `PortfolioHolding` 类（P1-07 修复），但 `api/v1/portfolio.py` 仍 `from app.models.portfolio import PortfolioHolding`，import 时即 `ImportError`。
- **影响**：portfolio API 模块无法加载，所有持仓接口 500 错误。
- **同时**：L127, L158, L214, L243, L276 仍 `FROM portfolio_holding`（表不存在），L164 `insert(PortfolioHolding)` 也引用已删除的类。
- **修复**：将所有 `portfolio_holding` → `portfolio`，移除 `PortfolioHolding` import，改用原生 SQL 或 `Portfolio` 模型。

---

## 六、🔴 仍未修复的 P1 问题（5 项 + 2 项部分修复）

### 完全未修复

| # | v5/v6 编号 | 文件 | 行号 | 问题 |
|---|-----------|------|------|------|
| 1 | P1-07(部分) | [models/stock.py](file:///d:/code/project/trading_tools/backend/app/models/stock.py) L19 | `industry` 列未删除，与 `sector` 同义重复 |
| 2 | P1-16 | [main.py](file:///d:/code/project/trading_tools/backend/app/main.py) L77-80 | CORS 仍 `allow_origins=["*"]` + `allow_credentials=True` |
| 3 | P1-18 | [tushare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tushare.py) L53, L92 | async 方法仍直接同步调用 `self._pro.realtime_quote()`/`self._pro.daily()` |
| 4 | P1-19 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L367-479 | N+1 查询未修复，每只股票每次检查新建 session |
| 5 | P1-21 | [config.py](file:///d:/code/project/trading_tools/backend/app/config.py) L28 | `DATABASE_URL` 默认值仍含弱口令 `postgres:postgres` |
| 6 | v5遗留 | [factor_lib/base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) L82 | `compute_all()` 仍只调 `technical`，未调 money/sentiment |
| 7 | v5遗留 | [factor_lib/money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) | 仍是 stub，因子名不匹配 |
| 8 | v5遗留 | [factor_lib/sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) | 仍用 `asyncio.run()`；且新增字段错配（NEW-05） |

### 部分修复

| # | v5/v6 编号 | 文件 | 修复点 | 未修复点 |
|---|-----------|------|--------|---------|
| 1 | P1-07 | [models/stock.py](file:///d:/code/project/trading_tools/backend/app/models/stock.py) | 5 个多余字段已删除 | `industry` 未删除 |
| 2 | P1-20 | [news_tasks.py](file:///d:/code/project/trading_tools/backend/app/tasks/news_tasks.py) | 动态 import 已消除 | N+1 查询仍存在（L113-119 逐条 SELECT） |

---

## 七、仍未修复的关键 P2 问题（28 项后端 + 10 项前端）

### 后端 P2（仅列出关键项，完整清单见 v5/v6）

| # | v5 编号 | 文件 | 问题 |
|---|---------|------|------|
| 1 | P2-1/2/3 | [database.py](file:///d:/code/project/trading_tools/backend/app/core/database.py) | close_db 未重置 None；get_session 无 rollback；无 pool_pre_ping |
| 2 | P2-6/7 | [redis_client.py](file:///d:/code/project/trading_tools/backend/app/core/redis_client.py) | 无 ping 健康检查；get_redis 返回 None |
| 3 | P2-9 | [config.yaml](file:///d:/code/project/trading_tools/backend/config.yaml) | 仍未被代码加载 |
| 4 | P2-13 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L110 | 浅拷贝，修改阈值污染类变量 |
| 5 | P2-14 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L330-332 | bollinger_breakdown 无 enabled 开关 |
| 6 | P2-15 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L256 | column 参数 f-string 拼接无白名单 |
| 7 | P2-16 | [backtester.py](file:///d:/code/project/trading_tools/backend/app/services/backtester.py) L377 | `momentum_20d` 依赖未注册因子 |
| 8 | P2-19 | [redis_stream.py](file:///d:/code/project/trading_tools/backend/app/services/redis_stream.py) L92-99 | xack 在 finally（注：本轮审查认为时机正确，但仍是"yield 后即 ack"模式） |
| 9 | P2-21 | [ai_explainer.py](file:///d:/code/project/trading_tools/backend/app/services/ai_explainer.py) L174 | 引用未注册因子 `pe_ttm`/`change_pct` |
| 10 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L42-51 | 仍故意 raise+catch 走 mock |
| 11 | P2-30/31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) | 缓存无锁；float() 未防御 None |
| 12 | P2-34/35 | [portfolio.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/portfolio.py) | 仍用 `portfolio_holding` 表 + mock 回退（已升级为 NEW-07 崩溃） |
| 13 | P2-36 | [risk.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) L29-31 | 吞异常返回空列表 |
| 14 | P2-37 | [ai.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L50-51 | 仍用 Query 参数传 message |
| 15 | P2-38 | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L62-63 | neutral 查询 `score == 0` 与标签定义不一致 |
| 16 | P2-39/41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) | 广播未用 gather；无心跳 |
| 17 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) | 未判 None；无 commit/rollback |
| 18 | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) | `ipo_date`/`code`/`exchange`/`is_active` 仍不匹配 |
| 19 | P2-44(部分) | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L65 | `strategy: dict` 仍无结构校验（日期校验已修复） |

### 前端 P2（10 项，全部未修复）

| # | v6 编号 | 文件 | 问题 |
|---|---------|------|------|
| 1 | P2-45 | [App.tsx](file:///d:/code/project/trading_tools/frontend/src/App.tsx) | 仍无 ErrorBoundary |
| 2 | P2-46 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L27-34 | 未校验业务 code |
| 3 | P2-47 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L427-475 | sendChatMessage 无超时；`!reader` 不调 onDone |
| 4 | P2-48 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L70 | quotes 仍 useState<Map> |
| 5 | P2-49 | useWebSocket.ts L92, useNewsStream.ts L130 | 仍硬编码 `ws://localhost:8000` |
| 6 | P2-51 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L46-73 | 变更操作无 try/catch |
| 7 | P2-52 | [useReports.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Reports/hooks/useReports.ts) | 无竞态保护 |
| 8 | P2-53 | [StockTable/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/StockTable/index.tsx) L47 | toFixed 未判空 |
| 9 | P2-54 | [useUserStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useUserStore.ts) L40-46 | addWatchlistCode 无去重 |
| 10 | P2-55 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L178 | 未 encodeURIComponent |

---

## 八、模块状态总览

| 模块 | v6 状态 | v7 状态 | 变化 |
|------|---------|---------|------|
| 回测引擎 | 🟢 已修复 | 🟢 正常 | 稳定 |
| 风控-负面舆情方向 | 🟢 已修复 | 🟢 正常 | 稳定 |
| query_router SQL 注入 | 🟡 部分 | 🟢 **已修复** | table 白名单已加 |
| ORM 模型 | 🟡 部分 | 🟡 **基本修复** | PortfolioHolding 已删；stock.py 仍残留 `industry` |
| news API 字段对齐 | 🔴 崩溃 | 🟢 **已修复** | NEW-01 已修 |
| data_collect import | 🔴 崩溃 | 🟢 **已修复** | NEW-02 已修 |
| useNewsStream 重连 | 🟡 部分 | 🟢 **已修复** | NEW-03 递归重连已修 |
| **sentiment.py** | 🟡 未接入 | 🔴 **新崩溃** | NEW-05 字段错配 |
| **news_analysis.py** | 🟡 未检查 | 🔴 **新崩溃** | NEW-06 引用 `news.summary` |
| **portfolio API** | 🟡 未修复 | 🔴 **新崩溃** | NEW-07 import 已删除的 PortfolioHolding |
| CORS 安全 | 🔴 未修复 | 🔴 未修复 | — |
| Tushare 同步阻塞 | 🔴 未修复 | 🔴 未修复 | — |
| 风控 N+1 查询 | 🔴 未修复 | 🔴 未修复 | — |
| 弱口令 | 🔴 未修复 | 🔴 未修复 | — |
| money/sentiment 因子 | 🔴 未接入 | 🔴 未接入 | — |
| 前端 useWebSocket 回调依赖 | 🟡 潜在 | 🟡 未修复 | NEW-04 仍在 |
| 前端 P2 全部 | 🟡 未修复 | 🟡 未修复 | 0/10 修复 |

---

## 九、修复优先级建议

### 第一批：修复 3 个阻断性崩溃（立即）

1. **NEW-05** sentiment.py 字段对齐（`related_codes`→`related_stocks`, `published_at`→`publish_time`）
2. **NEW-06** news_analysis.py `news.summary` → `news.content`
3. **NEW-07** portfolio API 移除 `PortfolioHolding` import，`portfolio_holding` → `portfolio`

### 第二批：修复剩余 P1

4. **P1-07** stock.py 删除 `industry` 列
5. **P1-16** CORS 白名单
6. **P1-18** Tushare `asyncio.to_thread()`
7. **P1-19** 风控 N+1 批量查询
8. **P1-21** 弱口令移除
9. **NEW-04** useWebSocket 回调改用 ref
10. money.py / sentiment.py 接入因子流水线

### 第三批：修复 P2

11. 按清单逐项修复

---

## 十、评审结论

第七轮审查发现：

1. **v6 的 3 个回归性崩溃已修复**（NEW-01/02/03），这是本轮主要进展。
2. **但又引入了 3 个新的回归性崩溃**（NEW-05/06/07），其中 NEW-07 尤为严重——移除 `PortfolioHolding` 模型后未同步更新 portfolio API，导致 import 即报错。
3. **v6 未修复的大量 P1/P2 问题仍未修复**（44 项），特别是：
   - CORS 安全漏洞（已跨越 v5/v6/v7 三轮未修）
   - Tushare 同步阻塞（三轮未修）
   - 风控 N+1 查询（三轮未修）
   - 弱口令（三轮未修）
   - 前端 P2 全部 10 项（零修复）
4. **修复模式存在系统性问题**：每次修复一个层面（如 ORM 模型）时未联动检查其他层面（如 API、services、schemas），导致反复出现"改了 A 没改 B"的联动遗漏。

**建议**：
- 修复 NEW-05/06/07 三个崩溃后，进行一次**全链路导入冒烟测试**（`python -c "import app.main"` + `python -c "import app.tasks.data_collect"` 等），确保所有模块可正常加载。
- 对 v5 P1 清单中跨三轮未修复的 5 项（CORS、Tushare、N+1、弱口令、money/sentiment）进行**集中修复**，不再拖延。
- 前端 P2 零修复的状态需要改变，至少 ErrorBoundary 和 api.ts 业务码校验应优先处理。

---

*评审完成于 2026-07-07*
