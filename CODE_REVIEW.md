# trading_tools 代码评审报告

> 评审对象：`D:\code\project\trading_tools`（FastAPI 后端 + React 前端 + Docker）
> 评审日期：2026-07-07
> 评审范围：后端核心服务（行情/因子/选股/回测/风控/WebSocket）、前端关键点、部署与调度
> 结论：**架构骨架清晰、代码风格统一，但量化核心链路在真实运行环境下几乎全部失效**——因子表不存在、因子计算从未执行、回测用假数据掩盖故障、实时风控未接线、定时任务无调度。

---

## 一、严重程度总览

| 等级 | 数量 | 代表问题 |
|------|------|----------|
| 🔴 严重（系统不可用） | 4 | 因子表在 schema 中不存在；因子计算与入库从未执行；回测异常时返回假数据；Celery 无 beat 调度 |
| 🟠 高（正确性问题） | 5 | 回测前视偏差（用 T+1 数据选 T 日持仓）；K 线 `adjust=""` 不复权；`scan_realtime` 从未调用；选股/回测 SQL 注入因子名；`factor_daily` 长表/宽表 schema 矛盾 |
| 🟡 中（功能缺口/健壮性） | 5 | TTS 整体缺失；AKShare 每次单股查询拉全市场；mock 掩盖故障；幸存者偏差仅 docstring；MA 列名动态拼接 |
| 🟢 亮点（做对的地方） | 4 | WebSocket 扇出正确；前端配色符合 A 股惯例；`.env` 已 gitignore；风控查询参数化 |

---

## 二、🔴 严重问题（必须修，否则系统跑不起来）

### C1. 因子存储表在真实 schema 中完全不存在
**位置**：`docker/timescale/init.sql`、`backend/app/models/timescale.py`
- `init.sql` 只建了 `stock_daily / stock_minute / news_raw / portfolio / ...`，**没有 `factor_value`、没有 `factor_daily`、没有 `stock_info`**。
- ORM 模型（`FactorValue`→`factor_value`、`KlineDaily`→`kline_daily`、`Kline1m`→`kline_1m`）**全代码没有任何 `Base.metadata.create_all` 调用**，所以 ORM 也不会建表。
- 结果：真实数据库里这三张表都不存在。

### C2. 因子计算与入库从未执行
**位置**：`backend/app/services/factor_lib/base.py`、`backend/app/tasks/*`
- 全局搜索 `compute_all` / `FactorCalculator` / `session.add` 在 `tasks/` 中**零命中**——因子计算函数存在，但没有任何定时任务或流水线调用它，更没有 `INSERT` 写入。
- `backend/scripts/sync_history.py` 只写 `stock_daily`，不写因子。
- 结果：量化数据从源头就是空的。

### C3. 回测在 DB 异常时返回「假数据」，且表不存在必然走假数据
**位置**：`backend/app/services/backtester.py:81-83, 181-183, 384-431`
- 回测查 `factor_daily`（DuckDB）失败或空 → `except` → `_mock_result()` 返回随机生成的漂亮曲线（年化 ~18%、夏普 ~1.85）。
- 由于 C1/C2，`factor_daily` 必然为空/不存在，**回测永远返回假数据**，开发者极易误以为回测功能正常。这是最危险的一类 bug：不报错、给正反馈、但数据是编的。

### C4. Celery 没有任何 beat 调度
**位置**：`backend/app/core/celery_app.py:11-47`
- 只有 `autodiscover_tasks(["app.tasks"])`，**没有 `beat_schedule` / `crontab`**。
- 结果：`tasks/` 下的 `data_collect / news_analysis / screening / daily_report / data_quality` 全部不会被定时触发；系统无法自主采集数据、计算因子、生成报告。即使 C1/C2 修好，也不会有人往库里灌数据。

> **C1–C4 连锁效应**：没有调度(C4) → 不采集/不算因子(C2) → 因子表空(C1) → 选股返回空、回测返回假、盘后风控返回空。这是当前系统「能启动但核心功能零产出」的根因。

---

## 三、🟠 高严重度（正确性问题）

### H1. 回测存在前视偏差（与设计目标相反）
**位置**：`backend/app/services/backtester.py:116-145`
- 调仓日 `day` 上，持仓用 `daily_data[next_day]`（**T+1 日因子数据**）筛选（第 123 行），却把收益算在 `day_data`（**T 日** `change_pct`，第 134 行）。
- 即「用未来信息选今天的持仓」，正是设计文档明确要避免的前视偏差，实现反而踩进去了。
- **修复**：调仓日应用 `daily_data[day]`（T 日）的因子筛选，选出后从 `next_day` 起实现收益。

### H2. K 线 `adjust=""` 不复权
**位置**：`backend/app/services/data_providers/akshare.py:118-123`
- `ak.stock_zh_a_hist(..., adjust="")` 取不复权价。除权除息会在价格序列上造出假缺口，导致 MA/MACD/动量因子与回测收益全部失真。
- **修复**：量化场景应默认 `adjust="qfq"`（前复权）；展示用不复权另说。

### H3. `scan_realtime` 从未被调用 → 实时风控是死代码
**位置**：`backend/app/api/v1/ws.py:200-214`（仅广播）、`backend/app/services/risk_guard.py:142`
- `ws._consumer_loop` 里只 `broadcast_quote`，从不调用 `risk_guard.scan_realtime`。
- 结果：实时价格止损函数写好了但**永远不触发**，持仓跌破止损价不会有任何告警。
- **修复**：在 `broadcast_quote` 或直接消费循环里，对持仓标的调用 `scan_realtime(position, quote)`，命中则推送告警 + 浏览器语音。

### H4. 选股/回测 SQL 注入（因子名直接拼接）
**位置**：`backend/app/services/stock_picker.py:154,160-163`、`backend/app/core/query_router.py:108,111-126,164-180`
- `factor_names` 取自请求里的 `conditions[*].factor` / `weights` 键名，直接 f-string 拼进 SQL：
  ```python
  factor_list_str = ", ".join([f"'{f}'" for f in factor_names])
  ```
  因子名含单引号即可逃逸，如 `x'; DELETE FROM factor_value; --`。
- **修复**：用**因子注册表白名单**校验因子名（`FactorCalculator.FACTOR_REGISTRY` 已有），拒绝未知因子；值用参数化 `:param`。

### H5. `factor_daily` 长表/宽表 schema 自相矛盾
**位置**：`backend/app/core/query_router.py:170-180`（长表：`code,date,factor_name,value`）vs `backend/app/services/risk_guard.py:270-393`（宽表：`close,ma_20,dif,dea,bb_lower,...`）
- 同一张 `factor_daily` 被当成「长表 pivot」又被当成「宽表」。两者物理结构不可能同时满足。
- 而且和 C1 一起：这张表本来就不存在。
- **修复**：选定一种范式（推荐**长表 `factor_value` 已是 ORM 模型**，与 `stock_picker` 一致），让回测、风控都从同一张表读，删掉宽表假设。

---

## 四、🟡 中严重度（功能缺口 / 健壮性）

### M1. TTS 语音播报整体缺失
**位置**：`backend/app/services/tts.py`（已删除）、`frontend/src/**`（无 `SpeechSynthesis`/`Audio`）
- 后端 `tts.py` 已不存在，前端也未实现浏览器语音合成。
- 结果：设计里的「止损触发语音播报」功能完全没有。
- **修复**：在前端告警组件用 `window.speechSynthesis` 播报（WSL2 后端无音频设备，必须放前端）。

### M2. 单股实时行情每次拉全市场快照
**位置**：`backend/app/services/data_providers/akshare.py:49-94`
- `get_realtime_quote` 为查一只股票，调用 `stock_zh_a_spot_em()` 拉全市场 5000+ 只再过滤。单股查询成本 = 全市场下载，易被 AKShare 限流/IP 封禁。
- **修复**：缓存当天全市场快照（定时刷新），单股查询走缓存；或每标的独立接口。

### M3. mock 掩盖真实故障
**位置**：`backtester._mock_result`、`stock_picker`（空 DataFrame 返回空）、`risk_guard`（异常返回 `[]`）
- 多处「查不到就返回空/假」，开发期能跑通 UI，但生产故障被静默吞掉。
- **建议**：区分「无数据」与「出错」，出错记录明确 ERROR 并向前端返回错误态，至少加开关 `MOCK_ON_ERROR=false`。

### M4. 幸存者偏差防护仅存在于 docstring
**位置**：`backend/app/services/backtester.py:6`（注释）vs `_filter_stocks:206-242`
- 文档声称「按上市/退市日期过滤历史可交易集合避免幸存者偏差」，但代码无任何上市/退市日期过滤。属于「声明与实现不符」。

### M5. 动态列名拼接（低风险注入）
**位置**：`backend/app/services/risk_guard.py:270-282`（`ma_{period}`）
- `period = int(rule["threshold"])` 来自内部规则配置（非直接用户输入），风险低，但建议用白名单周期（5/10/20/60）替代任意拼接。

---

## 五、🟢 亮点（做对的地方，保持）

1. **WebSocket 扇出实现正确**：`ws.py` 用进程内订阅表 `symbol→set[WebSocket]` + 单消费者读 Redis Stream 再广播，正是设计评审推荐的模式；`main.py:55` 已在 lifespan 启动消费者。✅
2. **前端配色符合 A 股惯例**：`StockTable` 与 `Backtest/MetricsCards` 用涨=红 `#f5222d`、跌=绿 `#52c41a`，与 K 线、指数卡片一致。✅
3. **`.env` 已 gitignore**（含 `TUSHARE_TOKEN`/`SMTP_PASSWORD`），密钥不会入库。✅
4. **风控查询用了参数化**（`text(...)` + `:today`/`:threshold` 绑定），无注入。✅
5. 代码文档/类型注解/日志规范度高，模块分层清晰。✅

---

## 六、优先级修复清单

**P0（让系统真正跑起来）**
1. 在 `init.sql`（或 ORM `create_all`）中补齐 `factor_value`、`stock_info` 表；统一行情表名（`stock_daily` vs `kline_daily` 二选一并全链路一致）。【C1】
2. 在 `tasks/data_collect.py` 中调用 `FactorCalculator.compute_all()` 并把结果 `INSERT` 进 `factor_value`（长表）。【C2/H5】
3. 在 `celery_app.py` 增加 `beat_schedule`：交易日 15:30 采集+算因子、盘后风控、每日复盘报告等。【C4】
4. 回测/`_mock_result` 增加开关，默认不返回假数据；DB 不可用时明确报错而非编造。【C3/M3】

**P1（正确性）**
5. 修回测前视偏差：T 日因子选股、T+1 起实现收益。【H1】
6. K 线默认 `adjust="qfq"`。【H2】
7. 在行情消费循环接入 `scan_realtime`，命中即推送告警+前端语音。【H3】
8. 选股/回测因子名走白名单校验，值参数化。【H4】
9. 回测/风控统一读 `factor_value` 长表，删掉宽表假设。【H5】

**P2（健壮性/体验）**
10. 前端用 `speechSynthesis` 实现语音播报。【M1】
11. 实时行情加全市场快照缓存，避免每次单股全量拉取。【M2】
12. 补幸存者偏差的 point-in-time 可交易集过滤（按上市/退市日期）。【M4】
13. 因子名/周期用白名单替代任意拼接。【M5】

---

## 七、复核小结

这套代码的「壳」很完整——API、前端页面、WebSocket、Celery、Docker 一应俱全，看起来像能跑的系统。但「量化内核」是空心的：因子表没建、因子没算、调度没开、回测用假数据粉饰。当前状态下，启动后 UI 能开、但选股/回测/盘后风控**都没有真实产出**。

建议按 P0→P1→P2 顺序先把「数据能进来、因子能算、能真回测」这条主干打通，再补实时风控接线和语音播报。需要我直接就其中某一项（比如补齐 `init.sql` + 因子入库任务 + Celery beat 调度）动手改，告诉我即可。
