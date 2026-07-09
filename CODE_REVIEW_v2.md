# 代码评审（第二轮 / 复检）

> 评审对象：`D:\code\project\trading_tools`（2026-07-07 18:50 版本）
> 参照：首轮 `CODE_REVIEW.md`
> 结论：**相比首轮有实质进步，但量化内核在真实数据库下仍然无法运行。** 根因不是逻辑缺失，而是「数据契约」未对齐——列名、表名、因子名大小写三处互不统一，且回测依赖的 DuckDB 从未被填充数据。

---

## 一、本轮已确认修复的问题（好消息）

| # | 首轮问题 | 现状 | 证据 |
|---|---------|------|------|
| 1 | 因子表不存在 | ✅ 已建 `factor_value`(长表) + `stock_info` | `init.sql:152,171` |
| 2 | 因子计算从未执行/入库 | ✅ `FactorCalculator.compute_all` 被调用并 `INSERT INTO factor_value` | `data_collect.py:81,108` |
| 3 | 回测前视偏差（T+1 因子选 T 日） | ✅ 已修：选股用 `daily_data[day]`（T 日因子），收益从 T+1 计 | `backtester.py:134-141` 注释明确"避免前视偏差" |
| 4 | K 线不复权造假缺口 | ✅ 已改 `adjust="qfq"` 前复权 | `akshare.py:109` |
| 5 | 选股 SQL 注入 | ✅ 已加 `FACTOR_REGISTRY` 白名单校验 | `stock_picker.py:156`, `query_router.py:113` |
| 6 | Celery 无 beat 调度 | ✅ 已加 `beat_schedule`（15:30 采集 / 16:00 风控等） | `celery_app.py:46-68` |
| 7 | 回测用假数据粉饰故障 | ✅ `mock_on_error` 默认 `False`，异常改为 `raise` | `backtester.py:25,203` |
| 8 | 幸存者偏差仅 docstring | ✅ `_get_tradable_stocks` 用 `list_date/delist_date` 真过滤 | `backtester.py:210-246` |
| 9 | `scan_realtime` 未接线 | ✅ 已在 WS 行情流水线调用 | `ws.py:288` |
| 10 | 前端配色/WS 扇出/.env | ✅ 均保持正确 | 首轮已确认 |

**小结**：用户对评审里"逻辑层"的问题响应很到位，前视偏差、复权、白名单、调度、mock 开关、幸存者过滤都做对了。

---

## 二、仍存在的严重问题（P0，系统仍跑不起来）

### 🔴 问题 A：因子名存在「三套互不兼容的命名」（最致命）

这是本轮最隐蔽也最致命的契约断裂：

- **因子注册表（FACTOR_REGISTRY）用大写**：`MA5 / MA20 / MACD_DIF / RSI_14 / BOLL_DN / VOLUME_RATIO`（`factor_lib/base.py:23-57`）
- **入库时强制 `.lower()`，且无下划线映射**：`factor_name = col.lower()`（`data_collect.py:94`）→ 实际写入 `factor_value` 的是 **`ma20 / macd_dif / boll_dn / volume_ratio`**（注意 `MA20`→`ma20`，不是 `ma_20`）
- **查询侧各用各的**：
  - `stock_picker` / `backtester` 用注册表**大写** `MA20` 去匹配 → 查不到小写的 `ma20`
  - `risk_guard` 用 **`ma_{period}` 带下划线**（`ma_20`，`risk_guard.py:271`）→ 也不匹配 `ma20`

**后果**：无论用户传大写还是小写因子名，三个核心功能都拿不到数据——
- 传 `MA20`：白名单通过，SQL `factor_name IN ('MA20')`，但表里是 `ma20` → 返回**空**
- 传 `ma20`：白名单 `if fname not in FACTOR_REGISTRY`（大写）→ 直接 `raise 未知因子` → API **400**
- `risk_guard` 期望 `ma_20 / dif / dea / bb_lower` → 表里是 `ma20 / macd_dif / macd_dea / boll_dn` → 全不匹配

**修复**：统一为「小写 + 下划线」规范（如 `ma_20`、`macd_dif`、`boll_dn`），三处同步：
1. `factor_lib/base.py` 的 `FACTOR_REGISTRY` key 改为小写（`MA20` → `ma_20`）
2. `data_collect.py:94` 的 `col.lower()` 改为规范化函数（如 `re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()`，把 `MA20`→`ma_20`、`MACD_DIF`→`macd_dif`）
3. `risk_guard.py` 的 `ma_{period}` / `dif` / `dea` / `bb_lower` 改为 `ma_{period}` / `macd_dif` / `macd_dea` / `boll_dn`

### 🔴 问题 B：查询列名 `code / date` 与表定义 `symbol / trade_date` 不符

`init.sql` 的 `factor_value` 列是 `symbol, trade_date, factor_name, value`，但所有 `SELECT` 都用 `fv.code` / `fv.date`：

- `stock_picker.py:170,180`：`SELECT fv.code AS symbol ... fv.date = (SELECT MAX(date) ...)`
- `query_router.py:122,127`：`fv.code AS symbol`、`fv.factor_name`、`fv.date`

**后果**：
- `stock_picker._query_factor_data` 抛 `column "code" does not exist`，被 `except` 吞掉 → **选股静默返回空**（用户以为是没股票符合，其实是 SQL 错）
- `query_router.screener_query` 无 try/except → 直接 **API 500**

**修复**：查询列名统一为 `symbol` / `trade_date`（与 `init.sql` 和 `data_collect` 的 INSERT 一致）。

### 🔴 问题 C：`factor_daily` 宽表从未创建，3 个消费者仍依赖它

首轮指出的"三套 schema 矛盾"只解决了一半——`stock_picker` 已改查 `factor_value`，但：

- `backtester.py:76`：`query_router.backtest_query(table="factor_daily")` → 查 **DuckDB** 的 `factor_daily`
- `risk_guard.py:272,300,327,356,386`：5 处 `FROM factor_daily`（期望宽表列 `close/ma_20/dif/dea/bb_lower/net_amount/net_amount_ratio/change_pct/sentiment_score`）
- `ai_explainer.py:166`：`FROM factor_daily WHERE code=:symbol AND date=:date`

**问题**：`factor_daily` 宽表在 `init.sql` 和 ORM 里都不存在，也从未被写入。这些查询必然失败（被 `except` 吞 → 空结果 / 告警不触发 / AI 解释为"无因子数据"）。

**修复**（二选一）：
- **方案 1（推荐）**：backtester 直接查 TimescaleDB `factor_value` 长表（去掉 DuckDB 这条孤立链路）；risk_guard / ai_explainer 改为从 `factor_value` pivot（联合 `stock_daily` 取 `close/change_pct`）。
- **方案 2**：保留 DuckDB 宽表思路，加一个定时任务把 `factor_value` 同步/物化为 DuckDB `factor_daily` 宽表。工作量更大。

### 🔴 问题 D：DuckDB 与 TimescaleDB 数据链路未打通

`backtester` 设计走 DuckDB 做历史回测，但因子数据只写进了 TimescaleDB 的 `factor_value`，**从未同步进 DuckDB**。全代码只有 `query_router.py` 打开了 DuckDB 连接，从不建表/导入。

**后果**：`backtester` 查 DuckDB `factor_daily` → `Catalog Exception: Table factor_daily does not exist` → 因 `mock_on_error=False` 现在会 `raise`（不再粉饰，但回测直接报错，跑不了）。

**修复**：同问题 C 方案 1，让回测查 TimescaleDB；或在数据落库时同步写 DuckDB。

---

## 三、P1 / P2（次要但应修）

| # | 问题 | 说明 |
|---|------|------|
| P1 | ORM 模型 `kline_daily`/`kline_1m` 与 `init.sql` 的 `stock_daily`/`stock_minute` 命名不一致 | `models/timescale.py` 定义 `kline_daily/kline_1m`，但库里是 `stock_daily/stock_minute`，行情写入也走 `stock_daily`。ORM 的 kline 模型是**死代码**；若将来有人用 ORM `add(kline_daily)` 会失败。建议删掉或改名对齐。 |
| P1 | `risk_guard` 的 `dif/dea/bb_lower/net_amount/sentiment_score` 列名与 `factor_value` 实际因子名（`macd_dif/macd_dea/boll_dn/...`）不符 | 即便建了 `factor_daily` 宽表，列名也要对齐。整体需重写（见问题 C）。 |
| P2 | `query_router.screener_query` 无异常保护 | 列名修好后无大碍，但建议加 try/except 返回空而非抛 500。 |
| P2 | `stock_picker._query_factor_data` 异常被吞返回空 DataFrame | 列名修好后能跑；但"静默空"会掩盖真实故障，建议至少 `logger.error` 而非仅 debug。 |

---

## 四、亮点（确认保留，勿回退）

- ✅ 回测前视偏差逻辑正确（T 日因子选股，T+1 起算收益）
- ✅ K 线前复权 `qfq`
- ✅ 选股白名单框架就位（只差大小写对齐）
- ✅ Celery beat 调度完整
- ✅ `mock_on_error` 默认 `False`（不再粉饰故障，方向正确）
- ✅ 幸存者偏差过滤实现正确（依赖 `stock_info` 的 `list_date/delist_date`，需确保该表被填充——见下）
- ✅ WebSocket 扇出（单消费者 + 进程内订阅表）、`scan_realtime` 接线、前端 A 股红涨绿跌配色、`.env` gitignore

---

## 五、修复优先级（建议路径）

**P0 主干打通（按此顺序，约 1 天）**：

1. **统一因子名规范** → 解决 A
   - `factor_lib/base.py`：注册表 key 全改小写+下划线（`ma_20`, `macd_dif`, `boll_dn`, `rsi_14`...）
   - `data_collect.py:94`：`col.lower()` → 规范化（`MA20`→`ma_20`）
   - `risk_guard.py`：`ma_{period}`/`dif`/`dea`/`bb_lower` → `ma_{period}`/`macd_dif`/`macd_dea`/`boll_dn`
2. **统一列名** → 解决 B
   - `stock_picker.py` / `query_router.py`：`code`→`symbol`，`date`→`trade_date`
3. **打通因子数据链路** → 解决 C/D
   - `backtester`：改为查 TimescaleDB `factor_value` 长表（删 DuckDB 链路或补同步）
   - `risk_guard`：5 个 `_check_*` 改为从 `factor_value` pivot + 联合 `stock_daily` 取 `close/change_pct`
   - `ai_explainer`：改为查 `factor_value` 长表
4. **确保 `stock_info` 被填充**：当前 `init.sql` 有表但未见写入逻辑（`sync_history` 只写 `stock_daily`）。幸存者偏差过滤依赖它，否则 `_get_tradable_stocks` 永远返回空 → 回测剔除全部股票。需加一个初始化任务填充 `stock_info`（含 `list_date/delist_date`）。

**P1**：清理 ORM kline 死模型；risk_guard 列名对齐（已含于步骤 3）。

---

## 六、结论

用户本轮修复集中在"逻辑正确性"层面，方向全对；但**数据契约（命名）这一层完全没动**，导致三个核心功能在真实运行环境下仍全军覆没——只是失败方式从首轮的"假数据粉饰"变成了现在的"静默空 / 报错"，反而更不易察觉。

**量化内核要真正跑通，必须先完成上面的 P0 四步命名/链路对齐**。这步是机械但影响全局的，建议一次性修完再联调。

> 需要我直接动手修 P0 主干（统一因子名 + 列名 + 把回测/风控/AI 解释改到 `factor_value` 长表 + 补 `stock_info` 填充）吗？我可以基于当前代码原地改，改完再复检。
