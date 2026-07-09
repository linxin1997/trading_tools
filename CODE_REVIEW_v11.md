# 代码评审 · 第十一轮（2026-07-07）

> 评审对象：`D:\code\project\trading_tools`（NEW-09/10/11 修复后）
> 对照：第十轮 `CODE_REVIEW_v10.md` 提出的 3 个新回归问题
> 方法：实读源码逐项核验

---

## 一句话结论

**v10 提出的 3 个新回归问题（NEW-09/10/11）全部修复，无新引入问题。** 代码质量稳定向好。

---

## 二、修复验证

### NEW-09 · `_batch_get_stock_daily` 缺列名白名单 — **FIXED**

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L354-358
- **证据**：
  ```python
  # 列名白名单校验（防 SQL 注入）
  VALID_COLUMNS = {"close", "pct_change", "volume", "amount"}
  if column not in VALID_COLUMNS:
      logger.warning("不允许的列名: {}", column)
      return {}
  ```
- **说明**：批量方法 `_batch_get_stock_daily` 入口已加 `VALID_COLUMNS` 白名单校验，与单条方法 `_get_stock_daily_value` 防护一致。

---

### NEW-10 · `_check_bollinger_breakdown` 是死代码 — **FIXED**

- **文件**：[risk_guard.py](file:///d:/code/project/trading_tools/backend/app/services/risk_guard.py) L107-114
- **证据**：`DEFAULT_RULES` 中已添加 `bollinger_breakdown` 条目：
  ```python
  "bollinger_breakdown": {
      "id": 6,
      "name": "布林带破位",
      "description": "收盘价跌破布林带下轨时触发",
      "enabled": True,
      "threshold": 0,
      "severity": "warning",
  },
  ```
- **说明**：方法内部 L511-513 `rule.get("enabled", False)` 现在返回 `True`，不再立即 return，布林带破位检查可正常执行。

---

### NEW-11 · `deps.py get_db` 成功路径无 commit — **FIXED**

- **文件**：[deps.py](file:///d:/code/project/trading_tools/backend/app/api/deps.py) L29-36
- **证据**：
  ```python
  try:
      yield await session.__aenter__()
      await session.commit()  # 请求成功后提交事务
  except Exception:
      await session.rollback()
      raise
  finally:
      await session.__aexit__(None, None, None)
  ```
- **说明**：`yield` 后添加 `await session.commit()`，成功路径提交事务，异常路径 rollback，写操作不再丢失。

---

## 三、新引入问题检查

未发现新引入的回归问题。

**小瑕疵（非阻断，P3 级）**：`scan_after_hours` L410 对 `_check_bollinger_breakdown` 的调用仍是无条件的（其他检查都有 `if self._rules.get(...).get("enabled"):` 守卫），但方法内部 L511-513 已有 enabled 检查，功能上无影响，仅风格不一致。

---

## 四、修复统计

| 编号 | 问题 | 状态 | 修复证据 |
|------|------|------|---------|
| NEW-09 | `_batch_get_stock_daily` 白名单 | **FIXED** | risk_guard.py L354-358 |
| NEW-10 | bollinger_breakdown 死代码 | **FIXED** | risk_guard.py L107-114 DEFAULT_RULES 新增条目 |
| NEW-11 | deps.py get_db 缺 commit | **FIXED** | deps.py L31 `await session.commit()` |

**修复率：3/3（100%）。无新回归。**

---

## 五、当前遗留问题汇总

### P1（1 项）— 跨六轮

- **money/sentiment 因子流水线未接入**：[base.py](file:///d:/code/project/trading_tools/backend/app/services/factor_lib/base.py) `compute_all()` 仍只调 technical；money.py 仍是 stub；sentiment.py 未被调用；data_collect.py 不写入 sentiment/money 因子。`_check_fund_outflow` 和 `_check_negative_sentiment` 虽已改用批量查询，但查询的因子永远不会被写入数据库。

### P2（部分修复 4 项 + 未修复 6 项）

**部分修复**：
- P2-15 risk_guard column 白名单（单条✓ 批量✓，但 `_batch_get_stock_daily` 的 f-string 拼接在白名单通过后仍是 f-string，可接受）
- P2-36 risk.py `get_rules` 仍吞异常
- P2-42 deps.py commit 已加（NEW-11 已修），但 `get_redis` 仍直接返回 `global_redis`（可能 None）
- P2-43 schemas/stock.py 仅 `list_date` 改名，`code`/`exchange`/`is_active` 仍未对齐

**未修复**：
- P2-22 report_service mock raise+catch
- P2-30/31 akshare 缓存锁 + float None 防御
- P2-37 ai.py message Query→body
- P2-38 news.py neutral `== 0` → 范围查询
- P2-39/41 ws.py gather + heartbeat
- P2-44 backtest strategy dict→model

### 前端 P2（10+ 项）

- 全部未修复（跨多轮，开发者明确表示仅修后端 P2）

---

## 六、评审结论

第十轮提出的 3 个新回归问题**全部修复，无新引入问题**。代码质量稳定向好。

**当前唯一阻断性 P1 是 money/sentiment 因子流水线**（跨六轮未修），导致 `_check_fund_outflow` 和 `_check_negative_sentiment` 两条风控规则虽有正确的批量查询逻辑，但查询的因子永远不会被写入数据库，实质仍是死代码。

建议下一步集中精力接入 money/sentiment 因子管线，这是当前后端唯一的核心功能缺失。

---

*评审完成于 2026-07-07*
