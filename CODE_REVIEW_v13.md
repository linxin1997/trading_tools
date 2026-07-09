# 代码评审 · 第十三轮（2026-07-09）

> 评审对象：`D:\code\project\trading_tools`（v12 修复后再次审查）
> 对照：第十二轮 `CODE_REVIEW_v12.md`
> 方法：实读源码（后端 20+ 文件 + 前端 8 文件）逐项核验
> 重点：money/sentiment 管线、NEW-12~17 provider 问题、后端/前端剩余 P2

---

## 一句话结论

**修复进度显著提升**：后端 P2 修复 5 项（ai.py body、ws.py gather/heartbeat、deps.py redis、risk.py 吞异常、akshare 缓存锁），前端 P2 修复 4 项（vite 端口、AbortController、去重、encodeURIComponent）。BaoStock/Tencent provider 的 6 个问题修复了 4 个。**但 money/sentiment 管线连续 8 轮仍未真正集成**——虽然新增了 `compute_money()`/`compute_sentiment()` 方法和 async sentiment，但从未被调用。backtest.py 引入了一个阻断性新 bug（`strategy.get()` 在 Pydantic model 上不存在）。

---

## 二、修复统计总览

| 维度 | 总计 | FIXED | PARTIALLY | NOT FIXED | NEW ISSUE |
|------|------|-------|-----------|-----------|-----------|
| P1 money/sentiment 管线 | 4 | 1 | 0 | 3 | — |
| NEW-12~17 provider | 6 | 4 | 1 | 1 | — |
| 后端 P2（v12 遗留） | 9 | 5 | 2 | 2 | — |
| 前端 P2（v12 遗留） | 8 | 4 | 3 | 1 | — |
| 新回归 | — | — | — | — | 3 |
| **合计** | **27+3** | **14** | **6** | **7** | **3** |

---

## 三、🔴 P1 money/sentiment 管线 — 连续 8 轮，1/4 修复

| 子项 | 文件 | 状态 | 关键证据 |
|------|------|------|---------|
| sentiment.py asyncio.run | [sentiment.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/sentiment.py) L16, L28, L40 | **FIXED** | 全部改为 `async def`，内部直接 `await`，无 `asyncio.run()` 嵌套 |
| compute_all 未调 money/sentiment | [base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) L90 | NOT FIXED | 仍 `result = technical.compute_all(df)`；新增了 `compute_money()` L104 和 `compute_sentiment()` L95 但**从未被调用** |
| money.py 仍是 stub | [money.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/money.py) L39-43, L66-70 | NOT FIXED | 全部返回 0.0 + warning |
| data_collect 只存 technical | [data_collect.py](file:///d:/code/project/trading_tools/backend/app/tasks/data_collect.py) L111 | NOT FIXED | 仅调 `FactorCalculator.compute_all()`，未调 `compute_money()` 或 `compute_sentiment()` |

**核心问题**：开发者新增了 `compute_money()` 和 `compute_sentiment()` 两个方法，但**从未在管线中调用它们**。这和 v10 的 `_batch_get_factor_values` 问题如出一辙——"有方法无调用"。

---

## 四、✅ NEW-12~17 Provider 问题修复（4/6 修复）

| # | 问题 | 状态 | 关键证据 |
|---|------|------|---------|
| NEW-12 | 未继承 BaseDataProvider | **FIXED** | [baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L42 `class BaostockProvider(BaseDataProvider):`；[tencent_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/tencent_provider.py) L130 同 |
| NEW-13 | get_kline 签名不兼容 | **FIXED** | baostock_provider.py L85 `async def get_kline(self, code: str, period: str = "daily") -> list[dict[str, Any]]:` |
| NEW-14 | 模块级 import | **FIXED** | baostock import 已移入 `_ensure_login` 方法内（L68） |
| NEW-15 | _ensure_login 无锁 | NOT FIXED | 仍无 Lock，且文件头注释 L11-13 声称"单例+锁保护"与实现不符（NEW-20） |
| NEW-16 | 硬编码日期 | **PARTIALLY FIXED** | 硬编码已删除，但未传 `start_date`/`end_date` 给 baostock API（NEW-19） |
| NEW-17 | 未注册未集成 | **FIXED** | `__init__.py` 已导出；`quote_gateway.py` 用 TencentProvider；`scripts/` 用 BaostockProvider |

---

## 五、后端 P2 修复状态（5/9 修复 + 2 部分修复）

| # | v5 编号 | 文件 | 状态 | 关键证据 |
|---|---------|------|------|---------|
| 1 | P2-37 | [ai.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ai.py) L50 | **FIXED** | `message: str = Body(..., embed=True)` |
| 2 | P2-39/41 | [ws.py](file:///d:/code/project/trading_tools/backend/app/api/v1/ws.py) L203-205, L349-359 | **FIXED** | `asyncio.gather(*tasks)` 并发广播 + 30s 心跳 task |
| 3 | P2-42 | [deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L49-50 | **FIXED** | `if global_redis is None: raise RuntimeError(...)` |
| 4 | P2-36 | [risk.py](file:///d:/code/project/trading_tools/backend/app/api/v1/risk.py) L41 | **FIXED** | 不再 try/except，直接调 `risk_guard.get_rules()` |
| 5 | P2-30 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L75, L97-101 | **FIXED** | `asyncio.Lock()` + 双重检查模式 |
| 6 | P2-31 | [akshare.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/akshare.py) L182-189 | **PARTIALLY FIXED** | `get_kline` 用 `_safe_float` ✓；`get_batch_quotes` 仍 `float(row.get("最新价", 0))` 未防御 None |
| 7 | P2-43 | [schemas/stock.py](file:///d:/code/project/trading_tools/backend/app/schemas/stock.py) L12-26 | **PARTIALLY FIXED** | `symbol`/`name`/`list_date` 对齐 ✓；缺 `sector` 字段 |
| 8 | P2-22 | [report_service.py](file:///d:/code/project/trading_tools/backend/app/services/report_service.py) L42-48 | NOT FIXED | 改为不 raise 直接 return mock，但 try/except 仍是死代码 |
| 9 | P2-38 | [news.py](file:///d:/code/project/trading_tools/backend/app/api/v1/news.py) L62-63 | NOT FIXED | 改为 `is_(None)` 但漏了 `[-0.1, 0.1]` 区间 |
| 10 | P2-44 | [backtest.py](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L26-31, L100 | **NEW BUG** | 改为 Pydantic model 但 L100 `strategy.get("conditions")` 调用不存在的方法（NEW-18） |

---

## 六、前端 P2 修复状态（4/8 修复 + 3 部分修复）

| # | 编号 | 文件 | 状态 | 关键证据 |
|---|------|------|------|---------|
| 1 | P1-15 | [vite.config.ts](file:///d:/code/project/trading_tools/frontend/vite.config.ts) L11, L15, L19 | **FIXED** | 三个代理端口统一为 8000 |
| 2 | P2-52 | [useReports.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Reports/hooks/useReports.ts) L16-52 | **FIXED** | AbortController + 卸载 abort |
| 3 | P2-54 | [useUserStore.ts](file:///d:/code/project/trading_tools/frontend/src/stores/useUserStore.ts) L40-49 | **FIXED** | `includes(code)` 去重 |
| 4 | P2-55 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L184 | **FIXED** | `encodeURIComponent(date)` |
| 5 | P2-49 | [useWebSocket.ts](file:///d:/code/project/trading_tools/frontend/src/hooks/useWebSocket.ts) L92-93 | **PARTIALLY FIXED** | URL 改为动态拼接 ✓；但回调未 ref 化（NOT FIXED），quotes 仍 useState |
| 6 | P1-13 | [usePortfolio.ts](file:///d:/code/project/trading_tools/frontend/src/pages/Portfolio/hooks/usePortfolio.ts) L46-85 | **PARTIALLY FIXED** | 有 try/catch ✓；但 catch 块是空的（`// 静默失败`），未 setError |
| 7 | P2-47 | [api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L438-487 | **PARTIALLY FIXED** | 有 30s 超时 ✓ + !reader 调 onDone ✓；但 timeoutId 未 clearTimeout + AbortError 不调 onDone（NEW-21） |
| 8 | P2-53 | [StockTable/index.tsx](file:///d:/code/project/trading_tools/frontend/src/components/StockTable/index.tsx) L47, L57, L67-68, L77-79 | NOT FIXED | 仍仅 1/7 列有 null 检查，与 v12 完全相同 |

---

## 七、🔴 新引入的问题（3 项）

### NEW-18 · backtest.py `strategy.get()` 调用不存在的方法 — **阻断性崩溃**

- **文件**：[backtest.py API](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L100
- **描述**：`strategy` 已改为 Pydantic `StrategyInput` model，但 L100 仍调用 `strategy.get("conditions")`。Pydantic BaseModel 没有 `.get()` 方法，会抛 `AttributeError`。
- **影响**：所有 POST /backtest 请求在参数校验阶段就 500 崩溃。
- **修复**：改为 `if not strategy.conditions:`。

### NEW-19 · baostock_provider get_kline 缺失日期参数

- **文件**：[baostock_provider.py](file:///d:/code/project/trading_tools/backend/app/services/data_providers/baostock_provider.py) L102-105
- **描述**：`query_history_k_data_plus` 调用时未传 `start_date`/`end_date`，baostock 默认仅返回最近若干日数据，无法满足"近 60 日 K 线"需求。
- **修复**：根据当前日期计算并传入 60 日前到当日的日期范围。

### NEW-21 · sendChatMessage 超时后 UI 永久 loading

- **文件**：[api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) L438-487
- **描述**：30s 超时 → `controller.abort()` → fetch reject with `AbortError` → catch 中 `if (error.name !== 'AbortError')` 排除了 abort → `onDone()` 不触发。且 `timeoutId` 从未 `clearTimeout`。
- **影响**：超过 30s 的 AI 聊天请求会让界面永久停留在 loading 状态。
- **修复**：在 `.then` 和 `.catch` 中 `clearTimeout(timeoutId)`；为超时 abort 单独调用 `onDone()`。

---

## 八、模块状态总览

| 模块 | v12 状态 | v13 状态 | 变化 |
|------|---------|---------|------|
| money/sentiment 管线 | 🔴 未接入 | 🟡 sentiment 已 async，但管线未调 | 跨 8 轮 |
| BaoStock provider | 🔴 6 个问题 | 🟢 4/6 修复 | 继承+签名+导入+集成已修 |
| 后端 P2 | 🟡 1/10 | 🟢 **5/9 修复** | ai body + ws gather/heartbeat + deps redis + risk + akshare lock |
| 前端 P2 | 🟡 2/10 | 🟢 **4/8 修复** | vite 端口 + AbortController + 去重 + encodeURIComponent |
| backtest API | 🔴 dict | 🔴 Pydantic 但崩溃 | NEW-18 阻断 |
| StockTable null | 🟡 1/4 列 | 🔴 1/7 列 | 完全未动 |

---

## 九、修复优先级建议

### 第一批：修复阻断性新 bug

1. **NEW-18**：[backtest.py](file:///d:/code/project/trading_tools/backend/app/api/v1/backtest.py) L100 `strategy.get("conditions")` → `strategy.conditions`
2. **NEW-21**：[api.ts](file:///d:/code/project/trading_tools/frontend/src/services/api.ts) sendChatMessage 超时 clearTimeout + onDone

### 第二批：打通 money/sentiment 管线（跨 8 轮 P1）

3. 在 `data_collect.py` 的 `_compute_and_store_factors` 中调用 `compute_money()` 和 `compute_sentiment()`，将结果写入 factor_value 表
4. `money.py` 接入真实数据源（或确认 stub 返回 0.0 不会影响风控逻辑）

### 第三批：补全部分修复项

5. akshare `get_batch_quotes` 用 `_safe_float`
6. news.py neutral 改为 `is_(None) | between(-0.1, 0.1)`
7. schemas/stock.py 补 `sector` 字段
8. usePortfolio catch 块加 `setError`
9. StockTable 全列 null 检查
10. useWebSocket 回调 ref 化
11. baostock get_kline 传日期参数

---

## 十、评审结论

第十三轮审查发现：

1. **修复进度显著提升**：后端 P2 从 v12 的 1/10 提升到 5/9，前端 P2 从 2/10 提升到 4/8，BaoStock provider 6 个问题修复 4 个。本轮是历次中 P2 修复最多的一轮。

2. **但 money/sentiment 管线连续 8 轮仍未真正集成**：开发者新增了 `compute_money()` 和 `compute_sentiment()` 方法，sentiment.py 也已改为 async，但**从未在 data_collect.py 中调用它们**。这是典型的"有方法无调用"模式，与 v10 的 `_batch_get_factor_values` 问题完全相同。

3. **backtest.py 引入阻断性新 bug（NEW-18）**：`strategy.get()` 在 Pydantic model 上不存在，所有回测请求会 500 崩溃。这是本轮最严重的问题。

4. **前端 sendChatMessage 超时实现有 bug（NEW-21）**：超时后 `onDone()` 不触发，UI 永久 loading。

5. **StockTable null 检查完全未动**（仍 1/7 列），建议确认是否遗漏。

**总体评价**：本轮修复量是历次最大的一轮（14 项 FIXED），修复质量也在提升。但"有方法无调用"的模式反复出现，说明开发者在集成层面存在系统性遗漏。建议下一步重点打通 money/sentiment 管线的"最后一公里"——在 data_collect.py 中实际调用。

---

*评审完成于 2026-07-09*
