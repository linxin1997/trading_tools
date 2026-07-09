# 行情数据源替代方案 — 去东方财富依赖

> 背景：当前 `quote_gateway.py` 经 AKShare 取数，AKShare 的实时主力接口（`stock_zh_a_spot_em` 等）底层爬**东方财富 push2**。
> 问题：东方财富**没有面向个人的官方免费 API**，`push2` 是无文档公共端点，无 SLA、按 IP 限流/封禁风险高，"个人免费用"不可靠。
> 目标：为「实时行情 / 历史回测 / 资金流」三类需求各找稳定、keyless（或极低门槛）的替代，并把改动落到本项目代码。

---

## 一、可用免费源全景（按个人可用可靠性排序）

| 源 | 实时行情 | 历史K线 | 资金流 | 鉴权 | 稳定性 | 备注 |
|----|:--:|:--:|:--:|------|--------|------|
| **腾讯财经 qt.gtimg.cn** | ✅ | ❌ | ❌ | 无 | ★★★★★ | 最稳、keyless、管道分隔、可批量 |
| **新浪财经 hq.sinajs.cn** | ✅ | ❌ | ❌ | 无（需 Referer） | ★★★★☆ | keyless，需带 `Referer` 头 |
| **baostock** | ❌ | ✅ | ❌ | 无 | ★★★★★ | 专为回测，日线 + 部分分钟，keyless |
| **pytdx（通达信）** | ✅ | ✅ | 部分 | 无 | ★★★★☆ | 直连券商行情服，法律灰区 |
| **Tushare Pro 免费** | 点数门槛 | ✅ | 点数门槛 | token（免费注册） | ★★★★☆ | 实时/资金流需 ~200 积分 |
| 东方财富 push2 | ✅ | ✅ | ✅ | 无 | ★★☆☆☆ | 无官方免费 API、封禁风险 → **弃用** |
| AKShare | 取决于底层 | 取决于底层 | 取决于底层 | 无 | ★★★☆☆ | 封装层，底层多为上面对应爬取 |

**结论**：把"实时行情"从东方财富换成**腾讯 gtimg（主）+ 新浪 sinajs（备）**；"历史回测"换成 **baostock（主）+ Tushare（备）**；"资金流"是唯一较难免费化的，现实路径是 **Tushare 积分**或 **pytdx**。

---

## 二、针对本项目的推荐架构

### 2.1 实时行情（QuoteGateway）—— 彻底去东方财富

**主源：腾讯财经 gtimg**
```
GET http://qt.gtimg.cn/q=sh600000,sz000001,sh601318
```
- 返回 `v_sh600000="1~平安银行~600000~11.22~11.30~11.25~..."`，管道 `|` 分隔。
- 关键字段（按位置）：`[1]`名字 `[2]`代码 `[3]`当前价 `[4]`昨收 `[5]`今开 `[6]`成交量(手) `[7]`外盘 `[8]`内盘 `[30]`时间 `[31]`涨跌 `[32]`涨跌% `[33]`最高 `[34]`最低`，其后为买一~买五 / 卖一~卖五 价量。
- 优点：keyless、极稳、单请求可带多只（降低请求数，缓解限流）。

**备源：新浪财经 sinajs**
```
GET http://hq.sinajs.cn/list=sh600000
Header: Referer: https://finance.sina.com.cn
```
- 返回 `var hq_str_sh600000="平安银行,11.30,11.22,11.25,..."`，逗号分隔：`[0]`名字 `[1]`今开 `[2]`昨收 `[3]`当前 `[4]`最高 `[5]`最低`。
- 近年需带 `Referer` 否则 403；加上即可。

**可选高性能：pytdx 直连**
```python
from pytdx.hq import TdxHqAPI
api = TdxHqAPI()
if api.connect('119.147.212.81', 7709):
    api.get_security_quotes([(0, '600000')])   # 0=上海 1=深圳
```
- 亚秒级轮询更强；缺点：直连券商行情服务器，法律灰区，介意就只用 gtimg/sinajs。

**实现建议**：把 provider 抽成 `RealtimeProvider` 抽象，gtimg 为主、sinajs 为 fallback；**不再依赖 AKShare 的实时路径**。这样即使某个源临时抖动，也能自动切换。

### 2.2 历史 / 回测（sync_history.py）—— 用 baostock 为主

```python
import baostock as bs
bs.login()
rs = bs.query_history_k_data_plus(
    "sh.600000",
    "date,open,high,low,close,volume",
    start_date='2020-01-01', end_date='2026-07-09',
    frequency="d", adjustflag="2")   # 1后复权 2前复权 3不复权
```
- keyless、稳定、适合批量日线；`adjustflag` 正好呼应此前评审的"前复权(qfq)"修正（用 `"2"`）。
- 备选：Tushare Pro（`pro_bar`，注册即够日线，含复权、质量高）。
- **弃用 AKShare 的 eastmoney 历史接口**，从源头消除东方财富依赖。

### 2.3 资金流（risk_guard 的 net_amount 桩）—— 当前最大缺口

- 最现实免费路径：**Tushare `moneyflow`**（需 ~200 积分；积分靠注册 + 社区活跃获取，**非付费**）。
- 或 **pytdx** 取主力资金（部分字段）。
- 东方财富 push2 资金流虽免费，但同属封禁风险源，不建议作主依赖。
- **重要**：把 `net_amount` 明确标注为"需 Tushare 积分 / pytdx"，**不要继续返回 0.0 假数据**（呼应第四轮评审发现的 stub 问题）。因子缺失应"静默跳过 + 前端提示"，而不是假装接通。

---

## 三、落地步骤（对应现有代码）

1. **抽 provider 接口**：`QuoteGateway` 调用 `RealtimeProvider` 抽象；实现 `TencentProvider`（主）+ `SinaProvider`（fallback）。
2. **保持 1–3s 轮询**（设计已定），gtimg 单请求批量多只，降低请求频率。
3. **历史同步切 baostock**，复权统一前复权（`adjustflag="2"` / qfq）。
4. **资金流**：先接 Tushare（积分）或 pytdx，保留"因子缺失 → 跳过 + 提示"的诚实行为。
5. `.env` 增加可选 `TUSHARE_TOKEN`（已有）与 `QUOTE_PROVIDER=tence入/auto` 开关，便于切换与灰度。

---

## 四、合规与注意事项

- 这些公共端点都**无 SLA、无官方支持**，属"灰色爬取"。个人研究/自用通常无碍，但：
  - **不要商用**、不要高频暴击（加合理间隔与指数退避）；
  - 遵守服务条款与 robots；
  - pytdx 直连券商行情服务器属法律灰区，介意则只用 gtimg / sinajs / baostock。
- 我在本次**无法联网实时验证端点存活**（联网工具报错）。请你花 30 秒实测再定：
  - 浏览器打开 `http://qt.gtimg.cn/q=sh600000` 看是否返回 `v_sh600000=...`；
  - 用带 `Referer` 的请求测 `http://hq.sinajs.cn/list=sh600000`；
  - `pip install baostock` 后跑一段 `query_history_k_data_plus` 看是否返回数据。

---

## 五、一句话总结

> 实时行情换 **腾讯 gtimg（主）+ 新浪 sinajs（备）**，历史回测换 **baostock**，资金流用 **Tushare 积分 / pytdx**；AKShare 退居可选封装层，**东方财富从主路径彻底移除**。这样既保持 keyless、又消除封禁风险与单点依赖。
