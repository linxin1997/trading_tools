# 代码评审 · 第十二轮（2026-07-09）

> 评审对象：`D:\code\project\trading_tools`（数据源调研后再次审查）
> 对照：第十一轮 `CODE_REVIEW_v11.md` + 数据源替代方案调研
> 方法：实读源码（后端 20+ 文件 + 前端 10 文件）逐项核验
> 重点：money/sentiment 管线、新增 BaoStock/Tencent provider、剩余 P2

---

## 一句话结论

**新增了 `baostock_provider.py` 和 `tencent_provider.py` 两个数据源文件，但都是无法使用的孤岛代码**——未继承基类、签名不兼容、未导出、未被调用。**money/sentiment 管线连续 7 轮未修复**，仍是死代码。前端仅修复了 ErrorBoundary 和业务码校验 2 项，其余 8 项 P2 全部未动。本轮引入 6 个新问题。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY | NOT FIXED | NEW ISSUE |
|------|------|-------|-----------|-----------|-----------|
| P1 money/sentiment 管线 | 4 | 0 | 0 | 4 | — |
| 新增 BaoStock/Tencent provider | — | — | — | — | 6 |
| 后端 P2（v11 遗留） | 10 | 1 | 0 | 9 | — |
| 前端 P2（v11 遗留） | 10 | 2 | 1 | 7 | — |
| **合计** | **24+6** | **3** | **1** | **20** | **6** |

---

## 三、🔴 P1 money/sentiment 管线 — 连续 7 轮未修复

| 子项 | 文件 | 状态 | 关键证据 |
|------|------|------|---------|
| compute_all 未调 money/sentiment | [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) L82 | NOT FIXED | 仍 `result = technical.compute_all(df)` |
| money.py 仍是 stub | [money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) L39-43, L66-70 | NOT FIXED | 全部返回 0.0 + warning 日志 |
| sentiment.py asyncio.run 嵌套 | [sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) L27, L46, L69 | NOT FIXED | 同步函数内调 `asyncio.run()`，async 上下文会崩 |
| data_collect 只存 technical | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L111 | NOT FIXED | 仅调 `FactorCalculator.compute_all()` |

**影响**：`_check_fund_outflow` 查询的 `net_amount`/`net_amount_ratio` 和 `_check_negative_sentiment` 查询的 `sentiment_score_1d` 永远不会写入数据库，两条风控规则仍是死代码。

---

## 四、🔴 新增 BaoStock/Tencent Provider — 6 个新问题

### NEW-12 · 未继承 BaseDataProvider — 接口契约破坏

- **文件**：[baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L58, [tencent_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tencent_provider.py) L172
- **描述**：`class BaostockProvider:` 和 `class TencentProvider:` 均未继承 `BaseDataProvider`，无法与其他 provider 多态互换。

### NEW-13 · get_kline 签名/返回类型与基类不兼容

- **文件**：[baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L101-108
- **描述**：
  - 参数名 `symbol` vs 基类 `code`
  - 多了 `start_date/end_date/adjust` 参数
  - 返回类型 `pd.DataFrame | None` vs 基类 `list[dict[str, Any]]`
- **影响**：即使继承基类也无法通过类型检查，调用方代码需完全重写。

### NEW-14 · baostock 模块级 import — 未安装时崩溃

- **文件**：[baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L16
- **描述**：`import baostock as bs` 在模块顶层，未安装 baostock 时整个模块 import 失败。应改为方法内惰性导入（对比 `tushare.py` L31 在 `__init__` 内导入）。

### NEW-15 · _ensure_login 非线程安全

- **文件**：[baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L87-93
- **描述**：全局单例 + 无锁 `bs.login()`，并发场景下可能多次调用。

### NEW-16 · 硬编码魔法日期

- **文件**：[baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L187
- **描述**：`date = "2025-12-31"` 硬编码默认值，随时间推移会失效。

### NEW-17 · 新 provider 未注册未集成 — 孤岛代码

- **文件**：[`__init__.py`](file:///d:/code/project/trading_tools/backend/app/services/data_providers/__init__.py) L1, [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L20
- **描述**：`__init__.py` 未导出新类；`data_collect.py` 仍只 `from app.services.data_providers.akshare import AKShareProvider`。新增的两个 provider 文件没有任何调用方。

---

## 五、后端 P2 修复状态（1/10 修复）

| # | v5 编号 | 文件 | 状态 | 关键证据 |
|---|---------|------|------|---------|
| 1 | P2-14 | [risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L107-114 | **FIXED** | `bollinger_breakdown` 已在 DEFAULT_RULES 中 |
| 2 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L48-51 | NOT FIXED | 仍 raise+catch 走 mock |
| 3 | P2-30 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L72-75 | NOT FIXED | 缓存刷新无 asyncio.Lock |
| 4 | P2-31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L121-128 | NOT FIXED | `float(row.get("开盘", 0))` 未防御 None |
| 5 | P2-36 | [risk.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) L42-47 | NOT FIXED | get_rules 仍吞异常返回 DEFAULT_RULES |
| 6 | P2-37 | [ai.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L50 | NOT FIXED | message 仍 `Query(...)` |
| 7 | P2-38 | [news.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L63 | NOT FIXED | neutral 仍 `sentiment_score == 0` |
| 8 | P2-39/41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L153-158 | NOT FIXED | 广播仍顺序 await；无心跳 |
| 9 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L46 | NOT FIXED | get_redis 仍直接返回 `global_redis`（可能 None） |
| 10 | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) L15-20 | NOT FIXED | code/exchange/industry/is_active 仍不匹配 ORM |
| 11 | P2-44 | [backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L66 | NOT FIXED | strategy 仍 `dict` |

---

## 六、前端 P2 修复状态（2/10 修复 + 1 部分修复）

| # | 编号 | 文件 | 状态 | 关键证据 |
|---|------|------|------|---------|
| 1 | P2-45 | [App.tsx](file:///d:/code/project/trading_tools/frontend/src/App.tsx) L14-50 | **FIXED** | ErrorBoundary 类组件已添加，包裹路由 |
| 2 | P2-46 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L29-32 | **FIXED** | `response.data.code !== 0` 时 reject |
| 3 | P2-53 | [StockTable/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/StockTable/index.tsx) L47 | **PARTIALLY FIXED** | 仅"最新价"列做了 null 检查，涨跌幅/成交量/成交额 3 列未做 |
| 4 | NEW-04 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L154 | NOT FIXED | connect 仍依赖回调引用，未改 ref |
| 5 | P2-48 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L70 | NOT FIXED | quotes 仍 useState<Map>（高频未节流） |
| 6 | P2-49 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L92 | NOT FIXED | 仍硬编码 `ws://localhost:8000/ws/market` |
| 7 | P1-13 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L46-73 | NOT FIXED | 三个 mutation 均无 try/catch |
| 8 | P1-15 | [vite.config.ts](file:///d:/code/project/trading_tools/frontend/vite.config.ts) L9-17 | NOT FIXED | API 8080 vs WS 8000 端口不一致；/ws 代理被硬编码 URL 绕过 |
| 9 | P2-47 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L448-449 | NOT FIXED | sendChatMessage 无超时；reader 为空未调 onDone |
| 10 | P2-52 | [useReports.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Reports/hooks/useReports.ts) L16-39 | NOT FIXED | 无 AbortController |
| 11 | P2-54 | [useUserStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useUserStore.ts) L44 | NOT FIXED | addWatchlistCode 无去重 |
| 12 | P2-55 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L184 | NOT FIXED | getReportDetail 未 encodeURIComponent |

---

## 七、模块状态总览

| 模块 | v11 状态 | v12 状态 | 变化 |
|------|---------|---------|------|
| money/sentiment 管线 | 🔴 未接入 | 🔴 未接入 | 跨 7 轮 |
| BaoStock provider | — | 🟡 新增但有 6 个问题 | 孤岛代码，未集成 |
| Tencent provider | — | 🟡 新增但未继承基类 | 孤岛代码，未集成 |
| 前端 ErrorBoundary | 🔴 未修复 | 🟢 **已修复** | App.tsx L14-50 |
| 前端业务码校验 | 🔴 未修复 | 🟢 **已修复** | api.ts L29-32 |
| 前端 StockTable null | 🔴 未修复 | 🟡 部分修复 | 仅 1/4 列 |
| 后端 P2 整体 | 🟡 多数未修 | 🟡 1/10 修复 | 仅 bollinger |
| 前端 P2 整体 | 🔴 零修复 | 🟡 2/10 修复 | ErrorBoundary + 业务码 |

---

## 八、修复优先级建议

### 第一批：修复新 provider 的接口契约（阻断性）

1. **NEW-12**：`BaostockProvider(BaseDataProvider)` / `TencentProvider(BaseDataProvider)` 继承基类
2. **NEW-13**：`get_kline` 签名对齐基类（参数名 `code`、返回 `list[dict]`）
3. **NEW-14**：baostock 改为方法内惰性导入
4. **NEW-17**：`__init__.py` 导出新类；在 `data_collect.py` 中可选切换 provider

### 第二批：打通 money/sentiment 管线（跨 7 轮 P1）

5. `sentiment.py` 用 `asyncio.to_thread()` 替代 `asyncio.run()`（或改为 async 函数）
6. `money.py` 接入真实数据源（Tushare `moneyflow` 或 BaoStock 财务数据）
7. `base.compute_all()` 中调用 money/sentiment 计算函数
8. `data_collect.py` 中将 money/sentiment 因子写入 factor_value 表

### 第三批：后端剩余 P2

9. report_service mock、akshare 缓存锁/None、ai.py body、news.py neutral 范围、ws.py gather/heartbeat、deps.py redis None、schemas/stock 字段对齐、backtest strategy model

### 第四批：前端剩余 P2

10. useWebSocket 回调 ref 化 + 硬编码 URL、usePortfolio try/catch、useReports AbortController、StockTable null 补全、useUserStore 去重、sendChatMessage 超时/onDone

---

## 九、评审结论

第十二轮审查发现：

1. **money/sentiment 管线连续 7 轮未修复**，仍是当前唯一的阻断性 P1。开发者虽然调研了数据源替代方案并新增了两个 provider 文件，但管线集成完全未落地。

2. **新增的 BaoStock/Tencent provider 是"写了但没法用"的孤岛代码**：未继承基类、签名不兼容、未导出、未被调用，且引入 6 个新问题。这属于典型的"研究阶段产物"而非"工程阶段产物"。

3. **前端终于开始修复**：ErrorBoundary 和业务码校验 2 项已修复，StockTable null 检查部分修复，但其余 8 项 P2 仍未动。

4. **后端 P2 几乎停滞**：10 项中仅 bollinger_breakdown 1 项修复（这是 v10 已确认的），其余 9 项原封不动。

5. **整体修复进度严重不足**：本轮 24 个遗留问题中仅修复 3 项，新增 6 个问题，净减少 -3 项。建议停止新增功能，集中精力打通现有管线和清理 P2 债务。

---

*评审完成于 2026-07-09*
